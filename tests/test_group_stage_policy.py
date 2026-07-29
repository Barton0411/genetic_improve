from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import xlsxwriter

from core.group_tasks.stage_policy import (
    commit_child_stage,
    invalidate_stage_and_downstream,
    validate_child_stage,
)
from utils.file_manager import FileManager


def _write_book(path: Path, headers, rows=()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(path))
    worksheet = workbook.add_worksheet("Sheet1")
    worksheet.write_row(0, 0, list(headers))
    for row_index, row in enumerate(rows, start=1):
        worksheet.write_row(row_index, 0, list(row))
    workbook.close()


class GroupStagePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        project = FileManager.create_group_project(
            Path(self.temporary_dir.name),
            [{"code": "010", "name": "测试牧场"}],
            data_source="伊起牛",
            task_mode="analysis",
        )
        metadata = FileManager.load_project_metadata(project)
        self.project = project
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

    def tearDown(self):
        self.temporary_dir.cleanup()

    def _write_data(self) -> None:
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

    def _write_analysis(self, marker: str = "new") -> None:
        analysis = self.child / "analysis_results"
        for filename in (
            "processed_cow_data_key_traits_final.xlsx",
            "processed_index_cow_index_scores.xlsx",
        ):
            _write_book(
                analysis / filename,
                ["cow_id", "牧场编号", "marker"],
                [["001", "010", marker], ["002", "010", marker]],
            )
        _write_book(
            analysis / "关键育种性状分析结果.xlsx",
            ["marker"],
            [[marker]],
        )
        _write_book(
            analysis / "系谱识别分析结果.xlsx",
            ["marker"],
            [[marker]],
        )

    def _commit(self, stage: str) -> None:
        commit_child_stage(
            self.child,
            stage,
            expected_task_id=self.task["task_id"],
            expected_farm_code="010",
        )

    def test_all_three_stages_require_current_committed_manifests(self):
        self._write_data()
        self._commit("data")
        self._write_analysis()
        self._commit("analysis")
        _write_book(
            self.child / "reports" / "育种分析综合报告_测试.xlsx",
            ["报告"],
            [["ok"]],
        )
        self._commit("child_excel")

        for stage in ("data", "analysis", "child_excel"):
            self.assertTrue(
                validate_child_stage(
                    self.child,
                    stage,
                    expected_task_id=self.task["task_id"],
                    expected_farm_code="010",
                )["valid"]
            )

        _write_book(
            self.child
            / "standardized_data"
            / "processed_cow_data.xlsx",
            ["cow_id", "牧场编号"],
            [["001", "010"]],
        )
        self.assertFalse(validate_child_stage(self.child, "data")["valid"])
        self.assertFalse(
            validate_child_stage(self.child, "analysis")["valid"]
        )

    def test_manual_bull_upload_invalidates_analysis_but_not_data(self):
        self._write_data()
        self._commit("data")
        self._write_analysis()
        self._commit("analysis")

        _write_book(
            self.child
            / "standardized_data"
            / "processed_bull_data.xlsx",
            ["bull_id"],
            [["HO123"]],
        )
        _write_book(
            self.child / "raw_data" / "bull_data.xlsx",
            ["bull_id"],
            [["HO123"]],
        )

        self.assertTrue(validate_child_stage(self.child, "data")["valid"])
        analysis_validation = validate_child_stage(
            self.child,
            "analysis",
        )
        self.assertFalse(analysis_validation["valid"])
        self.assertEqual(
            analysis_validation["status"],
            "config_mismatch",
        )

    def test_child_stage_stat_verification_skips_content_hashing(self):
        self._write_data()
        self._commit("data")

        with patch(
            "core.group_tasks.stage_manifest.stream_sha256",
            side_effect=AssertionError("stat 模式不应读取文件内容"),
        ):
            validation = validate_child_stage(
                self.child,
                "data",
                verification="stat",
            )
        self.assertTrue(validation["valid"])
        self.assertTrue(validation["artifact_stats"])

    def test_retry_archives_old_outputs_and_never_reuses_optional_file(self):
        self._write_data()
        self._commit("data")
        self._write_analysis("old")
        optional = (
            self.child
            / "analysis_results"
            / "已配公牛_近交系数及隐性基因分析结果_20260729_120000.xlsx"
        )
        _write_book(optional, ["marker"], [["old"]])
        self._commit("analysis")

        archived = invalidate_stage_and_downstream(
            self.child,
            "analysis",
        )
        self.assertFalse(optional.exists())
        self.assertFalse(
            (
                self.child
                / "group_store"
                / "stage_manifests"
                / "analysis.json"
            ).exists()
        )
        self.assertTrue(
            any(path.name == optional.name for path in archived)
        )

        self._write_analysis("new")
        self._commit("analysis")
        manifest = validate_child_stage(
            self.child,
            "analysis",
        )["manifest"]
        output_names = {
            item["relative_path"] for item in manifest["outputs"]
        }
        self.assertNotIn(
            "analysis_results/" + optional.name,
            output_names,
        )


if __name__ == "__main__":
    unittest.main()
