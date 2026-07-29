"""把在牧场组子项目中手动完成的结果提交回父任务。

用户可以从牧场组任务管理器进入单牧场子项目，再按需运行各分析页和
单场 Excel。这个路径不经过牧场组子进程，因此必须在可信的“分析/报告
成功”边界显式提交阶段清单；父任务不能仅凭目录里出现了某个文件猜测
阶段已经完成。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional


class ManualGroupStageBridgeError(RuntimeError):
    """手动子项目结果无法安全关联回父牧场组。"""


def _group_context(child_path: Path) -> Optional[Dict[str, Any]]:
    from utils.file_manager import FileManager

    child = Path(child_path).resolve()
    metadata = FileManager.load_project_metadata(child)
    if metadata.get("project_type") != "group_child":
        return None

    task_id = str(metadata.get("group_task_id") or "").strip()
    farm_code = str(metadata.get("group_farm_code") or "").strip()
    parent_reference = str(metadata.get("parent_group") or "").strip()
    if not task_id or not farm_code or not parent_reference:
        raise ManualGroupStageBridgeError("牧场组子项目身份信息不完整")

    parent = (child / parent_reference).resolve()
    parent_metadata = FileManager.load_project_metadata(parent)
    if parent_metadata.get("project_type") != "multi_farm_group":
        raise ManualGroupStageBridgeError("找不到有效的父牧场组项目")
    try:
        task = FileManager._resolve_group_task(parent_metadata, task_id)
    except KeyError as exc:
        raise ManualGroupStageBridgeError("父牧场组中找不到当前子任务") from exc
    expected_child = (parent / str(task.get("relative_path") or "")).resolve()
    if expected_child != child:
        raise ManualGroupStageBridgeError("父任务记录的子项目路径不一致")
    if str(task.get("farm_code") or "").strip() != farm_code:
        raise ManualGroupStageBridgeError("父子项目 API farmcode 不一致")

    return {
        "child": child,
        "parent": parent,
        "task_id": task_id,
        "farm_code": farm_code,
    }


def _manifest_artifacts(root: Path, manifest: Dict[str, Any]) -> Dict[str, str]:
    return {
        str(item.get("logical_name") or item.get("relative_path")): str(
            root / str(item.get("relative_path") or "")
        )
        for item in manifest.get("outputs", [])
        if item.get("relative_path")
    }


def commit_manual_group_analysis_if_ready(
    child_path: Path,
) -> Dict[str, Any]:
    """若当前项目是组内子项目，校验数据并提交手动分析阶段。"""
    context = _group_context(child_path)
    if context is None:
        return {"applicable": False, "committed": False}

    from core.group_tasks.stage_policy import (
        StagePolicyError,
        commit_child_stage,
        validate_child_stage,
    )
    from utils.file_manager import FileManager

    data_validation = validate_child_stage(
        context["child"],
        "data",
        expected_task_id=context["task_id"],
        expected_farm_code=context["farm_code"],
    )
    if not data_validation.get("valid"):
        raise StagePolicyError(
            "数据阶段提交清单无效，不能采纳手动分析结果"
        )
    manifest = commit_child_stage(
        context["child"],
        "analysis",
        expected_task_id=context["task_id"],
        expected_farm_code=context["farm_code"],
    )
    FileManager.update_group_stage(
        context["parent"],
        context["task_id"],
        "analysis",
        status="completed",
        artifacts=_manifest_artifacts(context["child"], manifest),
    )
    FileManager.update_group_task(
        context["parent"],
        context["task_id"],
        stage="手动分析已提交",
    )
    return {
        "applicable": True,
        "committed": True,
        "manifest": manifest,
    }


def commit_manual_group_excel_if_ready(
    child_path: Path,
    report_path: Path,
) -> Dict[str, Any]:
    """提交手动分析和单场 Excel，并同步父任务阶段状态。"""
    context = _group_context(child_path)
    if context is None:
        return {"applicable": False, "committed": False}

    from core.group_tasks.stage_policy import commit_child_stage
    from utils.file_manager import FileManager

    analysis = commit_manual_group_analysis_if_ready(context["child"])
    report = Path(report_path).resolve()
    manifest = commit_child_stage(
        context["child"],
        "child_excel",
        expected_task_id=context["task_id"],
        expected_farm_code=context["farm_code"],
        report_path=report,
    )
    artifacts = _manifest_artifacts(context["child"], manifest)
    FileManager.update_group_stage(
        context["parent"],
        context["task_id"],
        "child_excel",
        status="completed",
        artifacts=artifacts,
    )
    FileManager.update_group_task(
        context["parent"],
        context["task_id"],
        stage="手动分析和单场Excel已提交",
        progress=100,
        result={"excel_path": str(report)},
    )
    return {
        "applicable": True,
        "committed": True,
        "analysis": analysis,
        "manifest": manifest,
    }
