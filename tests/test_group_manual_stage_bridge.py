from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import xlsxwriter

from core.group_tasks.manual_stage_bridge import (
    commit_manual_group_analysis_if_ready,
    commit_manual_group_excel_if_ready,
)
from core.group_tasks.stage_policy import (
    StagePolicyError,
    commit_child_stage,
    validate_child_stage,
)
from utils.file_manager import FileManager


def _book(path: Path, headers=("cow_id",), rows=(("001",),)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(path))
    worksheet = workbook.add_worksheet("Sheet1")
    worksheet.write_row(0, 0, list(headers))
    for row_index, row in enumerate(rows, start=1):
        worksheet.write_row(row_index, 0, list(row))
    workbook.close()


class ManualGroupStageBridgeTests(unittest.TestCase):
    def _project(self, root: Path):
        project = FileManager.create_group_project(
            root,
            [{"code": "010", "name": "测试牧场"}],
            data_source="伊起牛",
            task_mode="data_only",
        )
        task = FileManager.load_project_metadata(project)["group_tasks"][0]
        child = project / task["relative_path"]
        _book(child / "raw_data" / "cow_data.xlsx")
        _book(
            child / "standardized_data" / "processed_cow_data.xlsx",
            ("cow_id", "牧场编号"),
            (("001", "010"),),
        )
        data_manifest = commit_child_stage(
            child,
            "data",
            expected_task_id=task["task_id"],
            expected_farm_code="010",
        )
        FileManager.update_group_stage(
            project,
            task["task_id"],
            "data",
            status="completed",
            artifacts={
                item["relative_path"]: str(
                    child / item["relative_path"]
                )
                for item in data_manifest["outputs"]
            },
        )
        return project, task, child

    @staticmethod
    def _analysis_outputs(child: Path) -> None:
        analysis = child / "analysis_results"
        for filename in (
            "processed_cow_data_key_traits_final.xlsx",
            "processed_index_cow_index_scores.xlsx",
        ):
            _book(
                analysis / filename,
                ("cow_id", "牧场编号"),
                (("001", "010"),),
            )
        for filename in (
            "关键育种性状分析结果.xlsx",
            "系谱识别分析结果.xlsx",
        ):
            _book(analysis / filename, ("结果",), (("完成",),))

    def test_manual_excel_commits_analysis_and_report_to_parent(self):
        with tempfile.TemporaryDirectory() as temporary_dir, patch(
            "core.group_tasks.stage_policy._analysis_configuration",
            return_value={"revision": "test"},
        ):
            project, task, child = self._project(
                Path(temporary_dir)
            )
            self._analysis_outputs(child)
            report = child / "reports" / "育种分析综合报告_测试牧场.xlsx"
            _book(report, ("报告",), (("完成",),))

            result = commit_manual_group_excel_if_ready(child, report)

            self.assertTrue(result["committed"])
            for stage in ("data", "analysis", "child_excel"):
                validation = validate_child_stage(
                    child,
                    stage,
                    expected_task_id=task["task_id"],
                    expected_farm_code="010",
                )
                self.assertTrue(validation["valid"], validation)
            parent_task = FileManager._group_task_store(project).get_task(
                task["task_id"]
            )
            self.assertEqual(
                parent_task["stages"]["analysis"]["status"],
                "completed",
            )
            self.assertEqual(
                parent_task["stages"]["child_excel"]["status"],
                "completed",
            )
            self.assertTrue(
                FileManager.get_group_summary_readiness(project)["ready"]
            )

    def test_analysis_is_not_adopted_without_valid_data_manifest(self):
        with tempfile.TemporaryDirectory() as temporary_dir, patch(
            "core.group_tasks.stage_policy._analysis_configuration",
            return_value={"revision": "test"},
        ):
            project, task, child = self._project(
                Path(temporary_dir)
            )
            self._analysis_outputs(child)
            (
                child
                / "group_store"
                / "stage_manifests"
                / "data.json"
            ).unlink()

            with self.assertRaisesRegex(StagePolicyError, "数据阶段"):
                commit_manual_group_analysis_if_ready(child)
            parent_task = FileManager._group_task_store(project).get_task(
                task["task_id"]
            )
            self.assertEqual(
                parent_task["stages"]["analysis"]["status"],
                "skipped",
            )

    def test_regular_single_project_is_not_affected(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            result = commit_manual_group_analysis_if_ready(root)
            self.assertEqual(
                result,
                {"applicable": False, "committed": False},
            )


if __name__ == "__main__":
    unittest.main()
