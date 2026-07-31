import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd
from pandas.testing import assert_frame_equal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.auto_analysis_runner import (  # noqa: E402
    DEFECT_GENES,
    _analyze_candidate_pairs,
    _analyze_mated_pairs,
    _collect_required_bulls,
)
from core.inbreeding.analysis_scope import (  # noqa: E402
    STANDARDIZED_BULL_ID_COLUMN,
    build_inbreeding_analysis_scope,
)
from core.inbreeding.inbreeding_page import InbreedingPage  # noqa: E402


class _FakePedigree:
    def standardize_animal_id(self, animal_id, animal_type):
        text = str(animal_id).strip()
        return {
            "NAAB-A": "REG-A",
            "REG-A": "REG-A",
            "NAAB-B": "REG-B",
        }.get(text, text)

    def _is_naab_format(self, animal_id):
        return str(animal_id).startswith("NAAB-")


class _UiHarness:
    defect_genes = DEFECT_GENES

    def update_progress(self, *_args, **_kwargs):
        return None

    def analyze_gene_safety(self, cow_genes, bull_genes):
        return InbreedingPage.analyze_gene_safety(self, cow_genes, bull_genes)


class InbreedingAnalysisScopeTests(unittest.TestCase):
    def setUp(self):
        self.cows = pd.DataFrame(
            [
                {
                    "cow_id": "DAIRY-IN",
                    "sire": "SIRE-1",
                    "breed": "荷斯坦",
                    "sex": "母",
                    "是否在场": "是",
                },
                {
                    "cow_id": "DAIRY-LEFT",
                    "sire": "SIRE-2",
                    "breed": "中国荷斯坦",
                    "sex": "母",
                    "是否在场": "否",
                },
                {
                    "cow_id": "BEEF-IN",
                    "sire": "SIRE-3",
                    "breed": "安格斯",
                    "sex": "母",
                    "是否在场": "是",
                },
                {
                    "cow_id": "DAIRY-MALE",
                    "sire": "SIRE-4",
                    "breed": "荷斯坦",
                    "sex": "公",
                    "是否在场": "是",
                },
            ]
        )
        self.breeding = pd.DataFrame(
            [
                {"耳号": "DAIRY-IN", "父号": "SIRE-1", "冻精编号": "MATED-1"},
                {"耳号": "DAIRY-LEFT", "父号": "SIRE-2", "冻精编号": "MATED-2"},
                {"耳号": "BEEF-IN", "父号": "SIRE-3", "冻精编号": "MATED-3"},
                {"耳号": "DAIRY-MALE", "父号": "SIRE-4", "冻精编号": "MATED-4"},
                {"耳号": "NOT-IN-COW-FILE", "父号": "SIRE-X", "冻精编号": "MATED-X"},
            ]
        )
        self.bulls = pd.DataFrame(
            [
                {"bull_id": "NAAB-A", "支数": 10, "semen_type": "常规"},
                {"bull_id": "REG-A", "支数": 20, "semen_type": "性控"},
                {"bull_id": "NAAB-B", "支数": 30, "semen_type": "常规"},
            ]
        )
        self.pedigree = _FakePedigree()

    def _write_project(self, root: Path):
        data_dir = root / "standardized_data"
        data_dir.mkdir(parents=True)
        self.cows.to_excel(data_dir / "processed_cow_data.xlsx", index=False)
        self.breeding.to_excel(data_dir / "processed_breeding_data.xlsx", index=False)
        self.bulls.to_excel(data_dir / "processed_bull_data.xlsx", index=False)

    def test_candidate_scope_excludes_beef_males_and_off_farm_cows(self):
        scope = build_inbreeding_analysis_scope(
            "candidate",
            self.cows,
            candidate_bull_df=self.bulls,
            standardize_bull_id=lambda value: self.pedigree.standardize_animal_id(
                value, "bull"
            ),
        )

        self.assertEqual(set(scope.cows["cow_id"]), {"DAIRY-IN"})

    def test_mated_scope_keeps_off_farm_history_and_excludes_non_dairy_records(self):
        scope = build_inbreeding_analysis_scope(
            "mated",
            self.cows,
            breeding_df=self.breeding,
        )

        self.assertEqual(
            set(scope.breeding_records["耳号"]),
            {"DAIRY-IN", "DAIRY-LEFT"},
        )
        self.assertIn("DAIRY-LEFT", set(scope.breeding_records["耳号"]))

    def test_mated_scope_matches_excel_numeric_text_without_losing_leading_zeroes(self):
        cows = pd.DataFrame(
            [
                {
                    "cow_id": 123,
                    "breed": "荷斯坦",
                    "sex": "母",
                    "是否在场": "是",
                },
                {
                    "cow_id": "00124",
                    "breed": "荷斯坦",
                    "sex": "母",
                    "是否在场": "是",
                },
            ]
        )
        breeding = pd.DataFrame(
            [
                {"耳号": "123.0", "冻精编号": "MATED-1"},
                {"耳号": "00124.0", "冻精编号": "MATED-2"},
            ]
        )

        scope = build_inbreeding_analysis_scope(
            "mated",
            cows,
            breeding_df=breeding,
        )

        self.assertEqual(len(scope.breeding_records), 2)

    def test_candidate_bulls_deduplicate_after_standardization_without_mutation(self):
        original = self.bulls.copy(deep=True)

        scope = build_inbreeding_analysis_scope(
            "candidate",
            self.cows,
            candidate_bull_df=self.bulls,
            standardize_bull_id=lambda value: self.pedigree.standardize_animal_id(
                value, "bull"
            ),
        )

        self.assertEqual(
            list(scope.candidate_bulls[STANDARDIZED_BULL_ID_COLUMN]),
            ["REG-A", "REG-B"],
        )
        assert_frame_equal(self.bulls, original)
        self.assertNotIn(STANDARDIZED_BULL_ID_COLUMN, self.bulls.columns)

    def test_auto_and_ui_use_identical_candidate_and_mated_sets(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            self._write_project(project_path)
            harness = _UiHarness()

            with mock.patch(
                "core.data.update_manager.get_pedigree_db",
                return_value=self.pedigree,
            ):
                auto_candidate_bulls, _ = _collect_required_bulls(
                    "candidate", project_path, self.pedigree
                )
                ui_candidate_bulls, _ = InbreedingPage.collect_required_bulls(
                    harness, "candidate", project_path
                )
                auto_mated_bulls, _ = _collect_required_bulls(
                    "mated", project_path, self.pedigree
                )
                ui_mated_bulls, _ = InbreedingPage.collect_required_bulls(
                    harness, "mated", project_path
                )
                auto_candidate = _analyze_candidate_pairs(
                    project_path, {}, self.pedigree
                )
                ui_candidate = InbreedingPage.analyze_candidate_pairs(
                    harness, project_path, {}
                )
                auto_mated = _analyze_mated_pairs(
                    project_path, {}, self.pedigree
                )
                ui_mated = InbreedingPage.analyze_mated_pairs(
                    harness, project_path, {}
                )

        candidate_key = lambda row: (row["母牛号"], row["备选公牛号"])
        mated_key = lambda row: (row["母牛号"], row["配种公牛号"])
        self.assertEqual(auto_candidate_bulls, ui_candidate_bulls)
        self.assertEqual(auto_mated_bulls, ui_mated_bulls)
        self.assertEqual(
            {candidate_key(row) for row in auto_candidate},
            {candidate_key(row) for row in ui_candidate},
        )
        self.assertEqual(
            {mated_key(row) for row in auto_mated},
            {mated_key(row) for row in ui_mated},
        )
        self.assertEqual(
            {candidate_key(row) for row in auto_candidate},
            {("DAIRY-IN", "REG-A"), ("DAIRY-IN", "REG-B")},
        )
        self.assertEqual(
            {mated_key(row) for row in auto_mated},
            {("DAIRY-IN", "MATED-1"), ("DAIRY-LEFT", "MATED-2")},
        )


if __name__ == "__main__":
    unittest.main()
