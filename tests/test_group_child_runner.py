from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from core.group_tasks.child_runner import (
    ANALYSIS_ARTIFACTS,
    ChildRequestError,
    execute_request,
    load_and_validate_request,
    main,
)
from utils.file_manager import FileManager


class _Signal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in self._callbacks:
            callback(*args)


def _write_xlsx(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    workbook.active.append(["牧场编号", "牛号"])
    workbook.active.append(["1001", "C001"])
    workbook.save(path)


class _FakeWorker:
    calls = []
    runtime_error = ""

    def __init__(self, api_client, farms, project_path, is_merged, **kwargs):
        self.progress = _Signal()
        self.project_path = Path(project_path)
        self.api_client = api_client
        self.farms = farms
        self.kwargs = kwargs

    def execute(self, **flags):
        type(self).calls.append(
            {
                "api_client": self.api_client,
                "farms": self.farms,
                "project_path": self.project_path,
                "kwargs": self.kwargs,
                "flags": flags,
            }
        )
        print("这条旧模块输出不能进入 JSONL 协议")
        if type(self).runtime_error:
            raise RuntimeError(type(self).runtime_error)
        self.progress.emit(45, "正在处理")
        result = {
            "failed_items": [],
            "success_items": [],
            "excel_path": None,
        }
        if flags["analysis"]:
            for relative in ANALYSIS_ARTIFACTS:
                _write_xlsx(self.project_path / relative)
        if flags["excel"]:
            report = (
                self.project_path
                / "reports"
                / "育种分析综合报告_测试.xlsx"
            )
            _write_xlsx(report)
            result["excel_path"] = str(report)
        return result


class GroupChildRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temporary_dir.name)
        farms = [{"code": "1001", "name": "测试牧场"}]
        self.parent = FileManager.create_group_project(
            self.base_path,
            farms,
            data_source="伊起牛",
            task_mode="analysis",
        )
        metadata = FileManager.load_project_metadata(self.parent)
        self.task = metadata["group_tasks"][0]
        self.child = (
            self.parent / self.task["relative_path"]
        ).resolve(strict=True)
        _write_xlsx(
            self.child
            / "standardized_data"
            / "processed_cow_data.xlsx"
        )
        self.request_path = self.base_path / "request.json"
        self._write_request()
        _FakeWorker.calls = []
        _FakeWorker.runtime_error = ""

    def tearDown(self):
        self.temporary_dir.cleanup()

    def _write_request(self, **overrides):
        payload = {
            "schema_version": 1,
            "task_id": self.task["task_id"],
            "farm_code": "1001",
            "project_path": str(self.child),
            "stages": ["analysis", "child_excel"],
        }
        payload.update(overrides)
        self.request_path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _events(output: io.StringIO):
        return [
            json.loads(line)
            for line in output.getvalue().splitlines()
            if line.strip()
        ]

    def test_runs_both_stages_without_api_client_and_outputs_only_jsonl(self):
        output = io.StringIO()
        result = execute_request(
            self.request_path,
            worker_factory=_FakeWorker,
            output_stream=output,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["completed_stages"], ["analysis", "child_excel"])
        self.assertEqual(len(_FakeWorker.calls), 2)
        self.assertTrue(
            all(call["api_client"] is None for call in _FakeWorker.calls)
        )
        self.assertEqual(
            _FakeWorker.calls[0]["flags"],
            {
                "download": False,
                "analysis": True,
                "excel": False,
                "ppt": False,
            },
        )
        self.assertTrue(
            all(
                call["kwargs"]["reliability_mode"]
                for call in _FakeWorker.calls
            )
        )

        events = self._events(output)
        self.assertEqual(events[-1]["type"], "result")
        self.assertTrue(events[-1]["success"])
        self.assertEqual(
            [event["type"] for event in events].count("stage_completed"),
            2,
        )
        self.assertNotIn("旧模块输出", output.getvalue())
        for relative in result["artifacts"]:
            self.assertFalse(Path(relative).is_absolute())
            self.assertTrue((self.child / relative).is_file())

    def test_rejects_farm_mismatch_before_worker_creation(self):
        self._write_request(farm_code="9999")
        with self.assertRaisesRegex(ChildRequestError, "父组任务不一致"):
            load_and_validate_request(self.request_path)
        self.assertEqual(_FakeWorker.calls, [])

    def test_rejects_unknown_fields_without_echoing_secret_value(self):
        self._write_request(api_token="DO-NOT-ECHO")
        output = io.StringIO()
        exit_code = main(
            [str(self.request_path)],
            worker_factory=_FakeWorker,
            output_stream=output,
        )
        self.assertEqual(exit_code, 1)
        self.assertNotIn("DO-NOT-ECHO", output.getvalue())
        self.assertIn("api_token", output.getvalue())

    def test_rejects_project_not_equal_to_parent_task_child(self):
        rogue_child = self.base_path / "rogue"
        rogue_child.mkdir()
        child_metadata = json.loads(
            (self.child / "project_metadata.json").read_text(encoding="utf-8")
        )
        child_metadata["parent_group"] = "../" + self.parent.name
        (rogue_child / "project_metadata.json").write_text(
            json.dumps(child_metadata, ensure_ascii=False),
            encoding="utf-8",
        )
        self._write_request(project_path=str(rogue_child.resolve()))
        with self.assertRaisesRegex(
            ChildRequestError,
            "project_path 与父组 task 描述不一致",
        ):
            load_and_validate_request(self.request_path)

    def test_runtime_error_is_redacted_and_returns_nonzero(self):
        _FakeWorker.runtime_error = "token=TOP-SECRET computation failed"
        output = io.StringIO()
        exit_code = main(
            [str(self.request_path)],
            worker_factory=_FakeWorker,
            output_stream=output,
        )
        self.assertEqual(exit_code, 1)
        events = self._events(output)
        self.assertEqual(events[-1]["type"], "result")
        self.assertFalse(events[-1]["success"])
        self.assertNotIn("TOP-SECRET", events[-1]["error"])
        self.assertIn("<redacted>", events[-1]["error"])


if __name__ == "__main__":
    unittest.main()
