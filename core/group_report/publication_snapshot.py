"""牧场组汇总结果发布前后的稳定输入快照。

快照只记录 SQLite 任务身份、选择版本、执行 attempt 和阶段 manifest
摘要，不复制业务明细、配置原文或任务 metadata。正式报告应先生成
``before`` 快照，在临时位置完成报告后重算 ``after`` 快照；两者任一
稳定字段不同，都不得把临时报告提升为正式结果。
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Union

from core.group_tasks.stage_manifest import (
    stream_sha256,
    validate_stage_manifest,
)
from utils.group_task_store import GROUP_TASK_STAGES, GroupTaskStore


SNAPSHOT_SCHEMA_VERSION = 1
SNAPSHOT_KIND = "group_summary_publication_inputs"
COMPLETED_STAGE_STATUSES = {"completed", "completed_with_warning"}
PathLike = Union[str, os.PathLike]
ManifestResolver = Callable[[Dict[str, Any], str, Path], PathLike]

_DEFAULT_MANIFEST_PATHS = {
    "data": (
        Path("group_store") / "stage_manifests" / "data.json",
        Path("standardized_data") / ".manifests" / "data.json",
        Path("raw_data") / ".manifests" / "data.json",
        Path(".manifests") / "data.json",
    ),
    "analysis": (
        Path("group_store") / "stage_manifests" / "analysis.json",
        Path("analysis_results") / ".manifests" / "analysis.json",
        Path(".manifests") / "analysis.json",
    ),
    "child_excel": (
        Path("group_store") / "stage_manifests" / "child_excel.json",
        Path("reports") / ".manifests" / "child_excel.json",
        Path(".manifests") / "child_excel.json",
    ),
}


class PublicationSnapshotError(RuntimeError):
    """无法构造可信发布快照。"""


class PublicationInputsChangedError(PublicationSnapshotError):
    """报告生成前后输入发生变化。"""

    def __init__(self, comparison: Dict[str, Any]):
        self.comparison = comparison
        codes = "、".join(
            str(change.get("code") or "input_changed")
            for change in comparison.get("changes", [])[:5]
        )
        super().__init__(
            "牧场组汇总输入在生成期间发生变化，拒绝正式发布"
            + (f"：{codes}" if codes else "")
        )


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    descriptor_open = True
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor_open = False
            json.dump(
                payload,
                stream,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        try:
            directory_descriptor = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except OSError:
            pass
    finally:
        if descriptor_open:
            try:
                os.close(descriptor)
            except OSError:
                pass
        temporary.unlink(missing_ok=True)


def _safe_relative_path(value: Any, *, label: str) -> Path:
    text = str(value or "").strip()
    if not text or "\\" in text:
        raise PublicationSnapshotError(f"{label}不是有效相对路径")
    pure = PurePosixPath(text)
    if pure.is_absolute() or any(
        part in {"", ".", ".."} for part in pure.parts
    ):
        raise PublicationSnapshotError(f"{label}包含不安全路径")
    return Path(*pure.parts)


def _safe_child_path(project_path: Path, task: Dict[str, Any]) -> Path:
    relative = _safe_relative_path(
        task.get("relative_path"),
        label=f"任务 {task.get('task_id', '')} 子项目路径",
    )
    candidate = project_path / relative
    if candidate.is_symlink():
        raise PublicationSnapshotError("子项目不能是符号链接")
    child = candidate.resolve()
    farm_projects = (project_path / "farm_projects").resolve()
    try:
        child.relative_to(farm_projects)
    except ValueError as exc:
        raise PublicationSnapshotError("子项目超出 farm_projects 目录") from exc
    if not child.is_dir():
        raise PublicationSnapshotError("子项目不存在")
    return child


def _path_inside(root: Path, value: PathLike, *, label: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved_parent = candidate.parent.resolve()
    resolved = resolved_parent / candidate.name
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise PublicationSnapshotError(f"{label}超出子项目目录") from exc
    if candidate.is_symlink() or resolved.is_symlink():
        raise PublicationSnapshotError(f"{label}不能是符号链接")
    return resolved


def _configured_manifest_candidates(
    task: Dict[str, Any],
    stage: str,
) -> list[PathLike]:
    metadata = task.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    candidates: list[PathLike] = []
    for key in (
        f"{stage}_manifest_path",
        f"{stage}_manifest",
        "stage_manifest_paths",
    ):
        value = metadata.get(key)
        if key == "stage_manifest_paths" and isinstance(value, Mapping):
            value = value.get(stage)
        if isinstance(value, (str, os.PathLike)) and str(value).strip():
            candidates.append(value)

    artifacts = metadata.get(f"{stage}_artifacts")
    if isinstance(artifacts, Mapping):
        for key, value in artifacts.items():
            if (
                "manifest" in str(key).casefold()
                and isinstance(value, (str, os.PathLike))
                and str(value).strip()
            ):
                candidates.append(value)

    stage_row = task.get("stages", {}).get(stage, {})
    output_path = stage_row.get("output_path")
    if (
        isinstance(output_path, str)
        and output_path.strip()
        and output_path.casefold().endswith(".json")
    ):
        candidates.append(output_path)
    return candidates


def _existing_unique_candidate(
    child_path: Path,
    candidates: Sequence[PathLike],
    *,
    task_id: str,
    stage: str,
) -> Optional[Path]:
    existing = []
    seen = set()
    for value in candidates:
        candidate = _path_inside(
            child_path,
            value,
            label=f"任务 {task_id} 阶段 {stage} manifest",
        )
        key = candidate.as_posix()
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file():
            existing.append(candidate)
    if len(existing) > 1:
        raise PublicationSnapshotError(
            f"任务 {task_id} 阶段 {stage} 存在多个 manifest，无法确定版本"
        )
    return existing[0] if existing else None


def _resolve_manifest_path(
    task: Dict[str, Any],
    stage: str,
    child_path: Path,
    resolver: Optional[ManifestResolver],
) -> Path:
    task_id = str(task.get("task_id") or "")
    if resolver is not None:
        resolved = _path_inside(
            child_path,
            resolver(task, stage, child_path),
            label=f"任务 {task_id} 阶段 {stage} manifest",
        )
        if not resolved.is_file():
            raise PublicationSnapshotError(
                f"任务 {task_id} 阶段 {stage} manifest 不存在"
            )
        return resolved

    explicit = _existing_unique_candidate(
        child_path,
        _configured_manifest_candidates(task, stage),
        task_id=task_id,
        stage=stage,
    )
    if explicit is not None:
        return explicit
    default = _existing_unique_candidate(
        child_path,
        _DEFAULT_MANIFEST_PATHS[stage],
        task_id=task_id,
        stage=stage,
    )
    if default is None:
        raise PublicationSnapshotError(
            f"任务 {task_id} 阶段 {stage} 缺少已提交 manifest"
        )
    return default


def _required_stage_names(
    task: Dict[str, Any],
    required_stages: Optional[Sequence[str]],
) -> list[str]:
    stages = task.get("stages")
    if not isinstance(stages, dict):
        raise PublicationSnapshotError(
            f"任务 {task.get('task_id', '')} 缺少阶段状态"
        )
    if required_stages is None:
        names = [
            stage
            for stage in GROUP_TASK_STAGES
            if bool(stages.get(stage, {}).get("required"))
        ]
    else:
        names = list(dict.fromkeys(str(stage) for stage in required_stages))
        unknown = set(names) - set(GROUP_TASK_STAGES)
        if unknown:
            raise ValueError(
                f"不支持的发布阶段：{', '.join(sorted(unknown))}"
            )
    if not names:
        raise PublicationSnapshotError("纳入汇总的任务没有必需阶段")
    return names


def _database_state(
    store: GroupTaskStore,
    required_stages: Optional[Sequence[str]],
) -> Dict[str, Any]:
    revision_before = store.get_selection_revision()
    tasks = store.list_tasks(with_stages=True)
    revision_after = store.get_selection_revision()
    if revision_before != revision_after:
        raise PublicationSnapshotError("读取任务时牧场选择范围发生变化")

    included = [task for task in tasks if task["included_in_summary"]]
    if not included:
        raise PublicationSnapshotError("没有纳入汇总范围的牧场任务")
    included_entries = []
    for task in included:
        stage_names = _required_stage_names(task, required_stages)
        included_entries.append(
            {
                "task_id": str(task["task_id"]),
                "farm_code": str(task.get("farm_code") or ""),
                "farm_name": str(task.get("farm_name") or ""),
                "relative_path": str(task.get("relative_path") or ""),
                "source_kind": str(task.get("source_kind") or ""),
                "source_system": str(task.get("source_system") or ""),
                "status": str(task.get("status") or ""),
                "attempt": int(task.get("attempt", 0) or 0),
                "stages": [
                    {
                        "stage": stage,
                        "required": bool(
                            task["stages"][stage].get("required")
                        ),
                        "status": str(
                            task["stages"][stage].get("status") or ""
                        ),
                        "attempt": int(
                            task["stages"][stage].get("attempt", 0) or 0
                        ),
                        "detail_count": task["stages"][stage].get(
                            "detail_count"
                        ),
                    }
                    for stage in stage_names
                ],
            }
        )
    return {
        "selection_revision": int(revision_before),
        "included_task_ids": [
            str(task["task_id"]) for task in included
        ],
        "excluded_task_ids": [
            str(task["task_id"])
            for task in tasks
            if not task["included_in_summary"]
        ],
        "included_tasks": included_entries,
        "_raw_tasks": included,
    }


def _public_database_state(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in state.items()
        if not key.startswith("_")
    }


def _capture_stage(
    project_path: Path,
    child_path: Path,
    task: Dict[str, Any],
    stage: str,
    resolver: Optional[ManifestResolver],
    verification: str,
) -> Dict[str, Any]:
    task_id = str(task.get("task_id") or "")
    farm_code = str(task.get("farm_code") or "")
    stage_row = task["stages"][stage]
    status = str(stage_row.get("status") or "")
    if status not in COMPLETED_STAGE_STATUSES:
        raise PublicationSnapshotError(
            f"任务 {task_id} 阶段 {stage} 尚未完成，状态为 {status}"
        )

    manifest_path = _resolve_manifest_path(
        task,
        stage,
        child_path,
        resolver,
    )
    before = manifest_path.stat()
    before_sha256 = stream_sha256(manifest_path)
    validation = validate_stage_manifest(
        child_path,
        manifest_path,
        expected_task_id=task_id,
        expected_farm_code=farm_code,
        expected_stage=stage,
        verification=verification,
    )
    after_sha256 = stream_sha256(manifest_path)
    after = manifest_path.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or before_sha256 != after_sha256
    ):
        raise PublicationSnapshotError(
            f"任务 {task_id} 阶段 {stage} manifest 在扫描期间发生变化"
        )
    if not validation.get("valid"):
        raise PublicationSnapshotError(
            f"任务 {task_id} 阶段 {stage} manifest 校验失败："
            f"{validation.get('status', 'invalid')}"
        )

    manifest = validation["manifest"]
    artifact_states = sorted(
        (
            {
                "logical_name": str(state.get("logical_name") or ""),
                "kind": str(state.get("kind") or ""),
                "relative_path": str(state.get("relative_path") or ""),
                "size_bytes": int(state.get("size_bytes", -1)),
                "mtime_ns": int(state.get("mtime_ns", -1)),
            }
            for state in validation.get("artifact_stats", [])
        ),
        key=lambda state: (
            state["kind"],
            state["relative_path"],
            state["logical_name"],
        ),
    )
    return {
        "stage": stage,
        "required": bool(stage_row.get("required")),
        "status": status,
        "attempt": int(stage_row.get("attempt", 0) or 0),
        "detail_count": stage_row.get("detail_count"),
        "manifest_relative_path": manifest_path.relative_to(
            project_path
        ).as_posix(),
        "manifest_sha256": before_sha256,
        "manifest_size_bytes": int(before.st_size),
        "config_fingerprint": str(
            manifest.get("config_fingerprint") or ""
        ),
        "input_count": len(manifest.get("inputs") or []),
        "output_count": len(manifest.get("outputs") or []),
        "artifact_states": artifact_states,
        "artifact_state_sha256": _fingerprint(artifact_states),
    }


def _capture_basis(
    project_path: Path,
    store: GroupTaskStore,
    required_stages: Optional[Sequence[str]],
    resolver: Optional[ManifestResolver],
    verification: str,
) -> Dict[str, Any]:
    before = _database_state(store, required_stages)
    raw_by_id = {
        str(task["task_id"]): task for task in before["_raw_tasks"]
    }
    task_entries = []
    for database_task in before["included_tasks"]:
        task_id = database_task["task_id"]
        if database_task["status"] not in COMPLETED_STAGE_STATUSES:
            raise PublicationSnapshotError(
                f"任务 {task_id} 尚未完成，状态为 "
                f"{database_task['status']}"
            )
        raw_task = raw_by_id[task_id]
        child_path = _safe_child_path(project_path, raw_task)
        stage_entries = [
            _capture_stage(
                project_path,
                child_path,
                raw_task,
                stage["stage"],
                resolver,
                verification,
            )
            for stage in database_task["stages"]
        ]
        task_entry = {
            key: value
            for key, value in database_task.items()
            if key != "stages"
        }
        task_entry["stages"] = stage_entries
        task_entries.append(task_entry)

    after = _database_state(store, required_stages)
    if _fingerprint(_public_database_state(before)) != _fingerprint(
        _public_database_state(after)
    ):
        raise PublicationSnapshotError(
            "扫描阶段 manifest 期间任务状态或选择范围发生变化"
        )
    return {
        "selection_revision": before["selection_revision"],
        "selection_scope": {
            "included_task_ids": before["included_task_ids"],
            "excluded_task_ids": before["excluded_task_ids"],
            "included_count": len(before["included_task_ids"]),
            "excluded_count": len(before["excluded_task_ids"]),
        },
        "tasks": task_entries,
    }


def _safe_snapshot_output_path(project_path: Path, output_path: PathLike) -> Path:
    candidate = Path(output_path)
    if not candidate.is_absolute():
        candidate = project_path / candidate
    resolved_parent = candidate.parent.resolve()
    target = resolved_parent / candidate.name
    try:
        target.relative_to(project_path.resolve())
    except ValueError as exc:
        raise PublicationSnapshotError(
            "发布快照输出路径超出牧场组项目"
        ) from exc
    if candidate.is_symlink() or target.is_symlink():
        raise PublicationSnapshotError("发布快照不能写入符号链接")
    return target


def capture_group_publication_snapshot(
    project_path: PathLike,
    *,
    output_path: Optional[PathLike] = None,
    required_stages: Optional[Sequence[str]] = None,
    manifest_resolver: Optional[ManifestResolver] = None,
    verification: str = "full",
) -> Dict[str, Any]:
    """重算当前发布输入并可原子写出稳定 JSON 快照。

    默认 ``full`` 用于报告生成前建立可信基线；报告生成后的
    :func:`recompute_and_compare_group_publication_snapshot` 固定使用
    ``stat``，并比较基线中每个产物的实际大小和修改时间摘要。
    """
    if verification not in {"full", "stat"}:
        raise ValueError("verification 只能是 'full' 或 'stat'")
    project = Path(project_path).resolve()
    database_path = project / "group_store" / "group_tasks.sqlite3"
    if not project.is_dir() or not database_path.is_file():
        raise PublicationSnapshotError("牧场组项目或任务状态库不存在")
    store = GroupTaskStore(database_path)
    basis = _capture_basis(
        project,
        store,
        required_stages,
        manifest_resolver,
        verification,
    )
    snapshot = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "kind": SNAPSHOT_KIND,
        "captured_at": _utc_now(),
        "basis_sha256": _fingerprint(basis),
        "basis": basis,
    }
    if output_path is not None:
        target = _safe_snapshot_output_path(project, output_path)
        _atomic_write_json(target, snapshot)
        result = dict(snapshot)
        result["snapshot_relative_path"] = target.relative_to(
            project
        ).as_posix()
        result["snapshot_file_sha256"] = stream_sha256(target)
        return result
    return snapshot


def _coerce_snapshot(value: Union[Mapping[str, Any], PathLike]) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        snapshot = dict(value)
    else:
        path = Path(value)
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PublicationSnapshotError("发布快照无法读取") from exc
    if snapshot.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise PublicationSnapshotError("发布快照版本不受支持")
    if snapshot.get("kind") != SNAPSHOT_KIND:
        raise PublicationSnapshotError("JSON 不是牧场组发布快照")
    basis = snapshot.get("basis")
    if not isinstance(basis, dict):
        raise PublicationSnapshotError("发布快照缺少稳定 basis")
    expected = str(snapshot.get("basis_sha256") or "")
    actual = _fingerprint(basis)
    if expected != actual:
        raise PublicationSnapshotError("发布快照 basis 摘要校验失败")
    return snapshot


def _task_map(basis: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(task.get("task_id") or ""): task
        for task in basis.get("tasks", [])
        if isinstance(task, dict)
    }


def compare_group_publication_snapshots(
    before: Union[Mapping[str, Any], PathLike],
    after: Union[Mapping[str, Any], PathLike],
) -> Dict[str, Any]:
    """比较两次稳定快照，返回可供 UI 展示的变化原因。"""
    first = _coerce_snapshot(before)
    second = _coerce_snapshot(after)
    first_basis = first["basis"]
    second_basis = second["basis"]
    changes = []

    if first_basis.get("selection_revision") != second_basis.get(
        "selection_revision"
    ):
        changes.append(
            {
                "code": "selection_revision_changed",
                "before": first_basis.get("selection_revision"),
                "after": second_basis.get("selection_revision"),
            }
        )
    if first_basis.get("selection_scope") != second_basis.get(
        "selection_scope"
    ):
        changes.append({"code": "selection_scope_changed"})

    first_tasks = _task_map(first_basis)
    second_tasks = _task_map(second_basis)
    for task_id in sorted(set(first_tasks) | set(second_tasks)):
        if task_id not in first_tasks:
            changes.append({"code": "task_added", "task_id": task_id})
            continue
        if task_id not in second_tasks:
            changes.append({"code": "task_removed", "task_id": task_id})
            continue
        if first_tasks[task_id] == second_tasks[task_id]:
            continue
        before_task = first_tasks[task_id]
        after_task = second_tasks[task_id]
        for field in (
            "farm_code",
            "farm_name",
            "relative_path",
            "source_kind",
            "source_system",
            "status",
            "attempt",
        ):
            if before_task.get(field) != after_task.get(field):
                changes.append(
                    {
                        "code": f"task_{field}_changed",
                        "task_id": task_id,
                    }
                )
        before_stages = {
            stage["stage"]: stage
            for stage in before_task.get("stages", [])
        }
        after_stages = {
            stage["stage"]: stage
            for stage in after_task.get("stages", [])
        }
        for stage in sorted(set(before_stages) | set(after_stages)):
            if before_stages.get(stage) == after_stages.get(stage):
                continue
            if stage not in before_stages:
                code = "stage_added"
            elif stage not in after_stages:
                code = "stage_removed"
            elif (
                before_stages[stage].get("manifest_sha256")
                != after_stages[stage].get("manifest_sha256")
            ):
                code = "stage_manifest_changed"
            elif (
                before_stages[stage].get("attempt")
                != after_stages[stage].get("attempt")
            ):
                code = "stage_attempt_changed"
            elif (
                before_stages[stage].get("artifact_state_sha256")
                != after_stages[stage].get("artifact_state_sha256")
            ):
                code = "stage_artifact_state_changed"
            else:
                code = "stage_state_changed"
            changes.append(
                {
                    "code": code,
                    "task_id": task_id,
                    "stage": stage,
                }
            )

    unchanged = (
        first["basis_sha256"] == second["basis_sha256"]
        and not changes
    )
    if not unchanged and not changes:
        changes.append({"code": "publication_basis_changed"})
    return {
        "unchanged": unchanged,
        "before_basis_sha256": first["basis_sha256"],
        "after_basis_sha256": second["basis_sha256"],
        "changes": changes,
    }


def recompute_and_compare_group_publication_snapshot(
    project_path: PathLike,
    before_snapshot: Union[Mapping[str, Any], PathLike],
    *,
    output_path: Optional[PathLike] = None,
    required_stages: Optional[Sequence[str]] = None,
    manifest_resolver: Optional[ManifestResolver] = None,
    raise_on_change: bool = True,
) -> Dict[str, Any]:
    """重算 after 快照并与 before 比较；默认变化即抛错。"""
    after = capture_group_publication_snapshot(
        project_path,
        output_path=output_path,
        required_stages=required_stages,
        manifest_resolver=manifest_resolver,
        verification="stat",
    )
    comparison = compare_group_publication_snapshots(
        before_snapshot,
        after,
    )
    result = {
        "after_snapshot": after,
        "comparison": comparison,
    }
    if raise_on_change and not comparison["unchanged"]:
        raise PublicationInputsChangedError(comparison)
    return result


__all__ = [
    "PublicationInputsChangedError",
    "PublicationSnapshotError",
    "SNAPSHOT_KIND",
    "SNAPSHOT_SCHEMA_VERSION",
    "capture_group_publication_snapshot",
    "compare_group_publication_snapshots",
    "recompute_and_compare_group_publication_snapshot",
]
