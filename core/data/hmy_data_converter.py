"""慧牧云 API 牛群数据转换器。"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd


class HMYDataConverter:
    """将慧牧云 API 字段转换为现有慧牧云导入格式。"""

    FIELDS_NEED_PREFIX = ("cowId", "dam")

    FIELD_MAPPING = {
        "cowId": "耳号",
        "birthDate": "生日",
        "breed": "品种",
        "calvingDate": "产犊日期",
        "dam": "母号",
        "dim": "泌乳天数",
        "farmCode": "牧场编号",
        "id": "牛只ID",
        "isAct": "是否在场",
        "lac": "胎次",
        "mgs": "外祖父",
        "milk305": "305奶量2",
        "mmgs": "外曾外祖父",
        "peakMilk": "本胎次奶厅高峰产量",
        "relv": "305奶量",
        "reproStatus": "繁育状态",
        "reproStatus2": "繁育状态2",
        "sex": "性别",
        "sire": "父号",
        "tbrd": "配次",
        "age": "月龄",
    }

    @staticmethod
    def _is_valid_id(value) -> bool:
        if value is None:
            return False
        text = str(value).strip()
        return bool(text) and text.lower() not in {"nan", "none", "null"}

    @classmethod
    def add_farm_prefix(cls, records: List[dict], farm_code: str) -> List[dict]:
        """多牧场时仅给牛号和母号加站号前缀，保持公牛编号不变。"""
        prefixed = []
        for source in records:
            record = dict(source)
            record["farmCode"] = str(farm_code).strip()
            for field in cls.FIELDS_NEED_PREFIX:
                value = record.get(field)
                if cls._is_valid_id(value):
                    record[field] = f"{farm_code}{str(value).strip()}"
            prefixed.append(record)
        return prefixed

    @classmethod
    def merge_herd_data(cls, all_api_data: list) -> dict:
        merged = []
        for farm_code, api_data in all_api_data:
            records = api_data.get("data") or []
            merged.extend(cls.add_farm_prefix(records, str(farm_code)))
        return {"code": 200, "count": len(merged), "data": merged}

    @classmethod
    def convert_herd_to_excel(cls, api_data: dict, output_path: Path) -> Path:
        records = api_data.get("data") or []
        if not records:
            raise ValueError("慧牧云接口返回的牛群数据为空")

        frame = pd.DataFrame(records).rename(columns=cls.FIELD_MAPPING)

        id_columns = ["耳号", "母号", "父号", "外祖父", "外曾外祖父", "牧场编号"]
        for column in id_columns:
            if column in frame.columns:
                frame[column] = frame[column].astype(str).str.strip()
                frame[column] = frame[column].replace(["nan", "None", "null"], "")

        for column in ["生日", "产犊日期"]:
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column], errors="coerce")

        if "耳号" in frame.columns:
            frame = frame[frame["耳号"].notna() & (frame["耳号"] != "")]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_excel(output_path, index=False)
        return output_path
