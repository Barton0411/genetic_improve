"""母牛标识符在性状和指数 Excel 链路中的回归测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from core.breeding_calc.index_calculation import IndexCalculation
from core.breeding_calc.traits_calculation import TraitsCalculation
from utils.large_excel_writer import read_excel_identifier_safe


class IdentifierSafeBreedingPipelineTests(unittest.TestCase):
    def test_index_rejects_blank_or_duplicate_cow_ids_without_exposing_them(self):
        identifiers, message = IndexCalculation.validate_cow_identifiers(
            pd.DataFrame(
                {
                    "cow_id": ["123.0", 123, "", "private-cow"],
                }
            )
        )

        self.assertIsNone(identifiers)
        self.assertIn("空牛号 1 行", message)
        self.assertIn("重复牛号 1 组/2 行", message)
        self.assertNotIn("123.0", message)
        self.assertNotIn("private-cow", message)

    def test_index_identifier_validation_preserves_leading_zeroes(self):
        identifiers, message = IndexCalculation.validate_cow_identifiers(
            pd.DataFrame({"cow_id": ["00123", 123]})
        )

        self.assertEqual(message, "")
        self.assertIsNotNone(identifiers)
        self.assertEqual(identifiers.tolist(), ["00123", "123"])

    def test_traits_fallback_and_index_result_keep_identifiers_as_text(self):
        source = pd.DataFrame(
            {
                "cow_id": ["000123", "000456"],
                "raw_dam_id": ["000001", "000002"],
                "牧场编号": ["0101001", "0101001"],
                "birth_date": ["2020-01-02", "2021-03-04"],
                "birth_date_dam": ["2016-01-02", "2017-03-04"],
                "birth_date_mgd": ["2012-01-02", "2013-03-04"],
                "NM$_score": [123.45, -6.75],
            }
        )

        with tempfile.TemporaryDirectory() as temporary_dir:
            project_path = Path(temporary_dir)
            standardized_dir = project_path / "standardized_data"
            analysis_dir = project_path / "analysis_results"
            standardized_dir.mkdir()
            analysis_dir.mkdir()

            # 模拟外部/旧版 Excel：单元格虽是文本，普通 read_excel 会把
            # 纯数字标识符推断成整数。
            source.to_excel(
                standardized_dir / "processed_cow_data.xlsx",
                index=False,
            )

            traits_calculator = TraitsCalculation()
            standardized = traits_calculator.read_data(
                project_path,
                "processed_cow_data.xlsx",
            )
            self.assertIsNotNone(standardized)
            self.assertEqual(
                standardized["cow_id"].tolist(),
                ["000123", "000456"],
            )
            self.assertEqual(
                standardized["raw_dam_id"].tolist(),
                ["000001", "000002"],
            )
            self.assertEqual(
                standardized["牧场编号"].tolist(),
                ["0101001", "0101001"],
            )
            self.assertTrue(
                pd.api.types.is_numeric_dtype(standardized["NM$_score"])
            )

            traits_path = (
                analysis_dir
                / "processed_cow_data_key_traits_scores_pedigree.xlsx"
            )
            self.assertTrue(
                traits_calculator.save_results_with_retry(
                    standardized,
                    traits_path,
                )
            )

            index_calculator = IndexCalculation()
            traits_result, complete = (
                index_calculator.check_existing_traits_results(
                    project_path,
                    ["NM$"],
                )
            )
            self.assertTrue(complete)
            self.assertEqual(
                traits_result["cow_id"].tolist(),
                ["000123", "000456"],
            )
            self.assertEqual(
                traits_result["raw_dam_id"].tolist(),
                ["000001", "000002"],
            )
            self.assertEqual(
                traits_result["牧场编号"].tolist(),
                ["0101001", "0101001"],
            )
            self.assertTrue(
                pd.api.types.is_numeric_dtype(traits_result["NM$_score"])
            )

            traits_result["NM$权重_index"] = [12.345, -0.675]
            index_path = analysis_dir / "processed_index_cow_index_scores.xlsx"
            self.assertTrue(
                index_calculator.save_results_with_retry(
                    traits_result,
                    index_path,
                )
            )
            final_result = read_excel_identifier_safe(index_path)

        self.assertEqual(final_result["cow_id"].tolist(), ["000123", "000456"])
        self.assertEqual(
            final_result["raw_dam_id"].tolist(),
            ["000001", "000002"],
        )
        self.assertEqual(
            final_result["牧场编号"].tolist(),
            ["0101001", "0101001"],
        )
        self.assertTrue(
            pd.api.types.is_numeric_dtype(final_result["NM$权重_index"])
        )


if __name__ == "__main__":
    unittest.main()
