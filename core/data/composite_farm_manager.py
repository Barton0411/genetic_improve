"""接口复合牧场项目的本地补充牧场暂存与合并。"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

import pandas as pd

from core.data.hmy_data_converter import HMYDataConverter
from core.data.uploader import (
    upload_and_standardize_breeding_data,
    upload_and_standardize_cow_data,
)
from core.group_tasks.dataset_plan import (
    BREEDING_RAW_RECEIPT,
    BREEDING_STANDARDIZED_RECEIPT,
    normalize_dataset_selection,
    validate_empty_breeding_receipt_pair,
    write_empty_breeding_receipts,
)
from utils.file_manager import FileManager


logger = logging.getLogger(__name__)

LOCAL_SOURCE_SYSTEMS = ("伊起牛", "优源-DC305", "慧牧云")
LOCAL_STAGING_PREFIX = "genetic_improve_local_farm_"
LOCAL_INPUT_BUNDLE_SCHEMA_VERSION = 1
LOCAL_DATA_COMMIT_SCHEMA_VERSION = 1
LOCAL_INPUT_BUNDLE_RELATIVE_PATH = Path("raw_data") / "input_bundle"
LOCAL_DATA_COMMIT_RELATIVE_PATH = (
    Path("standardized_data") / "local_data_commit.json"
)
_COW_ID_COLUMNS = ("cow_id", "dam", "mgd")
_COW_READ_DTYPES = {
    "cow_id": str,
    "dam": str,
    "mgd": str,
    "sire": str,
    "mgs": str,
    "mmgs": str,
    "API farmcode": str,
    "farm_code": str,
    "牧场编号": str,
    "牧场名称": str,
}
_BREEDING_READ_DTYPES = {
    "耳号": str,
    "父号": str,
    "冻精编号": str,
    "API farmcode": str,
    "farm_code": str,
    "牧场编号": str,
    "牧场名称": str,
}
_FARM_CODE_ALIASES = (
    "API farmcode",
    "牧场编号",
    "牧场代码",
    "站号",
    "farmCode",
    "farm_code",
    "farm_id",
)

_LOCAL_BUNDLE_COPY_ROOTS = (
    "input_sources",
    "raw_data",
    "standardized_data",
)
_LOCAL_BUNDLE_REQUIRED_PATHS = (
    "raw_data/cow_data.xlsx",
    "standardized_data/processed_cow_data.xlsx",
)
_LOCAL_BUNDLE_BREEDING_PATHS = (
    "raw_data/breeding_records.xlsx",
    "standardized_data/processed_breeding_data.xlsx",
)


def _emit(progress_callback: Optional[Callable], value: int, message: str) -> None:
    if progress_callback:
        progress_callback(value, message)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_directory(path: Path) -> None:
    """尽力把目录项落盘；不支持目录 fsync 的平台直接跳过。"""
    try:
        descriptor = os.open(str(path), os.O_RDONLY)
    except (AttributeError, OSError):
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_json_atomic(path: Path, payload: Dict) -> None:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    _write_bytes_atomic(path, encoded)


def _copy_file_atomic(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(
        f".{target.name}.{uuid.uuid4().hex}.copying"
    )
    try:
        shutil.copy2(source, temporary)
        if source.stat().st_size != temporary.stat().st_size:
            raise IOError(f"文件复制大小不一致：{source.name}")
        if _sha256_file(source) != _sha256_file(temporary):
            raise IOError(f"文件复制摘要不一致：{source.name}")
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def _safe_bundle_member(bundle_path: Path, relative_path: str) -> Path:
    relative = Path(str(relative_path))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"输入包包含不安全路径：{relative_path}")
    bundle_resolved = bundle_path.resolve()
    member = (bundle_path / relative).resolve()
    if member != bundle_resolved and bundle_resolved not in member.parents:
        raise ValueError(f"输入包路径越界：{relative_path}")
    return member


def _bundle_file_role(relative_path: str) -> str:
    path = Path(relative_path)
    name = path.name
    if path.parts and path.parts[0] == "input_sources":
        if name.startswith("cow_original"):
            return "cow_original"
        if name.startswith("breeding_original"):
            return "breeding_original"
        return "original_supporting"
    role_by_path = {
        "raw_data/cow_data.xlsx": "cow_raw",
        "raw_data/breeding_records.xlsx": "breeding_raw",
        "standardized_data/processed_cow_data.xlsx": "cow_standardized_seed",
        "standardized_data/processed_breeding_data.xlsx": (
            "breeding_standardized_seed"
        ),
    }
    return role_by_path.get(relative_path, "supporting_input")


def _manifest_file_entries(bundle_path: Path) -> List[Dict]:
    entries = []
    for root_name in _LOCAL_BUNDLE_COPY_ROOTS:
        root = bundle_path / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"本地输入暂存中不允许符号链接：{path.name}")
            if not path.is_file():
                continue
            relative = path.relative_to(bundle_path).as_posix()
            entries.append(
                {
                    "role": _bundle_file_role(relative),
                    "path": relative,
                    "size": path.stat().st_size,
                    "sha256": _sha256_file(path),
                }
            )
    return entries


def _validate_bundle_directory(
    bundle_path: Path,
    *,
    expected_task_id: Optional[str] = None,
    expected_farm_code: Optional[str] = None,
    dataset_selection: Optional[Dict] = None,
) -> Dict:
    bundle_path = Path(bundle_path)
    manifest_path = bundle_path / "manifest.json"
    digest_path = bundle_path / "manifest.sha256"
    if not manifest_path.is_file() or not digest_path.is_file():
        raise FileNotFoundError("本地输入包缺少 manifest.json 或 manifest.sha256")

    expected_digest = digest_path.read_text(encoding="ascii").strip().lower()
    actual_digest = _sha256_file(manifest_path)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
        raise ValueError("本地输入包 manifest 摘要格式无效")
    if expected_digest != actual_digest:
        raise ValueError("本地输入包 manifest 摘要校验失败")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("本地输入包 manifest 无法读取") from exc
    if manifest.get("schema_version") != LOCAL_INPUT_BUNDLE_SCHEMA_VERSION:
        raise ValueError("不支持的本地输入包版本")

    task_id = str(manifest.get("task_id") or "")
    farm_code = str(manifest.get("farm_code") or "")
    if expected_task_id and task_id != str(expected_task_id):
        raise ValueError("本地输入包 task_id 与当前子任务不一致")
    if expected_farm_code and farm_code != str(expected_farm_code):
        raise ValueError("本地输入包牧场编号与当前子任务不一致")

    selection = (
        normalize_dataset_selection(
            dataset_selection,
            has_local_farms=True,
        )
        if dataset_selection is not None
        else None
    )
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("本地输入包 manifest 没有文件清单")
    seen_paths = set()
    roles = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("本地输入包文件清单格式无效")
        relative = str(entry.get("path") or "")
        if not relative or relative in seen_paths:
            raise ValueError("本地输入包包含空路径或重复路径")
        seen_paths.add(relative)
        role = str(entry.get("role") or "")
        roles.add(role)
        if (
            selection is not None
            and not selection["breeding"]
            and role.startswith("breeding_")
        ):
            continue
        member = _safe_bundle_member(bundle_path, relative)
        if member.is_symlink() or not member.is_file():
            raise FileNotFoundError(f"本地输入包文件缺失：{relative}")
        if member.stat().st_size != int(entry.get("size", -1)):
            raise ValueError(f"本地输入包文件大小不一致：{relative}")
        if _sha256_file(member) != str(entry.get("sha256") or "").lower():
            raise ValueError(f"本地输入包文件摘要不一致：{relative}")

    missing = set(_LOCAL_BUNDLE_REQUIRED_PATHS) - seen_paths
    if missing:
        raise FileNotFoundError(
            f"本地输入包缺少必要文件：{', '.join(sorted(missing))}"
        )

    has_breeding = bool(manifest.get("has_breeding_records"))
    if has_breeding and (
        selection is None or selection["breeding"]
    ):
        missing_breeding = set(_LOCAL_BUNDLE_BREEDING_PATHS) - seen_paths
        if missing_breeding:
            raise FileNotFoundError(
                "本地输入包声明含配种记录，但缺少："
                + ", ".join(sorted(missing_breeding))
            )
    if manifest.get("original_source_preserved"):
        if "cow_original" not in roles:
            raise FileNotFoundError("本地输入包缺少原始母牛文件")
        if (
            has_breeding
            and (selection is None or selection["breeding"])
            and "breeding_original" not in roles
        ):
            raise FileNotFoundError("本地输入包缺少原始配种记录文件")

    manifest["manifest_sha256"] = actual_digest
    manifest["bundle_path"] = str(bundle_path)
    return manifest


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

    staging_path = Path(tempfile.mkdtemp(prefix=LOCAL_STAGING_PREFIX))
    for name in ("raw_data", "standardized_data", "analysis_results", "reports"):
        (staging_path / name).mkdir(parents=True, exist_ok=True)

    try:
        source_directory = staging_path / "input_sources"
        source_directory.mkdir(parents=True, exist_ok=True)
        cow_suffix = cow_file.suffix.lower() or ".data"
        cow_original = source_directory / f"cow_original{cow_suffix}"
        _copy_file_atomic(cow_file, cow_original)
        breeding_original = None
        if breeding_file:
            breeding_suffix = breeding_file.suffix.lower() or ".data"
            breeding_original = (
                source_directory / f"breeding_original{breeding_suffix}"
            )
            _copy_file_atomic(breeding_file, breeding_original)

        cow_input = _prepare_tabular_input(
            cow_original, staging_path / "incoming_cow_data.xlsx"
        )
        breeding_input = (
            _prepare_tabular_input(
                breeding_original,
                staging_path / "incoming_breeding_records.xlsx",
            )
            if breeding_original
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
            "has_breeding_records": breeding_count > 0,
            "source_kind": "local",
            "source_system": source_system,
            "staging_path": str(staging_path),
            "cow_source_name": cow_file.name,
            "breeding_source_name": (
                breeding_file.name if breeding_file else ""
            ),
            "original_source_preserved": True,
        }
    except Exception:
        shutil.rmtree(staging_path, ignore_errors=True)
        raise


def cleanup_local_farm(farm: Dict) -> bool:
    """只清理本模块创建的系统临时目录，绝不删除持久输入包。"""
    raw_path = str(farm.get("staging_path") or "").strip()
    if not raw_path:
        return False

    candidate = Path(raw_path)
    try:
        resolved = candidate.resolve(strict=False)
        temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
    except OSError:
        logger.warning("无法确认本地牧场暂存路径，已拒绝清理：%s", candidate)
        return False

    if (
        resolved.parent != temp_root
        or not resolved.name.startswith(LOCAL_STAGING_PREFIX)
    ):
        logger.warning("拒绝清理非受管本地牧场暂存目录：%s", candidate)
        return False

    shutil.rmtree(resolved, ignore_errors=True)
    farm.pop("staging_path", None)
    return not resolved.exists()


def persist_local_input_bundle(project_path: Path, farm: Dict) -> Dict:
    """把本地牧场 staging 原子固化到子项目的只读输入包。"""
    project_path = Path(project_path)
    bundle_path = project_path / LOCAL_INPUT_BUNDLE_RELATIVE_PATH
    code = str(farm.get("code") or farm.get("farmCode") or "").strip()
    task_id = str(
        farm.get("task_id") or farm.get("group_task_id") or ""
    ).strip()

    if bundle_path.exists():
        return validate_local_input_bundle(
            project_path,
            expected_task_id=task_id or None,
            expected_farm_code=code or None,
        )

    staging_value = str(farm.get("staging_path") or "").strip()
    if not staging_value:
        raise FileNotFoundError("本地牧场没有可持久化的暂存数据")
    staging_path = Path(staging_value)
    if not staging_path.is_dir():
        raise FileNotFoundError("本地牧场暂存数据不存在，请重新添加该牧场")

    for relative in _LOCAL_BUNDLE_REQUIRED_PATHS:
        if not (staging_path / relative).is_file():
            raise FileNotFoundError(f"本地牧场暂存缺少必要文件：{relative}")

    has_breeding = bool(farm.get("has_breeding_records")) or any(
        (staging_path / relative).exists()
        for relative in _LOCAL_BUNDLE_BREEDING_PATHS
    )
    if has_breeding:
        missing_breeding = [
            relative
            for relative in _LOCAL_BUNDLE_BREEDING_PATHS
            if not (staging_path / relative).is_file()
        ]
        if missing_breeding:
            raise FileNotFoundError(
                "本地牧场声明含配种记录，但暂存缺少："
                + ", ".join(missing_breeding)
            )

    raw_parent = bundle_path.parent
    raw_parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".input_bundle.{task_id or uuid.uuid4().hex}.",
            dir=raw_parent,
        )
    )
    try:
        for root_name in _LOCAL_BUNDLE_COPY_ROOTS:
            source_root = staging_path / root_name
            if not source_root.exists():
                continue
            for source in sorted(source_root.rglob("*")):
                if source.is_symlink():
                    raise ValueError(
                        f"本地输入暂存中不允许符号链接：{source.name}"
                    )
                if not source.is_file():
                    continue
                relative = source.relative_to(staging_path)
                _copy_file_atomic(source, temporary / relative)

        entries = _manifest_file_entries(temporary)
        entry_paths = {entry["path"] for entry in entries}
        original_roles = {entry["role"] for entry in entries}
        original_preserved = (
            "cow_original" in original_roles
            and (
                not has_breeding
                or "breeding_original" in original_roles
            )
        )
        manifest = {
            "schema_version": LOCAL_INPUT_BUNDLE_SCHEMA_VERSION,
            "created_at": _utc_now(),
            "task_id": task_id,
            "farm_code": code,
            "farm_name": str(farm.get("name") or code),
            "source_kind": "local",
            "source_system": str(farm.get("source_system") or ""),
            "cow_count": int(farm.get("cow_count", 0) or 0),
            "breeding_count": int(
                farm.get("breeding_count", 0) or 0
            ),
            "has_breeding_records": has_breeding,
            "original_source_preserved": original_preserved,
            "original_names": {
                "cow": str(farm.get("cow_source_name") or ""),
                "breeding": str(
                    farm.get("breeding_source_name") or ""
                ),
            },
            "files": entries,
        }
        missing = set(_LOCAL_BUNDLE_REQUIRED_PATHS) - entry_paths
        if missing:
            raise FileNotFoundError(
                f"本地输入包缺少必要文件：{', '.join(sorted(missing))}"
            )

        manifest_path = temporary / "manifest.json"
        _write_json_atomic(manifest_path, manifest)
        digest = _sha256_file(manifest_path)
        _write_bytes_atomic(
            temporary / "manifest.sha256",
            f"{digest}\n".encode("ascii"),
        )
        _validate_bundle_directory(
            temporary,
            expected_task_id=task_id or None,
            expected_farm_code=code or None,
        )

        if bundle_path.exists():
            raise FileExistsError("本地输入包在提交前被其他任务创建")
        os.replace(temporary, bundle_path)
        _fsync_directory(raw_parent)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)

    return validate_local_input_bundle(
        project_path,
        expected_task_id=task_id or None,
        expected_farm_code=code or None,
    )


def persist_group_local_input_bundles(
    group_project_path: Path,
    farms: List[Dict],
) -> List[Dict]:
    """先持久化全部本地输入，全部成功后才清理临时 staging。"""
    persisted = []
    local_farms = [
        farm for farm in farms if farm.get("source_kind") == "local"
    ]
    for farm in local_farms:
        task_id = str(
            farm.get("task_id") or farm.get("group_task_id") or ""
        ).strip()
        if not task_id:
            raise ValueError("本地牧场任务缺少 task_id，无法定位子项目")
        child_path = FileManager.get_group_child_path(
            Path(group_project_path), task_id
        )
        if child_path is None:
            raise FileNotFoundError(f"找不到本地牧场子项目：{task_id}")
        manifest = persist_local_input_bundle(child_path, farm)
        persisted.append(manifest)
        farm["input_bundle_relative_path"] = (
            LOCAL_INPUT_BUNDLE_RELATIVE_PATH.as_posix()
        )
        farm["input_manifest_sha256"] = manifest["manifest_sha256"]

    for farm in local_farms:
        cleanup_local_farm(farm)
    return persisted


def validate_local_input_bundle(
    project_path: Path,
    *,
    expected_task_id: Optional[str] = None,
    expected_farm_code: Optional[str] = None,
    dataset_selection: Optional[Dict] = None,
) -> Dict:
    """完整校验子项目本地输入包并返回 manifest。"""
    bundle_path = Path(project_path) / LOCAL_INPUT_BUNDLE_RELATIVE_PATH
    return _validate_bundle_directory(
        bundle_path,
        expected_task_id=expected_task_id,
        expected_farm_code=expected_farm_code,
        dataset_selection=dataset_selection,
    )


def _local_data_output_entries(
    project_path: Path,
    dataset_selection: Optional[Dict] = None,
) -> List[Dict]:
    selection = normalize_dataset_selection(dataset_selection)
    output_paths = []
    if selection["herd"]:
        output_paths.append(
            Path("standardized_data") / "processed_cow_data.xlsx"
        )
    if selection["breeding"]:
        output_paths.append(
            Path("standardized_data")
            / "processed_breeding_data.xlsx"
        )
    entries = []
    for relative in output_paths:
        path = project_path / relative
        if not path.is_file():
            continue
        entries.append(
            {
                "role": (
                    "cow_standardized"
                    if path.name == "processed_cow_data.xlsx"
                    else "breeding_standardized"
                ),
                "path": relative.as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return entries


def validate_local_data_commit(
    project_path: Path,
    *,
    expected_input_manifest_sha256: Optional[str] = None,
    expected_farm_code: Optional[str] = None,
    expected_task_id: Optional[str] = None,
    expected_dataset_selection: Optional[Dict] = None,
) -> Dict:
    """校验本地数据阶段提交标记及其全部输出。"""
    project_path = Path(project_path)
    commit_path = project_path / LOCAL_DATA_COMMIT_RELATIVE_PATH
    if not commit_path.is_file():
        raise FileNotFoundError("本地数据阶段尚未完整提交")
    try:
        commit = json.loads(commit_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("本地数据阶段提交标记无法读取") from exc
    if commit.get("schema_version") != LOCAL_DATA_COMMIT_SCHEMA_VERSION:
        raise ValueError("不支持的本地数据阶段提交标记版本")
    if (
        expected_farm_code
        and str(commit.get("farm_code") or "") != str(expected_farm_code)
    ):
        raise ValueError("本地数据阶段提交标记牧场编号不一致")
    if (
        expected_task_id
        and str(commit.get("task_id") or "") != str(expected_task_id)
    ):
        raise ValueError("本地数据阶段提交标记 task_id 不一致")
    input_digest = str(commit.get("input_manifest_sha256") or "")
    if (
        expected_input_manifest_sha256
        and input_digest != str(expected_input_manifest_sha256)
    ):
        raise ValueError("本地数据阶段引用的输入包摘要不一致")
    commit_selection = normalize_dataset_selection(
        commit.get("dataset_selection")
    )
    if expected_dataset_selection is not None:
        expected_selection = normalize_dataset_selection(
            expected_dataset_selection,
            has_local_farms=True,
        )
        if commit_selection != expected_selection:
            raise ValueError("本地数据阶段的数据集选择不一致")

    bundle_path = project_path / LOCAL_INPUT_BUNDLE_RELATIVE_PATH
    if bundle_path.exists():
        bundle = validate_local_input_bundle(
            project_path,
            expected_task_id=expected_task_id,
            expected_farm_code=expected_farm_code,
            dataset_selection=commit_selection,
        )
        if input_digest != bundle["manifest_sha256"]:
            raise ValueError("本地数据阶段未引用当前输入包")
        if (
            str(commit.get("task_id") or "")
            != str(bundle.get("task_id") or "")
        ):
            raise ValueError("本地数据阶段与输入包 task_id 不一致")
        selected_bundle_breeding = bool(
            commit_selection["breeding"]
            and int(bundle.get("breeding_count") or 0) > 0
        )
        if bool(commit.get("has_breeding_records")) != selected_bundle_breeding:
            raise ValueError("本地数据阶段与输入包的配种记录状态不一致")

    entries = commit.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("本地数据阶段提交标记没有输出清单")
    roles = set()
    seen_paths = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("本地数据阶段输出清单格式无效")
        relative = str(entry.get("path") or "")
        if not relative or relative in seen_paths:
            raise ValueError("本地数据阶段包含空路径或重复路径")
        seen_paths.add(relative)
        roles.add(str(entry.get("role") or ""))
        member = _safe_bundle_member(project_path, relative)
        if member.is_symlink() or not member.is_file():
            raise FileNotFoundError(f"本地数据阶段输出缺失：{relative}")
        if member.stat().st_size != int(entry.get("size", -1)):
            raise ValueError(f"本地数据阶段输出大小不一致：{relative}")
        if _sha256_file(member) != str(entry.get("sha256") or "").lower():
            raise ValueError(f"本地数据阶段输出摘要不一致：{relative}")

    if commit_selection["herd"] and "cow_standardized" not in roles:
        raise FileNotFoundError("本地数据阶段缺少母牛标准化输出")
    if (
        commit_selection["breeding"]
        and commit.get("has_breeding_records")
        and "breeding_standardized" not in roles
    ):
        raise FileNotFoundError("本地数据阶段缺少配种记录标准化输出")
    return commit


def materialize_single_local_project(
    project_path: Path,
    farm: Dict,
    data_source: str,
    progress_callback: Optional[Callable] = None,
    dataset_selection: Optional[Dict] = None,
) -> Dict:
    """把已暂存的本地牧场复制为一个独立、可继续计算的子项目。"""
    project_path = Path(project_path)
    existing_metadata = FileManager.load_project_metadata(project_path)
    code = str(farm.get("code") or farm.get("farmCode") or "").strip()
    name = str(farm.get("name") or code).strip()
    group_task_id = str(
        farm.get("task_id") or farm.get("group_task_id") or ""
    ).strip()
    selection = normalize_dataset_selection(
        dataset_selection,
        has_local_farms=True,
    )
    _validate_existing_dataset_selection(
        existing_metadata,
        selection,
        has_local_farms=True,
    )
    bundle_path = project_path / LOCAL_INPUT_BUNDLE_RELATIVE_PATH
    input_manifest = None
    if bundle_path.exists():
        input_manifest = validate_local_input_bundle(
            project_path,
            expected_task_id=group_task_id or None,
            expected_farm_code=code or None,
            dataset_selection=selection,
        )
        source_root = bundle_path
    else:
        staging_value = str(farm.get("staging_path") or "").strip()
        if not staging_value or not Path(staging_value).is_dir():
            raise FileNotFoundError(
                "本地牧场持久输入包和暂存数据均不存在，请重新添加该牧场"
            )
        source_root = Path(staging_value)
    breeding_source = (
        source_root / "standardized_data" / "processed_breeding_data.xlsx"
    )
    source_has_breeding_records = bool(
        input_manifest.get("has_breeding_records")
        if input_manifest is not None
        else farm.get("has_breeding_records") or breeding_source.exists()
    )
    has_breeding_records = False

    _emit(progress_callback, 5, "正在复制本地牧场原始文件...")
    raw_target = project_path / "raw_data"
    standardized_target = project_path / "standardized_data"
    raw_target.mkdir(parents=True, exist_ok=True)
    standardized_target.mkdir(parents=True, exist_ok=True)
    commit_path = project_path / LOCAL_DATA_COMMIT_RELATIVE_PATH
    if commit_path.exists():
        commit_path.unlink()

    selected_raw_files = ["cow_data.xlsx"]
    if selection["breeding"]:
        selected_raw_files.append("breeding_records.xlsx")
    for filename in selected_raw_files:
        source = source_root / "raw_data" / filename
        if source.exists():
            _copy_file_atomic(source, raw_target / filename)
        elif filename == "breeding_records.xlsx":
            stale_target = raw_target / filename
            if stale_target.exists():
                stale_target.unlink()
    if not selection["breeding"]:
        stale_breeding_raw = raw_target / "breeding_records.xlsx"
        if stale_breeding_raw.exists():
            stale_breeding_raw.unlink()

    _emit(progress_callback, 30, "正在写入牧场归属信息...")
    cow_source = source_root / "standardized_data" / "processed_cow_data.xlsx"
    if not cow_source.exists():
        raise FileNotFoundError("本地牧场缺少标准化母牛数据")
    cow_frame = _read_excel(cow_source, _COW_READ_DTYPES)
    cow_frame["raw_cow_id"] = cow_frame["cow_id"].apply(_clean_id)
    cow_frame["raw_dam_id"] = (
        cow_frame["dam"].apply(_clean_id) if "dam" in cow_frame.columns else ""
    )
    cow_frame["farm_code"] = code
    cow_frame["farm_name"] = name
    cow_frame["牧场编号"] = code
    cow_frame["牧场名称"] = name
    cow_frame["source_kind"] = "local"
    cow_frame["source_system"] = farm.get("source_system", data_source)
    _atomic_write_excel(
        cow_frame, standardized_target / "processed_cow_data.xlsx"
    )

    breeding_count = 0
    if (
        selection["breeding"]
        and source_has_breeding_records
        and not breeding_source.is_file()
    ):
        raise FileNotFoundError(
            "本地牧场声明含配种记录，但缺少标准化配种记录"
        )
    if selection["breeding"] and breeding_source.exists():
        _emit(progress_callback, 70, "正在复制并标记配种记录...")
        breeding_frame = _read_excel(breeding_source, _BREEDING_READ_DTYPES)
        breeding_frame["raw_cow_id"] = breeding_frame["耳号"].apply(_clean_id)
        breeding_frame["farm_code"] = code
        breeding_frame["farm_name"] = name
        breeding_frame["牧场编号"] = code
        breeding_frame["牧场名称"] = name
        breeding_frame["source_kind"] = "local"
        breeding_frame["source_system"] = farm.get(
            "source_system", data_source
        )
        breeding_count = len(breeding_frame)
        if breeding_count:
            _atomic_write_excel(
                breeding_frame,
                standardized_target / "processed_breeding_data.xlsx",
            )
            has_breeding_records = True
            for receipt in (
                project_path / BREEDING_RAW_RECEIPT,
                project_path / BREEDING_STANDARDIZED_RECEIPT,
            ):
                receipt.unlink(missing_ok=True)
        else:
            (
                standardized_target
                / "processed_breeding_data.xlsx"
            ).unlink(missing_ok=True)
            write_empty_breeding_receipts(
                project_path,
                data_source=data_source,
                farms=[farm],
            )
    else:
        stale_breeding_output = (
            standardized_target / "processed_breeding_data.xlsx"
        )
        if stale_breeding_output.exists():
            stale_breeding_output.unlink()
        if selection["breeding"]:
            write_empty_breeding_receipts(
                project_path,
                data_source=data_source,
                farms=[farm],
            )
        else:
            for receipt in (
                project_path / BREEDING_RAW_RECEIPT,
                project_path / BREEDING_STANDARDIZED_RECEIPT,
            ):
                receipt.unlink(missing_ok=True)

    normalized = dict(farm)
    normalized["code"] = code
    normalized["name"] = name
    normalized["cow_count"] = len(cow_frame)
    normalized["breeding_count"] = breeding_count
    normalized["has_breeding_records"] = has_breeding_records
    normalized["source_kind"] = "local"
    normalized["source_system"] = farm.get("source_system", data_source)
    input_manifest_sha256 = (
        input_manifest.get("manifest_sha256", "")
        if input_manifest is not None
        else ""
    )
    metadata_extra = {
        "parent_group": "../..",
        "group_farm_code": code,
        "group_task_id": group_task_id,
        "local_input_bundle": {
            "relative_path": (
                LOCAL_INPUT_BUNDLE_RELATIVE_PATH.as_posix()
                if input_manifest is not None
                else ""
            ),
            "manifest_sha256": input_manifest_sha256,
        },
        "dataset_selection": selection,
        "dataset_selection_explicit": bool(
            existing_metadata.get(
                "dataset_selection_explicit",
                "dataset_selection" in existing_metadata,
            )
        ),
    }
    FileManager.save_project_metadata(
        project_path,
        [normalized],
        data_source=data_source,
        project_type="group_child",
        extra=metadata_extra,
    )

    output_entries = _local_data_output_entries(
        project_path,
        selection,
    )
    data_commit = {
        "schema_version": LOCAL_DATA_COMMIT_SCHEMA_VERSION,
        "completed_at": _utc_now(),
        "task_id": group_task_id,
        "farm_code": code,
        "farm_name": name,
        "input_manifest_sha256": input_manifest_sha256,
        "has_breeding_records": has_breeding_records,
        "dataset_selection": selection,
        "cow_count": len(cow_frame),
        "breeding_count": breeding_count,
        "files": output_entries,
    }
    _write_json_atomic(commit_path, data_commit)
    validate_local_data_commit(
        project_path,
        expected_input_manifest_sha256=(
            input_manifest_sha256 or None
        ),
        expected_dataset_selection=selection,
        expected_farm_code=code or None,
        expected_task_id=group_task_id or None,
    )
    _emit(progress_callback, 100, "本地牧场子项目准备完成")
    return normalized


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


def _hmy_farm_identity(farm: Dict) -> tuple[str, str]:
    """读取显式慧牧云身份；兼容只保存原始接口名称的旧项目。"""
    source_name = str(
        farm.get("source_farm_name")
        or farm.get("name")
        or ""
    ).strip()
    parsed_number, parsed_name = HMYDataConverter.split_farm_name(
        source_name
    )
    farm_number = (
        str(farm.get("farm_number") or "").strip()
        if "farm_number" in farm
        else parsed_number
    )
    display_name = str(
        farm.get("display_name") or parsed_name or source_name
    ).strip()
    return farm_number, display_name


def _annotate_interface_cows(
    frame: pd.DataFrame,
    interface_farms: List[Dict],
    ids_are_prefixed: bool,
    data_source: str,
) -> pd.DataFrame:
    result = frame.copy()
    codes = [str(farm.get("code", "")) for farm in interface_farms]
    names = {str(farm.get("code", "")): farm.get("name", "") for farm in interface_farms}
    hmy_identities = {
        str(farm.get("code", "")): _hmy_farm_identity(farm)
        for farm in interface_farms
    }

    code_columns = (
        ("API farmcode", "farm_code")
        if data_source == "慧牧云"
        else ("API farmcode", "farm_code", "牧场编号")
    )
    existing_code_column = next(
        (
            column
            for column in code_columns
            if column in result.columns
        ),
        None,
    )
    if existing_code_column:
        result["farm_code"] = result[existing_code_column].apply(_clean_id)
    else:
        result["farm_code"] = ""

    invalid_code_mask = ~result["farm_code"].isin(codes)
    if (
        data_source == "慧牧云"
        and existing_code_column
        and (result["farm_code"].ne("") & invalid_code_mask).any()
    ):
        missing = int(
            (result["farm_code"].ne("") & invalid_code_mask).sum()
        )
        raise ValueError(
            f"有 {missing} 条接口母牛记录的 API farmcode "
            "与当前牧场不一致"
        )
    if invalid_code_mask.any():
        if ids_are_prefixed:
            inferred_codes = result.loc[invalid_code_mask, "cow_id"].apply(
                lambda value: _match_farm_code(value, codes)
            )
            inferred_mask = inferred_codes.ne("")
            result.loc[
                inferred_codes.index[inferred_mask], "farm_code"
            ] = inferred_codes[inferred_mask]
        invalid_code_mask = ~result["farm_code"].isin(codes)
    if invalid_code_mask.any() and len(interface_farms) == 1:
        result.loc[invalid_code_mask, "farm_code"] = codes[0]
        invalid_code_mask = ~result["farm_code"].isin(codes)
    if invalid_code_mask.any():
        missing = int(invalid_code_mask.sum())
        raise ValueError(
            f"有 {missing} 条接口母牛记录无法识别所属牧场；"
            "多牧场数据必须保留 API farmcode"
        )

    if data_source == "慧牧云":
        result["API farmcode"] = result["farm_code"]
        mapped_identities = result["farm_code"].map(hmy_identities)
        mapped_numbers = mapped_identities.map(
            lambda item: item[0] if isinstance(item, tuple) else ""
        )
        mapped_names = mapped_identities.map(
            lambda item: item[1] if isinstance(item, tuple) else ""
        )

        if "牧场名称" not in result.columns:
            result["牧场名称"] = ""
        result["牧场名称"] = (
            result["牧场名称"].fillna("").astype(str).str.strip()
        )
        missing_name = result["牧场名称"].eq("")
        result.loc[missing_name, "牧场名称"] = mapped_names[missing_name]

        if "牧场编号" not in result.columns:
            result["牧场编号"] = ""
        result["牧场编号"] = result["牧场编号"].apply(_clean_id)
        needs_display_number = result["牧场编号"].eq("") | result[
            "牧场编号"
        ].eq(result["farm_code"])
        result.loc[needs_display_number, "牧场编号"] = mapped_numbers[
            needs_display_number
        ]
        result["farm_name"] = result["牧场名称"]
    else:
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
    hmy_identities = {
        str(farm.get("code", "")): _hmy_farm_identity(farm)
        for farm in interface_farms
    }
    code_columns = (
        ("API farmcode", "farm_code")
        if data_source == "慧牧云"
        else ("API farmcode", "farm_code", "牧场编号")
    )
    existing_code_column = next(
        (
            column
            for column in code_columns
            if column in result.columns
        ),
        None,
    )
    if existing_code_column:
        result["farm_code"] = result[existing_code_column].apply(_clean_id)
    else:
        result["farm_code"] = ""

    invalid_code_mask = ~result["farm_code"].isin(codes)
    if (
        data_source == "慧牧云"
        and existing_code_column
        and (result["farm_code"].ne("") & invalid_code_mask).any()
    ):
        missing = int(
            (result["farm_code"].ne("") & invalid_code_mask).sum()
        )
        raise ValueError(
            f"有 {missing} 条接口配种记录的 API farmcode "
            "与当前牧场不一致"
        )
    if invalid_code_mask.any() and ids_are_prefixed:
        inferred_codes = result.loc[invalid_code_mask, "耳号"].apply(
            lambda value: _match_farm_code(value, codes)
        )
        inferred_mask = inferred_codes.ne("")
        result.loc[
            inferred_codes.index[inferred_mask], "farm_code"
        ] = inferred_codes[inferred_mask]
        invalid_code_mask = ~result["farm_code"].isin(codes)
    if invalid_code_mask.any() and len(interface_farms) == 1:
        result.loc[invalid_code_mask, "farm_code"] = codes[0]
        invalid_code_mask = ~result["farm_code"].isin(codes)
    if invalid_code_mask.any():
        missing = int(invalid_code_mask.sum())
        raise ValueError(
            f"有 {missing} 条接口配种记录无法识别所属牧场；"
            "多牧场数据必须保留 API farmcode"
        )
    if data_source == "慧牧云":
        result["API farmcode"] = result["farm_code"]
        mapped_identities = result["farm_code"].map(hmy_identities)
        result["牧场编号"] = mapped_identities.map(
            lambda item: item[0] if isinstance(item, tuple) else ""
        )
        result["牧场名称"] = mapped_identities.map(
            lambda item: item[1] if isinstance(item, tuple) else ""
        )
        result["farm_name"] = result["牧场名称"]
    else:
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


def _copy_local_raw_files(
    project_path: Path,
    farm: Dict,
    dataset_selection: Optional[Dict] = None,
) -> None:
    selection = normalize_dataset_selection(
        dataset_selection,
        has_local_farms=True,
    )
    staging_path = Path(farm["staging_path"])
    target = project_path / "raw_data" / "farms" / str(farm["code"])
    target.mkdir(parents=True, exist_ok=True)
    filenames = ["cow_data.xlsx"]
    if selection["breeding"]:
        filenames.append("breeding_records.xlsx")
    for filename in filenames:
        source = staging_path / "raw_data" / filename
        if source.exists():
            shutil.copy2(source, target / filename)


def _group_child_metadata_extra(
    existing_metadata: Dict,
    dataset_selection: Dict,
) -> Optional[Dict]:
    if existing_metadata.get("project_type") != "group_child":
        return None
    extra = {
        key: existing_metadata.get(key)
        for key in (
            "parent_group",
            "group_farm_code",
            "group_api_farmcode",
            "group_farm_number",
            "group_task_id",
            "created_at",
            "dataset_selection_explicit",
        )
        if existing_metadata.get(key) not in (None, "")
    }
    extra["dataset_selection"] = dict(dataset_selection)
    return extra


def _validate_existing_dataset_selection(
    existing_metadata: Dict,
    dataset_selection: Dict,
    *,
    has_local_farms: bool = False,
) -> None:
    """显式创建的组子项目不得在低层写入时改变数据选择。"""

    if existing_metadata.get("project_type") != "group_child":
        return
    explicit = bool(
        existing_metadata.get(
            "dataset_selection_explicit",
            "dataset_selection" in existing_metadata,
        )
    )
    if not explicit:
        return
    persisted = normalize_dataset_selection(
        existing_metadata.get("dataset_selection"),
        has_local_farms=has_local_farms,
    )
    if persisted != dataset_selection:
        raise ValueError("本次数据集选择与子项目创建时不一致")


def finalize_composite_project(
    project_path: Path,
    interface_farms: List[Dict],
    local_farms: List[Dict],
    data_source: str,
    ids_are_prefixed: bool,
    progress_callback: Optional[Callable] = None,
    dataset_selection: Optional[Dict] = None,
) -> List[Dict]:
    """把暂存的本地牧场合并进接口项目，并保存可追踪的牧场归属。"""
    project_path = Path(project_path)
    existing_metadata = FileManager.load_project_metadata(project_path)
    selection = normalize_dataset_selection(
        dataset_selection,
        has_local_farms=bool(local_farms),
    )
    _validate_existing_dataset_selection(
        existing_metadata,
        selection,
        has_local_farms=bool(local_farms),
    )
    if not selection["herd"]:
        raise ValueError("复合母牛项目必须选择牛群/系谱数据")
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
        _copy_local_raw_files(project_path, farm, selection)

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
    if selection["breeding"] and breeding_output.exists():
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
    if selection["breeding"]:
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
        breeding_output.unlink(missing_ok=True)
        if selection["breeding"]:
            write_empty_breeding_receipts(
                project_path,
                data_source=data_source,
                farms=all_farms,
            )
    if breeding_frames:
        for receipt in (
            project_path / BREEDING_RAW_RECEIPT,
            project_path / BREEDING_STANDARDIZED_RECEIPT,
        ):
            receipt.unlink(missing_ok=True)
    elif not selection["breeding"]:
        for receipt in (
            project_path / BREEDING_RAW_RECEIPT,
            project_path / BREEDING_STANDARDIZED_RECEIPT,
        ):
            receipt.unlink(missing_ok=True)

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
    project_type = None
    metadata_extra = None
    if existing_metadata.get("project_type") == "group_child":
        if len(all_farms) != 1:
            raise ValueError("牧场组子项目只能保存一个牧场")
        expected_code = str(
            existing_metadata.get("group_farm_code") or ""
        ).strip()
        actual_code = str(all_farms[0].get("code") or "").strip()
        if expected_code and actual_code != expected_code:
            raise ValueError("下载结果牧场编码与牧场组子任务不一致")
        project_type = "group_child"
        metadata_extra = _group_child_metadata_extra(
            existing_metadata,
            selection,
        )
    FileManager.save_project_metadata(
        project_path,
        all_farms,
        data_source=data_source,
        project_type=project_type,
        extra=metadata_extra,
    )
    FileManager.generate_merged_farms_info(project_path, all_farms)
    _emit(progress_callback, 100, "复合牧场数据合并完成")
    return all_farms


def finalize_breeding_only_project(
    project_path: Path,
    interface_farms: List[Dict],
    data_source: str,
    *,
    ids_are_prefixed: bool = False,
    progress_callback: Optional[Callable] = None,
    dataset_selection: Optional[Dict] = None,
) -> List[Dict]:
    """提交仅含配种记录的数据子项目，不创建或伪造母牛数据。"""
    project_path = Path(project_path)
    selection = normalize_dataset_selection(dataset_selection)
    if selection["herd"] or not selection["breeding"]:
        raise ValueError("仅配种记录项目的数据集选择不一致")
    if not interface_farms:
        raise ValueError("仅配种记录项目没有接口牧场")

    existing_metadata = FileManager.load_project_metadata(project_path)
    _validate_existing_dataset_selection(
        existing_metadata,
        selection,
    )
    for relative in (
        Path("raw_data") / "cow_data.xlsx",
        Path("standardized_data") / "processed_cow_data.xlsx",
    ):
        (project_path / relative).unlink(missing_ok=True)
    breeding_output = (
        project_path / "standardized_data" / "processed_breeding_data.xlsx"
    )
    raw_receipt = project_path / BREEDING_RAW_RECEIPT
    receipt = project_path / BREEDING_STANDARDIZED_RECEIPT
    all_farms = [dict(farm) for farm in interface_farms]
    breeding_counts: Dict[str, int] = {}

    if breeding_output.is_file():
        _emit(progress_callback, 30, "正在标记配种记录牧场归属...")
        breeding = _annotate_interface_breeding(
            _read_excel(breeding_output, _BREEDING_READ_DTYPES),
            interface_farms,
            ids_are_prefixed,
            data_source,
        )
        _atomic_write_excel(breeding, breeding_output)
        breeding_counts = {
            str(code): int(count)
            for code, count in breeding.groupby("farm_code").size().items()
        }
        raw_receipt.unlink(missing_ok=True)
        receipt.unlink(missing_ok=True)
    elif receipt.is_file():
        validate_empty_breeding_receipt_pair(
            raw_receipt,
            receipt,
            expected_data_source=data_source,
            expected_farm_codes=[
                str(farm.get("code") or farm.get("farmCode") or "")
                for farm in interface_farms
            ],
        )
        (
            project_path / "raw_data" / "breeding_records.xlsx"
        ).unlink(missing_ok=True)
        _emit(progress_callback, 50, "配种记录接口已返回 0 条，正在保存回执...")
    else:
        raise FileNotFoundError(
            "仅配种记录任务缺少标准化结果或 0 条回执"
        )

    for farm in all_farms:
        breeding_count = int(
            breeding_counts.get(str(farm.get("code") or ""), 0)
        )
        farm["cow_count"] = 0
        farm["breeding_count"] = breeding_count
        farm["has_breeding_records"] = breeding_count > 0
        farm["source_kind"] = farm.get("source_kind", "api")
        farm["source_system"] = farm.get("source_system", data_source)

    project_type = None
    metadata_extra = None
    if existing_metadata.get("project_type") == "group_child":
        if len(all_farms) != 1:
            raise ValueError("牧场组子项目只能保存一个牧场")
        expected_code = str(
            existing_metadata.get("group_farm_code") or ""
        ).strip()
        actual_code = str(all_farms[0].get("code") or "").strip()
        if expected_code and actual_code != expected_code:
            raise ValueError("下载结果牧场编码与牧场组子任务不一致")
        project_type = "group_child"
        metadata_extra = _group_child_metadata_extra(
            existing_metadata,
            selection,
        )

    _emit(progress_callback, 80, "正在保存仅配种记录项目元数据...")
    FileManager.save_project_metadata(
        project_path,
        all_farms,
        data_source=data_source,
        project_type=project_type,
        extra=metadata_extra,
    )
    FileManager.generate_merged_farms_info(project_path, all_farms)
    _emit(progress_callback, 100, "配种记录数据准备完成")
    return all_farms
