"""牧场分类和分组批量选择测试。"""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt

from api.hmy_api_client import HMYApiClient
from gui.farm_selection_page import (
    FarmSelectionPage,
    HMY_CLASSIFICATION_OPTIONS,
    group_hmy_farms,
)


class FarmClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = HMYApiClient(
            auth_token="test-only-token",
            proxy_base_url="https://api.example.test",
        )
        cls.farms = cls.client.get_farm_list()["data"]

    def test_real_hmy_farm_config_has_complete_classification_fallback(self):
        self.assertEqual(len(self.farms), 105)
        self.assertEqual(len({farm["farmCode"] for farm in self.farms}), 105)

        classified = next(
            farm
            for farm in self.farms
            if farm["farmCode"] == "1100110001"
        )
        self.assertEqual(classified["area"], "华北大区")
        self.assertEqual(classified["heat_stress"], "是")
        self.assertEqual(classified["source_mode"], "自繁")

        unmatched = next(
            farm
            for farm in self.farms
            if farm["farmCode"] == "1100310015"
        )
        for _, field in HMY_CLASSIFICATION_OPTIONS:
            self.assertEqual(unmatched[field], "其他")

    def test_each_hmy_classification_dimension_contains_every_farm_once(self):
        expected_counts = {
            "area": {
                "东北大区": 16,
                "中西部大区": 14,
                "内蒙大区": 24,
                "华北大区": 18,
                "其他": 33,
            },
            "organic_hp": {"是": 17, "否": 55, "其他": 33},
            "heat_stress": {"是": 22, "否": 50, "其他": 33},
            "source_mode": {"自繁": 54, "进口": 18, "其他": 33},
            "a2": {"是": 9, "否": 63, "其他": 33},
            "dha": {"是": 2, "否": 70, "其他": 33},
        }

        for _, field in HMY_CLASSIFICATION_OPTIONS:
            groups = group_hmy_farms(self.farms, field)
            counts = {name: len(farms) for name, farms in groups.items()}
            self.assertEqual(counts, expected_counts[field])
            grouped_codes = [
                farm["farmCode"]
                for group_farms in groups.values()
                for farm in group_farms
            ]
            self.assertEqual(len(grouped_codes), 105)
            self.assertEqual(len(set(grouped_codes)), 105)
            self.assertEqual(list(groups)[-1], "其他")

    def test_recent_youran_farms_use_classification_source_values(self):
        farms_by_code = {
            farm["farmCode"]: farm for farm in self.farms
        }
        expected = {
            "1100110065": ("华北大区", "否"),
            "1100110073": ("内蒙大区", "是"),
            "1100110074": ("华北大区", "否"),
            "1100110075": ("中西部大区", "否"),
        }

        for code, (area, dha) in expected.items():
            self.assertEqual(farms_by_code[code]["area"], area)
            self.assertEqual(farms_by_code[code]["dha"], dha)

    def test_saikexing_same_name_farms_do_not_inherit_youran_categories(self):
        farms_by_code = {
            farm["farmCode"]: farm for farm in self.farms
        }

        for code in ("1100310009", "1100310026"):
            farm = farms_by_code[code]
            for _, field in HMY_CLASSIFICATION_OPTIONS:
                self.assertEqual(
                    farm[field],
                    "其他",
                    f"{code} 的 {field} 不应继承优然同名牧场分类",
                )

    def test_group_select_and_deselect_updates_whole_current_group(self):
        group = self.farms[:3]
        visible_widgets = {
            farm["farmCode"]: MagicMock()
            for farm in group
        }
        page = SimpleNamespace(
            current_group_farms=group,
            selected_farms={},
            farm_list_items=visible_widgets,
            update_selection_ui=MagicMock(),
        )

        FarmSelectionPage.set_current_group_checked(page, True)
        self.assertEqual(
            set(page.selected_farms),
            {farm["farmCode"] for farm in group},
        )
        for widget in visible_widgets.values():
            widget.set_checked.assert_called_with(True)

        FarmSelectionPage.set_current_group_checked(page, False)
        self.assertEqual(page.selected_farms, {})
        for widget in visible_widgets.values():
            widget.set_checked.assert_called_with(False)
        self.assertEqual(page.update_selection_ui.call_count, 2)

    def test_index_weight_path_supports_git_worktree_directory_names(self):
        from core.breeding_calc.index_calculation import IndexCalculation

        project_root = Path(__file__).resolve().parents[1]
        if project_root.parent.name == ".worktrees":
            workspace_root = project_root.parent.parent
        else:
            workspace_root = project_root.parent
        expected = workspace_root / "genetic_projects" / "index_weights"

        self.assertEqual(
            IndexCalculation.get_global_weights_path(),
            expected,
        )


class FarmClassificationUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with patch("PyQt6.QtCore.QTimer.singleShot"):
            self.page = FarmSelectionPage(
                yqn_token="test-yqn-token",
                username="10075345",
            )

    def tearDown(self):
        self.page.close()
        self.page.deleteLater()

    def _set_selected_farm_type(self, value):
        for checkbox in self.page.farm_type_checkboxes:
            checkbox.blockSignals(True)
            checkbox.setChecked(checkbox.property("type_value") == value)
            checkbox.blockSignals(False)

    def test_hmy_tree_switches_dimensions_and_selects_whole_group(self):
        client = HMYApiClient(
            auth_token="test-only-token",
            proxy_base_url="https://api.example.test",
        )
        self.page.data_source = "慧牧云"
        self.page.all_farms = client.get_farm_list()["data"]
        self._set_selected_farm_type(None)

        self.page.build_region_tree()

        self.assertEqual(self.page.region_tree.topLevelItemCount(), 5)
        group_names = [
            self.page.region_tree.topLevelItem(index)
            .data(0, Qt.ItemDataRole.UserRole)["name"]
            for index in range(self.page.region_tree.topLevelItemCount())
        ]
        self.assertEqual(
            group_names,
            ["东北大区", "中西部大区", "内蒙大区", "华北大区", "其他"],
        )

        first_group = self.page.region_tree.topLevelItem(0)
        self.page.on_region_selected(first_group, 0)
        self.assertEqual(len(self.page.current_group_farms), 16)
        self.page.set_current_group_checked(True)
        self.assertEqual(len(self.page.selected_farms), 16)

        organic_index = self.page.classification_combo.findData("organic_hp")
        self.page.classification_combo.setCurrentIndex(organic_index)
        organic_groups = [
            self.page.region_tree.topLevelItem(index)
            .data(0, Qt.ItemDataRole.UserRole)["name"]
            for index in range(self.page.region_tree.topLevelItemCount())
        ]
        self.assertEqual(organic_groups, ["是", "否", "其他"])

    def test_yqn_big_area_and_region_are_both_selectable_groups(self):
        self.page.data_source = "伊起牛"
        self._set_selected_farm_type("社会奶源")
        self.page.all_farms = [
            {
                "farmCode": "1",
                "name": "牧场1",
                "area": "东部大区",
                "region": "京津区域",
                "farmType": "社会奶源",
                "isAvailable": 1,
            },
            {
                "farmCode": "2",
                "name": "牧场2",
                "area": "东部大区",
                "region": "京津区域",
                "farmType": "社会奶源",
                "isAvailable": 1,
            },
            {
                "farmCode": "3",
                "name": "牧场3",
                "area": "东部大区",
                "region": "唐山区域",
                "farmType": "社会奶源",
                "isAvailable": 1,
            },
            {
                "farmCode": "4",
                "name": "牧场4",
                "area": None,
                "region": None,
                "farmType": "社会奶源",
                "isAvailable": 1,
            },
        ]

        self.page.build_region_tree()
        east = self.page.region_tree.topLevelItem(0)
        self.page.on_region_selected(east, 0)
        self.assertEqual(len(self.page.current_group_farms), 3)
        self.page.set_current_group_checked(True)
        self.assertEqual(set(self.page.selected_farms), {"1", "2", "3"})

        jingjin = east.child(0)
        self.page.on_region_selected(jingjin, 0)
        self.assertEqual(len(self.page.current_group_farms), 2)
        self.page.set_current_group_checked(False)
        self.assertEqual(set(self.page.selected_farms), {"3"})

        other = self.page.region_tree.topLevelItem(1)
        self.assertEqual(
            other.data(0, Qt.ItemDataRole.UserRole)["name"],
            "其他",
        )
        self.page.on_region_selected(other, 0)
        self.page.set_current_group_checked(True)
        self.assertEqual(set(self.page.selected_farms), {"3", "4"})


if __name__ == "__main__":
    unittest.main()
