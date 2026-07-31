from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import xlsxwriter

from core.breeding_calc.traits_calculation import TraitsCalculation
from scripts.acceptance_formula_checks import validate_cow_formulas
from scripts.validate_multi_farm_acceptance import (
    ResultBuilder,
    _validate_formula_integrity,
)


def _write_table(path: Path, headers, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(path))
    worksheet = workbook.add_worksheet("Sheet1")
    worksheet.write_row(0, 0, list(headers))
    for index, row in enumerate(rows, start=1):
        worksheet.write_row(index, 0, list(row))
    workbook.close()


def _write_formula_fixture(
    root: Path,
    *,
    trait: str,
    trait_rows,
    index_rows,
    final_trait_rows=None,
) -> Path:
    child = root / "child"
    analysis = child / "analysis_results"
    _write_table(
        analysis
        / "processed_cow_data_key_traits_scores_pedigree.xlsx",
        [
            "cow_id",
            f"sire_{trait}",
            f"mgs_{trait}",
            f"mmgs_{trait}",
            f"{trait}_score",
        ],
        trait_rows,
    )
    _write_table(
        analysis / "processed_cow_data_key_traits_final.xlsx",
        [
            "cow_id",
            f"sire_{trait}",
            f"mgs_{trait}",
            f"mmgs_{trait}",
            f"{trait}_score",
            f"{trait}_score_source",
        ],
        [
            [*row, "P"]
            for row in (
                trait_rows
                if final_trait_rows is None
                else final_trait_rows
            )
        ],
    )
    _write_table(
        analysis / "processed_index_cow_index_scores.xlsx",
        ["cow_id", "NM$_score", "NM$权重_index"],
        index_rows,
    )
    return child


