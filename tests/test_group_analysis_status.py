from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QTableWidget, QWidget  # noqa: E402

from core.group_tasks.analysis_status import (  # noqa: E402
    analysis_status_tooltip,
    format_analysis_status_cells,
    resolve_child_analysis_status,
)
from gui.main_window import MainWindow  # noqa: E402


def _validation_with_outputs(*relative_paths: str) -> dict:
    return {
        "valid": True,
        "status": "valid",
        "manifest": {
            "outputs": [
                {"relative_path": relative}
                for relative in relative_paths
            ]
        },
    }


class GroupChildAnalysisStatusTests(unittest.TestCase):
    def setUp(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.child = Path(self.temporary_dir.name)
        (self.child / "standardized_data").mkdir()

    def tearDown(self):
        self.temporary_dir.cleanup()

    def _touch_input(self, name: str) -> None:
        (
            self.child / "standardized_data" / name
        ).write_bytes(b"test")

    def test_missing_optional_inputs_are_not_reported_as_unfinished(self):
        self._touch_input("processed_cow_data.xlsx")

        with (
            patch(
                "core.group_tasks.analysis_status."
                "_analysis_manifest_validation",
                return_value={
                    "valid": False,
                    "status": "manifest_missing",
                },
            ),
            patch(
                "core.group_tasks.analysis_status."
                "validate_recorded_feature_manifest",
                return_value={
                    "valid": False,
                    "status": "manifest_missing",
                },
            ),
        ):
            inventory = resolve_child_analysis_status(
                self.child,
                expected_task_id="task-1",
                expected_farm_code="farm-1",
                dataset_selection={"herd": True, "breeding": True},
            )

        self.assertEqual(inventory["applicable_count"], 3)
        self.assertEqual(inventory["pending_count"], 3)
        self.assertEqual(inventory["not_applicable_count"], 5)
        self.assertEqual(
            {item["operation"] for item in inventory["pending"]},
            {"cow_traits", "cow_index", "cow_self_inbreeding"},
        )
        self.assertNotIn(
            "bull_traits",
            {item["operation"] for item in inventory["pending"]},
        )

    def test_valid_complete_analysis_manifest_lists_all_declared_analyses(self):
        for name in (
            "processed_cow_data.xlsx",
            "processed_bull_data.xlsx",
            "processed_breeding_data.xlsx",
        ):
            self._touch_input(name)
        validation = _validation_with_outputs(
            "analysis_results/processed_cow_data_key_traits_final.xlsx",
            "analysis_results/关键育种性状分析结果.xlsx",
            "analysis_results/系谱识别分析结果.xlsx",
            "analysis_results/processed_index_cow_index_scores.xlsx",
            "analysis_results/母牛近交系数分析结果.xlsx",
            "analysis_results/processed_bull_data_key_traits.xlsx",
            "analysis_results/processed_index_bull_scores.xlsx",
            "analysis_results/备选公牛_近交系数及隐性基因分析结果_1.xlsx",
            "analysis_results/processed_mated_bull_traits.xlsx",
            "analysis_results/已配公牛_近交系数及隐性基因分析结果_1.xlsx",
        )

        with (
            patch(
                "core.group_tasks.analysis_status."
                "_analysis_manifest_validation",
                return_value=validation,
            ),
            patch(
                "core.group_tasks.analysis_status."
                "validate_recorded_feature_manifest"
            ) as feature_validation,
        ):
            inventory = resolve_child_analysis_status(
                self.child,
                expected_task_id="task-1",
                expected_farm_code="farm-1",
                dataset_selection={"herd": True, "breeding": True},
            )

        self.assertTrue(inventory["analysis_stage_valid"])
        self.assertEqual(inventory["completed_count"], 8)
        self.assertEqual(inventory["pending_count"], 0)
        self.assertEqual(inventory["not_applicable_count"], 0)
        feature_validation.assert_not_called()

    def test_partial_complete_manifest_does_not_mark_all_eight_complete(self):
        for name in (
            "processed_cow_data.xlsx",
            "processed_bull_data.xlsx",
            "processed_breeding_data.xlsx",
        ):
            self._touch_input(name)
        validation = _validation_with_outputs(
            "analysis_results/processed_cow_data_key_traits_final.xlsx",
            "analysis_results/关键育种性状分析结果.xlsx",
            "analysis_results/系谱识别分析结果.xlsx",
            "analysis_results/processed_index_cow_index_scores.xlsx",
        )

        with (
            patch(
                "core.group_tasks.analysis_status."
                "_analysis_manifest_validation",
                return_value=validation,
            ),
            patch(
                "core.group_tasks.analysis_status."
                "validate_recorded_feature_manifest",
                return_value={
                    "valid": False,
                    "status": "manifest_missing",
                },
            ),
        ):
            inventory = resolve_child_analysis_status(
                self.child,
                expected_task_id="task-1",
                expected_farm_code="farm-1",
                dataset_selection={"herd": True, "breeding": True},
            )

        self.assertEqual(
            {item["operation"] for item in inventory["completed"]},
            {"cow_traits", "cow_index"},
        )
        self.assertEqual(inventory["pending_count"], 6)

    def test_page_analysis_is_visible_without_claiming_report_stage_ready(self):
        self._touch_input("processed_cow_data.xlsx")

        def feature_validation(
            _root,
            operation,
            **_kwargs,
        ):
            return {
                "valid": operation == "cow_self_inbreeding",
                "status": (
                    "valid"
                    if operation == "cow_self_inbreeding"
                    else "manifest_missing"
                ),
            }

        with (
            patch(
                "core.group_tasks.analysis_status."
                "_analysis_manifest_validation",
                return_value={
                    "valid": False,
                    "status": "manifest_missing",
                },
            ),
            patch(
                "core.group_tasks.analysis_status."
                "validate_recorded_feature_manifest",
                side_effect=feature_validation,
            ),
        ):
            inventory = resolve_child_analysis_status(
                self.child,
                expected_task_id="task-1",
                expected_farm_code="farm-1",
                dataset_selection={"herd": True, "breeding": False},
            )

        self.assertFalse(inventory["analysis_stage_valid"])
        self.assertEqual(
            [item["operation"] for item in inventory["completed"]],
            ["cow_self_inbreeding"],
        )
        self.assertEqual(
            {item["operation"] for item in inventory["pending"]},
            {"cow_traits", "cow_index"},
        )
        self.assertEqual(
            inventory["completed"][0]["source"],
            "page_feature",
        )

    def test_cell_copy_and_tooltip_keep_required_optional_meaning(self):
        inventory = {
            "completed_count": 1,
            "applicable_count": 3,
            "completed": [
                {
                    "short_title": "母牛近交",
                    "title": "母牛近交系数及隐性基因分析",
                    "required_for_report": False,
                    "reason": "已完成",
                }
            ],
            "pending": [
                {
                    "short_title": "母牛性状",
                    "title": "在群母牛关键育种性状分析",
                    "required_for_report": True,
                    "reason": "尚无有效分析结果",
                }
            ],
            "not_applicable": [],
        }

        cells = format_analysis_status_cells(inventory)
        tooltip = analysis_status_tooltip(
            inventory["pending"],
            empty="无",
        )

        self.assertEqual(cells["progress"], "1/3")
        self.assertEqual(cells["completed"], "页面：母牛近交")
        self.assertEqual(cells["pending"], "必需：母牛性状")
        self.assertIn("完整报告必需", tooltip)


class GroupTaskManagerAnalysisColumnsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_task_manager_displays_completed_pending_and_not_applicable(self):
        parent = QWidget()
        parent.selected_project_path = Path("/tmp/group-status-ui")
        parent.is_group_project = True
        parent._load_project_metadata = MagicMock()
        parent.farm_selection_page = SimpleNamespace(
            continue_group_project=MagicMock(),
        )
        metadata = {
            "project_type": "multi_farm_group",
            "data_source": "伊起牛",
            "task_mode": "data_only",
            "dataset_selection": {"herd": True, "breeding": False},
            "group_tasks": [
                {
                    "task_id": "task-1",
                    "farm_code": "0101001",
                    "farm_number": "0101001",
                    "farm_name": "测试牧场",
                    "relative_path": "farm_projects/0101001_测试牧场",
                    "included_in_summary": True,
                    "status": "completed",
                    "progress": 100,
                    "stage": "已完成",
                    "error": "",
                    "metadata": {
                        "dataset_selection": {
                            "herd": True,
                            "breeding": False,
                        }
                    },
                    "stages": {
                        "data": {"status": "completed"},
                        "analysis": {"status": "skipped"},
                        "child_excel": {"status": "skipped"},
                    },
                }
            ],
        }
        inventory = {
            "completed": [
                {
                    "short_title": "母牛性状",
                    "title": "在群母牛关键育种性状分析",
                    "required_for_report": True,
                    "reason": "已按上次页面参数完成并通过产物校验",
                }
            ],
            "pending": [
                {
                    "short_title": "母牛指数",
                    "title": "母牛群指数排名",
                    "required_for_report": True,
                    "reason": "尚无有效分析结果",
                }
            ],
            "not_applicable": [
                {
                    "short_title": "已配公牛性状",
                    "title": "已配公牛关键育种性状分析",
                    "required_for_report": False,
                    "reason": "创建项目时未选择配种记录",
                }
            ],
            "completed_count": 1,
            "pending_count": 1,
            "not_applicable_count": 1,
            "applicable_count": 2,
        }
        captured = {}

        def capture_dialog(dialog):
            captured["table"] = dialog.findChild(QTableWidget)
            captured["summary"] = dialog.findChildren(QLabel)[0].text()
            return 0

        with (
            patch(
                "gui.main_window.FileManager.load_project_metadata",
                return_value=metadata,
            ),
            patch(
                "core.group_tasks.analysis_status."
                "resolve_child_analysis_status",
                return_value=inventory,
            ),
            patch("gui.main_window.QDialog.exec", new=capture_dialog),
        ):
            MainWindow.open_group_task_manager(parent)

        table = captured["table"]
        headers = [
            table.horizontalHeaderItem(column).text()
            for column in range(table.columnCount())
        ]
        self.assertIn("完整报告分析", headers)
        self.assertIn("已完成分析", headers)
        self.assertIn("未完成分析", headers)
        self.assertIn("按需/不适用", headers)
        self.assertEqual(
            table.item(0, headers.index("已完成分析")).text(),
            "页面：母牛性状",
        )
        self.assertEqual(
            table.item(0, headers.index("未完成分析")).text(),
            "必需：母牛指数",
        )
        self.assertEqual(
            table.item(0, headers.index("按需/不适用")).text(),
            "已配公牛性状",
        )
        self.assertIn("分析明细完成 1/2", captured["summary"])
        parent.deleteLater()


if __name__ == "__main__":
    unittest.main()
