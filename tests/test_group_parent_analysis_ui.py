from __future__ import annotations

import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gui.main_window import MainWindow  # noqa: E402


class _NavItem:
    def __init__(self, text: str):
        self._text = text

    def text(self) -> str:
        return self._text


class _NavList:
    def __init__(self, text: str):
        self._item = _NavItem(text)

    def item(self, _index: int):
        return self._item


def _navigation_harness(feature_name: str):
    return SimpleNamespace(
        is_group_project=True,
        merged_farms=[{"code": "001"}, {"code": "002"}],
        nav_list=_NavList(feature_name),
        content_stack=MagicMock(),
        update_nav_selected_style=MagicMock(),
    )


def _full_report_harness(project_path: Path):
    farm_selection_page = SimpleNamespace(
        group_worker=None,
        continue_group_project=MagicMock(),
    )
    return SimpleNamespace(
        selected_project_path=project_path,
        is_group_project=True,
        farm_selection_page=farm_selection_page,
        group_feature_worker=None,
        _group_batch_is_running=MagicMock(return_value=False),
        _load_project_metadata=MagicMock(),
    )


class GroupParentAnalysisNavigationTests(unittest.TestCase):
    def test_analysis_entries_only_open_their_parameter_pages(self):
        expected_entries = {
            "关键育种性状分析": 3,
            "牛只指数计算排名": 4,
            "近交系数及隐性基因分析": 5,
        }

        for feature_name, page_index in expected_entries.items():
            with self.subTest(feature_name=feature_name):
                window = _navigation_harness(feature_name)

                with patch(
                    "gui.main_window.QMessageBox.question"
                ) as question:
                    MainWindow.on_nav_item_changed(window, 0)

                window.content_stack.setCurrentIndex.assert_called_once_with(
                    page_index
                )
                question.assert_not_called()

    def test_group_parent_individual_mating_remains_rejected(self):
        window = _navigation_harness("个体选配")

        with patch(
            "gui.main_window.QMessageBox.information"
        ) as information:
            MainWindow.on_nav_item_changed(window, 0)

        window.content_stack.setCurrentIndex.assert_called_once_with(1)
        information.assert_called_once()
        self.assertIn(
            "不执行个体选配",
            information.call_args.args[2],
        )


class GroupAutomaticGenerationTests(unittest.TestCase):
    def setUp(self):
        self.project_path = Path("/tmp/group-parent-analysis")
        self.metadata = {
            "project_type": "multi_farm_group",
            "task_mode": "data_only",
            "dataset_selection": {"herd": True, "breeding": True},
            "group_tasks": [
                {
                    "task_id": "task-a",
                    "farm_name": "牧场A",
                    "included_in_summary": True,
                },
                {
                    "task_id": "task-b",
                    "farm_name": "牧场B",
                    "included_in_summary": True,
                },
            ],
        }

    def test_automatic_generation_upgrades_and_starts_full_group_flow(self):
        window = _full_report_harness(self.project_path)
        call_order = []
        window._load_project_metadata.side_effect = (
            lambda: call_order.append("reload")
        )
        window.farm_selection_page.continue_group_project.side_effect = (
            lambda path: call_order.append(("continue", path))
        )

        with (
            patch(
                "gui.main_window.FileManager.load_project_metadata",
                return_value=self.metadata,
            ),
            patch(
                "gui.main_window.FileManager.ensure_group_analysis_mode",
                side_effect=lambda path: call_order.append(("ensure", path)),
            ) as ensure_mode,
            patch("gui.main_window.QMessageBox.critical") as critical,
        ):
            MainWindow._start_group_full_report(window)

        ensure_mode.assert_called_once_with(self.project_path)
        window._load_project_metadata.assert_called_once_with()
        (
            window.farm_selection_page.continue_group_project
            .assert_called_once_with(self.project_path)
        )
        self.assertEqual(
            call_order,
            [
                ("ensure", self.project_path),
                "reload",
                ("continue", self.project_path),
            ],
        )
        critical.assert_not_called()

    def test_group_excel_button_starts_full_flow_when_summary_not_ready(self):
        window = SimpleNamespace(
            selected_project_path=self.project_path,
            is_group_project=True,
            _start_group_full_report=MagicMock(),
        )

        with patch(
            "gui.main_window.FileManager.get_group_summary_readiness",
            return_value={"ready": False},
        ):
            MainWindow.on_generate_excel_report(window)

        window._start_group_full_report.assert_called_once_with()

    def test_missing_herd_data_does_not_upgrade_or_start(self):
        window = _full_report_harness(self.project_path)
        metadata = {
            **self.metadata,
            "dataset_selection": {"herd": False, "breeding": True},
        }

        with (
            patch(
                "gui.main_window.FileManager.load_project_metadata",
                return_value=metadata,
            ),
            patch(
                "gui.main_window.FileManager.ensure_group_analysis_mode"
            ) as ensure_mode,
            patch("gui.main_window.QMessageBox.warning") as warning,
        ):
            MainWindow._start_group_full_report(window)

        ensure_mode.assert_not_called()
        window._load_project_metadata.assert_not_called()
        (
            window.farm_selection_page.continue_group_project
            .assert_not_called()
        )
        warning.assert_called_once()


class GroupFeatureCompletionCopyTests(unittest.TestCase):
    def test_all_success_is_explicitly_labeled_completed(self):
        dialog = MagicMock()
        window = SimpleNamespace(
            _set_group_feature_dialog_close_mode=MagicMock(),
        )
        result = {
            "title": "已配公牛关键育种性状分析",
            "completed": [{"farm_name": "牧场A"}, {"farm_name": "牧场B"}],
            "skipped": [],
            "failed": [],
            "interrupted": False,
            "paused_for_memory": False,
        }

        MainWindow._on_group_feature_finished(window, dialog, result)

        dialog.title_label.setText.assert_called_once_with(
            "已配公牛关键育种性状分析（已完成）"
        )
        task_copy = dialog.set_task_info.call_args.args[0]
        self.assertIn("已完成", task_copy)
        self.assertIn("成功 2 个", task_copy)
        self.assertIn("失败 0 个", task_copy)
        (
            window._set_group_feature_dialog_close_mode
            .assert_called_once_with(dialog, button_text="已完成")
        )


if __name__ == "__main__":
    unittest.main()
