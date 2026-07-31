from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from core.data.hmy_data_converter import HMYDataConverter
from core.data.processor import preprocess_cow_data


class HMYEnumNormalizationTests(unittest.TestCase):
    def test_known_sex_and_active_values_are_normalized(self):
        records = []
        sex_values = [
            0,
            0.0,
            "0",
            "0.0",
            "母",
            " female ",
            1,
            1.0,
            "1",
            "1.0",
            "公",
            "MALE",
            None,
            "",
            pd.NA,
            "null",
            "母",
            "female",
            0,
            1,
        ]
        active_values = [
            1,
            1.0,
            "1",
            "1.0",
            "是",
            True,
            "TRUE",
            " yes ",
            "active",
            0,
            0.0,
            "0",
            "0.0",
            "否",
            False,
            "false",
            "NO",
            "inactive",
            None,
            "",
            pd.NA,
            "null",
        ]
        for index, (sex, is_active) in enumerate(
            zip(sex_values, active_values),
            start=1,
        ):
            records.append(
                {
                    "cowId": str(index),
                    "sex": sex,
                    "isAct": is_active,
                }
            )

        with tempfile.TemporaryDirectory() as temporary_dir:
            output = Path(temporary_dir) / "cow_data.xlsx"
            HMYDataConverter.convert_herd_to_excel(
                {"data": records},
                output,
            )
            result = pd.read_excel(
                output,
                dtype=str,
                keep_default_na=False,
            )

        self.assertEqual(
            result["性别"].tolist(),
            [
                "母",
                "母",
                "母",
                "母",
                "母",
                "母",
                "公",
                "公",
                "公",
                "公",
                "公",
                "公",
                "",
                "",
                "",
                "",
                "母",
                "母",
                "母",
                "公",
            ],
        )
        self.assertEqual(
            result["是否在场"].tolist(),
            [
                "是",
                "是",
                "是",
                "是",
                "是",
                "是",
                "是",
                "是",
                "是",
                "否",
                "否",
                "否",
                "否",
                "否",
                "否",
                "否",
                "否",
                "否",
                "",
                "",
            ],
        )

    def test_boolean_sex_is_rejected_instead_of_silently_treated_as_numeric(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            output = Path(temporary_dir) / "cow_data.xlsx"
            with self.assertRaises(ValueError) as raised:
                HMYDataConverter.convert_herd_to_excel(
                    {
                        "data": [
                            {
                                "cowId": "1",
                                "sex": True,
                                "isAct": True,
                            }
                        ]
                    },
                    output,
                )

        self.assertIn("sex 字段 1 条", str(raised.exception))
        self.assertFalse(output.exists())

    def test_hmy_unknown_active_status_is_not_defaulted_to_in_herd(self):
        source = pd.DataFrame(
            {
                "耳号": ["1", "2"],
                "品种": ["荷斯坦", "荷斯坦"],
                "性别": ["母", "母"],
                "是否在场": ["", pd.NA],
                "生日": ["2024-01-01", "2024-01-02"],
                "母号": ["", ""],
            }
        )

        result = preprocess_cow_data(
            source,
            source_system="慧牧云",
        )

        self.assertEqual(result["是否在场"].tolist(), ["", ""])

    def test_unknown_nonempty_values_are_rejected_in_one_redacted_error(self):
        records = [
            {
                "cowId": "1",
                "sex": "unexpected-sex-secret",
                "isAct": "unexpected-active-secret",
            },
            {
                "cowId": "2",
                "sex": "another-sex-secret",
                "isAct": "yes",
            },
        ]

        with tempfile.TemporaryDirectory() as temporary_dir:
            output = Path(temporary_dir) / "cow_data.xlsx"
            with self.assertRaises(ValueError) as raised:
                HMYDataConverter.convert_herd_to_excel(
                    {"data": records},
                    output,
                )

            message = str(raised.exception)
            self.assertIn("sex 字段 2 条", message)
            self.assertIn("isAct 字段 1 条", message)
            self.assertNotIn("unexpected-sex-secret", message)
            self.assertNotIn("another-sex-secret", message)
            self.assertNotIn("unexpected-active-secret", message)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
