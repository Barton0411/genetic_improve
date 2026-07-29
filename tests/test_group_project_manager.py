from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path

from utils.file_manager import FileManager


class GroupProjectManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temporary_dir.name)

    def tearDown(self):
        self.temporary_dir.cleanup()

    def test_group_project_uses_uuid_tasks_and_sqlite_state(self):
        farms = [
            {"code": "1001", "name": "接口牧场", "source_kind": "api"},
            {"code": "1001", "name": "本地同号牧场", "source_kind": "local"},
        ]
        project = FileManager.create_group_project(
            self.base_path,
            farms,
            data_source="伊起牛",
            task_mode="analysis",
        )

        self.assertTrue(
            (project / "group_store" / "group_tasks.sqlite3").is_file()
        )
        metadata = FileManager.load_project_metadata(project)
        self.assertEqual(len(metadata["group_tasks"]), 2)
        task_ids = [task["task_id"] for task in metadata["group_tasks"]]
        self.assertEqual(len(set(task_ids)), 2)
        for task_id in task_ids:
            self.assertEqual(str(uuid.UUID(task_id)), task_id)
            self.assertTrue(
                FileManager.get_group_child_path(project, task_id).is_dir()
            )
        with self.assertRaisesRegex(KeyError, "多个任务"):
            FileManager._resolve_group_task(metadata, "1001")

    def test_stage_completion_and_exclusion_are_independent(self):
        farms = [
            {"code": "2001", "name": "一场"},
            {"code": "2002", "name": "二场"},
        ]
        project = FileManager.create_group_project(
            self.base_path,
            farms,
            data_source="伊起牛",
            task_mode="analysis",
        )
        metadata = FileManager.load_project_metadata(project)
        first, second = [
            task["task_id"] for task in metadata["group_tasks"]
        ]

        for task_id in (first, second):
            for stage in ("data", "analysis", "child_excel"):
                FileManager.update_group_stage(
                    project,
                    task_id,
                    stage,
                    status="completed",
                )
        self.assertTrue(
            FileManager.load_project_metadata(project)["all_tasks_complete"]
        )

        FileManager.update_group_stage(
            project,
            second,
            "analysis",
            status="failed",
            error="模拟失败",
        )
        failed = FileManager.load_project_metadata(project)
        second_task = next(
            task for task in failed["group_tasks"]
            if task["task_id"] == second
        )
        self.assertEqual(second_task["status"], "failed")
        self.assertFalse(failed["all_tasks_complete"])

        FileManager.set_group_task_excluded(project, second, True)
        excluded = FileManager.load_project_metadata(project)
        second_task = next(
            task for task in excluded["group_tasks"]
            if task["task_id"] == second
        )
        self.assertEqual(second_task["status"], "failed")
        self.assertFalse(second_task["included_in_summary"])
        self.assertTrue(excluded["all_tasks_complete"])

        FileManager.set_group_task_excluded(project, second, False)
        included = FileManager.load_project_metadata(project)
        self.assertFalse(included["all_tasks_complete"])

    def test_data_only_project_completes_without_analysis_stages(self):
        farms = [{"code": "3001", "name": "数据场"}]
        project = FileManager.create_group_project(
            self.base_path,
            farms,
            data_source="慧牧云",
            task_mode="data_only",
        )
        task_id = FileManager.load_project_metadata(project)[
            "group_tasks"
        ][0]["task_id"]
        FileManager.update_group_stage(
            project,
            task_id,
            "data",
            status="completed",
            detail_count=123,
        )
        metadata = FileManager.load_project_metadata(project)
        self.assertTrue(metadata["all_tasks_complete"])
        task = metadata["group_tasks"][0]
        self.assertEqual(task["stages"]["analysis"]["status"], "skipped")
        self.assertEqual(task["stages"]["child_excel"]["status"], "skipped")

    def test_hmy_group_persists_three_distinct_farm_identities(self):
        farms = [
            {
                "code": "1100110001",
                "name": "0101001合肥陈刘牧场",
                "source_kind": "api",
            },
            {
                "code": "1100310011",
                "name": "密云",
                "source_kind": "api",
            },
        ]
        project = FileManager.create_group_project(
            self.base_path,
            farms,
            data_source="慧牧云",
            task_mode="data_only",
        )

        metadata = FileManager.load_project_metadata(project)
        first, second = metadata["group_tasks"]
        self.assertEqual(first["farm_code"], "1100110001")
        self.assertEqual(first["api_farmcode"], "1100110001")
        self.assertEqual(first["farm_number"], "0101001")
        self.assertEqual(first["farm_name"], "合肥陈刘牧场")
        self.assertEqual(
            first["source_farm_name"],
            "0101001合肥陈刘牧场",
        )
        self.assertEqual(second["api_farmcode"], "1100310011")
        self.assertEqual(second["farm_number"], "")
        self.assertEqual(second["farm_name"], "密云")

        child_metadata = FileManager.load_project_metadata(
            project / first["relative_path"]
        )
        child_farm = child_metadata["farms"][0]
        self.assertEqual(child_farm["code"], "1100110001")
        self.assertEqual(child_farm["api_farmcode"], "1100110001")
        self.assertEqual(child_farm["farm_number"], "0101001")
        self.assertEqual(child_farm["name"], "合肥陈刘牧场")
        self.assertEqual(
            child_farm["source_farm_name"],
            "0101001合肥陈刘牧场",
        )
        self.assertEqual(
            child_metadata["group_api_farmcode"],
            "1100110001",
        )
        self.assertEqual(child_metadata["group_farm_number"], "0101001")

        info = (project / "merged_farms.txt").read_text(encoding="utf-8")
        self.assertIn("API farmcode: 1100110001", info)
        self.assertIn("牧场编号: 0101001", info)
        self.assertIn("牧场名称: 合肥陈刘牧场", info)
        self.assertIn("API farmcode: 1100310011", info)
        self.assertIn("牧场编号: -", info)


if __name__ == "__main__":
    unittest.main()
