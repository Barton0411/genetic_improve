from __future__ import annotations

import unittest

from gui.farm_selection_page import farm_selection_action_policy


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

    def test_multiple_farms_only_allow_group_project_creation(self):
        policy = farm_selection_action_policy(32)

        self.assertTrue(policy["create_enabled"])
        self.assertFalse(policy["auto_report_enabled"])
        self.assertEqual(policy["create_text"], "创建牧场组项目")
        self.assertEqual(
            policy["auto_report_text"],
            "自动报告仅支持单牧场",
        )
        self.assertIn("最终汇总Excel", policy["auto_report_tooltip"])


if __name__ == "__main__":
    unittest.main()
