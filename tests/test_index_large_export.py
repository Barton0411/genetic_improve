"""母牛指数结果低内存导出的回归测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from openpyxl import load_workbook

from core.breeding_calc.index_calculation import IndexCalculation


class IndexLargeExportTests(unittest.TestCase):
    def test_save_keeps_ids_and_source_styles_on_the_same_noncontiguous_row(
        self,
    ):
        frame = pd.DataFrame(
            {
                "cow_id": ["00123", "00007"],
                "sire_NM$": [10.25, 20.5],
                "sire_NM$_source": [3, 2],
                "mgs_NM$_source": [1, 1],
                "mmgs_NM$_source": [1, 1],
                "NM$_score": [8.5, 18.75],
            },
            index=[99, 3],
        )

        with tempfile.TemporaryDirectory() as temporary_dir:
            output = Path(temporary_dir) / "index-result.xlsx"
            calculator = IndexCalculation()

            with (
                patch.object(
                    pd.DataFrame,
                    "to_excel",
                    autospec=True,
                    side_effect=AssertionError("不得走 DataFrame.to_excel"),
                ) as to_excel_mock,
                patch(
                    "pandas.read_excel",
                    side_effect=AssertionError("保存不得重新读取 Excel"),
                ) as read_excel_mock,
            ):
                self.assertTrue(
                    calculator.save_results_with_retry(
                        frame,
                        output,
                        apply_formatting=True,
                    )
                )

            to_excel_mock.assert_not_called()
            read_excel_mock.assert_not_called()

            workbook = load_workbook(output, data_only=False)
            worksheet = workbook.active

            self.assertEqual(worksheet["A2"].value, "00123")
            self.assertEqual(worksheet["A2"].data_type, "s")
            self.assertEqual(worksheet["A3"].value, "00007")
            self.assertEqual(worksheet["A3"].data_type, "s")

            # 第一行来源为 3，应为黄字灰底；非连续索引 99 不得影响行号。
            self.assertEqual(worksheet["B2"].fill.fgColor.rgb, "FF808080")
            self.assertEqual(worksheet["B2"].font.color.rgb, "FFFFFF00")
            self.assertEqual(worksheet["F2"].fill.fgColor.rgb, "FF808080")
            self.assertEqual(worksheet["F2"].font.color.rgb, "FFFFFF00")

            # 第二行来源为 2，应为红字；索引 3 不得窜到第一行。
            self.assertEqual(worksheet["B3"].font.color.rgb, "FFFF0000")
            self.assertEqual(worksheet["F3"].font.color.rgb, "FFFF0000")
            workbook.close()


if __name__ == "__main__":
    unittest.main()
