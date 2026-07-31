"""牧场组子项目的逐项分析状态清单。

完整报告是否可以汇总，仍以 ``data -> analysis -> child_excel`` 三个
原子阶段清单为唯一真源。本模块只负责把用户能在分析页面执行的八项
分析拆开展示，避免任务管理器只显示一个含义不清的“按需”。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from core.group_tasks.dataset_plan import normalize_dataset_selection
from core.group_tasks.feature_policy import (
    FEATURE_TITLES,
    manifest_declares_report_analysis_outputs,
    validate_recorded_feature_manifest,
)
from core.group_tasks.stage_policy import validate_child_stage


ANALYSIS_OPERATION_ORDER = (
    "cow_traits",
    "cow_index",
    "cow_self_inbreeding",
    "bull_traits",
    "bull_index",
    "candidate_inbreeding",
    "mated_bull_traits",
    "mated_inbreeding",
)

ANALYSIS_SHORT_TITLES = {
    "cow_traits": "母牛性状",
    "cow_index": "母牛指数",
    "cow_self_inbreeding": "母牛近交",
    "bull_traits": "备选公牛性状",
    "bull_index": "备选公牛指数",
    "candidate_inbreeding": "备选公牛近交",
    "mated_bull_traits": "已配公牛性状",
    "mated_inbreeding": "已配公牛近交",
}

# 这两项是当前完整 Excel analysis 阶段的核心必需结果。其它项目在
# 对应数据存在时会由自动化生成尽量完成，但失败不会伪装成“必需结果
# 已完成”，也不会把没有公牛/配种数据的牧场永久卡死。
CORE_REPORT_OPERATIONS = frozenset({"cow_traits", "cow_index"})


def _analysis_manifest_validation(
    root: Path,
    *,
    expected_task_id: str,
    expected_farm_code: str,
    verification: str,
) -> dict[str, Any]:
    """轻量核验已提交的完整分析清单。

    任务管理器打开时使用 ``stat``，避免几十个牧场反复读取大型 Excel。
    最终汇总仍会走 ``validate_child_stage`` 的完整配置和哈希校验。
    """
    return validate_child_stage(
        root,
        "analysis",
        expected_task_id=expected_task_id or None,
        expected_farm_code=expected_farm_code or None,
        verification=verification,
    )


def _availability(
    root: Path,
    operation: str,
    selection: Mapping[str, bool],
) -> tuple[str, str]:
    """返回 applicable、pending_data 或 not_applicable。"""
    standardized = root / "standardized_data"
    cow_file = standardized / "processed_cow_data.xlsx"
    bull_file = standardized / "processed_bull_data.xlsx"
    breeding_file = standardized / "processed_breeding_data.xlsx"

    if not selection["herd"]:
        return "not_applicable", "未选择牛群/系谱数据"

    if operation in {
        "cow_traits",
        "cow_index",
        "cow_self_inbreeding",
    }:
        if not cow_file.is_file():
            return "pending_data", "等待标准化母牛数据"
        return "applicable", ""

    if operation in {
        "bull_traits",
        "bull_index",
        "candidate_inbreeding",
    }:
        if not bull_file.is_file():
            return "not_applicable", "未上传备选公牛数据"
        if operation == "candidate_inbreeding" and not cow_file.is_file():
            return "pending_data", "等待标准化母牛数据"
        return "applicable", ""

    if not selection["breeding"]:
        return "not_applicable", "创建项目时未选择配种记录"
    if not breeding_file.is_file():
        return "not_applicable", "该牧场没有可用配种记录"
    if operation == "mated_inbreeding" and not cow_file.is_file():
        return "pending_data", "等待标准化母牛数据"
    return "applicable", ""


def resolve_child_analysis_status(
    child_path: Path | str,
    *,
    expected_task_id: str = "",
    expected_farm_code: str = "",
    dataset_selection: Mapping[str, Any] | None = None,
    verification: str = "stat",
) -> dict[str, Any]:
    """返回一个牧场八项分析的完成、未完成和按需状态。

    “已完成”只接受两类可复核证据：

    1. 有效的完整自动分析阶段清单，且该分析的正式输出被清单登记；
    2. 有效的页面功能清单，且当前直接输入集合没有变化。

    仅有同名 Excel 文件不算完成。
    """
    if verification not in {"stat", "full"}:
        raise ValueError("verification 只能是 'stat' 或 'full'")

    root = Path(child_path).resolve()
    selection = normalize_dataset_selection(dataset_selection)
    analysis_validation = _analysis_manifest_validation(
        root,
        expected_task_id=str(expected_task_id or ""),
        expected_farm_code=str(expected_farm_code or ""),
        verification=verification,
    )

    entries: list[dict[str, Any]] = []
    for operation in ANALYSIS_OPERATION_ORDER:
        availability, reason = _availability(
            root,
            operation,
            selection,
        )
        required = operation in CORE_REPORT_OPERATIONS
        entry = {
            "operation": operation,
            "title": FEATURE_TITLES[operation],
            "short_title": ANALYSIS_SHORT_TITLES[operation],
            "required_for_report": required,
            "state": "not_applicable",
            "source": "",
            "reason": reason,
        }

        if availability == "not_applicable":
            entries.append(entry)
            continue

        if availability == "pending_data":
            entry["state"] = "pending"
            entries.append(entry)
            continue

        if manifest_declares_report_analysis_outputs(
            analysis_validation,
            operation,
        ):
            entry.update(
                state="completed",
                source="complete_report",
                reason="已纳入有效的完整报告分析阶段",
            )
            entries.append(entry)
            continue

        feature_validation = validate_recorded_feature_manifest(
            root,
            operation,
            expected_task_id=str(expected_task_id or ""),
            expected_farm_code=str(expected_farm_code or ""),
            verification=verification,
        )
        if feature_validation.get("valid"):
            entry.update(
                state="completed",
                source="page_feature",
                reason="已按上次页面参数完成并通过产物校验",
            )
        else:
            entry.update(
                state="pending",
                reason=(
                    "尚无有效分析结果"
                    if feature_validation.get("status")
                    == "manifest_missing"
                    else "现有结果已失效或与当前输入不一致"
                ),
            )
        entries.append(entry)

    completed = [
        entry for entry in entries if entry["state"] == "completed"
    ]
    pending = [entry for entry in entries if entry["state"] == "pending"]
    not_applicable = [
        entry for entry in entries if entry["state"] == "not_applicable"
    ]
    applicable_count = len(completed) + len(pending)
    return {
        "entries": entries,
        "completed": completed,
        "pending": pending,
        "not_applicable": not_applicable,
        "completed_count": len(completed),
        "pending_count": len(pending),
        "not_applicable_count": len(not_applicable),
        "applicable_count": applicable_count,
        "analysis_stage_valid": bool(analysis_validation.get("valid")),
        "analysis_stage_status": str(
            analysis_validation.get("status") or "unknown"
        ),
    }


def format_analysis_status_cells(
    inventory: Mapping[str, Any],
) -> dict[str, str]:
    """生成任务表单元格短文案；完整名称与原因由 tooltip 展示。"""

    def entry_titles(entries: list[Mapping[str, Any]]) -> str:
        return "、".join(
            str(entry.get("short_title") or entry.get("title") or "")
            for entry in entries
            if str(
                entry.get("short_title") or entry.get("title") or ""
            )
        )

    completed_entries = list(inventory.get("completed", []))
    report_completed = [
        entry
        for entry in completed_entries
        if entry.get("source") == "complete_report"
    ]
    page_completed = [
        entry
        for entry in completed_entries
        if entry.get("source") != "complete_report"
    ]
    completed_parts = []
    if report_completed:
        completed_parts.append(
            "报告：" + entry_titles(report_completed)
        )
    if page_completed:
        completed_parts.append(
            "页面：" + entry_titles(page_completed)
        )

    pending_entries = list(inventory.get("pending", []))
    required_pending = [
        entry
        for entry in pending_entries
        if entry.get("required_for_report")
    ]
    optional_pending = [
        entry
        for entry in pending_entries
        if not entry.get("required_for_report")
    ]
    pending_parts = []
    if required_pending:
        pending_parts.append(
            "必需：" + entry_titles(required_pending)
        )
    if optional_pending:
        pending_parts.append(
            "可选：" + entry_titles(optional_pending)
        )

    completed_count = int(inventory.get("completed_count", 0) or 0)
    applicable_count = int(inventory.get("applicable_count", 0) or 0)
    return {
        "progress": f"{completed_count}/{applicable_count}",
        "completed": "；".join(completed_parts) or "暂无",
        "pending": "；".join(pending_parts) or "无",
        "not_applicable": (
            entry_titles(list(inventory.get("not_applicable", [])))
            or "无"
        ),
    }


def analysis_status_tooltip(
    entries: list[Mapping[str, Any]],
    *,
    empty: str,
) -> str:
    if not entries:
        return empty
    lines = []
    for entry in entries:
        title = str(entry.get("title") or "")
        reason = str(entry.get("reason") or "")
        label = "完整报告必需" if entry.get("required_for_report") else "按数据可选"
        lines.append(f"{title}（{label}）：{reason}")
    return "\n".join(lines)
