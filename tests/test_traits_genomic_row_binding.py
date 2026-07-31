from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
from pandas.testing import assert_series_equal

from core.breeding_calc.traits_calculation import TraitsCalculation


class TraitsGenomicRowBindingTests(unittest.TestCase):
    def _run_update(
        self,
        pedigree: pd.DataFrame,
        genomic: pd.DataFrame,
    ):
        calculation = TraitsCalculation()
        saved = {}

        def capture_save(frame, _path, apply_formatting=False):
            saved["frame"] = frame.copy(deep=True)
            saved["apply_formatting"] = apply_formatting
            return True

        calculation.save_results_with_retry = Mock(side_effect=capture_save)
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            genomic_path = root / "processed_genomic_data.xlsx"
            genomic.to_excel(genomic_path, index=False)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                success = calculation.update_genomic_data(
                    root / "unused_pedigree.xlsx",
                    genomic_path,
                    root / "output.xlsx",
                    pedigree_df=pedigree,
                )

        return calculation, success, saved, stdout.getvalue()

    def test_preserves_row_binding_and_skips_blank_ids(self):
        pedigree = pd.DataFrame(
            {
                "cow_id": [123, "00123", "", None],
                "sire": ["S1", "S2", "S3", "S4"],
                "dam": ["D1", "D2", "D3", "D4"],
                "牧场编号": ["F1", "F1", "F2", "F2"],
                "NM$_score": [1.0, 2.0, 3.0, 4.0],
            }
        )
        original = pedigree.copy(deep=True)
        genomic = pd.DataFrame(
            {
                # 前两行规范化后同为 123，且性状相同，可确定性去重。
                "cow_id": [123.0, "123.0", "00123", None],
                "NM$": [500, "500.0", 700, 999],
            }
        )

        calculation, success, saved, output = self._run_update(
            pedigree,
            genomic,
        )

        self.assertTrue(success)
        self.assertIsNone(calculation._last_genomic_error)
        result = saved["frame"]
        self.assertEqual(len(result), len(original))
        assert_series_equal(result["cow_id"], original["cow_id"])
        assert_series_equal(result["sire"], original["sire"])
        assert_series_equal(result["dam"], original["dam"])
        assert_series_equal(result["牧场编号"], original["牧场编号"])

        self.assertEqual(float(result.loc[0, "NM$_score"]), 500.0)
        self.assertEqual(float(result.loc[1, "NM$_score"]), 700.0)
        self.assertEqual(result.loc[0, "NM$_score_source"], "G")
        self.assertEqual(result.loc[1, "NM$_score_source"], "G")

        # 空牛号不会互相命中。
        self.assertEqual(
            result.loc[2:3, "NM$_score"].tolist(),
            original.loc[2:3, "NM$_score"].tolist(),
        )
        self.assertEqual(
            result.loc[2:3, "NM$_score_source"].tolist(),
            ["P", "P"],
        )
        self.assertEqual(
            result["genomic_traits_count"].tolist(),
            [1, 1, 0, 0],
        )

        # 运行日志只允许出现聚合数量，不打印任何实际牛号。
        self.assertNotIn("00123", output)

    def test_duplicate_pedigree_ids_fail_before_mutation_or_save(self):
        pedigree = pd.DataFrame(
            {
                "cow_id": ["same-cow", "same-cow"],
                "sire": ["S1", "S2"],
                "NM$_score": [1.0, 2.0],
            }
        )
        original = pedigree.copy(deep=True)
        genomic = pd.DataFrame(
            {
                "cow_id": ["same-cow"],
                "NM$": [500],
            }
        )

        calculation, success, saved, output = self._run_update(
            pedigree,
            genomic,
        )

        self.assertFalse(success)
        self.assertEqual(saved, {})
        self.assertIn("系谱数据中存在", calculation._last_genomic_error)
        self.assertIn("牛号重复", calculation._last_genomic_error)
        self.assertNotIn("same-cow", calculation._last_genomic_error)
        self.assertNotIn("same-cow", output)
        self.assertNotIn("NM$_score_source", pedigree.columns)
        assert_series_equal(pedigree["cow_id"], original["cow_id"])
        assert_series_equal(pedigree["sire"], original["sire"])

    def test_conflicting_normalized_genomic_duplicates_fail_without_mutation(self):
        secret_cow_id = "99887766"
        pedigree = pd.DataFrame(
            {
                "cow_id": [secret_cow_id],
                "sire": ["S1"],
                "NM$_score": [12.0],
            }
        )
        original = pedigree.copy(deep=True)
        genomic = pd.DataFrame(
            {
                # Excel 数字和文本形式规范化后是同一牛号，但值冲突。
                "cow_id": [99887766.0, "99887766.0"],
                "NM$": [500, 600],
            }
        )

        calculation, success, saved, output = self._run_update(
            pedigree,
            genomic,
        )

        self.assertFalse(success)
        self.assertEqual(saved, {})
        self.assertIn("重复且性状值冲突", calculation._last_genomic_error)
        self.assertNotIn(secret_cow_id, calculation._last_genomic_error)
        self.assertNotIn(secret_cow_id, output)
        self.assertNotIn("NM$_score_source", pedigree.columns)
        assert_series_equal(pedigree["cow_id"], original["cow_id"])
        assert_series_equal(pedigree["sire"], original["sire"])
        assert_series_equal(pedigree["NM$_score"], original["NM$_score"])

    def test_leading_zero_identifier_does_not_collapse_into_numeric_identifier(self):
        pedigree = pd.DataFrame(
            {
                "cow_id": ["00123", 123],
                "sire": ["S1", "S2"],
                "NM$_score": [1.0, 2.0],
            }
        )
        genomic = pd.DataFrame(
            {
                "cow_id": ["00123", "123.0"],
                "NM$": [111, 222],
            }
        )

        _, success, saved, _ = self._run_update(pedigree, genomic)

        self.assertTrue(success)
        result = saved["frame"]
        self.assertEqual(
            [float(value) for value in result["NM$_score"]],
            [111.0, 222.0],
        )
        self.assertEqual(result["cow_id"].tolist(), ["00123", 123])


if __name__ == "__main__":
    unittest.main()
