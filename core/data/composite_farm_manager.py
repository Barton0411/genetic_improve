"""接口复合牧场项目的本地补充牧场暂存与合并。"""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

import pandas as pd

from core.data.uploader import (
    upload_and_standardize_breeding_data,
    upload_and_standardize_cow_data,
)
from utils.file_manager import FileManager


logger = logging.getLogger(__name__)

LOCAL_SOURCE_SYSTEMS = ("伊起牛", "优源-DC305", "慧牧云")
_COW_ID_COLUMNS = ("cow_id", "dam", "mgd")
_COW_READ_DTYPES = {
    "cow_id": str,
    "dam": str,
    "mgd": str,
    "sire": str,
    "mgs": str,
    "mmgs": str,
}
_BREEDING_READ_DTYPES = {"耳号": str, "父号": str, "冻精编号": str}
_FARM_CODE_ALIASES = (
    "牧场编号",
    "牧场代码",
    "站号",
    "farmCode",
    "farm_code",
    "farm_id",
)


def _emit(progress_callback: Optional[Callable], value: int, message: str) -> None:
    if progress_callback:
        progress_callback(value, message)


def _prepare_tabular_input(source: Path, target: Path) -> Path:
    """把CSV转换为现有上传器可处理的Excel文件。"""
    if source.suffix.lower() != ".csv":
        return source
    last_error = None
    for encoding in ("utf-8-sig", "gb18030", "utf-8"):
        try:
            frame = pd.read_csv(source, encoding=encoding)
            frame.to_excel(target, index=False)
            return target
        except UnicodeDecodeError as exc:
            last_error = exc
    raise ValueError(f"无法识别CSV文件编码：{last_error}")


def _read_source_frame(source: Path, **kwargs) -> pd.DataFrame:
    if source.suffix.lower() == ".csv":
        last_error = None
        for encoding in ("utf-8-sig", "gb18030", "utf-8"):
            try:
                return pd.read_csv(source, encoding=encoding, **kwargs)
            except UnicodeDecodeError as exc:
                last_error = exc
        raise ValueError(f"无法识别CSV文件编码：{last_error}")
    return pd.read_excel(source, **kwargs)


def _validate_file_farm_code(source: Path, expected_code: str) -> None:
    """文件包含牧场编号时，保证一份文件只属于一个牧场。"""
    header = _read_source_frame(source, nrows=0)
    code_column = next(
        (column for column in _FARM_CODE_ALIASES if column in header.columns),
        None,
    )
    if not code_column:
        return
    values = _read_source_frame(
        source, usecols=[code_column], dtype={code_column: str}
    )[code_column]
    unique_codes = {
        _clean_id(value) for value in values if _clean_id(value)
    }
    if len(unique_codes) > 1:
        raise ValueError("母牛信息文件中包含多个不同的牧场编号")
    if unique_codes and expected_code not in unique_codes:
        file_code = next(iter(unique_codes))
        raise ValueError(
            f"填写的牧场编号“{expected_code}”与文件中的“{file_code}”不一致"
        )


