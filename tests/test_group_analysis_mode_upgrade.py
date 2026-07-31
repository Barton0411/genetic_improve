from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from utils.file_manager import FileManager


class GroupAnalysisModeUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temporary_dir.name)

    def tearDown(self):
        self.temporary_dir.cleanup()

    @staticmethod
    def _raw_metadata(project: Path) -> dict:
        return json.loads(
            (project / "project_metadata.json").read_text(encoding="utf-8")
        )

    def _create_data_group(self, *, herd: bool = True) -> Path:
        return FileManager.create_group_project(
            self.base_path,
            [
                {"code": "1001", "name": "一号牧场"},
                {"code": "1002", "name": "二号牧场"},
            ],
            data_source="慧牧云",
            task_mode="data_only",
            dataset_selection={
                "herd": herd,
                "breeding": not herd,
            },
        )

    def test_upgrade_preserves_data_and_enables_pending_analysis_stages(self):
        project = self._create_data_group()
        store = FileManager._group_task_store(project)
        tasks = store.list_tasks()
        for offset, task in enumerate(tasks, 1):
            store.update_stage(
                task["task_id"],
                "data",
                status="completed",
                output_path=(
                    f"standardized_data/processed_cow_data_{offset}.xlsx"
                ),
                detail_count=offset * 100,
            )
        data_stages_before = {
            task["task_id"]: dict(task["stages"]["data"])
            for task in store.list_tasks()
        }

        raw = self._raw_metadata(project)
        raw["group_results"] = {
            "status": "current",
            "excel_path": "reports/旧汇总.xlsx",
        }
        FileManager._write_json_atomic(
            project / "project_metadata.json",
            raw,
        )

        metadata = FileManager.ensure_group_analysis_mode(project)

        self.assertEqual(metadata["task_mode"], "analysis")
        self.assertEqual(
            metadata["required_stages"],
            ["data", "analysis", "child_excel"],
        )
        self.assertFalse(metadata["all_tasks_complete"])
        self.assertEqual(
            metadata["analysis_mode_upgrade"]["state"],
            "ready",
        )

        raw = self._raw_metadata(project)
        self.assertEqual(raw["group_results"]["status"], "stale")
        self.assertIn("stale_at", raw["group_results"])
        self.assertTrue(
            all(
                task["required_stages"]
                == ["data", "analysis", "child_excel"]
                for task in raw["group_tasks"]
            )
        )

        upgraded = store.list_tasks()
        for offset, task in enumerate(upgraded, 1):
            self.assertEqual(task["status"], "pending")
            self.assertEqual(
                task["stages"]["data"],
                data_stages_before[task["task_id"]],
            )
            self.assertEqual(
                task["stages"]["data"]["status"],
                "completed",
            )
            self.assertTrue(task["stages"]["data"]["required"])
            self.assertEqual(
                task["stages"]["data"]["detail_count"],
                offset * 100,
            )
            for stage in ("analysis", "child_excel"):
                self.assertTrue(task["stages"][stage]["required"])
                self.assertEqual(
                    task["stages"][stage]["status"],
                    "pending",
                )
                self.assertEqual(task["stages"][stage]["progress"], 0)

        # 成功返回前必须释放升级租约，后续批处理可立即取得新租约。
        lease = store.acquire_run_lease(
            "test-after-upgrade",
            run_kind="test",
            lease_seconds=30,
        )
        self.assertIsNotNone(lease)
        self.assertTrue(store.release_run_lease(lease["lease_token"]))

    def test_breeding_only_group_is_rejected_without_mutation(self):
        project = self._create_data_group(herd=False)
        before_metadata = self._raw_metadata(project)
        store = FileManager._group_task_store(project)
        before_tasks = store.list_tasks()

        with self.assertRaisesRegex(
            ValueError,
            "批量分析必须选择牛群/系谱数据",
        ):
            FileManager.ensure_group_analysis_mode(project)

        self.assertEqual(self._raw_metadata(project), before_metadata)
        after_tasks = store.list_tasks()
        self.assertEqual(
            [
                (
                    task["stages"]["analysis"]["required"],
                    task["stages"]["analysis"]["status"],
                    task["stages"]["child_excel"]["required"],
                    task["stages"]["child_excel"]["status"],
                )
                for task in after_tasks
            ],
            [
                (
                    task["stages"]["analysis"]["required"],
                    task["stages"]["analysis"]["status"],
                    task["stages"]["child_excel"]["required"],
                    task["stages"]["child_excel"]["status"],
                )
                for task in before_tasks
            ],
        )

    def test_active_group_lease_blocks_upgrade_without_mutation(self):
        project = self._create_data_group()
        store = FileManager._group_task_store(project)
        lease = store.acquire_run_lease(
            "other-worker",
            run_kind="multi_farm_batch",
            lease_seconds=60,
        )
        self.assertIsNotNone(lease)
        before_metadata = self._raw_metadata(project)

        try:
            with self.assertRaisesRegex(
                RuntimeError,
                "正在处理或生成汇总报告",
            ):
                FileManager.ensure_group_analysis_mode(project)
        finally:
            store.release_run_lease(lease["lease_token"])

        self.assertEqual(self._raw_metadata(project), before_metadata)
        for task in store.list_tasks():
            self.assertFalse(task["stages"]["analysis"]["required"])
            self.assertEqual(
                task["stages"]["analysis"]["status"],
                "skipped",
            )

    def test_upgrade_recovers_after_sqlite_was_committed_before_json(self):
        project = self._create_data_group()
        store = FileManager._group_task_store(project)
        for task in store.list_tasks():
            store.update_stage(
                task["task_id"],
                "data",
                status="completed",
                detail_count=25,
            )

        # 模拟进程在 SQLite 原子升级成功、父 JSON 最终提交前退出。
        lease = store.acquire_run_lease(
            "simulated-crash",
            run_kind="group_analysis_mode_upgrade",
            lease_seconds=60,
        )
        self.assertIsNotNone(lease)
        store.set_required_stages_for_all(
            ("data", "analysis", "child_excel"),
            lease_token=lease["lease_token"],
        )
        store.release_run_lease(lease["lease_token"])
        self.assertEqual(
            self._raw_metadata(project)["task_mode"],
            "data_only",
        )

        metadata = FileManager.ensure_group_analysis_mode(project)

        self.assertEqual(metadata["task_mode"], "analysis")
        self.assertFalse(metadata["all_tasks_complete"])
        for task in metadata["group_tasks"]:
            self.assertEqual(
                task["stages"]["data"]["status"],
                "completed",
            )
            self.assertEqual(
                task["stages"]["analysis"]["status"],
                "pending",
            )
            self.assertEqual(
                task["stages"]["child_excel"]["status"],
                "pending",
            )

    def test_repeated_upgrade_does_not_reset_completed_analysis_or_report(self):
        project = self._create_data_group()
        store = FileManager._group_task_store(project)
        for task in store.list_tasks():
            store.update_stage(task["task_id"], "data", status="completed")

        FileManager.ensure_group_analysis_mode(project)
        for task in store.list_tasks():
            store.update_stage(
                task["task_id"],
                "analysis",
                status="completed",
                output_path="analysis_results",
            )
            store.update_stage(
                task["task_id"],
                "child_excel",
                status="completed",
                output_path="reports/单场.xlsx",
            )

        raw = self._raw_metadata(project)
        raw["group_results"] = {
            "status": "current",
            "excel_path": "reports/新汇总.xlsx",
        }
        FileManager._write_json_atomic(
            project / "project_metadata.json",
            raw,
        )
        attempts_before = {
            task["task_id"]: {
                stage: task["stages"][stage]["attempt"]
                for stage in ("data", "analysis", "child_excel")
            }
            for task in store.list_tasks()
        }

        metadata = FileManager.ensure_group_analysis_mode(project)

        self.assertTrue(metadata["all_tasks_complete"])
        self.assertEqual(
            self._raw_metadata(project)["group_results"]["status"],
            "current",
        )
        for task in store.list_tasks():
            self.assertEqual(task["status"], "completed")
            self.assertEqual(
                {
                    stage: task["stages"][stage]["attempt"]
                    for stage in ("data", "analysis", "child_excel")
                },
                attempts_before[task["task_id"]],
            )


if __name__ == "__main__":
    unittest.main()
