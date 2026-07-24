"""慧牧云生产只读链路验收。

JWT 仅从标准输入读取；脚本只输出汇总统计，不输出牛只明细。
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import logging
import math
import sys
import tempfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.hmy_api_client import HMYApiClient
from core.data.hmy_data_converter import HMYDataConverter
from core.data.uploader import upload_and_standardize_cow_data


NUMERIC_LIMITS = {
    "relv": (0, 30000),
    "milk305": (0, 30000),
    "peakMilk": (0, 100),
    "dim": (0, 1000),
    "lac": (0, 20),
    "tbrd": (0, 30),
    "age": (0, 300),
}


def _normalize_id(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null"} else text


def _row_signature(record: dict) -> str:
    values = (
        _normalize_id(record.get("cowId")),
        _normalize_id(record.get("dam")),
        _normalize_id(record.get("sire")),
        _normalize_id(record.get("farmCode")),
    )
    return hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()


def _numeric_summary(records: list[dict]) -> dict:
    result = {}
    for field, (minimum, maximum) in NUMERIC_LIMITS.items():
        values = []
        invalid = 0
        for record in records:
            value = record.get(field)
            if value in (None, ""):
                continue
            try:
                numeric = float(value)
                if not math.isfinite(numeric):
                    raise ValueError
                values.append(numeric)
            except (TypeError, ValueError):
                invalid += 1
        result[field] = {
            "non_null": len(values),
            "invalid": invalid,
            "fractional": sum(not value.is_integer() for value in values),
            "out_of_range": sum(
                value < minimum or value > maximum for value in values
            ),
            "minimum": min(values) if values else None,
            "maximum": max(values) if values else None,
        }
    return result


def _normalized_sex(value: object) -> str:
    return {
        0: "母",
        1: "公",
        0.0: "母",
        1.0: "公",
        "0": "母",
        "1": "公",
    }.get(value, "母" if value is None else str(value).strip())


def _verify_excel_roundtrip(records: list[dict], excel_path: Path) -> dict:
    HMYDataConverter.convert_herd_to_excel(
        {"code": 200, "count": len(records), "data": records},
        excel_path,
    )
    frame = pd.read_excel(excel_path, dtype=str, keep_default_na=False)
    expected_signatures = [_row_signature(record) for record in records]
    actual_signatures = []
    for row in frame.to_dict(orient="records"):
        actual_signatures.append(
            _row_signature(
                {
                    "cowId": row.get("耳号"),
                    "dam": row.get("母号"),
                    "sire": row.get("父号"),
                    "farmCode": row.get("牧场编号"),
                }
            )
        )

    max_abs_diff = {}
    source_frame = pd.DataFrame(records).rename(
        columns=HMYDataConverter.FIELD_MAPPING
    )
    raw_frame = pd.read_excel(excel_path)
    for api_field, excel_field in HMYDataConverter.FIELD_MAPPING.items():
        if api_field not in NUMERIC_LIMITS:
            continue
        if excel_field not in source_frame or excel_field not in raw_frame:
            continue
        source_values = pd.to_numeric(
            source_frame[excel_field], errors="coerce"
        )
        excel_values = pd.to_numeric(raw_frame[excel_field], errors="coerce")
        paired = pd.concat([source_values, excel_values], axis=1).dropna()
        max_abs_diff[api_field] = (
            float((paired.iloc[:, 0] - paired.iloc[:, 1]).abs().max())
            if not paired.empty
            else 0.0
        )

    return {
        "rows": len(frame),
        "row_order_and_columns_match": actual_signatures == expected_signatures,
        "numeric_max_abs_diff": max_abs_diff,
    }


def _verify_multi_farm_prefix(
    client: HMYApiClient,
    primary_farm: str,
    secondary_farm: str,
) -> dict:
    samples = []
    for farm_code in (primary_farm, secondary_farm):
        page = client._get_cow_page(farm_code, page_size=20, page_num=1)
        samples.append((farm_code, page.get("data") or []))
    merged = HMYDataConverter.merge_herd_data(
        [
            (farm_code, {"data": records})
            for farm_code, records in samples
        ]
    )["data"]

    expected = []
    for farm_code, records in samples:
        expected.extend(
            HMYDataConverter.add_farm_prefix(records, farm_code)
        )

    sire_unchanged = True
    mgs_unchanged = True
    for (_, records), prefixed_records in zip(
        samples,
        (
            HMYDataConverter.add_farm_prefix(records, farm_code)
            for farm_code, records in samples
        ),
    ):
        for original, prefixed in zip(records, prefixed_records):
            sire_unchanged &= original.get("sire") == prefixed.get("sire")
            mgs_unchanged &= original.get("mgs") == prefixed.get("mgs")

    return {
        "rows": len(merged),
        "cow_and_dam_prefix_exact": merged == expected,
        "sire_unchanged": bool(sire_unchanged),
        "mgs_unchanged": bool(mgs_unchanged),
    }


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: hmy_real_acceptance.py PRIMARY_FARM SECONDARY_FARM"
        )
    token_lines = sys.stdin.read().strip().splitlines()
    if not token_lines:
        raise SystemExit("JWT was not provided")

    primary_farm, secondary_farm = sys.argv[1:3]
    client = HMYApiClient(auth_token=token_lines[-1])
    herd = client.get_farm_herd(primary_farm, page_size=500)
    records = herd.get("data") or []
    if not records:
        raise RuntimeError("selected farm returned no records")

    cow_ids = [_normalize_id(record.get("cowId")) for record in records]
    api_ids = [_normalize_id(record.get("id")) for record in records]
    farm_codes = {
        _normalize_id(record.get("farmCode"))
        for record in records
        if _normalize_id(record.get("farmCode"))
    }

    with tempfile.TemporaryDirectory(prefix="hmy-acceptance-") as temp_dir:
        project_path = Path(temp_dir)
        raw_excel = project_path / "raw_data" / "cow_data.xlsx"
        excel_result = _verify_excel_roundtrip(records, raw_excel)

        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()
        previous_disable = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(
                captured_stderr
            ):
                processed_path = upload_and_standardize_cow_data(
                    input_files=[raw_excel],
                    project_path=project_path,
                    source_system="慧牧云",
                )
        finally:
            logging.disable(previous_disable)

        processed = pd.read_excel(
            processed_path,
            dtype={
                "cow_id": str,
                "dam": str,
                "sire": str,
                "mgs": str,
                "farm_code": str,
            },
        )
        expected_non_male = sum(
            _normalized_sex(record.get("sex")) != "公"
            for record in records
        )
        standardized = {
            "rows": len(processed),
            "expected_non_male_rows": expected_non_male,
            "matches_expected_non_male_rows": len(processed)
            == expected_non_male,
            "has_expected_columns": {
                "cow_id",
                "dam",
                "sire",
                "mgs",
                "milk_305",
            }.issubset(processed.columns),
            "cow_id_non_null": int(processed["cow_id"].notna().sum())
            if "cow_id" in processed
            else 0,
        }

    report = {
        "farm_code": primary_farm,
        "api_reported_count": int(herd.get("count") or 0),
        "downloaded_rows": len(records),
        "all_rows_are_objects": all(isinstance(record, dict) for record in records),
        "field_count_min": min(len(record) for record in records),
        "field_count_max": max(len(record) for record in records),
        "blank_cow_ids": sum(not cow_id for cow_id in cow_ids),
        "duplicate_cow_ids": len(cow_ids) - len(set(cow_ids)),
        "duplicate_api_ids": len(api_ids) - len(set(api_ids)),
        "farm_codes_seen": sorted(farm_codes),
        "sex_counts": {
            label: sum(
                _normalized_sex(record.get("sex")) == label
                for record in records
            )
            for label in sorted(
                {_normalized_sex(record.get("sex")) for record in records}
            )
        },
        "numeric": _numeric_summary(records),
        "excel_roundtrip": excel_result,
        "standardized": standardized,
        "multi_farm_prefix": _verify_multi_farm_prefix(
            client, primary_farm, secondary_farm
        ),
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
