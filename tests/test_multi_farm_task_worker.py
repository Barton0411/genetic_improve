from __future__ import annotations

import io
import json
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import xlsxwriter

from core.group_tasks.stage_policy import commit_child_stage
from gui.multi_farm_task_worker import (
    ChildProcessInterrupted,
    MemoryPressureInterrupted,
    MultiFarmTaskWorker,
)
from core.group_tasks.memory_guard import (
    GIB,
    AdaptiveMemoryGuard,
    MemoryGuardConfig,
    MemorySnapshot,
)
from utils.file_manager import FileManager


def _book(path: Path, headers, rows=()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(path))
    worksheet = workbook.add_worksheet("Sheet1")
    worksheet.write_row(0, 0, list(headers))
    for row_index, row in enumerate(rows, start=1):
        worksheet.write_row(row_index, 0, list(row))
    workbook.close()


class _FakeProcess:
    def __init__(self, events, return_code):
        payload = "".join(
            json.dumps(event, ensure_ascii=False) + "\n"
            for event in events
        ).encode("utf-8")
        self.stdout = io.BytesIO(payload)
        self.return_code = return_code
        self.killed = False
        self.terminated = False

    def wait(self, timeout=None):
        return self.return_code

    def poll(self):
        return self.return_code

    def terminate(self):
        self.terminated = True
        self.return_code = -15

    def kill(self):
        self.killed = True
        self.return_code = -9


class _BlockingStdout:
    def __init__(self):
        self.read_started = threading.Event()
        self.release = threading.Event()

    def readline(self):
        self.read_started.set()
        self.release.wait()
        return b""


class _SilentProcess:
    """模拟长计算期间完全不写 stdout 的仍在运行子进程。"""

    def __init__(self):
        self.stdout = _BlockingStdout()
        self.return_code = None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.return_code

    def terminate(self):
        self.terminated = True
        self.return_code = -15
        self.stdout.release.set()

    def kill(self):
        self.killed = True
        self.return_code = -9
        self.stdout.release.set()

    def wait(self, timeout=None):
        if self.return_code is not None:
            return self.return_code
        if not self.stdout.release.wait(timeout):
            raise subprocess.TimeoutExpired("silent-child", timeout)
        return self.return_code


class _ChildProcessOnlyWorker(MultiFarmTaskWorker):
    """只在真实 QThread 中执行子进程读取循环，便于验证中断。"""

    def __init__(self, project_path, invocation):
        super().__init__(
            None,
            [],
            project_path,
            data_source="伊起牛",
            full_analysis=True,
        )
        self.invocation = invocation
        self.child_result = None
        self.caught = None

    def run(self):
        try:
            self.child_result = self._run_analysis_child_process(
                **self.invocation
            )
        except Exception as exc:
            self.caught = exc


