"""牧场组数据集选择的规范化、校验与零记录回执。"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


DATASET_KEYS = ("herd", "breeding")
DEFAULT_DATASET_SELECTION = {
    "herd": True,
    "breeding": True,
}
BREEDING_RAW_RECEIPT = (
    Path("raw_data") / "breeding_records_receipt.json"
)
BREEDING_STANDARDIZED_RECEIPT = (
    Path("standardized_data") / "breeding_data_receipt.json"
)


class DatasetSelectionError(ValueError):
    """数据集选择不合法或与任务模式不兼容。"""


def _strict_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    raise DatasetSelectionError(f"dataset_selection.{field} 必须是布尔值")


def normalize_dataset_selection(
    value: Optional[Mapping[str, Any]] = None,
    *,
    task_mode: Optional[str] = None,
    has_local_farms: bool = False,
) -> Dict[str, bool]:
    """返回固定 ``herd/breeding`` 布尔字典。

    旧项目没有 ``dataset_selection`` 时按历史行为回退为两项全选。
    """

    if value is None:
        normalized = dict(DEFAULT_DATASET_SELECTION)
    else:
        if not isinstance(value, Mapping):
            raise DatasetSelectionError("dataset_selection 必须是字典")
        unknown = set(value) - set(DATASET_KEYS)
        if unknown:
            raise DatasetSelectionError(
                "dataset_selection 包含未知字段："
                + "、".join(sorted(str(item) for item in unknown))
            )
        missing = set(DATASET_KEYS) - set(value)
        if missing:
            raise DatasetSelectionError(
                "dataset_selection 缺少字段："
                + "、".join(sorted(missing))
            )
        normalized = {
            key: _strict_bool(value[key], key)
            for key in DATASET_KEYS
        }

    if not any(normalized.values()):
        raise DatasetSelectionError("牛群/系谱和配种记录至少选择一项")
    if task_mode is not None:
        mode = str(task_mode)
        if mode not in {"analysis", "data_only"}:
            raise DatasetSelectionError(f"不支持的牧场组任务模式：{mode}")
        if mode == "analysis" and not normalized["herd"]:
            raise DatasetSelectionError("批量分析必须选择牛群/系谱数据")
    if has_local_farms and not normalized["herd"]:
        raise DatasetSelectionError(
            "包含本地补充牧场时必须选择牛群/系谱数据"
        )
    return normalized


def metadata_dataset_selection(
    metadata: Mapping[str, Any],
    *,
    task_mode: Optional[str] = None,
    has_local_farms: bool = False,
) -> Dict[str, bool]:
    return normalize_dataset_selection(
        metadata.get("dataset_selection"),
        task_mode=task_mode,
        has_local_farms=has_local_farms,
    )


def write_empty_breeding_receipts(
    project_path: Path,
    *,
    data_source: str,
    farms: list[Mapping[str, Any]],
) -> tuple[Path, Path]:
    """原子记录“已请求但返回 0 条”，避免复用旧配种文件。"""

    from utils.file_manager import FileManager

    root = Path(project_path)
    payload = {
        "schema_version": 1,
        "dataset": "breeding",
        "status": "empty",
        "record_count": 0,
        "data_source": str(data_source),
        "farms": [
            {
                "code": str(farm.get("code") or farm.get("farmCode") or ""),
                "name": str(farm.get("name") or ""),
            }
            for farm in farms
        ],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    raw_receipt = root / BREEDING_RAW_RECEIPT
    standardized_receipt = root / BREEDING_STANDARDIZED_RECEIPT
    FileManager._write_json_atomic(raw_receipt, payload)
    FileManager._write_json_atomic(standardized_receipt, payload)
    return raw_receipt, standardized_receipt


def validate_empty_breeding_receipt(path: Path) -> Dict[str, Any]:
    """校验“接口已成功返回 0 条”的结构化回执。"""

    receipt_path = Path(path)
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DatasetSelectionError("配种记录 0 条回执无法读取") from exc
    if not isinstance(payload, dict):
        raise DatasetSelectionError("配种记录 0 条回执格式无效")
    expected_keys = {
        "schema_version",
        "dataset",
        "status",
        "record_count",
        "data_source",
        "farms",
        "created_at",
    }
    if set(payload) != expected_keys:
        raise DatasetSelectionError("配种记录 0 条回执字段不完整或含未知字段")
    if (
        type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != 1
    ):
        raise DatasetSelectionError("不支持的配种记录 0 条回执版本")
    if payload.get("dataset") != "breeding":
        raise DatasetSelectionError("配种记录 0 条回执数据集不一致")
    if payload.get("status") != "empty":
        raise DatasetSelectionError("配种记录 0 条回执状态无效")
    if (
        type(payload.get("record_count")) is not int
        or payload.get("record_count") != 0
    ):
        raise DatasetSelectionError("配种记录 0 条回执数量必须为 0")
    data_source = payload.get("data_source")
    if not isinstance(data_source, str) or not data_source.strip():
        raise DatasetSelectionError("配种记录 0 条回执缺少数据源")
    farms = payload.get("farms")
    if not isinstance(farms, list) or not farms:
        raise DatasetSelectionError("配种记录 0 条回执缺少牧场身份")
    farm_codes = set()
    for farm in farms:
        if not isinstance(farm, dict) or set(farm) != {"code", "name"}:
            raise DatasetSelectionError("配种记录 0 条回执牧场格式无效")
        code = farm.get("code")
        name = farm.get("name")
        if not isinstance(code, str) or not code.strip():
            raise DatasetSelectionError("配种记录 0 条回执缺少牧场编号")
        if not isinstance(name, str) or not name.strip():
            raise DatasetSelectionError("配种记录 0 条回执缺少牧场名称")
        if code.strip() in farm_codes:
            raise DatasetSelectionError("配种记录 0 条回执包含重复牧场编号")
        farm_codes.add(code.strip())
    created_at = payload.get("created_at")
    if not isinstance(created_at, str) or not created_at.strip():
        raise DatasetSelectionError("配种记录 0 条回执缺少完成时间")
    try:
        completed_at = datetime.fromisoformat(
            created_at.strip().replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise DatasetSelectionError(
            "配种记录 0 条回执完成时间格式无效"
        ) from exc
    if completed_at.tzinfo is None:
        raise DatasetSelectionError("配种记录 0 条回执完成时间缺少时区")
    return payload


def validate_empty_breeding_receipt_pair(
    raw_path: Path,
    standardized_path: Path,
    *,
    expected_data_source: Optional[str] = None,
    expected_farm_codes: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """校验原始/标准化两份 0 条回执及其项目身份完全一致。"""

    raw_payload = validate_empty_breeding_receipt(raw_path)
    standardized_payload = validate_empty_breeding_receipt(
        standardized_path
    )
    if raw_payload != standardized_payload:
        raise DatasetSelectionError("原始与标准化配种记录 0 条回执不一致")

    if expected_data_source is not None:
        expected_source = str(expected_data_source).strip()
        if raw_payload["data_source"] != expected_source:
            raise DatasetSelectionError(
                "配种记录 0 条回执数据源与当前项目不一致"
            )

    if expected_farm_codes is not None:
        expected_codes = {
            str(code).strip()
            for code in expected_farm_codes
            if str(code).strip()
        }
        receipt_codes = {
            str(farm["code"]).strip()
            for farm in raw_payload["farms"]
        }
        if receipt_codes != expected_codes:
            raise DatasetSelectionError(
                "配种记录 0 条回执与当前牧场身份不一致"
            )
    return standardized_payload
