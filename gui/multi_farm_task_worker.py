"""牧场组顺序任务工作线程：每个牧场独立计算，全部完成后再汇总。"""

from __future__ import annotations

import logging
import os
import queue
import subprocess
import threading
import time
import uuid
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from core.group_tasks.lease_heartbeat import GroupLeaseHeartbeat
from utils.file_manager import FileManager


logger = logging.getLogger(__name__)

CHILD_STDOUT_POLL_SECONDS = 0.25
CHILD_TASK_HEARTBEAT_SECONDS = 15.0
CHILD_STDOUT_DRAIN_GRACE_SECONDS = 1.0
CHILD_TERMINATION_GRACE_SECONDS = 3.0


class ChildProcessInterrupted(RuntimeError):
    """单牧场子进程被系统终止，已提交阶段仍可继续复用。"""


class MultiFarmTaskWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    parallel_start = pyqtSignal(list)
    sub_task_progress = pyqtSignal(str, int)
    sub_task_done = pyqtSignal(str, bool)

    def __init__(
        self,
        api_client,
        farms,
        project_path,
        *,
        data_source: str,
        service_staff: str = "",
        full_analysis: bool = False,
    ):
        super().__init__()
        self.api_client = api_client
        self.farms = [dict(farm) for farm in farms]
        self.project_path = Path(project_path)
        self.data_source = data_source
        self.service_staff = service_staff
        self.full_analysis = full_analysis
        self._last_saved_progress = {}
        self._lease_store = None
        self._lease_heartbeat = None

    def _acquire_batch_lease(self) -> None:
        store = FileManager._group_task_store(self.project_path)
        if store is None:
            return
        revision = store.get_selection_revision()
        lease = store.acquire_run_lease(
            f"desktop:{os.getpid()}:{uuid.uuid4()}",
            run_kind="multi_farm_batch",
            lease_seconds=600,
            expected_selection_revision=revision,
        )
        if lease is None:
            raise RuntimeError(
                "该牧场组已有另一个处理或汇总任务正在运行，请稍后再试"
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
                logger.warning(
                    "启动牧场组批处理租约续租器失败后释放租约失败",
                    exc_info=True,
                )
            raise
        self._lease_store = store
        self._lease_heartbeat = heartbeat
        # 能取得新的组级租约，说明不存在仍受保护的合法旧批次。把上次
        # 退出遗留的 running 状态恢复为可重试，已提交清单不受影响。
        store.mark_stale(
            stale_after_seconds=0,
            message="上次运行已中断，已按阶段提交清单恢复为可继续",
        )

    def _refresh_batch_lease(self) -> None:
        if self._lease_heartbeat is None:
            return
        self._lease_heartbeat.check()

    def _release_batch_lease(self) -> None:
        heartbeat = self._lease_heartbeat
        self._lease_heartbeat = None
        if heartbeat is not None:
            try:
                heartbeat.stop(timeout=30, release=True)
            except Exception:
                logger.warning("释放牧场组运行锁失败", exc_info=True)
        self._lease_store = None

    def _child_progress(self, index, total, task_id, name, value, message):
        try:
            child_value = max(0, min(100, int(value)))
        except (TypeError, ValueError):
            child_value = 0
        overall = int(((index + child_value / 100) / max(total, 1)) * 90)
        self.progress.emit(overall, f"[{name}] {message}")
        self.sub_task_progress.emit(task_id, child_value)
        previous = self._last_saved_progress.get(task_id, -10)
        if child_value >= previous + 5 or child_value in (0, 100):
            self._last_saved_progress[task_id] = child_value
            if self._lease_store is not None:
                self._lease_store.heartbeat(
                    task_id,
                    progress=child_value,
                )
            self._refresh_batch_lease()
            FileManager.update_group_task(
                self.project_path,
                task_id,
                stage=str(message or "处理中"),
                progress=child_value,
            )

    def _prepare_local_child(self, child_path: Path, farm: dict, callback):
        from core.data.composite_farm_manager import (
            materialize_single_local_project,
        )

        return materialize_single_local_project(
            child_path,
            farm,
            data_source=self.data_source,
            progress_callback=callback,
        )

    def _stage_update(self, task_id: str, stage_name: str, status: str, **extra):
        """兼容任务库接入前后的阶段状态更新。"""
        updater = getattr(FileManager, "update_group_stage", None)
        if updater:
            updater(
                self.project_path,
                task_id,
                stage_name,
                status=status,
                **extra,
            )

    def _heartbeat_silent_child(
        self,
        task_id: str,
        current_stage: str,
    ) -> None:
        """子进程暂时无输出时刷新单任务心跳，不伪造进度。"""
        store = self._lease_store or FileManager._group_task_store(
            self.project_path
        )
        if store is not None:
            store.heartbeat(task_id, stage=current_stage)
        self._refresh_batch_lease()

    @staticmethod
    def _start_stdout_reader(stdout, output_queue: queue.Queue) -> threading.Thread:
        """在守护线程中执行跨平台阻塞读取，任务线程只轮询队列。"""

        def read_lines() -> None:
            try:
                while True:
                    raw_line = stdout.readline()
                    if not raw_line:
                        break
                    output_queue.put(("line", raw_line))
            except Exception as exc:
                output_queue.put(("error", exc))
            finally:
                output_queue.put(("eof", None))

        reader = threading.Thread(
            target=read_lines,
            name="multi-farm-child-stdout-reader",
            daemon=True,
        )
        reader.start()
        return reader

    @staticmethod
    def _terminate_child_process(process) -> None:
        """请求子进程退出，短暂宽限后才强制终止。"""
        if process is None or process.poll() is not None:
            return
        try:
            process.terminate()
        except (AttributeError, OSError):
            try:
                process.kill()
            except OSError:
                return
        if process.poll() is not None:
            return
        try:
            process.wait(timeout=CHILD_TERMINATION_GRACE_SECONDS)
            return
        except TypeError:
            # 测试替身或极旧封装可能不支持 timeout；仅在已退出时回收，
            # 绝不退回到可能永久阻塞的 wait()。
            if process.poll() is not None:
                process.wait()
                return
        except subprocess.TimeoutExpired:
            pass
        try:
            process.kill()
        except OSError:
            return
        try:
            process.wait(timeout=CHILD_TERMINATION_GRACE_SECONDS)
        except TypeError:
            if process.poll() is not None:
                process.wait()
        except subprocess.TimeoutExpired:
            logger.warning("强制终止单牧场子进程后仍未在宽限期内退出")

    @staticmethod
    def _resolve_task_for_farm(farm: dict, tasks: list[dict]) -> dict:
        """按不可变 task_id 关联任务，避免排序/排除后发生牧场窜行。"""
        task_id = str(farm.get("task_id") or "").strip()
        if task_id:
            matches = [
                task
                for task in tasks
                if str(task.get("task_id") or "") == task_id
            ]
            if len(matches) == 1:
                return matches[0]
            raise RuntimeError(f"找不到牧场任务ID：{task_id}")

        code = str(farm.get("code") or farm.get("farmCode") or "").strip()
        matches = [
            task
            for task in tasks
            if str(task.get("farm_code") or "").strip() == code
        ]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise RuntimeError(f"找不到牧场编号对应的任务：{code}")
        raise RuntimeError(
            f"牧场编号 {code} 对应多个任务，不能按列表位置猜测，请使用 task_id"
        )

    def _run_child(
        self,
        index: int,
        total: int,
        farm: dict,
        child_path: Path,
        task_id: str,
    ):
        from gui.auto_report_worker import AutoReportWorker
        from core.group_tasks.stage_policy import (
            commit_child_stage,
            invalidate_stage_and_downstream,
            validate_child_stage,
        )

        code = str(farm.get("code") or farm.get("farmCode") or "")
        name = str(farm.get("name") or code)
        stage_order = ("data", "analysis", "child_excel")
        force_from = ""
        store = FileManager._group_task_store(self.project_path)
        if store is not None:
            task_state = store.get_task(task_id, with_stages=False) or {}
            force_from = str(
                task_state.get("metadata", {}).get(
                    "force_recompute_from", ""
                )
                or ""
            )

        def stage_forced(stage_name: str) -> bool:
            return (
                force_from in stage_order
                and stage_order.index(stage_name)
                >= stage_order.index(force_from)
            )

        def clear_force_recompute() -> None:
            if store is not None and force_from:
                store.update_task(
                    task_id,
                    metadata={"force_recompute_from": ""},
                )

        def relay(value, message=""):
            self._child_progress(index, total, task_id, name, value, message)

        is_local = farm.get("source_kind") == "local"

        def stage_validation(stage_name: str) -> dict:
            return validate_child_stage(
                child_path,
                stage_name,
                expected_task_id=task_id,
                expected_farm_code=code,
            )

        def stage_artifacts(validation: dict) -> dict:
            manifest = validation.get("manifest") or {}
            return {
                str(item.get("logical_name") or item.get("relative_path")):
                str(child_path / str(item.get("relative_path") or ""))
                for item in manifest.get("outputs", [])
                if item.get("relative_path")
            }

        def data_stage_ready() -> bool:
            try:
                if is_local:
                    from core.data.composite_farm_manager import (
                        validate_local_data_commit,
                    )

                    validate_local_data_commit(
                        child_path,
                        expected_farm_code=code,
                        expected_task_id=task_id,
                    )
                return bool(stage_validation("data").get("valid"))
            except Exception:
                return False

        normalized = farm
        if stage_forced("data") or not data_stage_ready():
            invalidate_stage_and_downstream(child_path, "data")
            self._stage_update(task_id, "data", "running")
            if is_local:
                normalized = self._prepare_local_child(child_path, farm, relay)
                download = False
            else:
                download = True
            child = AutoReportWorker(
                self.api_client,
                [normalized],
                child_path,
                False,
                service_staff=self.service_staff,
                data_source=self.data_source,
                local_farms=[],
                reliability_mode=True,
            )
            child.progress.connect(relay)
            results = child.execute(
                download=download,
                analysis=False,
                excel=False,
                ppt=False,
            )
            commit_child_stage(
                child_path,
                "data",
                expected_task_id=task_id,
                expected_farm_code=code,
            )
            if not data_stage_ready():
                data_error = "数据阶段提交清单校验失败"
                self._stage_update(
                    task_id,
                    "data",
                    "failed",
                    error=data_error,
                )
                raise RuntimeError(data_error)
            data_validation = stage_validation("data")
            self._stage_update(
                task_id,
                "data",
                "completed",
                artifacts=stage_artifacts(data_validation),
            )
        else:
            results = {
                "success_items": ["数据阶段已存在，断点续用"],
                "failed_items": [],
                "excel_path": None,
                "ppt_path": None,
            }
            data_validation = stage_validation("data")
            self._stage_update(
                task_id,
                "data",
                "completed",
                artifacts=stage_artifacts(data_validation),
            )

        if not self.full_analysis:
            clear_force_recompute()
            return results

        analysis_ready = bool(stage_validation("analysis").get("valid"))
        child_excel_ready = bool(
            stage_validation("child_excel").get("valid")
        )
        requested_stages = []
        if stage_forced("analysis") or not analysis_ready:
            requested_stages = ["analysis", "child_excel"]
        elif stage_forced("child_excel") or not child_excel_ready:
            requested_stages = ["child_excel"]

        if requested_stages:
            results = self._run_analysis_child_process(
                index=index,
                total=total,
                task_id=task_id,
                farm_code=code,
                farm_name=name,
                child_path=child_path,
                stages=requested_stages,
            )
        else:
            analysis_validation = stage_validation("analysis")
            excel_validation = stage_validation("child_excel")
            excel_artifacts = stage_artifacts(excel_validation)
            report_path = next(iter(excel_artifacts.values()), "")
            self._stage_update(
                task_id,
                "analysis",
                "completed",
                artifacts=stage_artifacts(analysis_validation),
            )
            self._stage_update(
                task_id,
                "child_excel",
                "completed",
                artifacts=excel_artifacts,
            )
            results = {
                "success_items": ["分析及单牧场报告已存在，断点续用"],
                "failed_items": [],
                "excel_path": report_path,
                "ppt_path": None,
            }
        clear_force_recompute()
        return results

    def _run_analysis_child_process(
        self,
        *,
        index: int,
        total: int,
        task_id: str,
        farm_code: str,
        farm_name: str,
        child_path: Path,
        stages: list[str],
    ) -> dict:
        """在一次性子进程内执行单场分析，进程退出即回收全部内存。"""
        from core.group_tasks.parent_process import (
            build_child_command,
            parse_jsonl_line,
            write_child_request,
        )
        from core.group_tasks.stage_policy import validate_child_stage

        request_path = write_child_request(
            self.project_path,
            task_id,
            stages,
            service_staff=self.service_staff,
        )
        command = build_child_command(request_path)
        process = None
        current_stage = stages[0]
        completed_stages = set()
        result_event = None
        warnings = []

        try:
            process = subprocess.Popen(
                command,
                cwd=str(Path(__file__).resolve().parents[1]),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
            )
            if process.stdout is None:
                raise RuntimeError("无法建立单牧场子进程通信管道")

            stdout_queue: queue.Queue = queue.Queue()
            stdout_reader = self._start_stdout_reader(
                process.stdout,
                stdout_queue,
            )
            stdout_eof = False
            process_exit_seen_at = None
            last_output_or_heartbeat = time.monotonic()
            while True:
                if self.isInterruptionRequested():
                    message = (
                        "用户请求停止牧场组任务，当前单牧场子进程已中断，"
                        f"可从 {current_stage} 阶段继续"
                    )
                    self._terminate_child_process(process)
                    self._stage_update(
                        task_id,
                        current_stage,
                        "interrupted",
                        error=message,
                    )
                    raise ChildProcessInterrupted(message)

                now = time.monotonic()
                return_code = process.poll()
                if return_code is not None:
                    if process_exit_seen_at is None:
                        process_exit_seen_at = now
                    if stdout_eof and stdout_queue.empty():
                        break
                    if (
                        not stdout_reader.is_alive()
                        and stdout_queue.empty()
                    ):
                        break
                    # 极少数子孙进程可能继承 stdout，父进程退出后不会立刻
                    # 收到 EOF；只限制退出后的排空等待，不限制正常运行时长。
                    if (
                        stdout_queue.empty()
                        and now - process_exit_seen_at
                        >= CHILD_STDOUT_DRAIN_GRACE_SECONDS
                    ):
                        break

                heartbeat_due_in = max(
                    0.01,
                    CHILD_TASK_HEARTBEAT_SECONDS
                    - (now - last_output_or_heartbeat),
                )
                poll_timeout = min(
                    CHILD_STDOUT_POLL_SECONDS,
                    heartbeat_due_in,
                )
                try:
                    item_type, payload = stdout_queue.get(
                        timeout=poll_timeout
                    )
                except queue.Empty:
                    now = time.monotonic()
                    if (
                        now - last_output_or_heartbeat
                        >= CHILD_TASK_HEARTBEAT_SECONDS
                    ):
                        self._heartbeat_silent_child(
                            task_id,
                            current_stage,
                        )
                        last_output_or_heartbeat = now
                    continue

                if item_type == "eof":
                    stdout_eof = True
                    continue
                if item_type == "error":
                    if process.poll() is None:
                        raise RuntimeError(
                            "读取单牧场子进程输出失败"
                        ) from payload
                    stdout_eof = True
                    continue

                raw_line = payload
                last_output_or_heartbeat = time.monotonic()
                event = parse_jsonl_line(raw_line)
                event_task_id = str(event.get("task_id") or task_id)
                event_farm_code = str(event.get("farm_code") or farm_code)
                if event_task_id != task_id or event_farm_code != farm_code:
                    raise RuntimeError("子进程返回了其他牧场的任务身份")

                event_type = event["type"]
                if event_type == "stage_started":
                    current_stage = str(event.get("stage") or current_stage)
                    self._stage_update(
                        task_id,
                        current_stage,
                        "running",
                    )
                elif event_type == "progress":
                    current_stage = str(event.get("stage") or current_stage)
                    self._child_progress(
                        index,
                        total,
                        task_id,
                        farm_name,
                        event.get("progress", 0),
                        event.get("message")
                        or f"{current_stage} 处理中",
                    )
                elif event_type == "stage_completed":
                    completed_stage = str(event.get("stage") or "")
                    validation = validate_child_stage(
                        child_path,
                        completed_stage,
                        expected_task_id=task_id,
                        expected_farm_code=farm_code,
                    )
                    if not validation.get("valid"):
                        raise RuntimeError(
                            f"{completed_stage} 阶段提交后校验失败"
                        )
                    manifest = validation["manifest"]
                    artifacts = {
                        str(
                            item.get("logical_name")
                            or item.get("relative_path")
                        ): str(
                            child_path
                            / str(item.get("relative_path") or "")
                        )
                        for item in manifest.get("outputs", [])
                    }
                    self._stage_update(
                        task_id,
                        completed_stage,
                        "completed",
                        artifacts=artifacts,
                    )
                    completed_stages.add(completed_stage)
                elif event_type == "result":
                    result_event = event
                    warnings = list(event.get("warnings") or [])

            return_code = process.poll()
            if return_code is None:
                raise RuntimeError("单牧场子进程状态异常：输出结束但进程仍在运行")
            if result_event and not result_event.get("success"):
                message = str(
                    result_event.get("error")
                    or f"{current_stage} 阶段执行失败"
                )
                self._stage_update(
                    task_id,
                    current_stage,
                    "failed",
                    error=message,
                )
                raise RuntimeError(message)
            if return_code != 0 or not result_event:
                message = (
                    f"单牧场子进程异常退出（代码 {return_code}），"
                    f"可从 {current_stage} 阶段继续"
                )
                self._stage_update(
                    task_id,
                    current_stage,
                    "interrupted",
                    error=message,
                )
                raise ChildProcessInterrupted(message)
            missing = set(stages) - completed_stages
            if missing:
                raise RuntimeError(
                    "子进程未提交全部请求阶段: "
                    + "、".join(sorted(missing))
                )

            excel_validation = validate_child_stage(
                child_path,
                "child_excel",
                expected_task_id=task_id,
                expected_farm_code=farm_code,
            )
            report_path = ""
            if excel_validation.get("valid"):
                outputs = excel_validation["manifest"].get("outputs", [])
                if outputs:
                    report_path = str(
                        child_path / outputs[0]["relative_path"]
                    )
            return {
                "success_items": [
                    f"{stage} 阶段" for stage in sorted(completed_stages)
                ],
                "failed_items": [
                    (
                        str(item.get("item") or "可选分析"),
                        str(item.get("message") or ""),
                    )
                    for item in warnings
                ],
                "excel_path": report_path,
                "ppt_path": None,
            }
        except ChildProcessInterrupted:
            raise
        except Exception as exc:
            if process is not None and process.poll() is None:
                self._terminate_child_process(process)
            if current_stage not in completed_stages:
                self._stage_update(
                    task_id,
                    current_stage,
                    "failed",
                    error=str(exc),
                )
            raise
        finally:
            request_path.unlink(missing_ok=True)

    def run(self):
        try:
            self._acquire_batch_lease()
            # 不能仅信任上次保存的 completed：先核验实际产物，缺失或
            # 半成品会被降为 stale，再进入本轮可恢复队列。
            FileManager.refresh_group_task_statuses(self.project_path)
            metadata = FileManager.load_project_metadata(self.project_path)
            tasks = metadata.get("group_tasks", [])
            specs = [
                {
                    "id": str(
                        task.get("task_id")
                        or task.get("farm_code", "")
                    ),
                    "name": str(task.get("farm_name", task.get("farm_code", ""))),
                    "path": str(self.project_path / task["relative_path"]),
                }
                for task in tasks
                if task.get("included_in_summary", True)
            ]
            self.parallel_start.emit(specs)

            completed = []
            failed = []
            runnable = []
            for farm in self.farms:
                try:
                    task = self._resolve_task_for_farm(farm, tasks)
                except Exception as exc:
                    code = str(
                        farm.get("code") or farm.get("farmCode") or ""
                    )
                    failed.append(
                        {
                            "farm_code": code,
                            "farm_name": str(farm.get("name") or code),
                            "path": str(self.project_path),
                            "error": str(exc),
                        }
                    )
                    logger.error("牧场任务关联失败（继续后续任务）: %s", exc)
                    continue
                if not task.get("included_in_summary", True):
                    continue
                if task.get("status") in {
                    "completed",
                    "completed_with_warning",
                }:
                    task_id = str(
                        task.get("task_id")
                        or task.get("farm_code", "")
                    )
                    completed.append(
                        {
                            "farm_code": task.get("farm_code", ""),
                            "farm_name": task.get("farm_name", ""),
                            "path": str(
                                self.project_path / task.get("relative_path", "")
                            ),
                            "resumed": True,
                        }
                    )
                    self.sub_task_progress.emit(task_id, 100)
                    self.sub_task_done.emit(task_id, True)
                    continue
                runnable.append((farm, task))

            total = len(runnable)
            for index, (farm, task) in enumerate(runnable):
                if self.isInterruptionRequested():
                    break
                self._refresh_batch_lease()
                code = str(farm.get("code") or farm.get("farmCode") or "")
                name = str(farm.get("name") or code)
                task_id = str(task.get("task_id") or code)
                child_path = self.project_path
                try:
                    child_path = FileManager.get_group_child_path(
                        self.project_path, task_id
                    )
                    if child_path is None:
                        raise RuntimeError(f"找不到牧场子项目：{code}")
                    FileManager.update_group_task(
                        self.project_path,
                        task_id,
                        status="running",
                        stage="开始处理",
                        progress=0,
                        error="",
                    )
                    self.progress.emit(
                        int(index / max(total, 1) * 90),
                        f"正在处理 {name}（{index + 1}/{total}）",
                    )
                    results = self._run_child(
                        index, total, farm, child_path, task_id
                    )
                    status = (
                        "completed_with_warning"
                        if results.get("failed_items")
                        else "completed"
                    )
                    FileManager.update_group_task(
                        self.project_path,
                        task_id,
                        status=status,
                        stage=(
                            "已完成（部分可选分析缺少数据）"
                            if status == "completed_with_warning"
                            else "已完成"
                        ),
                        progress=100,
                        error="",
                        result={
                            "excel_path": results.get("excel_path") or "",
                            "success_items": results.get("success_items", []),
                        },
                    )
                    completed.append(
                        {"farm_code": code, "farm_name": name, "path": str(child_path)}
                    )
                    self.sub_task_progress.emit(task_id, 100)
                    self.sub_task_done.emit(task_id, True)
                except Exception as exc:
                    interrupted = isinstance(exc, ChildProcessInterrupted)
                    logger.exception(
                        "牧场子任务%s: %s",
                        "中断" if interrupted else "失败",
                        name,
                    )
                    FileManager.update_group_task(
                        self.project_path,
                        task_id,
                        status="interrupted" if interrupted else "failed",
                        stage=(
                            "子进程中断，可继续"
                            if interrupted
                            else "处理失败"
                        ),
                        error=str(exc),
                    )
                    failed.append(
                        {
                            "farm_code": code,
                            "farm_name": name,
                            "path": str(child_path),
                            "error": str(exc),
                            "interrupted": interrupted,
                        }
                    )
                    self.sub_task_done.emit(task_id, False)
                    if interrupted and self.isInterruptionRequested():
                        break
                finally:
                    try:
                        from core.data.update_manager import reset_pedigree_db
                        import gc

                        reset_pedigree_db()
                        gc.collect()
                    except Exception:
                        logger.debug("清理单牧场资源失败", exc_info=True)

            excel_path = None
            summary_error = ""
            if self.full_analysis and not failed:
                # 最终汇总使用自己的一致性快照租约；先释放批处理租约。
                self._release_batch_lease()
                self.progress.emit(92, "全部牧场完成，正在生成最终汇总Excel...")
                from core.group_report import GroupExcelReportGenerator

                generator = GroupExcelReportGenerator(
                    self.project_path,
                    service_staff=self.service_staff,
                    progress_callback=lambda value, message: self.progress.emit(
                        90 + int(value * 0.1), message
                    ),
                )
                success, result = generator.generate()
                if success:
                    excel_path = result
                else:
                    summary_error = result

            self.progress.emit(100, "牧场组任务处理完成")
            self.finished.emit(
                {
                    "project_path": str(self.project_path),
                    "completed": completed,
                    "failed": failed,
                    "summary_error": summary_error,
                    "excel_path": excel_path,
                    "ppt_path": None,
                    "full_analysis": self.full_analysis,
                }
            )
        except Exception as exc:
            logger.exception("牧场组任务执行失败")
            self.error.emit(f"牧场组任务执行失败：{exc}")
        finally:
            self._release_batch_lease()
