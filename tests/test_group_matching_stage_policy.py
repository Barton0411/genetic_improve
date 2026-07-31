from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import xlsxwriter

from core.group_tasks.stage_policy import (
    commit_child_stage,
    validate_child_stage,
)
from utils.file_manager import FileManager


MATCHING_FILES = (
    "个体选配推荐矩阵.xlsx",
    "个体选配报告.xlsx",
    "individual_mating_report.xlsx",
)


def _write_book(path: Path, headers, rows=()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(path))
    worksheet = workbook.add_worksheet("Sheet1")
    worksheet.write_row(0, 0, list(headers))
    for row_index, row in enumerate(rows, start=1):
        worksheet.write_row(row_index, 0, list(row))
    workbook.close()


class GroupMatchingStagePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        project = FileManager.create_group_project(
            Path(self.temporary_dir.name),
            [{"code": "010", "name": "测试牧场"}],
            data_source="伊起牛",
            task_mode="analysis",
        )
        metadata = FileManager.load_project_metadata(project)
        self.task = metadata["group_tasks"][0]
        self.child = project / self.task["relative_path"]
        self.analysis_configuration = patch(
            "core.group_tasks.stage_policy._analysis_configuration",
            return_value={
                "traits": ["NM$", "TPI"],
                "weight_name": "NM$权重",
                "weight_values": {"NM$": 100.0},
                "trait_sd": {"NM$": 100.0},
                "defect_genes": ["HH1"],
                "bull_library_version": "test",
                "analysis_calendar_year": 2026,
            },
        )
        self.analysis_configuration.start()
        self.addCleanup(self.analysis_configuration.stop)
        self._write_standardized_input()
        commit_child_stage(
            self.child,
            "data",
            expected_task_id=self.task["task_id"],
            expected_farm_code="010",
        )
        self._write_required_analysis()

    def tearDown(self):
        self.temporary_dir.cleanup()

    def _write_standardized_input(self) -> None:
        _write_book(
            self.child / "raw_data" / "cow_data.xlsx",
            ["cow_id"],
            [["001"], ["002"]],
        )
        _write_book(
            self.child
            / "standardized_data"
            / "processed_cow_data.xlsx",
            ["cow_id", "牧场编号"],
            [["001", "010"], ["002", "010"]],
        )

    def _write_required_analysis(self) -> None:
        analysis = self.child / "analysis_results"
        for filename in (
            "processed_cow_data_key_traits_final.xlsx",
            "processed_index_cow_index_scores.xlsx",
        ):
            _write_book(
                analysis / filename,
                ["cow_id", "牧场编号"],
                [["001", "010"], ["002", "010"]],
            )
        for filename in (
            "关键育种性状分析结果.xlsx",
            "系谱识别分析结果.xlsx",
        ):
            _write_book(analysis / filename, ["结果"], [["ok"]])

    def _commit_analysis(self):
        return commit_child_stage(
            self.child,
            "analysis",
            expected_task_id=self.task["task_id"],
            expected_farm_code="010",
        )

    def _commit_child_excel(self):
        report = (
            self.child
            / "reports"
            / "育种分析综合报告_测试.xlsx"
        )
        _write_book(report, ["报告"], [["ok"]])
        return commit_child_stage(
            self.child,
            "child_excel",
            expected_task_id=self.task["task_id"],
            expected_farm_code="010",
            report_path=report,
        )

    def test_group_analysis_stage_excludes_matching_files_when_absent(self):
        analysis_manifest = self._commit_analysis()
        child_manifest = self._commit_child_excel()

        self.assertTrue(validate_child_stage(self.child, "analysis")["valid"])
        self.assertTrue(
            validate_child_stage(self.child, "child_excel")["valid"]
        )
        matching_paths = {
            f"analysis_results/{filename}" for filename in MATCHING_FILES
        }
        self.assertTrue(
            matching_paths.isdisjoint(
                {
                    item["relative_path"]
                    for item in analysis_manifest["outputs"]
                }
            )
        )
        self.assertTrue(
            matching_paths.isdisjoint(
                {
                    item["relative_path"]
                    for item in child_manifest["inputs"]
                }
            )
        )

    def test_group_analysis_stage_ignores_existing_matching_files(self):
        for filename in MATCHING_FILES:
            _write_book(
                self.child / "analysis_results" / filename,
                ["结果"],
                [["ok"]],
            )

        analysis_manifest = self._commit_analysis()
        child_manifest = self._commit_child_excel()
        matching_paths = {
            f"analysis_results/{filename}" for filename in MATCHING_FILES
        }

        self.assertTrue(
            matching_paths.isdisjoint(
                {
                    item["relative_path"]
                    for item in analysis_manifest["outputs"]
                }
            )
        )
        self.assertTrue(
            matching_paths.isdisjoint(
                {
                    item["relative_path"]
                    for item in child_manifest["inputs"]
                }
            )
        )
        self.assertTrue(validate_child_stage(self.child, "analysis")["valid"])
        self.assertTrue(
            validate_child_stage(self.child, "child_excel")["valid"]
        )


if __name__ == "__main__":
    unittest.main()
