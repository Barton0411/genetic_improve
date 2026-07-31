"""慧牧云配种记录转换、合并与标准化测试。"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from core.data.hmy_data_converter import HMYDataConverter
from core.data.uploader import upload_and_standardize_breeding_data


def _record(
    farm_code: str,
    farm_name: str,
    cow_id: str,
    siren: str,
    event_date: str,
) -> dict:
    return {
        "farmCode": farm_code,
        "farmName": farm_name,
        "cowId": cow_id,
        "siren": siren,
        "eventDate": event_date,
    }


class HMYBreedingConverterTests(unittest.TestCase):
    def test_converter_outputs_identity_and_uses_explicit_semen_type(self):
        records = [
            _record(
                "1100110001",
                "0101001测试一牧",
                "1001",
                "291HO23025",
                "2026-07-01",
            ),
            _record(
                "1100110001",
                "0101001测试一牧",
                "1002",
                "XK291HO23138",
                "2026-07-02",
            ),
        ]
        records[1]["isSexed"] = True

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "breeding.xlsx"
            HMYDataConverter.convert_breeding_records_to_excel(
                {"data": records},
                output,
            )
            frame = pd.read_excel(
                output,
                dtype=str,
                keep_default_na=False,
            )

        self.assertEqual(
            list(frame.columns),
            HMYDataConverter.BREEDING_OUTPUT_COLUMNS,
        )
        self.assertEqual(
            frame["API farmcode"].tolist(),
            ["1100110001", "1100110001"],
        )
        self.assertEqual(frame["牧场编号"].tolist(), ["0101001", "0101001"])
        self.assertEqual(frame["牧场名称"].tolist(), ["测试一牧", "测试一牧"])
        self.assertEqual(
            frame["冻精类型"].tolist(),
            ["未知", "性控冻精"],
        )

    def test_multi_farm_merge_prefixes_only_cow_id(self):
        first = _record(
            "1100110001",
            "0101001测试一牧",
            "1001",
            "291HO23025",
            "2026-07-01",
        )
        second = _record(
            "1100110002",
            "0101002测试二牧",
            "1001",
            "XK291HO23138",
            "2026-07-02",
        )

        merged = HMYDataConverter.merge_breeding_records(
            [
                ("1100110001", {"data": [first]}),
                ("1100110002", {"data": [second]}),
            ]
        )["data"]

        self.assertEqual(
            [row["cowId"] for row in merged],
            ["11001100011001", "11001100021001"],
        )
        self.assertEqual(
            [row["siren"] for row in merged],
            ["291HO23025", "XK291HO23138"],
        )

    def test_converted_multi_farm_records_pass_existing_standardizer(self):
        farms = [
            ("1100110001", "0101001测试一牧", "1001", "291HO23025"),
            ("1100110002", "0101002测试二牧", "1001", "XK291HO23138"),
        ]
        all_records = [
            (
                code,
                {
                    "data": [
                        _record(
                            code,
                            name,
                            cow_id,
                            siren,
                            f"2026-07-0{index}",
                        )
                    ]
                },
            )
            for index, (code, name, cow_id, siren) in enumerate(
                farms, start=1
            )
        ]
        merged = HMYDataConverter.merge_breeding_records(all_records)

        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            raw_dir = project / "raw_data"
            standardized_dir = project / "standardized_data"
            raw_dir.mkdir()
            standardized_dir.mkdir()
            pd.DataFrame(
                {
                    "cow_id": [
                        "11001100011001",
                        "11001100021001",
                    ],
                    "sire": ["001HO10001", "001HO10002"],
                    "API farmcode": ["1100110001", "1100110002"],
                    "牧场编号": ["0101001", "0101002"],
                    "牧场名称": ["测试一牧", "测试二牧"],
                }
            ).to_excel(
                standardized_dir / "processed_cow_data.xlsx",
                index=False,
            )
            raw_breeding = raw_dir / "breeding_records.xlsx"
            HMYDataConverter.convert_breeding_records_to_excel(
                merged,
                raw_breeding,
            )

            with (
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                processed_path = upload_and_standardize_breeding_data(
                    [raw_breeding],
                    project,
                    source_system="慧牧云",
                )
            processed = pd.read_excel(
                processed_path,
                dtype=str,
                keep_default_na=False,
            )

        self.assertEqual(len(processed), 2)
        self.assertEqual(
            processed["耳号"].tolist(),
            ["11001100011001", "11001100021001"],
        )
        self.assertEqual(
            processed["API farmcode"].tolist(),
            ["1100110001", "1100110002"],
        )
        self.assertEqual(
            processed["牧场编号"].tolist(),
            ["0101001", "0101002"],
        )
        self.assertEqual(
            processed["牧场名称"].tolist(),
            ["测试一牧", "测试二牧"],
        )
        self.assertEqual(
            processed["冻精类型"].tolist(),
            ["未知", "未知"],
        )
        self.assertEqual(
            processed["冻精编号"].tolist(),
            ["291HO23025", "291HO23138"],
        )


if __name__ == "__main__":
    unittest.main()
