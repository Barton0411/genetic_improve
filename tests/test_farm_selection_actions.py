from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from gui.farm_selection_page import (
    FarmSelectionPage,
    farm_selection_action_policy,
    group_dataset_selection_policy,
)


class FarmSelectionActionPolicyTests(unittest.TestCase):
    def test_no_selection_disables_both_creation_actions(self):
        policy = farm_selection_action_policy(0)

        self.assertFalse(policy["create_enabled"])
        self.assertFalse(policy["auto_report_enabled"])
        self.assertEqual(policy["create_text"], "创建牧场项目")

    def test_single_farm_keeps_auto_report_available(self):
        policy = farm_selection_action_policy(1)

        self.assertTrue(policy["create_enabled"])
        self.assertTrue(policy["auto_report_enabled"])
        self.assertEqual(
            policy["auto_report_text"],
            "创建项目并自动生成报告",
        )
        self.assertEqual(policy["auto_report_tooltip"], "")

    def test_multiple_farms_allow_group_batch_analysis(self):
        policy = farm_selection_action_policy(32)

        self.assertTrue(policy["create_enabled"])
        self.assertTrue(policy["auto_report_enabled"])
        self.assertEqual(policy["create_text"], "创建牧场组项目")
        self.assertEqual(
            policy["auto_report_text"],
            "创建牧场组并批量分析",
        )
        self.assertIn("牧场组汇总Excel", policy["auto_report_tooltip"])
        self.assertIn("不执行个体选配", policy["auto_report_tooltip"])

    def test_multi_selection_dispatches_full_group_analysis(self):
        page = MagicMock()
        page.data_source = "慧牧云"
        page.hmy_access_allowed = True
        farms = [
            {"code": "101", "name": "牧场A"},
            {"code": "102", "name": "牧场B"},
        ]
        page._build_selected_farm_specs.return_value = (farms, [])
        group_path = Path("/tmp/test-group-analysis")
        selection = {"herd": True, "breeding": False}

        with (
            patch(
                "config.settings.Settings.get_default_storage",
                return_value="/tmp",
            ),
            patch(
                "gui.farm_selection_page.FileManager.create_group_project",
                return_value=group_path,
            ) as create_group,
            patch(
                "core.data.composite_farm_manager."
                "persist_group_local_input_bundles"
            ) as persist_local,
        ):
            FarmSelectionPage._start_auto_report(
                page,
                dataset_selection=selection,
            )

        create_group.assert_called_once_with(
            Path("/tmp"),
            farms,
            data_source="慧牧云",
            task_mode="analysis",
            dataset_selection=selection,
        )
        persist_local.assert_called_once_with(group_path, farms)
        page._start_group_tasks.assert_called_once_with(
            group_path,
            farms,
            full_analysis=True,
            dataset_selection=selection,
        )

    def test_green_group_creation_allows_breeding_only_for_api_farms(self):
        page = MagicMock()
        page.data_source = "慧牧云"
        page.hmy_access_allowed = True
        farms = [
            {"code": "101", "name": "牧场A"},
            {"code": "102", "name": "牧场B"},
        ]
        page._build_selected_farm_specs.return_value = (farms, [])
        group_path = Path("/tmp/test-group-data-only")
        selection = {"herd": False, "breeding": True}

        with (
            patch(
                "config.settings.Settings.get_default_storage",
                return_value="/tmp",
            ),
            patch(
                "gui.farm_selection_page.FileManager.create_group_project",
                return_value=group_path,
            ) as create_group,
            patch(
                "core.data.composite_farm_manager."
                "persist_group_local_input_bundles"
            ) as persist_local,
        ):
            FarmSelectionPage.create_farm_project(
                page,
                dataset_selection=selection,
            )

        create_group.assert_called_once_with(
            Path("/tmp"),
            farms,
            data_source="慧牧云",
            task_mode="data_only",
            dataset_selection=selection,
        )
        persist_local.assert_called_once_with(group_path, farms)
        page._start_group_tasks.assert_called_once_with(
            group_path,
            farms,
            full_analysis=False,
            dataset_selection=selection,
        )


class GroupDatasetSelectionPolicyTests(unittest.TestCase):
    def test_missing_selection_keeps_legacy_default_of_both_datasets(self):
        policy = group_dataset_selection_policy(
            None,
            full_analysis=True,
        )

        self.assertTrue(policy["valid"])
        self.assertEqual(
            policy["selection"],
            {"herd": True, "breeding": True},
        )

    def test_malformed_persisted_selection_is_rejected(self):
        policy = group_dataset_selection_policy(
            ["herd"],
            full_analysis=False,
        )

        self.assertFalse(policy["valid"])
        self.assertIn("至少选择", policy["error"])

    def test_green_entry_accepts_either_or_both_datasets(self):
        for selection in (
            {"herd": True, "breeding": False},
            {"herd": False, "breeding": True},
            {"herd": True, "breeding": True},
        ):
            with self.subTest(selection=selection):
                self.assertTrue(
                    group_dataset_selection_policy(
                        selection,
                        full_analysis=False,
                    )["valid"]
                )

    def test_no_dataset_is_rejected(self):
        policy = group_dataset_selection_policy(
            {"herd": False, "breeding": False},
            full_analysis=False,
        )

        self.assertFalse(policy["valid"])
        self.assertIn("至少选择", policy["error"])

    def test_batch_analysis_requires_herd_data(self):
        policy = group_dataset_selection_policy(
            {"herd": False, "breeding": True},
            full_analysis=True,
        )

        self.assertFalse(policy["valid"])
        self.assertIn("必须下载牛群/系谱数据", policy["error"])

    def test_batch_analysis_without_breeding_explains_skipped_analysis(self):
        policy = group_dataset_selection_policy(
            {"herd": True, "breeding": False},
            full_analysis=True,
        )

        self.assertTrue(policy["valid"])
        self.assertIn("已配公牛性状", policy["notice"])
        self.assertIn("隐性基因分析会自动跳过", policy["notice"])

    def test_local_supplement_requires_herd_data(self):
        policy = group_dataset_selection_policy(
            {"herd": False, "breeding": True},
            full_analysis=False,
            has_local_farms=True,
        )

        self.assertFalse(policy["valid"])
        self.assertIn("本地补充牧场", policy["error"])


if __name__ == "__main__":
    unittest.main()
