from __future__ import annotations

import unittest

from core.matching.scope_policy import (
    individual_mating_restriction_reason,
)


class IndividualMatingScopePolicyTests(unittest.TestCase):
    def test_single_farm_and_group_child_are_allowed(self):
        self.assertEqual(
            individual_mating_restriction_reason(
                is_group_project=False,
                is_merged_project=False,
                farm_count=1,
            ),
            "",
        )

    def test_group_parent_is_rejected_with_actionable_message(self):
        reason = individual_mating_restriction_reason(
            is_group_project=True,
            is_merged_project=False,
            farm_count=8,
        )

        self.assertIn("不执行个体选配", reason)
        self.assertIn("单牧场子项目", reason)
        self.assertIn("备选公牛和冻精库存不同", reason)

    def test_legacy_multi_farm_merge_is_rejected_for_every_source(self):
        reason = individual_mating_restriction_reason(
            is_group_project=False,
            is_merged_project=True,
            farm_count=2,
        )

        self.assertIn("仅支持单个牧场", reason)
        self.assertIn("多牧场合并项目", reason)

    def test_inconsistent_multi_farm_metadata_is_still_rejected(self):
        reason = individual_mating_restriction_reason(
            is_group_project=False,
            is_merged_project=False,
            farm_count=2,
        )

        self.assertTrue(reason)


if __name__ == "__main__":
    unittest.main()