def stage_local_farm(
    cow_file: Path,
    breeding_file: Optional[Path],
    source_system: str,
    farm_code: str,
    farm_name: str,
    progress_callback: Optional[Callable] = None,
) -> Dict:
    """在临时项目中复用现有单牧场标准化流程。"""
    if source_system not in LOCAL_SOURCE_SYSTEMS:
        raise ValueError(f"不支持的数据源：{source_system}")

    cow_file = Path(cow_file)
    breeding_file = Path(breeding_file) if breeding_file else None
    farm_code = str(farm_code).strip()
    farm_name = str(farm_name).strip()
    if not cow_file.exists():
        raise FileNotFoundError(f"母牛信息文件不存在：{cow_file}")
    if breeding_file and not breeding_file.exists():
        raise FileNotFoundError(f"配种记录文件不存在：{breeding_file}")
    if not farm_code:
        raise ValueError("牧场编号不能为空")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", farm_code):
        raise ValueError("牧场编号只能包含字母、数字、下划线和连字符")
    if not farm_name:
        raise ValueError("牧场名称不能为空")
    _validate_file_farm_code(cow_file, farm_code)

    staging_path = Path(tempfile.mkdtemp(prefix="genetic_improve_local_farm_"))
    for name in ("raw_data", "standardized_data", "analysis_results", "reports"):
        (staging_path / name).mkdir(parents=True, exist_ok=True)

    try:
        cow_input = _prepare_tabular_input(
            cow_file, staging_path / "incoming_cow_data.xlsx"
        )
        breeding_input = (
            _prepare_tabular_input(
                breeding_file, staging_path / "incoming_breeding_records.xlsx"
            )
            if breeding_file
            else None
        )
        _emit(progress_callback, 5, "正在处理母牛信息...")

        def cow_progress(value, message=""):
            try:
                mapped = 5 + int(float(value) * 0.55)
            except (TypeError, ValueError):
                mapped = 5
            _emit(progress_callback, min(mapped, 60), message or "正在处理母牛信息...")

        cow_output = upload_and_standardize_cow_data(
            [cow_input],
            staging_path,
            progress_callback=cow_progress,
            source_system=source_system,
        )
        cow_df = pd.read_excel(cow_output, dtype=_COW_READ_DTYPES)
        if cow_df.empty:
            raise ValueError("母牛信息中没有可用记录")

        breeding_count = 0
        if breeding_input:
            _emit(progress_callback, 65, "正在处理配种记录...")

            def breeding_progress(value, message=""):
                try:
                    mapped = 65 + int(float(value) * 0.3)
                except (TypeError, ValueError):
                    mapped = 65
                _emit(
                    progress_callback,
                    min(mapped, 95),
                    message or "正在处理配种记录...",
                )

            breeding_output = upload_and_standardize_breeding_data(
                [breeding_input],
                staging_path,
                progress_callback=breeding_progress,
                source_system=source_system,
            )
            breeding_df = pd.read_excel(
                breeding_output, dtype=_BREEDING_READ_DTYPES
            )
            breeding_count = len(breeding_df)

        _emit(progress_callback, 100, "本地牧场数据处理完成")
        return {
            "farmCode": farm_code,
            "name": farm_name,
            "cow_count": len(cow_df),
            "breeding_count": breeding_count,
            "has_breeding_records": bool(breeding_file),
            "source_kind": "local",
            "source_system": source_system,
            "staging_path": str(staging_path),
        }
    except Exception:
        shutil.rmtree(staging_path, ignore_errors=True)
        raise


def cleanup_local_farm(farm: Dict) -> None:
    """清理尚未写入正式项目的本地牧场暂存目录。"""
    staging_path = farm.get("staging_path")
    if staging_path:
        shutil.rmtree(Path(staging_path), ignore_errors=True)


def _clean_id(value) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null", "<na>"}:
        return ""
    if text.endswith(".0"):
        number = text[:-2]
        if number.isdigit():
            return number
    return text


def _prefix_series(series: pd.Series, farm_code: str) -> pd.Series:
    return series.apply(
        lambda value: f"{farm_code}{_clean_id(value)}" if _clean_id(value) else pd.NA
    )


def _match_farm_code(animal_id, farm_codes: Iterable[str]) -> str:
    text = _clean_id(animal_id)
    for code in sorted((str(code) for code in farm_codes), key=len, reverse=True):
        if text.startswith(code):
            return code
    return ""


def _strip_farm_prefix(animal_id, farm_code: str) -> str:
    text = _clean_id(animal_id)
    code = str(farm_code)
    return text[len(code):] if code and text.startswith(code) else text


def _read_excel(path: Path, dtype: Dict[str, type]) -> pd.DataFrame:
    return pd.read_excel(path, dtype=dtype)


