"""慧牧云 API 牛群与配种数据转换器。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

import pandas as pd


class HMYDataConverter:
    """将慧牧云 API 牛群和配种字段转换为现有导入格式。"""

    SEX_ENUM_MAPPING = {
        "0": "母",
        "0.0": "母",
        "母": "母",
        "female": "母",
        "1": "公",
        "1.0": "公",
        "公": "公",
        "male": "公",
    }
    ACTIVE_ENUM_MAPPING = {
        "1": "是",
        "1.0": "是",
        "是": "是",
        "true": "是",
        "yes": "是",
        "active": "是",
        "0": "否",
        "0.0": "否",
        "否": "否",
        "false": "否",
        "no": "否",
        "inactive": "否",
    }
    EMPTY_ENUM_VALUES = {"", "nan", "none", "null", "nat", "<na>"}

    FIELDS_NEED_PREFIX = ("cowId", "dam")
    BREEDING_FIELDS_NEED_PREFIX = ("cowId",)
    API_FARM_CODE_COLUMN = "API farmcode"
    FARM_NUMBER_COLUMN = "牧场编号"
    FARM_NAME_COLUMN = "牧场名称"
    FARM_NAME_PATTERN = re.compile(r"^(?P<number>\d{7})(?P<name>.+)$")

    FIELD_MAPPING = {
        "cowId": "耳号",
        "birthDate": "生日",
        "breed": "品种",
        "calvingDate": "产犊日期",
        "dam": "母号",
        "dim": "泌乳天数",
        "farmCode": API_FARM_CODE_COLUMN,
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

    BREEDING_FIELD_MAPPING = {
        "cowId": "耳号",
        "eventDate": "配种日期",
        "siren": "冻精编号",
        "farmCode": API_FARM_CODE_COLUMN,
    }

    BREEDING_OUTPUT_COLUMNS = [
        API_FARM_CODE_COLUMN,
        FARM_NAME_COLUMN,
        FARM_NUMBER_COLUMN,
        "耳号",
        "配种日期",
        "冻精编号",
        "冻精类型",
    ]

    @staticmethod
    def _is_valid_id(value) -> bool:
        if value is None:
            return False
        text = str(value).strip()
        return bool(text) and text.lower() not in {"nan", "none", "null"}

    @classmethod
    def _normalize_enum_value(
        cls,
        value,
        mapping: dict[str, str],
        *,
        allow_boolean: bool,
    ) -> tuple[str, bool]:
        """规范化接口枚举，返回（规范值，是否为未知非空值）。"""
        if value is None:
            return "", False
        try:
            if bool(pd.isna(value)):
                return "", False
        except (TypeError, ValueError):
            pass
        if isinstance(value, bool) and not allow_boolean:
            return "", True
        if isinstance(value, bool):
            text = "1" if value else "0"
        else:
            text = str(value).strip()
        token = text.casefold()
        if token in cls.EMPTY_ENUM_VALUES:
            return "", False
        normalized = mapping.get(token)
        if normalized is None:
            return "", True
        return normalized, False

    @classmethod
    def _normalize_herd_enums(cls, frame: pd.DataFrame) -> pd.DataFrame:
        """在写入 Excel 前校验并规范化慧牧云牛群枚举。"""
        enum_fields = (
            ("sex", cls.SEX_ENUM_MAPPING, False),
            ("isAct", cls.ACTIVE_ENUM_MAPPING, True),
        )
        unknown_counts: dict[str, int] = {}
        normalized_columns: dict[str, list[str]] = {}
        for field, mapping, allow_boolean in enum_fields:
            if field not in frame.columns:
                continue
            normalized_values = []
            unknown_count = 0
            for value in frame[field]:
                normalized, is_unknown = cls._normalize_enum_value(
                    value,
                    mapping,
                    allow_boolean=allow_boolean,
                )
                normalized_values.append(normalized)
                unknown_count += int(is_unknown)
            normalized_columns[field] = normalized_values
            if unknown_count:
                unknown_counts[field] = unknown_count

        if unknown_counts:
            details = "、".join(
                f"{field} 字段 {unknown_counts[field]} 条"
                for field in ("sex", "isAct")
                if field in unknown_counts
            )
            raise ValueError(
                "慧牧云牛群接口包含无法识别的非空枚举值："
                + details
            )

        result = frame.copy()
        for field, values in normalized_columns.items():
            result[field] = values
        return result

    @classmethod
    def split_farm_name(cls, value) -> tuple[str, str]:
        """把接口牧场名拆为七位牧场编号和不带编号的牧场名称。"""
        if not cls._is_valid_id(value):
            return "", ""
        text = str(value).strip()
        match = cls.FARM_NAME_PATTERN.fullmatch(text)
        if not match:
            return "", text
        return match.group("number"), match.group("name").strip()

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
    def normalize_semen_type_flag(cls, value) -> str:
        """仅在接口明确返回性控标记时转换，缺失时不猜测。"""
        if value is None:
            return "未知"
        text = str(value).strip().lower()
        if text in {"true", "1", "1.0", "是", "性控", "性控冻精"}:
            return "性控冻精"
        if text in {"false", "0", "0.0", "否", "普通", "普通冻精", "常规"}:
            return "普通冻精"
        return "未知"

    @classmethod
    def add_breeding_farm_prefix(
        cls,
        records: List[dict],
        farm_code: str,
    ) -> List[dict]:
        """多牧场时只给配种记录牛号加接口牧场编码前缀。"""
        prefixed = []
        for source in records:
            record = dict(source)
            record["farmCode"] = str(farm_code).strip()
            for field in cls.BREEDING_FIELDS_NEED_PREFIX:
                value = record.get(field)
                if cls._is_valid_id(value):
                    record[field] = f"{farm_code}{str(value).strip()}"
            prefixed.append(record)
        return prefixed

    @classmethod
    def merge_breeding_records(
        cls,
        all_api_data: list,
        force_prefix: bool = False,
    ) -> dict:
        """合并接口配种记录，多牧场时给牛号添加牧场编码前缀。"""
        merged = []
        add_prefix = force_prefix or len(all_api_data) > 1
        for farm_code, api_data in all_api_data:
            records = api_data.get("data") or []
            if add_prefix:
                normalized = cls.add_breeding_farm_prefix(
                    records, str(farm_code)
                )
            else:
                normalized = [
                    dict(record, farmCode=str(farm_code).strip())
                    for record in records
                ]
            merged.extend(normalized)
        return {"code": 200, "count": len(merged), "data": merged}

    @classmethod
    def convert_herd_to_excel(cls, api_data: dict, output_path: Path) -> Path:
        records = api_data.get("data") or []
        if not records:
            raise ValueError("慧牧云接口返回的牛群数据为空")

        frame = cls._normalize_herd_enums(
            pd.DataFrame(records)
        ).rename(columns=cls.FIELD_MAPPING)
        if cls.API_FARM_CODE_COLUMN not in frame.columns:
            frame[cls.API_FARM_CODE_COLUMN] = ""

        farm_names = (
            frame.pop("farmName")
            if "farmName" in frame.columns
            else pd.Series("", index=frame.index, dtype=object)
        )
        identities = farm_names.map(cls.split_farm_name)
        frame[cls.FARM_NUMBER_COLUMN] = [
            number for number, _ in identities
        ]
        frame[cls.FARM_NAME_COLUMN] = [
            name for _, name in identities
        ]

        id_columns = [
            "耳号",
            "母号",
            "父号",
            "外祖父",
            "外曾外祖父",
            cls.API_FARM_CODE_COLUMN,
            cls.FARM_NUMBER_COLUMN,
        ]
        for column in id_columns:
            if column in frame.columns:
                frame[column] = frame[column].astype(str).str.strip()
                frame[column] = frame[column].replace(["nan", "None", "null"], "")

        for column in ["生日", "产犊日期"]:
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column], errors="coerce")

        if "耳号" in frame.columns:
            frame = frame[frame["耳号"].notna() & (frame["耳号"] != "")]

        identity_columns = [
            cls.API_FARM_CODE_COLUMN,
            cls.FARM_NAME_COLUMN,
            cls.FARM_NUMBER_COLUMN,
        ]
        other_columns = [
            column for column in frame.columns if column not in identity_columns
        ]
        frame = frame[identity_columns + other_columns]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_excel(output_path, index=False)
        return output_path

    @classmethod
    def convert_breeding_records_to_excel(
        cls,
        api_data: dict,
        output_path: Path,
    ) -> Path:
        """把慧牧云接口配种记录转换为现有标准化器可识别的 Excel。"""
        records = api_data.get("data") or []
        if not records:
            raise ValueError("慧牧云接口返回的配种记录为空")

        frame = pd.DataFrame(records).rename(
            columns=cls.BREEDING_FIELD_MAPPING
        )
        required = ("耳号", "配种日期", "冻精编号")
        missing_columns = [
            column for column in required if column not in frame.columns
        ]
        if missing_columns:
            raise ValueError(
                "慧牧云配种接口缺少字段："
                + "、".join(missing_columns)
            )

        if cls.API_FARM_CODE_COLUMN not in frame.columns:
            frame[cls.API_FARM_CODE_COLUMN] = ""
        farm_names = (
            frame.pop("farmName")
            if "farmName" in frame.columns
            else pd.Series("", index=frame.index, dtype=object)
        )
        identities = farm_names.map(cls.split_farm_name)
        frame[cls.FARM_NUMBER_COLUMN] = [
            number for number, _ in identities
        ]
        frame[cls.FARM_NAME_COLUMN] = [
            name for _, name in identities
        ]

        for column in (
            cls.API_FARM_CODE_COLUMN,
            cls.FARM_NUMBER_COLUMN,
            "耳号",
            "冻精编号",
        ):
            frame[column] = frame[column].astype(str).str.strip()
            frame[column] = frame[column].replace(
                ["nan", "None", "null"], ""
            )

        invalid = (
            frame["耳号"].eq("")
            | frame["冻精编号"].eq("")
            | frame["配种日期"].isna()
            | frame["配种日期"].astype(str).str.strip().eq("")
        )
        if invalid.any():
            raise ValueError(
                f"慧牧云配种接口有 {int(invalid.sum())} 条关键字段为空"
            )

        semen_type_field = next(
            (
                field
                for field in ("isSexed", "sexed", "是否性控")
                if field in frame.columns
            ),
            None,
        )
        if semen_type_field:
            frame["冻精类型"] = frame[semen_type_field].map(
                cls.normalize_semen_type_flag
            )
        else:
            # 当前已验收的接口不返回“是否性控”。网站历史数据也证明
            # XK/551 等编号标记与该字段并非总是一致，因此不能静默猜测。
            frame["冻精类型"] = "未知"
        frame["配种日期"] = pd.to_datetime(
            frame["配种日期"], errors="coerce"
        )
        if frame["配种日期"].isna().any():
            raise ValueError("慧牧云配种接口包含无法识别的配种日期")

        frame = frame[cls.BREEDING_OUTPUT_COLUMNS]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_excel(output_path, index=False)
        return output_path
