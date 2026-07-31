from __future__ import annotations

import unittest
from contextlib import redirect_stdout
from io import StringIO

import pandas as pd

from core.data.processor import preprocess_cow_data


class PreprocessCowDuplicateLineageTests(unittest.TestCase):
    @staticmethod
    def _run(source: pd.DataFrame) -> pd.DataFrame:
        with redirect_stdout(StringIO()):
            return preprocess_cow_data(
                source.copy(deep=True),
                source_system="伊起牛",
            )

    def test_lineage_is_rebuilt_from_the_retained_duplicate_record(self):
        source = pd.DataFrame(
            [
                {
                    "耳号": "DAM001",
                    "母亲号": "GRAND_RETAINED",
                    "出生日期": "2020-01-01",
                    "性别": "母",
                    "是否在场": "是",
                },
                {
                    "耳号": "DAM001",
                    "母亲号": "GRAND_DISCARDED",
                    "出生日期": "2021-01-01",
                    "性别": "母",
                    "是否在场": "否",
                },
                {
                    "耳号": "GRAND_RETAINED",
                    "母亲号": pd.NA,
                    "出生日期": "2010-01-01",
                    "性别": "母",
                    "是否在场": "是",
                },
                {
                    "耳号": "GRAND_DISCARDED",
                    "母亲号": pd.NA,
                    "出生日期": "2011-01-01",
                    "性别": "母",
                    "是否在场": "是",
                },
                {
                    "耳号": "CHILD001",
                    "母亲号": "DAM001",
                    "出生日期": "2023-01-01",
                    "性别": "母",
                    "是否在场": "是",
                },
            ]
        )

        first = self._run(source)
        second = self._run(source)

        retained_dam = first.loc[first["cow_id"] == "DAM001"].iloc[0]
        child = first.loc[first["cow_id"] == "CHILD001"].iloc[0]

        self.assertEqual(retained_dam["dam"], "GRAND_RETAINED")
        self.assertEqual(child["dam"], "DAM001")
        self.assertEqual(child["birth_date_dam"], pd.Timestamp("2020-01-01"))
        self.assertEqual(child["mgd"], "GRAND_RETAINED")
        self.assertEqual(child["birth_date_mgd"], pd.Timestamp("2010-01-01"))
        pd.testing.assert_frame_equal(first, second)

    def test_fully_tied_duplicates_keep_the_first_input_row(self):
        source = pd.DataFrame(
            [
                {
                    "耳号": "TIE001",
                    "母亲号": "FIRST_DAM",
                    "出生日期": pd.NaT,
                    "性别": "母",
                    "是否在场": "是",
                },
                {
                    "耳号": "TIE001",
                    "母亲号": "SECOND_DAM",
                    "出生日期": pd.NaT,
                    "性别": "母",
                    "是否在场": "是",
                },
            ]
        )

        first = self._run(source)
        second = self._run(source)

        self.assertEqual(first.iloc[0]["dam"], "FIRST_DAM")
        pd.testing.assert_frame_equal(first, second)


if __name__ == "__main__":
    unittest.main()