def _atomic_write_excel(frame: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f".{output_path.stem}.tmp.xlsx")
    try:
        frame.to_excel(temp_path, index=False)
        os.replace(temp_path, output_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _annotate_interface_cows(
    frame: pd.DataFrame,
    interface_farms: List[Dict],
    ids_are_prefixed: bool,
    data_source: str,
) -> pd.DataFrame:
    result = frame.copy()
    codes = [str(farm.get("code", "")) for farm in interface_farms]
    names = {str(farm.get("code", "")): farm.get("name", "") for farm in interface_farms}

    existing_code_column = next(
        (
            column
            for column in ("farm_code", "牧场编号")
            if column in result.columns
        ),
        None,
    )
    if existing_code_column:
        result["farm_code"] = result[existing_code_column].apply(_clean_id)
    elif ids_are_prefixed:
        result["farm_code"] = result["cow_id"].apply(
            lambda value: _match_farm_code(value, codes)
        )
    elif len(interface_farms) == 1:
        result["farm_code"] = codes[0]
    else:
        raise ValueError("多牧场接口数据缺少牧场归属，无法安全合并")

    invalid_code_mask = ~result["farm_code"].isin(codes)
    if invalid_code_mask.any():
        if ids_are_prefixed:
            inferred_codes = result.loc[invalid_code_mask, "cow_id"].apply(
                lambda value: _match_farm_code(value, codes)
            )
            result.loc[invalid_code_mask, "farm_code"] = inferred_codes
        invalid_code_mask = ~result["farm_code"].isin(codes)
    if invalid_code_mask.any():
        missing = int(invalid_code_mask.sum())
        raise ValueError(f"有 {missing} 条接口母牛记录无法识别所属牧场")

    result["farm_name"] = result["farm_code"].map(names).fillna("")
    result["牧场编号"] = result["farm_code"]
    result["牧场名称"] = result["farm_name"]
    result["source_kind"] = "api"
    result["source_system"] = data_source
    result["raw_cow_id"] = result.apply(
        lambda row: _strip_farm_prefix(row.get("cow_id"), row.get("farm_code"))
        if ids_are_prefixed
        else _clean_id(row.get("cow_id")),
        axis=1,
    )
    if "dam" in result.columns:
        result["raw_dam_id"] = result.apply(
            lambda row: _strip_farm_prefix(row.get("dam"), row.get("farm_code"))
            if ids_are_prefixed
            else _clean_id(row.get("dam")),
            axis=1,
        )
    else:
        result["raw_dam_id"] = ""
    return result


def _prepare_local_cows(farm: Dict) -> pd.DataFrame:
    staging_path = Path(farm["staging_path"])
    source = staging_path / "standardized_data" / "processed_cow_data.xlsx"
    frame = _read_excel(source, _COW_READ_DTYPES)
    code = str(farm["code"])

    frame["raw_cow_id"] = frame["cow_id"].apply(_clean_id)
    frame["raw_dam_id"] = (
        frame["dam"].apply(_clean_id) if "dam" in frame.columns else ""
    )
    for column in _COW_ID_COLUMNS:
        if column in frame.columns:
            frame[column] = _prefix_series(frame[column], code)
    frame["farm_code"] = code
    frame["farm_name"] = farm.get("name", "")
    frame["牧场编号"] = frame["farm_code"]
    frame["牧场名称"] = frame["farm_name"]
    frame["source_kind"] = "local"
    frame["source_system"] = farm.get("source_system", "")
    return frame


def _annotate_interface_breeding(
    frame: pd.DataFrame,
    interface_farms: List[Dict],
    ids_are_prefixed: bool,
    data_source: str,
) -> pd.DataFrame:
    result = frame.copy()
    codes = [str(farm.get("code", "")) for farm in interface_farms]
    names = {str(farm.get("code", "")): farm.get("name", "") for farm in interface_farms}
    existing_code_column = next(
        (
            column
            for column in ("farm_code", "牧场编号")
            if column in result.columns
        ),
        None,
    )
    if existing_code_column:
        result["farm_code"] = result[existing_code_column].apply(_clean_id)
    elif ids_are_prefixed:
        result["farm_code"] = result["耳号"].apply(
            lambda value: _match_farm_code(value, codes)
        )
    elif len(interface_farms) == 1:
        result["farm_code"] = codes[0]
    else:
        raise ValueError("多牧场接口配种记录缺少牧场归属")

    invalid_code_mask = ~result["farm_code"].isin(codes)
    if invalid_code_mask.any() and ids_are_prefixed:
        inferred_codes = result.loc[invalid_code_mask, "耳号"].apply(
            lambda value: _match_farm_code(value, codes)
        )
        result.loc[invalid_code_mask, "farm_code"] = inferred_codes
        invalid_code_mask = ~result["farm_code"].isin(codes)
    if invalid_code_mask.any():
        missing = int(invalid_code_mask.sum())
        raise ValueError(f"有 {missing} 条接口配种记录无法识别所属牧场")
    result["farm_name"] = result["farm_code"].map(names).fillna("")
    result["牧场编号"] = result["farm_code"]
    result["牧场名称"] = result["farm_name"]
    result["source_kind"] = "api"
    result["source_system"] = data_source
    result["raw_cow_id"] = result.apply(
        lambda row: _strip_farm_prefix(row.get("耳号"), row.get("farm_code"))
        if ids_are_prefixed
        else _clean_id(row.get("耳号")),
        axis=1,
    )
    return result


def _prepare_local_breeding(farm: Dict, valid_cow_ids: set) -> Optional[pd.DataFrame]:
    staging_path = Path(farm["staging_path"])
    source = staging_path / "standardized_data" / "processed_breeding_data.xlsx"
    if not source.exists():
        return None

    frame = _read_excel(source, _BREEDING_READ_DTYPES)
    code = str(farm["code"])
    frame["raw_cow_id"] = frame["耳号"].apply(_clean_id)
    frame["耳号"] = _prefix_series(frame["耳号"], code)
    populated_ids = {
        _clean_id(value) for value in frame["耳号"] if _clean_id(value)
    }
    unknown_ids = populated_ids - valid_cow_ids
    if unknown_ids:
        raise ValueError(
            f"本地牧场“{farm.get('name', code)}”有 "
            f"{len(unknown_ids)} 个配种记录牛号未出现在母牛信息中"
        )
    frame["farm_code"] = code
    frame["farm_name"] = farm.get("name", "")
    frame["牧场编号"] = frame["farm_code"]
    frame["牧场名称"] = frame["farm_name"]
    frame["source_kind"] = "local"
    frame["source_system"] = farm.get("source_system", "")
    return frame


def _copy_local_raw_files(project_path: Path, farm: Dict) -> None:
    staging_path = Path(farm["staging_path"])
    target = project_path / "raw_data" / "farms" / str(farm["code"])
    target.mkdir(parents=True, exist_ok=True)
    for filename in ("cow_data.xlsx", "breeding_records.xlsx"):
        source = staging_path / "raw_data" / filename
        if source.exists():
            shutil.copy2(source, target / filename)


def finalize_composite_project(
    project_path: Path,
    interface_farms: List[Dict],
    local_farms: List[Dict],
    data_source: str,
    ids_are_prefixed: bool,
    progress_callback: Optional[Callable] = None,
) -> List[Dict]:
    """把暂存的本地牧场合并进接口项目，并保存可追踪的牧场归属。"""
    project_path = Path(project_path)
    cow_output = project_path / "standardized_data" / "processed_cow_data.xlsx"
    if not cow_output.exists():
        raise ValueError("接口母牛数据尚未生成，无法合并本地牧场")

    _emit(progress_callback, 5, "正在标记接口牧场归属...")
    interface_cows = _annotate_interface_cows(
        _read_excel(cow_output, _COW_READ_DTYPES),
        interface_farms,
        ids_are_prefixed,
        data_source,
    )
    cow_frames = [interface_cows]
    all_farms = [dict(farm) for farm in interface_farms]

    for index, farm in enumerate(local_farms, start=1):
        _emit(
            progress_callback,
            10 + int(index / max(len(local_farms), 1) * 45),
            f"正在合并本地牧场：{farm.get('name', farm.get('code', ''))}",
        )
        local_frame = _prepare_local_cows(farm)
        farm_copy = dict(farm)
        farm_copy["cow_count"] = len(local_frame)
        cow_frames.append(local_frame)
        all_farms.append(farm_copy)
        _copy_local_raw_files(project_path, farm)

    combined_cows = pd.concat(cow_frames, ignore_index=True, sort=False)
    duplicate_mask = combined_cows["cow_id"].duplicated(keep=False)
    if duplicate_mask.any():
        duplicate_count = combined_cows.loc[duplicate_mask, "cow_id"].nunique()
        raise ValueError(f"合并后仍有 {duplicate_count} 个重复内部牛号，请检查牧场编号")

    counts = combined_cows.groupby("farm_code").size().to_dict()
    for farm in all_farms:
        farm["cow_count"] = int(counts.get(str(farm.get("code", "")), 0))

    _emit(progress_callback, 65, "正在保存合并母牛数据...")
    _atomic_write_excel(combined_cows, cow_output)

    breeding_output = (
        project_path / "standardized_data" / "processed_breeding_data.xlsx"
    )
    breeding_frames = []
    if breeding_output.exists():
        interface_breeding = _annotate_interface_breeding(
            _read_excel(breeding_output, _BREEDING_READ_DTYPES),
            interface_farms,
            ids_are_prefixed,
            data_source,
        )
        breeding_frames.append(interface_breeding)

    valid_ids_by_farm = {
        str(code): {
            _clean_id(value)
            for value in group["cow_id"]
            if _clean_id(value)
        }
        for code, group in combined_cows.groupby("farm_code")
    }
    for farm in local_farms:
        local_breeding = _prepare_local_breeding(
            farm, valid_ids_by_farm.get(str(farm["code"]), set())
        )
        if local_breeding is not None:
            breeding_frames.append(local_breeding)

    if breeding_frames:
        _emit(progress_callback, 80, "正在保存合并配种记录...")
        combined_breeding = pd.concat(
            breeding_frames, ignore_index=True, sort=False
        )
        _atomic_write_excel(combined_breeding, breeding_output)
        breeding_counts = (
            combined_breeding.groupby("farm_code").size().to_dict()
        )
    else:
        breeding_counts = {}

    for farm in all_farms:
        breeding_count = int(
            breeding_counts.get(str(farm.get("code", "")), 0)
        )
        farm["breeding_count"] = breeding_count
        farm["has_breeding_records"] = breeding_count > 0
        farm.pop("staging_path", None)
        farm["source_kind"] = farm.get("source_kind", "api")
        farm["source_system"] = farm.get("source_system", data_source)

    _emit(progress_callback, 90, "正在保存复合牧场项目元数据...")
    FileManager.save_project_metadata(
        project_path, all_farms, data_source=data_source
    )
    FileManager.generate_merged_farms_info(project_path, all_farms)
    _emit(progress_callback, 100, "复合牧场数据合并完成")
    return all_farms
