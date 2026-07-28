import tempfile
import unittest
from pathlib import Path

import pandas as pd

from api.hmy_api_client import HMYApiClient
from core.data.composite_farm_manager import (
    _annotate_interface_breeding,
    _annotate_interface_cows,
)
from core.data.hmy_data_converter import HMYDataConverter


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