class MultiFarmTaskWorkerProcessTests(unittest.TestCase):
    def setUp(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.project = FileManager.create_group_project(
            Path(self.temporary_dir.name),
            [{"code": "010", "name": "测试牧场"}],
            data_source="伊起牛",
            task_mode="analysis",
        )
        metadata = FileManager.load_project_metadata(self.project)
        self.task = metadata["group_tasks"][0]
        self.child = self.project / self.task["relative_path"]
        _book(
            self.child / "raw_data" / "cow_data.xlsx",
            ["cow_id"],
            [["001"]],
        )
        _book(
            self.child
            / "standardized_data"
            / "processed_cow_data.xlsx",
            ["cow_id", "牧场编号"],
            [["001", "010"]],
        )
        for filename in (
            "processed_cow_data_key_traits_final.xlsx",
            "processed_index_cow_index_scores.xlsx",
        ):
            _book(
                self.child / "analysis_results" / filename,
                ["cow_id", "牧场编号"],
                [["001", "010"]],
            )
        for filename in ("关键育种性状分析结果.xlsx", "系谱识别分析结果.xlsx"):
            _book(
                self.child / "analysis_results" / filename,
                ["result"],
                [["ok"]],
            )
        self.report = (
            self.child / "reports" / "育种分析综合报告_测试.xlsx"
        )
        _book(self.report, ["report"], [["ok"]])
        self.configuration = patch(
            "core.group_tasks.stage_policy._analysis_configuration",
            return_value={"revision": "test"},
        )
        self.configuration.start()
        self.addCleanup(self.configuration.stop)
        for stage in ("data", "analysis", "child_excel"):
            commit_child_stage(
                self.child,
                stage,
                expected_task_id=self.task["task_id"],
                expected_farm_code="010",
            )
        self.worker = MultiFarmTaskWorker(
            None,
            [],
            self.project,
            data_source="伊起牛",
            full_analysis=True,
        )

    def tearDown(self):
        self.temporary_dir.cleanup()

    def _event(self, event_type, **extra):
        return {
            "type": event_type,
            "task_id": self.task["task_id"],
            "farm_code": "010",
            **extra,
        }

    def test_successful_process_commits_both_stages_and_returns_report(self):
        events = [
            self._event("stage_started", stage="analysis"),
            self._event(
                "progress",
                stage="analysis",
                progress=50,
                message="分析",
            ),
            self._event("stage_completed", stage="analysis"),
            self._event("stage_started", stage="child_excel"),
            self._event("stage_completed", stage="child_excel"),
            self._event(
                "result",
                success=True,
                completed_stages=["analysis", "child_excel"],
                warnings=[],
            ),
        ]
        with patch(
            "gui.multi_farm_task_worker.subprocess.Popen",
            return_value=_FakeProcess(events, 0),
        ):
            result = self.worker._run_analysis_child_process(
                index=0,
                total=1,
                task_id=self.task["task_id"],
                farm_code="010",
                farm_name="测试牧场",
                child_path=self.child,
                stages=["analysis", "child_excel"],
            )
        self.assertEqual(Path(result["excel_path"]), self.report)
        task = FileManager._group_task_store(self.project).get_task(
            self.task["task_id"]
        )
        self.assertEqual(task["stages"]["analysis"]["status"], "completed")
        self.assertEqual(
            task["stages"]["child_excel"]["status"],
            "completed",
        )

    def test_exit_without_result_is_interrupted_not_silent_success(self):
        events = [
            self._event("stage_started", stage="analysis"),
            self._event(
                "progress",
                stage="analysis",
                progress=40,
                message="处理中",
            ),
        ]
        with patch(
            "gui.multi_farm_task_worker.subprocess.Popen",
            return_value=_FakeProcess(events, 137),
        ):
            with self.assertRaises(ChildProcessInterrupted):
                self.worker._run_analysis_child_process(
                    index=0,
                    total=1,
                    task_id=self.task["task_id"],
                    farm_code="010",
                    farm_name="测试牧场",
                    child_path=self.child,
                    stages=["analysis"],
                )
        task = FileManager._group_task_store(self.project).get_task(
            self.task["task_id"]
        )
        self.assertEqual(
            task["stages"]["analysis"]["status"],
            "interrupted",
        )

    def test_silent_process_heartbeats_and_can_be_interrupted(self):
        silent_process = _SilentProcess()
        worker = _ChildProcessOnlyWorker(
            self.project,
            {
                "index": 0,
                "total": 1,
                "task_id": self.task["task_id"],
                "farm_code": "010",
                "farm_name": "测试牧场",
                "child_path": self.child,
                "stages": ["analysis"],
            },
        )

        with (
            patch(
                "gui.multi_farm_task_worker.CHILD_STDOUT_POLL_SECONDS",
                0.01,
            ),
            patch(
                "gui.multi_farm_task_worker.CHILD_TASK_HEARTBEAT_SECONDS",
                0.02,
            ),
            patch(
                "gui.multi_farm_task_worker.subprocess.Popen",
                return_value=silent_process,
            ),
            patch.object(
                worker,
                "_heartbeat_silent_child",
                wraps=worker._heartbeat_silent_child,
            ) as heartbeat,
        ):
            worker.start()
            self.assertTrue(silent_process.stdout.read_started.wait(1))
            deadline = time.monotonic() + 1
            while heartbeat.call_count == 0 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertGreaterEqual(heartbeat.call_count, 1)

            worker.requestInterruption()
            self.assertTrue(worker.wait(3000))

        self.assertIsInstance(worker.caught, ChildProcessInterrupted)
        self.assertTrue(silent_process.terminated)
        self.assertFalse(silent_process.killed)
        task = FileManager._group_task_store(self.project).get_task(
            self.task["task_id"]
        )
        self.assertEqual(
            task["stages"]["analysis"]["status"],
            "interrupted",
        )

    def test_structured_failure_is_failed_not_interrupted(self):
        events = [
            self._event("stage_started", stage="analysis"),
            {"type": "result", "success": False, "error": "测试失败"},
        ]
        with patch(
            "gui.multi_farm_task_worker.subprocess.Popen",
            return_value=_FakeProcess(events, 1),
        ):
            with self.assertRaisesRegex(RuntimeError, "测试失败"):
                self.worker._run_analysis_child_process(
                    index=0,
                    total=1,
                    task_id=self.task["task_id"],
                    farm_code="010",
                    farm_name="测试牧场",
                    child_path=self.child,
                    stages=["analysis"],
                )
        task = FileManager._group_task_store(self.project).get_task(
            self.task["task_id"]
        )
        self.assertEqual(task["stages"]["analysis"]["status"], "failed")

    def test_sustained_memory_pressure_stops_child_and_keeps_retryable(self):
        silent_process = _SilentProcess()
        snapshots = iter(
            [
                MemorySnapshot(8 * GIB, 4 * GIB, "test", 0),
                MemorySnapshot(8 * GIB, int(0.8 * GIB), "test", 0),
                MemorySnapshot(8 * GIB, int(0.7 * GIB), "test", 0),
            ]
        )
        guard = AdaptiveMemoryGuard(
            provider=lambda: next(snapshots),
            config=MemoryGuardConfig(
                boundary_floor_bytes=1 * GIB,
                boundary_fraction=0,
                boundary_cap_bytes=1 * GIB,
                danger_floor_bytes=1 * GIB,
                danger_fraction=0,
                danger_cap_bytes=1 * GIB,
                sustained_danger_samples=2,
                runtime_check_interval_seconds=0,
            ),
        )
        worker = MultiFarmTaskWorker(
            None,
            [],
            self.project,
            data_source="伊起牛",
            full_analysis=True,
            memory_guard=guard,
        )

        with (
            patch(
                "gui.multi_farm_task_worker.CHILD_STDOUT_POLL_SECONDS",
                0.01,
            ),
            patch(
                "gui.multi_farm_task_worker.subprocess.Popen",
                return_value=silent_process,
            ),
        ):
            with self.assertRaises(MemoryPressureInterrupted):
                worker._run_analysis_child_process(
                    index=0,
                    total=1,
                    task_id=self.task["task_id"],
                    farm_code="010",
                    farm_name="测试牧场",
                    child_path=self.child,
                    stages=["analysis"],
                )

        self.assertTrue(silent_process.terminated)
        task = FileManager._group_task_store(self.project).get_task(
            self.task["task_id"]
        )
        self.assertEqual(
            task["stages"]["analysis"]["status"],
            "interrupted",
        )
        self.assertIn(
            "当前阶段可重试",
            task["stages"]["analysis"]["error"],
        )

    def test_data_stage_pauses_only_after_sustained_memory_pressure(self):
        guard = AdaptiveMemoryGuard(
            provider=lambda: MemorySnapshot(
                8 * GIB,
                int(0.7 * GIB),
                "test",
                0,
            ),
            config=MemoryGuardConfig(
                danger_floor_bytes=1 * GIB,
                danger_fraction=0,
                danger_cap_bytes=1 * GIB,
                sustained_danger_samples=2,
                runtime_check_interval_seconds=0,
            ),
        )
        worker = MultiFarmTaskWorker(
            None,
            [],
            self.project,
            data_source="慧牧云",
            full_analysis=True,
            memory_guard=guard,
        )

        worker._check_data_stage_resources()
        with self.assertRaisesRegex(
            MemoryPressureInterrupted,
            "数据处理的安全步骤边界暂停",
        ):
            worker._check_data_stage_resources()

    def test_one_farm_failure_does_not_block_later_farms(self):
        project = FileManager.create_group_project(
            Path(self.temporary_dir.name),
            [
                {"code": "101", "name": "失败牧场"},
                {"code": "102", "name": "后续牧场"},
            ],
            data_source="伊起牛",
            task_mode="data_only",
        )
        tasks = FileManager.load_project_metadata(project)["group_tasks"]
        farms = [
            {
                "task_id": task["task_id"],
                "code": task["farm_code"],
                "name": task["farm_name"],
            }
            for task in tasks
        ]
        worker = MultiFarmTaskWorker(
            None,
            farms,
            project,
            data_source="伊起牛",
            full_analysis=False,
        )
        results = []
        errors = []
        worker.finished.connect(results.append)
        worker.error.connect(errors.append)

        def run_child(index, total, farm, child_path, task_id):
            if farm["code"] == "101":
                worker._stage_update(task_id, "data", "running")
                raise RuntimeError("首场模拟失败")
            return {
                "success_items": ["数据阶段"],
                "failed_items": [],
                "excel_path": None,
                "ppt_path": None,
            }

        with (
            patch.object(worker, "_acquire_batch_lease"),
            patch.object(worker, "_refresh_batch_lease"),
            patch.object(worker, "_release_batch_lease"),
            patch.object(worker, "_run_child", side_effect=run_child) as runner,
        ):
            worker.run()

        self.assertEqual(errors, [])
        self.assertEqual(runner.call_count, 2)
        self.assertEqual(len(results), 1)
        self.assertEqual(
            [item["farm_code"] for item in results[0]["failed"]],
            ["101"],
        )
        self.assertEqual(
            [item["farm_code"] for item in results[0]["completed"]],
            ["102"],
        )
        failed_task = FileManager._group_task_store(project).get_task(
            tasks[0]["task_id"]
        )
        self.assertEqual(
            failed_task["stages"]["data"]["status"],
            "failed",
        )
        self.assertEqual(
            failed_task["stages"]["data"]["error"],
            "首场模拟失败",
        )

    def test_boundary_memory_pressure_stops_batch_and_preserves_completed(self):
        project = FileManager.create_group_project(
            Path(self.temporary_dir.name),
            [
                {"code": "201", "name": "已完成牧场"},
                {"code": "202", "name": "待重试牧场"},
                {"code": "203", "name": "未开始牧场"},
            ],
            data_source="伊起牛",
            task_mode="data_only",
        )
        tasks = FileManager.load_project_metadata(project)["group_tasks"]
        farms = [
            {
                "task_id": task["task_id"],
                "code": task["farm_code"],
                "name": task["farm_name"],
            }
            for task in tasks
        ]
        snapshots = iter(
            [
                MemorySnapshot(16 * GIB, 8 * GIB, "test", 0),
                MemorySnapshot(16 * GIB, int(0.5 * GIB), "test", 0),
            ]
        )
        guard = AdaptiveMemoryGuard(
            provider=lambda: next(snapshots),
            config=MemoryGuardConfig(
                boundary_floor_bytes=1 * GIB,
                boundary_fraction=0,
                boundary_cap_bytes=1 * GIB,
            ),
        )
        worker = MultiFarmTaskWorker(
            None,
            farms,
            project,
            data_source="伊起牛",
            full_analysis=False,
            memory_guard=guard,
        )
        results = []
        worker.finished.connect(results.append)

        with (
            patch.object(worker, "_acquire_batch_lease"),
            patch.object(worker, "_refresh_batch_lease"),
            patch.object(worker, "_release_batch_lease"),
            patch.object(
                worker,
                "_run_child",
                return_value={
                    "success_items": ["数据阶段"],
                    "failed_items": [],
                    "excel_path": None,
                    "ppt_path": None,
                },
            ) as runner,
        ):
            worker.run()

        self.assertEqual(runner.call_count, 1)
        self.assertEqual(
            [item["farm_code"] for item in results[0]["completed"]],
            ["201"],
        )
        self.assertEqual(
            [item["farm_code"] for item in results[0]["failed"]],
            ["202"],
        )
        self.assertTrue(results[0]["failed"][0]["memory_pressure"])
        self.assertTrue(results[0]["paused_for_memory"])
        self.assertTrue(results[0]["resume_available"])
        self.assertIn(
            "重新点击继续处理",
            results[0]["memory_pause_reason"],
        )
        store = FileManager._group_task_store(project)
        self.assertEqual(store.get_task(tasks[0]["task_id"])["status"], "completed")
        self.assertEqual(
            store.get_task(tasks[1]["task_id"])["status"],
            "interrupted",
        )
        self.assertEqual(store.get_task(tasks[2]["task_id"])["status"], "pending")

    def test_full_analysis_is_serial_and_failure_continues_to_next_farm(self):
        project = FileManager.create_group_project(
            Path(self.temporary_dir.name),
            [
                {"code": "301", "name": "首场失败"},
                {"code": "302", "name": "后续成功"},
            ],
            data_source="伊起牛",
            task_mode="analysis",
        )
        tasks = FileManager.load_project_metadata(project)["group_tasks"]
        farms = [
            {
                "task_id": task["task_id"],
                "code": task["farm_code"],
                "name": task["farm_name"],
            }
            for task in tasks
        ]
        worker = MultiFarmTaskWorker(
            None,
            farms,
            project,
            data_source="伊起牛",
            full_analysis=True,
        )
        events = []
        active_count = 0
        maximum_active_count = 0
        finished_results = []
        worker_errors = []
        worker.sub_task_done.connect(
            lambda task_id, success: events.append(
                ("done", task_id, success)
            )
        )
        worker.finished.connect(finished_results.append)
        worker.error.connect(worker_errors.append)

        def run_child(index, total, farm, child_path, task_id):
            nonlocal active_count, maximum_active_count
            active_count += 1
            maximum_active_count = max(maximum_active_count, active_count)
            events.append(("start", farm["code"]))
            try:
                if farm["code"] == "301":
                    raise RuntimeError("首场分析模拟失败")
                return {
                    "success_items": ["分析阶段", "单场Excel"],
                    "failed_items": [],
                    "excel_path": str(
                        child_path / "reports" / "单场报告.xlsx"
                    ),
                    "ppt_path": None,
                }
            finally:
                events.append(("end", farm["code"]))
                active_count -= 1

        with (
            patch.object(worker, "_acquire_batch_lease"),
            patch.object(worker, "_refresh_batch_lease"),
            patch.object(worker, "_release_batch_lease"),
            patch.object(worker, "_check_memory_boundary"),
            patch.object(worker, "_run_child", side_effect=run_child) as runner,
            patch(
                "core.group_report.GroupExcelReportGenerator"
            ) as group_excel_generator,
        ):
            worker.run()

        self.assertEqual(worker_errors, [])
        self.assertEqual(runner.call_count, 2)
        self.assertEqual(maximum_active_count, 1)
        self.assertEqual(
            events,
            [
                ("start", "301"),
                ("end", "301"),
                ("done", tasks[0]["task_id"], False),
                ("start", "302"),
                ("end", "302"),
                ("done", tasks[1]["task_id"], True),
            ],
        )
        self.assertEqual(len(finished_results), 1)
        result = finished_results[0]
        self.assertTrue(result["full_analysis"])
        self.assertEqual(
            [item["farm_code"] for item in result["failed"]],
            ["301"],
        )
        self.assertEqual(
            [item["farm_code"] for item in result["completed"]],
            ["302"],
        )
        group_excel_generator.assert_not_called()

    def test_batch_lease_lifecycle_uses_background_heartbeat_once(self):
        store = MagicMock()
        store.get_selection_revision.return_value = 9
        store.acquire_run_lease.return_value = {
            "lease_token": "batch-token",
            "selection_revision": 9,
            "current_selection_revision": 9,
            "selection_is_current": True,
        }
        with (
            patch.object(
                FileManager,
                "_group_task_store",
                return_value=store,
            ),
            patch(
                "gui.multi_farm_task_worker.GroupLeaseHeartbeat"
            ) as heartbeat_type,
        ):
            self.worker._acquire_batch_lease()
            self.worker._refresh_batch_lease()
            self.worker._release_batch_lease()
            self.worker._release_batch_lease()

        heartbeat_type.assert_called_once_with(
            store,
            store.acquire_run_lease.return_value,
            lease_seconds=600,
        )
        heartbeat = heartbeat_type.return_value
        heartbeat.start.assert_called_once_with()
        heartbeat.check.assert_called_once_with()
        heartbeat.stop.assert_called_once_with(
            timeout=30,
            release=True,
        )
        store.mark_stale.assert_called_once()
        store.release_run_lease.assert_not_called()


if __name__ == "__main__":
    unittest.main()
