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

from core.group_tasks.dataset_plan import normalize_dataset_selection
from core.group_tasks.lease_heartbeat import GroupLeaseHeartbeat
from core.group_tasks.memory_guard import (
    AdaptiveMemoryGuard,
    ResourcePressureError,
    boundary_pause_message,
    runtime_pause_message,
)
from utils.file_manager import FileManager


logger = logging.getLogger(__name__)

CHILD_STDOUT_POLL_SECONDS = 0.25
CHILD_TASK_HEARTBEAT_SECONDS = 15.0
CHILD_STDOUT_DRAIN_GRACE_SECONDS = 1.0
CHILD_TERMINATION_GRACE_SECONDS = 3.0


class ChildProcessInterrupted(RuntimeError):
    """单牧场子进程被系统终止，已提交阶段仍可继续复用。"""


class MemoryPressureInterrupted(
    ChildProcessInterrupted,
    ResourcePressureError,
):
    """内存压力触发的安全暂停；应停止本批次并保留断点。"""


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
        memory_guard: AdaptiveMemoryGuard | None = None,
        dataset_selection: dict | None = None,
    ):
        super().__init__()
        self.api_client = api_client
        self.farms = [dict(farm) for farm in farms]
        self.project_path = Path(project_path)
        self.data_source = data_source
        self.service_staff = service_staff
        self.full_analysis = full_analysis
        task_mode = "analysis" if full_analysis else "data_only"
        has_local_farms = any(
            str(farm.get("source_kind") or "api") == "local"
            for farm in self.farms
        )
        self._requested_dataset_selection = (
            None
            if dataset_selection is None
            else normalize_dataset_selection(
                dataset_selection,
                task_mode=task_mode,
                has_local_farms=has_local_farms,
            )
        )
        self.dataset_selection = normalize_dataset_selection(
            dataset_selection,
            task_mode=task_mode,
            has_local_farms=has_local_farms,
        )
        self._last_saved_progress = {}
        self._lease_store = None
        self._lease_heartbeat = None
        self._memory_guard = memory_guard or AdaptiveMemoryGuard()

    def _load_and_validate_dataset_selection(self) -> dict:
        """从父任务恢复不可变选择，并核对 SQLite/子项目副本。"""
        metadata = FileManager.load_project_metadata(self.project_path)
        task_mode = str(metadata.get("task_mode") or "analysis")
        expected_mode = "analysis" if self.full_analysis else "data_only"
        if task_mode != expected_mode:
            raise RuntimeError(
                f"任务模式不一致：项目为 {task_mode}，"
                f"本次运行请求为 {expected_mode}"
            )
        tasks = metadata.get("group_tasks") or []
        has_local_farms = any(
            str(task.get("source_kind") or "api") == "local"
            for task in tasks
        )
        parent_explicit = bool(
            metadata.get(
                "dataset_selection_explicit",
                "dataset_selection" in metadata,
            )
        )
        persisted = normalize_dataset_selection(
            metadata.get("dataset_selection"),
            task_mode=task_mode,
            has_local_farms=has_local_farms,
        )
        if (
            self._requested_dataset_selection is not None
            and self._requested_dataset_selection != persisted
        ):
            raise RuntimeError(
                "本次数据集选择与项目创建时不一致，不能改变断点任务口径"
            )

        for task in tasks:
            task_metadata = task.get("metadata") or {}
            task_explicit = bool(
                task_metadata.get(
                    "dataset_selection_explicit",
                    "dataset_selection" in task_metadata,
                )
            )
            if task_explicit != parent_explicit:
                raise RuntimeError("父任务与子任务的数据集选择标记不一致")
            task_selection = normalize_dataset_selection(
                task_metadata.get("dataset_selection"),
                task_mode=task_mode,
                has_local_farms=(
                    str(task.get("source_kind") or "api") == "local"
                ),
            )
            if task_selection != persisted:
                raise RuntimeError("父任务与子任务的数据集选择不一致")

            child_path = (
                self.project_path / str(task.get("relative_path") or "")
            )
            child_metadata = FileManager.load_project_metadata(child_path)
            child_explicit = bool(
                child_metadata.get(
                    "dataset_selection_explicit",
                    "dataset_selection" in child_metadata,
                )
            )
            if child_explicit != parent_explicit:
                raise RuntimeError("父任务与子项目的数据集选择标记不一致")
            child_selection = normalize_dataset_selection(
                child_metadata.get("dataset_selection"),
                task_mode=task_mode,
                has_local_farms=(
                    str(task.get("source_kind") or "api") == "local"
                ),
            )
            if child_selection != persisted:
                raise RuntimeError("父任务与子项目的数据集选择不一致")

        self.dataset_selection = persisted
        return metadata

    def _check_memory_boundary(self, progress_value: int = 0) -> None:
        """在单牧场安全边界检查内存，不按机器配置或牧场数限流。"""
        assessment = self._memory_guard.assess_boundary()
        if not assessment.should_pause:
            return
        message = boundary_pause_message(assessment)
        logger.warning("牧场组任务因内存安全余量不足暂停：%s", message)
        self.progress.emit(
            max(0, min(100, int(progress_value))),
            message,
        )
        raise MemoryPressureInterrupted(message)

    def _check_data_stage_resources(self) -> None:
        """在数据下载/转换/标准化步骤之间检查持续内存压力。

        数据阶段依赖桌面当前登录态，不能把凭据复制到分析子进程。
        因此这一阶段仍在工作线程内执行，并在各个安全步骤边界暂停。
        """
        assessment = self._memory_guard.poll_runtime()
        if not assessment.should_pause:
            return
        raise MemoryPressureInterrupted(
            runtime_pause_message(assessment).replace(
                "已安全终止当前牧场子进程；",
                "已在当前牧场数据处理的安全步骤边界暂停；",
            )
        )

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
            dataset_selection=self.dataset_selection,
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

    def _finish_running_stages(
        self,
        task_id: str,
        *,
        status: str,
        error: str,
    ) -> None:
        """任务异常退出时同步收尾仍为 running 的阶段。"""
        store = self._lease_store or FileManager._group_task_store(
            self.project_path
        )
        if store is None:
            return
        task = store.get_task(task_id, with_stages=True) or {}
        for stage_name, stage in (task.get("stages") or {}).items():
            if stage.get("status") != "running":
                continue
            self._stage_update(
                task_id,
                stage_name,
                status,
                error=error,
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
                        expected_dataset_selection=self.dataset_selection,
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
                def local_relay(value, message=""):
                    self._check_data_stage_resources()
                    relay(value, message)

                normalized = self._prepare_local_child(
                    child_path,
                    farm,
                    local_relay,
                )
                self._check_data_stage_resources()
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
                group_batch_mode=True,
                resource_check=self._check_data_stage_resources,
                dataset_selection=self.dataset_selection,
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
        if not self.dataset_selection["herd"]:
            raise RuntimeError("未选择牛群/系谱数据，不能进入批量分析")

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
            # 数据下载/标准化也可能改变主进程的内存占用，因此在真正
            # 启动分析子进程前再次检查。此处仍是安全边界，没有临时
            # 分析产物需要清理。
            assessment = self._memory_guard.assess_boundary()
            if assessment.should_pause:
                message = boundary_pause_message(assessment)
                self._stage_update(
                    task_id,
                    current_stage,
                    "interrupted",
                    error=message,
                )
                raise MemoryPressureInterrupted(message)

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
                if return_code is None:
                    memory_assessment = self._memory_guard.poll_runtime()
                    if memory_assessment.should_pause:
                        message = runtime_pause_message(memory_assessment)
                        self._terminate_child_process(process)
                        self._stage_update(
                            task_id,
                            current_stage,
                            "interrupted",
                            error=message,
                        )
                        raise MemoryPressureInterrupted(message)
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
                # 137/-9 是 Unix 下常见的 SIGKILL/OOM 表现，
                # STATUS_NO_MEMORY 是 Windows 的明确内存不足退出码。
                # 即使无法确定是 OOM，也应停下批次，避免随后牧场继续
                # 放大系统压力；已提交阶段仍可断点复用。
                if return_code in {
                    -9,
                    137,
                    -1073741801,
                    3221225495,
                }:
                    message = (
                        "单牧场子进程被操作系统终止，可能是系统内存不足。"
                        f"已保留已提交阶段，可从 {current_stage} 阶段重试；"
                        "请先关闭其他应用释放内存后继续处理。"
                    )
                    self._stage_update(
                        task_id,
                        current_stage,
                        "interrupted",
                        error=message,
                    )
                    raise MemoryPressureInterrupted(message)
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
            self._load_and_validate_dataset_selection()
            # 不能仅信任上次保存的 completed：先核验实际产物，缺失或
            # 半成品会被降为 stale，再进入本轮可恢复队列。
            FileManager.refresh_group_task_statuses(self.project_path)
            metadata = self._load_and_validate_dataset_selection()
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
            paused_for_memory = False
            memory_pause_reason = ""
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
                    self._check_memory_boundary(
                        int(index / max(total, 1) * 90)
                    )
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
                    if isinstance(exc, MemoryError):
                        exc = MemoryPressureInterrupted(
                            "系统在处理当前牧场数据时无法继续分配内存，"
                            "已完成牧场和已提交阶段均已保留，当前牧场可重试。"
                            "请关闭其他应用释放内存后继续处理。"
                        )
                    interrupted = isinstance(exc, ChildProcessInterrupted)
                    memory_pressure = isinstance(
                        exc,
                        MemoryPressureInterrupted,
                    )
                    if memory_pressure:
                        paused_for_memory = True
                        memory_pause_reason = str(exc)
                    terminal_status = (
                        "interrupted" if interrupted else "failed"
                    )
                    self._finish_running_stages(
                        task_id,
                        status=terminal_status,
                        error=str(exc),
                    )
                    if memory_pressure:
                        logger.warning(
                            "牧场子任务因内存保护暂停: %s - %s",
                            name,
                            exc,
                        )
                    else:
                        logger.exception(
                            "牧场子任务%s: %s",
                            "中断" if interrupted else "失败",
                            name,
                        )
                    FileManager.update_group_task(
                        self.project_path,
                        task_id,
                        status=terminal_status,
                        stage=(
                            "内存不足，已暂停，可继续"
                            if memory_pressure
                            else "子进程中断，可继续"
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
                            "memory_pressure": memory_pressure,
                        }
                    )
                    self.sub_task_done.emit(task_id, False)
                    if memory_pressure or (
                        interrupted and self.isInterruptionRequested()
                    ):
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
                    "paused_for_memory": paused_for_memory,
                    "memory_pause_reason": memory_pause_reason,
                    "resume_available": paused_for_memory,
                }
            )
        except Exception as exc:
            logger.exception("牧场组任务执行失败")
            self.error.emit(f"牧场组任务执行失败：{exc}")
        finally:
            self._release_batch_lease()
