"""牧场组页面分析：严格逐场、一次性子进程、无组汇总。"""

from __future__ import annotations

import gc
import logging
import os
import queue
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from PyQt6.QtCore import QThread, pyqtSignal

from core.group_tasks.feature_policy import (
    FEATURE_TITLES,
    normalize_feature_parameters,
    validate_feature_manifest,
)
from core.group_tasks.lease_heartbeat import GroupLeaseHeartbeat
from core.group_tasks.memory_guard import (
    AdaptiveMemoryGuard,
    boundary_pause_message,
    runtime_pause_message,
)
from core.group_tasks.parent_process import parse_jsonl_line
from gui.multi_farm_task_worker import (
    CHILD_STDOUT_DRAIN_GRACE_SECONDS,
    CHILD_STDOUT_POLL_SECONDS,
    CHILD_TASK_HEARTBEAT_SECONDS,
    ChildProcessInterrupted,
    MemoryPressureInterrupted,
    MultiFarmTaskWorker,
)
from utils.file_manager import FileManager


logger = logging.getLogger(__name__)


class GroupFeatureAnalysisWorker(QThread):
    """只运行用户在当前页面点击的一项分析，不生成任何汇总报告。"""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    parallel_start = pyqtSignal(list)
    sub_task_progress = pyqtSignal(str, int)
    sub_task_done = pyqtSignal(str, bool)

    def __init__(
        self,
        project_path: Path | str,
        operation: str,
        parameters: Mapping[str, Any] | None,
        *,
        memory_guard: AdaptiveMemoryGuard | None = None,
    ):
        super().__init__()
        self.project_path = Path(project_path)
        self.operation = str(operation or "").strip()
        self.parameters = normalize_feature_parameters(
            self.operation,
            parameters,
        )
        self._memory_guard = memory_guard or AdaptiveMemoryGuard()
        self._lease_store = None
        self._lease_heartbeat = None

    def _acquire_lease(self) -> None:
        store = FileManager._group_task_store(self.project_path)
        if store is None:
            return
        revision = store.get_selection_revision()
        lease = store.acquire_run_lease(
            f"desktop-feature:{os.getpid()}:{uuid.uuid4()}",
            run_kind=f"group_feature:{self.operation}",
            lease_seconds=600,
            expected_selection_revision=revision,
        )
        if lease is None:
            raise RuntimeError(
                "该牧场组已有另一个下载、分析或汇总任务正在运行"
            )
        heartbeat = GroupLeaseHeartbeat(
            store,
            lease,
            lease_seconds=600,
        )
        try:
            heartbeat.start()
        except Exception:
            try:
                store.release_run_lease(str(lease["lease_token"]))
            except Exception:
                logger.warning("功能批量租约启动失败后释放失败", exc_info=True)
            raise
        self._lease_store = store
        self._lease_heartbeat = heartbeat

    def _check_lease(self) -> None:
        if self._lease_heartbeat is not None:
            self._lease_heartbeat.check()

    def _release_lease(self) -> None:
        heartbeat = self._lease_heartbeat
        self._lease_heartbeat = None
        if heartbeat is not None:
            try:
                heartbeat.stop(timeout=30, release=True)
            except Exception:
                logger.warning("释放页面分析运行锁失败", exc_info=True)
        self._lease_store = None

    def _child_progress(
        self,
        index: int,
        total: int,
        task_id: str,
        farm_name: str,
        value: Any,
        message: Any,
    ) -> None:
        try:
            child_value = max(0, min(100, int(value)))
        except (TypeError, ValueError):
            child_value = 0
        overall = int(
            ((index + child_value / 100) / max(total, 1)) * 100
        )
        self.progress.emit(
            overall,
            f"[{farm_name}] {str(message or '处理中')}",
        )
        self.sub_task_progress.emit(task_id, child_value)

    def _run_child(
        self,
        *,
        index: int,
        total: int,
        task: Mapping[str, Any],
        child_path: Path,
    ) -> dict[str, Any]:
        from core.group_tasks.feature_process import (
            build_feature_command,
            write_feature_request,
        )

        task_id = str(task.get("task_id") or "")
        farm_code = str(task.get("farm_code") or "")
        farm_name = str(task.get("farm_name") or farm_code)
        request_path = write_feature_request(
            self.project_path,
            task_id,
            self.operation,
            self.parameters,
        )
        command = build_feature_command(request_path)
        process = None
        result_event = None
        committed = False

        try:
            assessment = self._memory_guard.assess_boundary()
            if assessment.should_pause:
                raise MemoryPressureInterrupted(
                    boundary_pause_message(assessment)
                )
            process = subprocess.Popen(
                command,
                cwd=str(Path(__file__).resolve().parents[1]),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
            )
            if process.stdout is None:
                raise RuntimeError("无法建立单牧场分析子进程通信管道")

            output_queue: queue.Queue = queue.Queue()
            reader = MultiFarmTaskWorker._start_stdout_reader(
                process.stdout,
                output_queue,
            )
            stdout_eof = False
            exit_seen_at = None
            last_output_or_heartbeat = time.monotonic()

            while True:
                if self.isInterruptionRequested():
                    MultiFarmTaskWorker._terminate_child_process(process)
                    raise ChildProcessInterrupted(
                        "用户已停止批量分析；已完成牧场结果仍保留"
                    )

                now = time.monotonic()
                return_code = process.poll()
                if return_code is None:
                    memory = self._memory_guard.poll_runtime()
                    if memory.should_pause:
                        MultiFarmTaskWorker._terminate_child_process(process)
                        raise MemoryPressureInterrupted(
                            runtime_pause_message(memory)
                        )
                else:
                    if exit_seen_at is None:
                        exit_seen_at = now
                    if stdout_eof and output_queue.empty():
                        break
                    if not reader.is_alive() and output_queue.empty():
                        break
                    if (
                        output_queue.empty()
                        and now - exit_seen_at
                        >= CHILD_STDOUT_DRAIN_GRACE_SECONDS
                    ):
                        break

                heartbeat_due = max(
                    0.01,
                    CHILD_TASK_HEARTBEAT_SECONDS
                    - (now - last_output_or_heartbeat),
                )
                try:
                    item_type, payload = output_queue.get(
                        timeout=min(
                            CHILD_STDOUT_POLL_SECONDS,
                            heartbeat_due,
                        )
                    )
                except queue.Empty:
                    now = time.monotonic()
                    if (
                        now - last_output_or_heartbeat
                        >= CHILD_TASK_HEARTBEAT_SECONDS
                    ):
                        self._check_lease()
                        last_output_or_heartbeat = now
                    continue

                if item_type == "eof":
                    stdout_eof = True
                    continue
                if item_type == "error":
                    if process.poll() is None:
                        raise RuntimeError(
                            "读取单牧场分析子进程输出失败"
                        ) from payload
                    stdout_eof = True
                    continue

                last_output_or_heartbeat = time.monotonic()
                event = parse_jsonl_line(payload)
                event_task = str(event.get("task_id") or task_id)
                event_farm = str(event.get("farm_code") or farm_code)
                if event_task != task_id or event_farm != farm_code:
                    raise RuntimeError("子进程返回了其他牧场的任务身份")

                if event["type"] == "progress":
                    self._child_progress(
                        index,
                        total,
                        task_id,
                        farm_name,
                        event.get("progress", 0),
                        event.get("message", ""),
                    )
                elif event["type"] == "stage_completed":
                    validation = validate_feature_manifest(
                        child_path,
                        self.operation,
                        self.parameters,
                        expected_task_id=task_id,
                        expected_farm_code=farm_code,
                        verification="full",
                    )
                    if not validation.get("valid"):
                        raise RuntimeError(
                            "单牧场结果提交后完整性校验失败"
                        )
                    committed = True
                elif event["type"] == "result":
                    result_event = event

            return_code = process.poll()
            if result_event and not result_event.get("success"):
                raise RuntimeError(
                    str(result_event.get("error") or "单牧场分析失败")
                )
            if return_code != 0 or not result_event:
                if return_code in {-9, 137, -1073741801, 3221225495}:
                    raise MemoryPressureInterrupted(
                        "单牧场子进程被系统终止，可能是可用内存不足。"
                        "已完成牧场仍保留，请释放内存后重试。"
                    )
                raise ChildProcessInterrupted(
                    f"单牧场分析子进程异常退出（代码 {return_code}）"
                )
            if not (
                committed
                or result_event.get("resumed")
                or result_event.get("skipped")
            ):
                raise RuntimeError("子进程成功返回但没有提交结果清单")
            self._child_progress(
                index,
                total,
                task_id,
                farm_name,
                100,
                result_event.get("message") or "完成",
            )
            return dict(result_event)
        except Exception:
            if process is not None and process.poll() is None:
                MultiFarmTaskWorker._terminate_child_process(process)
            raise
        finally:
            request_path.unlink(missing_ok=True)

    def run(self) -> None:
        try:
            self._acquire_lease()
            metadata = FileManager.load_project_metadata(self.project_path)
            if metadata.get("project_type") != "multi_farm_group":
                raise RuntimeError("当前项目不是牧场组项目")
            tasks = [
                dict(task)
                for task in metadata.get("group_tasks", [])
                if task.get("included_in_summary", True)
            ]
            if not tasks:
                raise RuntimeError("当前牧场组没有纳入处理范围的牧场")

            specs = [
                {
                    "id": str(task.get("task_id") or ""),
                    "name": str(
                        task.get("farm_name")
                        or task.get("farm_code")
                        or ""
                    ),
                    "path": str(
                        self.project_path
                        / str(task.get("relative_path") or "")
                    ),
                }
                for task in tasks
            ]
            self.parallel_start.emit(specs)

            completed: list[dict[str, Any]] = []
            skipped: list[dict[str, Any]] = []
            failed: list[dict[str, Any]] = []
            paused_for_memory = False

            for index, task in enumerate(tasks):
                if self.isInterruptionRequested():
                    break
                self._check_lease()
                task_id = str(task.get("task_id") or "")
                farm_code = str(task.get("farm_code") or "")
                farm_name = str(task.get("farm_name") or farm_code)
                child_path = (
                    self.project_path
                    / str(task.get("relative_path") or "")
                )
                try:
                    resolved = child_path.resolve(strict=True)
                    expected_root = (
                        self.project_path / "farm_projects"
                    ).resolve(strict=True)
                    resolved.relative_to(expected_root)
                    child_path = resolved
                    self.progress.emit(
                        int(index / max(len(tasks), 1) * 100),
                        f"正在分析 {farm_name}（{index + 1}/{len(tasks)}）",
                    )
                    result = self._run_child(
                        index=index,
                        total=len(tasks),
                        task=task,
                        child_path=child_path,
                    )
                    record = {
                        "task_id": task_id,
                        "farm_code": farm_code,
                        "farm_name": farm_name,
                        "path": str(child_path),
                        "message": str(result.get("message") or ""),
                        "resumed": bool(result.get("resumed")),
                    }
                    if result.get("skipped"):
                        skipped.append(record)
                    else:
                        completed.append(record)
                    self.sub_task_progress.emit(task_id, 100)
                    self.sub_task_done.emit(task_id, True)
                except Exception as exc:
                    memory_pressure = isinstance(
                        exc,
                        (MemoryPressureInterrupted, MemoryError),
                    )
                    if isinstance(exc, MemoryError):
                        exc = MemoryPressureInterrupted(
                            "系统无法继续分配内存，已安全停止当前牧场。"
                        )
                    failed.append(
                        {
                            "task_id": task_id,
                            "farm_code": farm_code,
                            "farm_name": farm_name,
                            "path": str(child_path),
                            "error": str(exc),
                            "memory_pressure": memory_pressure,
                        }
                    )
                    self.sub_task_done.emit(task_id, False)
                    logger.warning(
                        "牧场页面分析失败：%s：%s",
                        farm_name,
                        exc,
                        exc_info=not isinstance(
                            exc,
                            ChildProcessInterrupted,
                        ),
                    )
                    if memory_pressure or self.isInterruptionRequested():
                        paused_for_memory = memory_pressure
                        break
                finally:
                    try:
                        from core.data.update_manager import reset_pedigree_db

                        reset_pedigree_db()
                    except Exception:
                        logger.debug("重置系谱缓存失败", exc_info=True)
                    gc.collect()

            self.progress.emit(
                100,
                f"{FEATURE_TITLES[self.operation]}批量处理已完成",
            )
            self.finished.emit(
                {
                    "project_path": str(self.project_path),
                    "operation": self.operation,
                    "title": FEATURE_TITLES[self.operation],
                    "completed": completed,
                    "skipped": skipped,
                    "failed": failed,
                    "paused_for_memory": paused_for_memory,
                    "interrupted": self.isInterruptionRequested(),
                    "excel_path": None,
                    "ppt_path": None,
                }
            )
        except Exception as exc:
            logger.exception("牧场组页面分析启动失败")
            self.error.emit(f"牧场组页面分析失败：{exc}")
        finally:
            self._release_lease()