class AcceptanceFormulaChecksTests(unittest.TestCase):
    @staticmethod
    def _defaults(trait: str):
        return patch(
            "scripts.acceptance_formula_checks._load_trait_defaults",
            return_value=(TraitsCalculation(), {trait: 0.0}),
        )

    @staticmethod
    def _weights():
        return patch(
            "core.breeding_calc.index_calculation."
            "IndexCalculation.load_weights",
            return_value={"NM$权重": {"NM$": 100.0}},
        )

    def test_valid_trait_and_index_formulas_pass(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            child = _write_formula_fixture(
                Path(temporary_dir),
                trait="NM$",
                trait_rows=[
                    ["secret-cow-alpha", 100, 0, 0, 50],
                    ["secret-cow-beta", 300, 0, 0, 150],
                ],
                index_rows=[
                    ["secret-cow-alpha", 50, 50],
                    ["secret-cow-beta", 150, 150],
                ],
            )
            with self._defaults("NM$"), self._weights():
                result = validate_cow_formulas(child, batch_size=1)

            self.assertTrue(result["passed"])
            self.assertEqual(result["trait"]["checked_cells"], 4)
            self.assertEqual(result["index"]["checked_cells"], 2)
            self.assertEqual(result["trait"]["mismatch_cells"], 0)
            self.assertEqual(result["index"]["mismatch_cells"], 0)

    def test_swapped_scores_between_two_cows_are_detected_without_ids(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            child = _write_formula_fixture(
                Path(temporary_dir),
                trait="NM$",
                trait_rows=[
                    ["secret-cow-alpha", 100, 0, 0, 50],
                    ["secret-cow-beta", 300, 0, 0, 150],
                ],
                # 只篡改正式发布文件：两牛得分互换；行数、牛号集合和
                # 数值集合仍完全一致，普通聚合对账无法发现。
                final_trait_rows=[
                    ["secret-cow-alpha", 100, 0, 0, 150],
                    ["secret-cow-beta", 300, 0, 0, 50],
                ],
                index_rows=[
                    ["secret-cow-alpha", 150, 150],
                    ["secret-cow-beta", 50, 50],
                ],
            )
            with self._defaults("NM$"), self._weights():
                result = validate_cow_formulas(child)

            self.assertFalse(result["passed"])
            self.assertEqual(result["trait"]["mismatch_cells"], 2)
            self.assertEqual(result["trait"]["mismatch_rows"], 2)
            serialized = json.dumps(result, ensure_ascii=False)
            self.assertNotIn("secret-cow-alpha", serialized)
            self.assertNotIn("secret-cow-beta", serialized)

    def test_decimal_scale_change_00625_to_625_is_detected(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            child = _write_formula_fixture(
                Path(temporary_dir),
                trait="PROT%",
                trait_rows=[
                    ["secret-cow-percent", 0.125, 0, 0, 0.0625],
                ],
                final_trait_rows=[
                    # 0.5 * 0.125 = 0.0625，被错误放大成 6.25。
                    ["secret-cow-percent", 0.125, 0, 0, 6.25],
                ],
                index_rows=[["secret-cow-percent", 50, 50]],
            )
            with self._defaults("PROT%"), self._weights():
                result = validate_cow_formulas(child)

            self.assertFalse(result["passed"])
            self.assertEqual(result["trait"]["mismatch_cells"], 1)
            self.assertEqual(result["trait"]["mismatch_rows"], 1)
            self.assertNotIn(
                "secret-cow-percent",
                json.dumps(result, ensure_ascii=False),
            )

    def test_wrong_index_value_is_detected_without_ids(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            child = _write_formula_fixture(
                Path(temporary_dir),
                trait="NM$",
                trait_rows=[
                    ["secret-cow-index", 100, 0, 0, 50],
                ],
                index_rows=[
                    # (50 / TRAIT_SD['NM$']) * 100 = 50。
                    ["secret-cow-index", 50, 999],
                ],
            )
            with self._defaults("NM$"), self._weights():
                result = validate_cow_formulas(child)

            self.assertFalse(result["passed"])
            self.assertEqual(result["trait"]["mismatch_cells"], 0)
            self.assertEqual(result["index"]["mismatch_cells"], 1)
            self.assertEqual(result["index"]["mismatch_rows"], 1)
            self.assertNotIn(
                "secret-cow-index",
                json.dumps(result, ensure_ascii=False),
            )

    def test_validator_wiring_records_only_counts_and_fingerprints(self):
        formula_result = {
            "trait": {
                "checked_rows": 2,
                "checked_cells": 2,
                "checked_traits": 1,
                "mismatch_rows": 2,
                "mismatch_cells": 2,
                "mismatch_fingerprint": {"digest": "a" * 64},
                "configuration_fingerprint": "b" * 64,
                "passed": False,
            },
            "index": {
                "checked_rows": 2,
                "checked_cells": 2,
                "checked_indexes": 1,
                "mismatch_rows": 0,
                "mismatch_cells": 0,
                "mismatch_fingerprint": {"digest": "c" * 64},
                "configuration_fingerprint": "d" * 64,
                "passed": True,
            },
            "passed": False,
        }
        with tempfile.TemporaryDirectory() as temporary_dir:
            result = ResultBuilder(Path(temporary_dir))
            with patch(
                "scripts.validate_multi_farm_acceptance."
                "validate_cow_formulas",
                return_value=formula_result,
            ):
                _validate_formula_integrity(
                    [
                        {
                            "farm_code": "opaque-farm",
                            "farm_name": "测试牧场",
                            "child_path": Path(temporary_dir) / "child",
                        }
                    ],
                    result,
                )

        self.assertEqual(len(result.lineage_rows), 1)
        self.assertEqual(result.lineage_rows[0]["lineage"], "cow_formula")
        self.assertEqual(result.issues[0].code, "cow_trait_formula_mismatch")
        serialized = json.dumps(
            {
                "lineage": result.lineage_rows,
                "issues": [
                    issue.__dict__ for issue in result.issues
                ],
            },
            ensure_ascii=False,
        )
        self.assertNotIn("secret-cow", serialized)
        self.assertIn("a" * 64, serialized)


if __name__ == "__main__":
    unittest.main()
