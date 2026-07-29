"""牧场组子项目阶段清单的统一策略。

这里集中定义每个阶段的直接输入、正式输出和算法口径。调用方不能再用
“某个 xlsx 文件存在”推断阶段完成；只有当前清单验证通过时才允许复用。
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from core.group_tasks.stage_manifest import (
    commit_stage_manifest,
    validate_stage_manifest,
)


STAGE_ORDER = ("data", "analysis", "child_excel")
STAGE_POLICY_REVISIONS = {
    "data": 1,
    "analysis": 1,
    "child_excel": 1,
}
STAGE_MANIFEST_DIRECTORY = Path("group_store") / "stage_manifests"

REQUIRED_ANALYSIS_OUTPUTS = (
    Path("analysis_results") / "processed_cow_data_key_traits_final.xlsx",
    Path("analysis_results") / "processed_index_cow_index_scores.xlsx",
    Path("analysis_results") / "关键育种性状分析结果.xlsx",
    Path("analysis_results") / "系谱识别分析结果.xlsx",
)

_COW_ID_COLUMNS = ("cow_id", "母牛号", "牛号", "耳号")
_IGNORED_SUFFIXES = (".tmp", ".part", ".lock")

RAW_DATA_FILES = (
    Path("raw_data") / "cow_data.xlsx",
    Path("raw_data") / "breeding_records.xlsx",
    Path("raw_data") / "semen_inventory.xlsx",
    Path("raw_data") / "bull_data.xlsx",
    Path("raw_data") / "body_conformation.xlsx",
)
REGENERATED_RAW_DATA_FILES = RAW_DATA_FILES[:3]
STANDARDIZED_DATA_FILES = (
    Path("standardized_data") / "processed_cow_data.xlsx",
    Path("standardized_data") / "processed_breeding_data.xlsx",
    Path("standardized_data") / "processed_bull_data.xlsx",
    Path("standardized_data") / "processed_body_conformation_data.xlsx",
    Path("standardized_data") / "processed_genomic_data.xlsx",
    Path("standardized_data") / "local_data_commit.json",
)
ANALYSIS_FIXED_FILES = (
    Path("analysis_results") / "processed_cow_data_key_traits_detail.xlsx",
    Path("analysis_results") / "processed_cow_data_key_traits_final.xlsx",
    Path("analysis_results") / "processed_cow_data_key_traits_mean_by_year.xlsx",
    Path("analysis_results") / "processed_cow_data_key_traits_scores_genomic.xlsx",
    Path("analysis_results") / "processed_cow_data_key_traits_scores_pedigree.xlsx",
    Path("analysis_results") / "sire_traits_mean_by_cow_birth_year.xlsx",
    Path("analysis_results") / "sire_traits_mean_by_cow_birth_year_by_farm.xlsx",
    Path("analysis_results") / "processed_index_cow_index_scores.xlsx",
    Path("analysis_results") / "processed_bull_data_key_traits.xlsx",
    Path("analysis_results") / "processed_index_bull_scores.xlsx",
    Path("analysis_results") / "processed_index_bull_index_scores.xlsx",
    Path("analysis_results") / "processed_mated_bull_traits.xlsx",
    Path("analysis_results") / "关键育种性状分析结果.xlsx",
    Path("analysis_results") / "系谱识别分析结果.xlsx",
    Path("analysis_results") / "母牛近交系数分析结果.xlsx",
)
ANALYSIS_LATEST_PATTERNS = (
    "备选公牛_近交系数及隐性基因分析结果*.xlsx",
    "已配公牛_近交系数及隐性基因分析结果*.xlsx",
)


class StagePolicyError(RuntimeError):
    """阶段输入或输出不满足提交策略。"""


def _utc_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def stage_manifest_path(stage: str) -> Path:
    if stage not in STAGE_ORDER:
        raise ValueError(f"不支持的牧场组阶段: {stage}")
    return STAGE_MANIFEST_DIRECTORY / f"{stage}.json"


def _is_managed_file(path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    name = path.name
    if name.startswith("."):
        return False
    lowered = name.casefold()
    return not any(lowered.endswith(suffix) for suffix in _IGNORED_SUFFIXES)


def _existing(root: Path, relative_paths: Iterable[Path]) -> list[Path]:
    return [
        root / relative
        for relative in relative_paths
        if _is_managed_file(root / relative)
    ]


def _local_bundle_inputs(root: Path) -> list[Path]:
    bundle = root / "raw_data" / "input_bundle"
    if not bundle.is_dir():
        return []
    return sorted(
        (
            path
            for path in bundle.rglob("*")
            if _is_managed_file(path)
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _genomic_raw_inputs(root: Path) -> list[Path]:
    genomic = root / "raw_data" / "genomic_data"
    if not genomic.is_dir():
        return []
    return sorted(
        (
            path
            for path in genomic.iterdir()
            if _is_managed_file(path)
        ),
        key=lambda path: path.name,
    )


def _analysis_outputs(root: Path) -> list[Path]:
    outputs = _existing(root, ANALYSIS_FIXED_FILES)
    directory = root / "analysis_results"
    for pattern in ANALYSIS_LATEST_PATTERNS:
        candidates = [
            path
            for path in directory.glob(pattern)
            if _is_managed_file(path)
        ]
        if candidates:
            outputs.append(
                max(candidates, key=lambda path: path.stat().st_mtime_ns)
            )
    return sorted(
        dict.fromkeys(outputs),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _data_outputs(root: Path, source_kind: str) -> list[Path]:
    relative_paths = [
        Path("standardized_data") / "processed_cow_data.xlsx"
    ]
    if (root / "raw_data" / "breeding_records.xlsx").is_file():
        relative_paths.append(
            Path("standardized_data") / "processed_breeding_data.xlsx"
        )
    if (root / "raw_data" / "semen_inventory.xlsx").is_file():
        relative_paths.append(
            Path("standardized_data") / "processed_bull_data.xlsx"
        )
    if source_kind == "local":
        relative_paths.append(
            Path("standardized_data") / "local_data_commit.json"
        )
    return _existing(root, relative_paths)


def _all_analysis_managed_outputs(root: Path) -> list[Path]:
    outputs = _existing(root, ANALYSIS_FIXED_FILES)
    directory = root / "analysis_results"
    for pattern in ANALYSIS_LATEST_PATTERNS:
        outputs.extend(
            path
            for path in directory.glob(pattern)
            if _is_managed_file(path)
        )
    return sorted(
        dict.fromkeys(outputs),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _all_single_farm_reports(root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in (root / "reports").glob(
                "育种分析综合报告_*.xlsx"
            )
            if _is_managed_file(path)
        ),
        key=lambda path: path.stat().st_mtime_ns,
    )


def _artifact_map(
    root: Path,
    paths: Iterable[Path],
) -> Dict[str, Path]:
    result: Dict[str, Path] = {}
    for path in paths:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
        result[relative] = path
    return result


def _relative_names(root: Path, paths: Iterable[Path]) -> list[str]:
    return [
        path.resolve().relative_to(root.resolve()).as_posix()
        for path in paths
    ]


def _load_child_identity(root: Path) -> Dict[str, str]:
    metadata_path = root / "project_metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StagePolicyError("无法读取牧场子项目身份信息") from exc
    if metadata.get("project_type") != "group_child":
        raise StagePolicyError("当前目录不是牧场组子项目")
    farms = metadata.get("farms")
    if not isinstance(farms, list) or len(farms) != 1:
        raise StagePolicyError("牧场组子项目必须且只能包含一个牧场")
    return {
        "task_id": str(metadata.get("group_task_id") or "").strip(),
        "farm_code": str(
            metadata.get("group_farm_code")
            or farms[0].get("code")
            or farms[0].get("farmCode")
            or ""
        ).strip(),
        "data_source": str(
            metadata.get("data_source")
            or metadata.get("interface_source")
            or farms[0].get("source_system")
            or ""
        ).strip(),
        "source_kind": str(
            farms[0].get("source_kind") or "api"
        ).strip(),
    }


def _analysis_configuration() -> Dict[str, Any]:
    """取得自动分析实际使用的性状和权重，不保存配置文件路径。"""
    from core.auto_analysis_runner import (
        DEFAULT_TRAITS,
        DEFAULT_WEIGHT,
        DEFECT_GENES,
    )
    from core.breeding_calc.index_calculation import (
        IndexCalculation,
        TRAIT_SD,
    )
    from core.data.update_manager import get_local_db_version

    weights = IndexCalculation().load_weights()
    selected_weight = weights.get(DEFAULT_WEIGHT)
    if not isinstance(selected_weight, Mapping) or not selected_weight:
        raise StagePolicyError(f"无法读取自动分析权重: {DEFAULT_WEIGHT}")
    return {
        "traits": [str(value) for value in DEFAULT_TRAITS],
        "weight_name": str(DEFAULT_WEIGHT),
        "weight_values": {
            str(key): float(value)
            for key, value in sorted(
                selected_weight.items(),
                key=lambda item: str(item[0]),
            )
        },
        "trait_sd": {
            str(key): float(value)
            for key, value in sorted(
                TRAIT_SD.items(),
                key=lambda item: str(item[0]),
            )
        },
        "defect_genes": [str(value) for value in DEFECT_GENES],
        "bull_library_version": get_local_db_version(),
        "analysis_calendar_year": datetime.now().year,
    }


def _latest_report(root: Path) -> Optional[Path]:
    reports = _all_single_farm_reports(root)
    return max(reports, key=lambda path: path.stat().st_mtime_ns) if reports else None


def _definition(
    root_path: Path,
    stage: str,
    *,
    report_path: Optional[Path] = None,
) -> Dict[str, Any]:
    root = Path(root_path).resolve()
    identity = _load_child_identity(root)
    if stage not in STAGE_ORDER:
        raise ValueError(f"不支持的牧场组阶段: {stage}")

    raw_files = (
        _existing(root, REGENERATED_RAW_DATA_FILES)
        + _local_bundle_inputs(root)
    )
    standardized_files = _existing(root, STANDARDIZED_DATA_FILES)
    analysis_files = _analysis_outputs(root)

    if stage == "data":
        inputs = raw_files
        outputs = _data_outputs(root, identity["source_kind"])
        required = root / "standardized_data" / "processed_cow_data.xlsx"
        if required not in outputs:
            raise StagePolicyError("数据阶段缺少 processed_cow_data.xlsx")
        config: Dict[str, Any] = {
            "policy_revision": STAGE_POLICY_REVISIONS[stage],
            "data_source": identity["data_source"],
            "source_kind": identity["source_kind"],
            "raw_input_set": _relative_names(root, inputs),
            "standardized_output_set": _relative_names(root, outputs),
        }
    elif stage == "analysis":
        inputs = standardized_files
        outputs = analysis_files
        missing = [
            path.relative_to(root).as_posix()
            for path in (root / relative for relative in REQUIRED_ANALYSIS_OUTPUTS)
            if path not in outputs
        ]
        if missing:
            raise StagePolicyError(
                "分析阶段缺少核心结果: " + "、".join(missing)
            )
        config = {
            "policy_revision": STAGE_POLICY_REVISIONS[stage],
            "data_source": identity["data_source"],
            "standardized_input_set": _relative_names(root, inputs),
            "analysis_output_set": _relative_names(root, outputs),
            "capabilities": _capabilities(root),
            **_analysis_configuration(),
        }
    else:
        inputs = standardized_files + analysis_files
        selected_report = Path(report_path).resolve() if report_path else _latest_report(root)
        if selected_report is None or not selected_report.is_file():
            raise StagePolicyError("单牧场 Excel 阶段缺少正式报告")
        try:
            selected_report.relative_to((root / "reports").resolve())
        except ValueError as exc:
            raise StagePolicyError("单牧场 Excel 报告不在子项目 reports 目录") from exc
        outputs = [selected_report]
        config = {
            "policy_revision": STAGE_POLICY_REVISIONS[stage],
            "data_source": identity["data_source"],
            "standardized_input_set": _relative_names(
                root, standardized_files
            ),
            "analysis_input_set": _relative_names(root, analysis_files),
            "report_kind": "single_farm_excel",
            "report_relative_path": selected_report.relative_to(
                root
            ).as_posix(),
            "capabilities": _capabilities(root),
        }

    if not inputs:
        raise StagePolicyError(f"{stage} 阶段没有可核验的直接输入")
    if not outputs:
        raise StagePolicyError(f"{stage} 阶段没有可核验的正式输出")

    cow_sources: Dict[str, Any] = {}
    for path in inputs + outputs:
        relative = path.resolve().relative_to(root).as_posix()
        if relative in {
            "standardized_data/processed_cow_data.xlsx",
            "analysis_results/processed_cow_data_key_traits_final.xlsx",
            "analysis_results/processed_index_cow_index_scores.xlsx",
        }:
            cow_sources[relative] = {"columns": _COW_ID_COLUMNS}
        elif relative == "standardized_data/processed_breeding_data.xlsx":
            cow_sources[relative] = {"columns": ("耳号", "cow_id")}
        elif relative == "standardized_data/processed_bull_data.xlsx":
            cow_sources[relative] = {
                "columns": ("bull_id", "公牛号", "NAAB")
            }

    return {
        "identity": identity,
        "inputs": _artifact_map(root, inputs),
        "outputs": _artifact_map(root, outputs),
        "config": config,
        "cow_id_sources": cow_sources,
    }


def _capabilities(root: Path) -> Dict[str, bool]:
    standardized = root / "standardized_data"
    return {
        "breeding": (
            standardized / "processed_breeding_data.xlsx"
        ).is_file(),
        "candidate_bulls": (
            standardized / "processed_bull_data.xlsx"
        ).is_file(),
        "genomic": (
            standardized / "processed_genomic_data.xlsx"
        ).is_file(),
        "body_conformation": (
            standardized / "processed_body_conformation_data.xlsx"
        ).is_file(),
    }


def commit_child_stage(
    root_path: Path,
    stage: str,
    *,
    expected_task_id: Optional[str] = None,
    expected_farm_code: Optional[str] = None,
    report_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """在全部产物完成后原子提交阶段清单。"""
    root = Path(root_path).resolve()
    definition = _definition(root, stage, report_path=report_path)
    identity = definition["identity"]
    if expected_task_id and identity["task_id"] != str(expected_task_id):
        raise StagePolicyError("阶段 task_id 与父任务不一致")
    if expected_farm_code and identity["farm_code"] != str(expected_farm_code):
        raise StagePolicyError("阶段牧场编号与父任务不一致")
    return commit_stage_manifest(
        root,
        stage_manifest_path(stage),
        task_id=identity["task_id"],
        farm_code=identity["farm_code"],
        stage=stage,
        config=definition["config"],
        inputs=definition["inputs"],
        outputs=definition["outputs"],
        cow_id_sources=definition["cow_id_sources"],
    )


def validate_child_stage(
    root_path: Path,
    stage: str,
    *,
    expected_task_id: Optional[str] = None,
    expected_farm_code: Optional[str] = None,
    verification: str = "full",
) -> Dict[str, Any]:
    """验证当前阶段清单、输入、输出、身份和算法口径。"""
    root = Path(root_path).resolve()
    try:
        definition = _definition(root, stage)
    except Exception as exc:
        return {
            "valid": False,
            "status": "stage_definition_invalid",
            "issues": [
                {
                    "code": "stage_definition_invalid",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            ],
        }
    identity = definition["identity"]
    return validate_stage_manifest(
        root,
        stage_manifest_path(stage),
        expected_task_id=expected_task_id or identity["task_id"],
        expected_farm_code=expected_farm_code or identity["farm_code"],
        expected_stage=stage,
        expected_config=definition["config"],
        verification=verification,
    )


def invalidate_stage_and_downstream(
    root_path: Path,
    stage: str,
) -> list[Path]:
    """开始新尝试前归档当前阶段及所有下游正式清单。

    旧结果文件不会删除；即使新尝试中途退出，也不会把旧清单误当成新结果。
    """
    if stage not in STAGE_ORDER:
        raise ValueError(f"不支持的牧场组阶段: {stage}")
    root = Path(root_path).resolve()
    history = root / STAGE_MANIFEST_DIRECTORY / "history"
    archived: list[Path] = []
    attempt_id = f"{_utc_compact()}_{os.getpid()}"

    # 先把本阶段上一轮产物移出正式目录。不能删除，也不能让本轮可选
    # 分析失败后继续拾取上一轮同名或时间戳结果。
    if stage == "data":
        identity = _load_child_identity(root)
        previous_outputs = _data_outputs(
            root,
            identity["source_kind"],
        )
    elif stage == "analysis":
        previous_outputs = _all_analysis_managed_outputs(root)
    else:
        previous_outputs = _all_single_farm_reports(root)
    output_history = (
        root
        / "group_store"
        / "stage_output_history"
        / stage
        / attempt_id
    )
    for source in previous_outputs:
        relative = source.relative_to(root)
        target = output_history / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)
        archived.append(target)

    if stage == "data":
        for source in _existing(root, REGENERATED_RAW_DATA_FILES):
            relative = source.relative_to(root)
            target = output_history / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
            archived.append(target)

    start = STAGE_ORDER.index(stage)
    for downstream in STAGE_ORDER[start:]:
        current = root / stage_manifest_path(downstream)
        if not current.is_file():
            continue
        history.mkdir(parents=True, exist_ok=True)
        target = history / (
            f"{downstream}_{attempt_id}.json"
        )
        os.replace(current, target)
        archived.append(target)
    return archived


def copy_manifest_snapshot(
    root_path: Path,
    stage: str,
    destination: Path,
) -> Path:
    """复制一个已验证清单供汇总批次冻结使用。"""
    root = Path(root_path).resolve()
    validation = validate_child_stage(root, stage)
    if not validation.get("valid"):
        raise StagePolicyError(f"{stage} 阶段清单无效，不能冻结")
    source = root / stage_manifest_path(stage)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
