import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import pandas as pd
from PyQt6.QtWidgets import QApplication

from api.hmy_api_client import HMYApiClient
from core.data.composite_farm_manager import (
    _COW_READ_DTYPES,
    _annotate_interface_breeding,
    _annotate_interface_cows,
    _read_excel,
    finalize_composite_project,
)
from core.group_tasks.stage_policy import commit_child_stage
from core.data.hmy_data_converter import HMYDataConverter
from core.data.processor import preprocess_cow_data
from gui.farm_selection_page import FarmListItem
from utils.file_manager import FileManager


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _FakeSession:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.headers = {}
        self.trust_env = True
        self.proxies = {}

    def get(self, _url, **_kwargs):
        return _FakeResponse(self.payloads.pop(0))


class HMYFarmIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_split_numbered_farm_name(self):
        self.assertEqual(
            HMYDataConverter.split_farm_name("0101001合肥陈刘牧场"),
            ("0101001", "合肥陈刘牧场"),
        )

    def test_split_unnumbered_farm_name(self):
        self.assertEqual(
            HMYDataConverter.split_farm_name("密云"),
            ("", "密云"),
        )

    def test_hmy_list_item_displays_three_separate_identity_columns(self):
        item = FarmListItem(
            {
                "farmCode": "1100110001",
                "name": "0101001合肥陈刘牧场",
            },
            show_hmy_identity=True,
        )

        self.assertEqual(item.api_farmcode_label.text(), "1100110001")
        self.assertEqual(item.farm_name_label.text(), "合肥陈刘牧场")
        self.assertEqual(item.farm_number_label.text(), "0101001")
        item.deleteLater()

    def test_hmy_list_item_leaves_missing_farm_number_blank(self):
        item = FarmListItem(
            {
                "farmCode": "1100310011",
                "name": "密云",
            },
            show_hmy_identity=True,
        )

        self.assertEqual(item.api_farmcode_label.text(), "1100310011")
        self.assertEqual(item.farm_name_label.text(), "密云")
        self.assertEqual(item.farm_number_label.text(), "")
        item.deleteLater()

    def test_excel_outputs_three_farm_identity_columns(self):
        records = [
            {
                "farmCode": "1100110001",
                "farmName": "0101001合肥陈刘牧场",
                "cowId": "123",
            },
            {
                "farmCode": "1100310011",
                "farmName": "密云",
                "cowId": "456",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "cow_data.xlsx"
            HMYDataConverter.convert_herd_to_excel(
                {"data": records},
                output,
            )
            frame = pd.read_excel(output, dtype=str, keep_default_na=False)

        self.assertEqual(
            frame.columns[:3].tolist(),
            ["API farmcode", "牧场名称", "牧场编号"],
        )
        self.assertEqual(
            frame[
                ["API farmcode", "牧场名称", "牧场编号"]
            ].to_dict(orient="records"),
            [
                {
                    "API farmcode": "1100110001",
                    "牧场名称": "合肥陈刘牧场",
                    "牧场编号": "0101001",
                },
                {
                    "API farmcode": "1100310011",
                    "牧场名称": "密云",
                    "牧场编号": "",
                },
            ],
        )

    def test_hmy_standardization_keeps_api_and_business_farm_codes(self):
        frame = pd.DataFrame(
            {
                "API farmcode": ["1100110013"],
                "牧场编号": ["0102004"],
                "牧场名称": ["肇东长青牧场"],
                "耳号": ["123"],
                "品种": ["荷斯坦"],
                "性别": ["母"],
                "父号": ["001HO00001"],
                "母号": [""],
                "外祖父": ["001HO00002"],
                "外曾外祖父": ["001HO00003"],
                "胎次": [1],
                "产犊日期": ["2026-01-01"],
                "生日": ["2023-01-01"],
                "月龄": [36],
                "配次": [0],
                "305奶量": [10000],
                "泌乳天数": [100],
                "繁育状态": ["空怀"],
                "离场日期": [""],
            }
        )

        with redirect_stdout(StringIO()):
            result = preprocess_cow_data(
                frame,
                source_system="慧牧云",
            )

        self.assertEqual(result.loc[0, "API farmcode"], "1100110013")
        self.assertEqual(result.loc[0, "牧场编号"], "0102004")
        self.assertEqual(result.loc[0, "牧场名称"], "肇东长青牧场")
        self.assertEqual(
            result.columns[-3:].tolist(),
            ["API farmcode", "牧场编号", "牧场名称"],
        )

    def test_composite_excel_read_keeps_business_number_leading_zero(self):
        frame = pd.DataFrame(
            {
                "cow_id": ["123"],
                "API farmcode": ["1100110013"],
                "牧场编号": ["0102004"],
                "牧场名称": ["肇东长青牧场"],
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "processed_cow_data.xlsx"
            frame.to_excel(output, index=False)
            result = _read_excel(output, _COW_READ_DTYPES)

        self.assertEqual(result.loc[0, "API farmcode"], "1100110013")
        self.assertEqual(result.loc[0, "牧场编号"], "0102004")

    def test_composite_annotation_uses_api_code_for_lineage(self):
        frame = pd.DataFrame(
            {
                "cow_id": ["1100110001123"],
                "API farmcode": ["1100110001"],
                "牧场编号": ["0101001"],
                "牧场名称": ["合肥陈刘牧场"],
            }
        )

        result = _annotate_interface_cows(
            frame,
            [
                {
                    "code": "1100110001",
                    "name": "0101001合肥陈刘牧场",
                }
            ],
            ids_are_prefixed=True,
            data_source="慧牧云",
        )

        self.assertEqual(result.loc[0, "farm_code"], "1100110001")
        self.assertEqual(result.loc[0, "API farmcode"], "1100110001")
        self.assertEqual(result.loc[0, "牧场编号"], "0101001")
        self.assertEqual(result.loc[0, "牧场名称"], "合肥陈刘牧场")

    def test_single_hmy_child_ignores_business_number_as_api_lineage(self):
        farm = FileManager._normalize_farm(
            {
                "code": "1100110013",
                "name": "0102004肇东长青牧场",
            },
            "慧牧云",
        )
        frame = pd.DataFrame(
            {
                "cow_id": ["123", "456"],
                "牧场编号": ["0102004", "0102004"],
                "牧场名称": ["肇东长青牧场", "肇东长青牧场"],
            }
        )

        result = _annotate_interface_cows(
            frame,
            [farm],
            ids_are_prefixed=False,
            data_source="慧牧云",
        )

        self.assertEqual(
            result["farm_code"].tolist(),
            ["1100110013", "1100110013"],
        )
        self.assertEqual(
            result["API farmcode"].tolist(),
            ["1100110013", "1100110013"],
        )
        self.assertEqual(
            result["牧场编号"].tolist(),
            ["0102004", "0102004"],
        )

    def test_single_hmy_breeding_ignores_business_number_as_api_lineage(self):
        farm = FileManager._normalize_farm(
            {
                "code": "1100110013",
                "name": "0102004肇东长青牧场",
            },
            "慧牧云",
        )
        frame = pd.DataFrame(
            {
                "耳号": ["123"],
                "牧场编号": ["0102004"],
                "牧场名称": ["肇东长青牧场"],
            }
        )

        result = _annotate_interface_breeding(
            frame,
            [farm],
            ids_are_prefixed=False,
            data_source="慧牧云",
        )

        self.assertEqual(result.loc[0, "farm_code"], "1100110013")
        self.assertEqual(result.loc[0, "API farmcode"], "1100110013")
        self.assertEqual(result.loc[0, "牧场编号"], "0102004")

    def test_multi_hmy_data_without_api_lineage_is_rejected(self):
        frame = pd.DataFrame(
            {
                "cow_id": ["123", "456"],
                "牧场编号": ["0102004", "0102007"],
            }
        )
        farms = [
            {"code": "1100110013", "name": "0102004肇东长青牧场"},
            {"code": "1100110016", "name": "0102007杜蒙一心牧场"},
        ]

        with self.assertRaisesRegex(ValueError, "必须保留 API farmcode"):
            _annotate_interface_cows(
                frame,
                farms,
                ids_are_prefixed=False,
                data_source="慧牧云",
            )

    def test_explicit_mismatched_hmy_api_code_is_rejected(self):
        frame = pd.DataFrame(
            {
                "cow_id": ["123"],
                "API farmcode": ["1100119999"],
                "牧场编号": ["0102004"],
            }
        )

        with self.assertRaisesRegex(ValueError, "与当前牧场不一致"):
            _annotate_interface_cows(
                frame,
                [{"code": "1100110013", "name": "0102004肇东长青牧场"}],
                ids_are_prefixed=False,
                data_source="慧牧云",
            )

    def test_fresh_hmy_group_download_preserves_child_identity_for_commit(self):
        farm = {
            "code": "1100110013",
            "name": "0102004肇东长青牧场",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            parent = FileManager.create_group_project(
                Path(temp_dir),
                [farm],
                data_source="慧牧云",
                task_mode="data_only",
            )
            task = FileManager.load_project_metadata(parent)["group_tasks"][0]
            child = parent / task["relative_path"]
            raw_file = child / "raw_data" / "cow_data.xlsx"
            raw_file.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                {
                    "API farmcode": ["1100110013"],
                    "牧场编号": ["0102004"],
                    "牧场名称": ["肇东长青牧场"],
                    "cow_id": ["123"],
                }
            ).to_excel(raw_file, index=False)
            standardized_file = (
                child
                / "standardized_data"
                / "processed_cow_data.xlsx"
            )
            pd.DataFrame(
                {
                    "cow_id": ["123"],
                    "API farmcode": ["1100110013"],
                    "牧场编号": ["0102004"],
                    "牧场名称": ["肇东长青牧场"],
                }
            ).to_excel(standardized_file, index=False)

            finalize_composite_project(
                child,
                [FileManager._normalize_farm(farm, "慧牧云")],
                [],
                data_source="慧牧云",
                ids_are_prefixed=False,
            )
            metadata = FileManager.load_project_metadata(child)
            manifest = commit_child_stage(
                child,
                "data",
                expected_task_id=task["task_id"],
                expected_farm_code="1100110013",
            )

        self.assertEqual(metadata["project_type"], "group_child")
        self.assertEqual(metadata["group_task_id"], task["task_id"])
        self.assertEqual(metadata["group_farm_code"], "1100110013")
        self.assertEqual(manifest["task_id"], task["task_id"])

    def test_composite_annotation_accepts_normalized_group_metadata(self):
        numbered = FileManager._normalize_farm(
            {
                "code": "1100110001",
                "name": "0101001合肥陈刘牧场",
            },
            "慧牧云",
        )
        unnumbered = FileManager._normalize_farm(
            {
                "code": "1100310011",
                "name": "密云",
            },
            "慧牧云",
        )
        frame = pd.DataFrame(
            {
                "cow_id": ["1100110001123", "1100310011456"],
                "API farmcode": ["1100110001", "1100310011"],
                # 模拟旧处理中间表把 API 编码误写入业务编号的形态。
                "牧场编号": ["1100110001", "1100310011"],
                "牧场名称": ["", ""],
            }
        )

        result = _annotate_interface_cows(
            frame,
            [numbered, unnumbered],
            ids_are_prefixed=True,
            data_source="慧牧云",
        )

        self.assertEqual(
            result["API farmcode"].tolist(),
            ["1100110001", "1100310011"],
        )
        self.assertEqual(
            result["牧场编号"].tolist(),
            ["0101001", ""],
        )
        self.assertEqual(
            result["牧场名称"].tolist(),
            ["合肥陈刘牧场", "密云"],
        )

        breeding_result = _annotate_interface_breeding(
            pd.DataFrame(
                {
                    "耳号": ["1100110001123", "1100310011456"],
                    "API farmcode": ["1100110001", "1100310011"],
                }
            ),
            [numbered, unnumbered],
            ids_are_prefixed=True,
            data_source="慧牧云",
        )
        self.assertEqual(
            breeding_result["API farmcode"].tolist(),
            ["1100110001", "1100310011"],
        )
        self.assertEqual(
            breeding_result["牧场编号"].tolist(),
            ["0101001", ""],
        )
        self.assertEqual(
            breeding_result["牧场名称"].tolist(),
            ["合肥陈刘牧场", "密云"],
        )

    def test_breeding_annotation_outputs_three_farm_identity_columns(self):
        frame = pd.DataFrame(
            {
                "耳号": ["1100110001123"],
                "牧场编号": ["1100110001"],
                "牧场名称": ["合肥陈刘牧场"],
            }
        )

        result = _annotate_interface_breeding(
            frame,
            [
                {
                    "code": "1100110001",
                    "name": "0101001合肥陈刘牧场",
                }
            ],
            ids_are_prefixed=True,
            data_source="慧牧云",
        )

        self.assertEqual(result.loc[0, "farm_code"], "1100110001")
        self.assertEqual(result.loc[0, "API farmcode"], "1100110001")
        self.assertEqual(result.loc[0, "牧场编号"], "0101001")
        self.assertEqual(result.loc[0, "牧场名称"], "合肥陈刘牧场")

    def test_client_validates_code_and_propagates_farm_name(self):
        session = _FakeSession(
            [
                {
                    "count": 2,
                    "data": [
                        {
                            "farmCode": "1100110001",
                            "farmName": "0101001合肥陈刘牧场",
                            "cowId": "1",
                        }
                    ],
                },
                {
                    "count": 2,
                    "data": [
                        {
                            "farmCode": "1100110001",
                            "cowId": "2",
                        }
                    ],
                },
            ]
        )
        client = HMYApiClient(
            auth_token="test-token",
            proxy_base_url="https://example.test",
            session=session,
        )

        result = client.get_farm_herd("1100110001", page_size=1)

        self.assertEqual(result["farmName"], "0101001合肥陈刘牧场")
        self.assertEqual(
            [row["farmName"] for row in result["data"]],
            ["0101001合肥陈刘牧场", "0101001合肥陈刘牧场"],
        )

    def test_client_rejects_mismatched_farm_code(self):
        client = HMYApiClient(
            auth_token="test-token",
            proxy_base_url="https://example.test",
            session=_FakeSession(
                [
                    {
                        "count": 1,
                        "data": [
                            {
                                "farmCode": "1100119999",
                                "farmName": "错误牧场",
                            }
                        ],
                    }
                ]
            ),
        )

        with self.assertRaisesRegex(ValueError, "牧场编码与请求不一致"):
            client.get_farm_herd("1100110001", page_size=1)

    def test_client_rejects_multiple_names_for_one_farm(self):
        client = HMYApiClient(
            auth_token="test-token",
            proxy_base_url="https://example.test",
            session=_FakeSession(
                [
                    {
                        "count": 2,
                        "data": [
                            {
                                "farmCode": "1100110001",
                                "farmName": "牧场甲",
                            }
                        ],
                    },
                    {
                        "count": 2,
                        "data": [
                            {
                                "farmCode": "1100110001",
                                "farmName": "牧场乙",
                            }
                        ],
                    },
                ]
            ),
        )

        with self.assertRaisesRegex(ValueError, "多个牧场名称"):
            client.get_farm_herd("1100110001", page_size=1)


if __name__ == "__main__":
    unittest.main()
