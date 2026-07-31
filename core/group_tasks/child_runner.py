"""在独立 Python 进程中执行一个牧场的分析或单场 Excel 阶段。

命令行协议::

    python -m core.group_tasks.child_runner /absolute/path/to/request.json

请求文件只接受任务身份、子项目路径和待执行阶段，不接受任何凭据。标准
输出严格使用逐行 JSON，便于桌面端父进程读取；旧分析代码偶尔产生的
``print`` 输出会被丢弃，避免破坏协议或把业务数据带到进程间日志。
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, TextIO


REQUEST_SCHEMA_VERSION = 1
MAX_REQUEST_BYTES = 64 * 1024
ALLOWED_REQUEST_FIELDS = {
    "schema_version",
    "task_id",
    "farm_code",
    "project_path",
    "stages",
    "service_staff",
}
REQUIRED_REQUEST_FIELDS = ALLOWED_REQUEST_FIELDS - {"service_staff"}
SUPPORTED_STAGES = ("analysis", "child_excel")
ESSENTIAL_ANALYSIS_ITEMS = {"母牛性状分析", "母牛指数排名"}
ANALYSIS_ARTIFACTS = (
    Path("analysis_results") / "processed_cow_data_key_traits_final.xlsx",
    Path("analysis_results") / "processed_index_cow_index_scores.xlsx",
    Path("analysis_results") / "关键育种性状分析结果.xlsx",
    Path("analysis_results") / "系谱识别分析结果.xlsx",
)


class ChildRequestError(RuntimeError):
    """子进程请求不合法或不属于指定牧场组。"""


class ChildExecutionError(RuntimeError):
    """子任务执行完成，但必需产物不完整。"""


@dataclass(frozen=True)
class ValidatedChildRequest:
    """已经与父组任务描述交叉核验的执行请求。"""

    task_id: str
    farm_code: str
    farm_name: str
    project_path: Path
    parent_group_path: Path
    data_source: str
    dataset_selection: Dict[str, bool]
    stages: tuple[str, ...]
    service_staff: str


class JsonLineEmitter:
    """只向指定流输出一行一个 JSON 对象。"""

    def __init__(self, stream: TextIO):
        self.stream = stream

    def emit(self, event_type: str, **payload: Any) -> None:
        event = {"type": str(event_type), **payload}
        self.stream.write(
            json.dumps(
                event,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        )
        self.stream.flush()


class _DiscardingTextIO(io.TextIOBase):
    """吞掉旧模块的标准输出，同时满足常见的文本流接口。"""

    encoding = "utf-8"

    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        return None


def _safe_error_message(value: Any, limit: int = 2000) -> str:
    """清理异常中的常见凭据形态，不回显请求原文。"""

    text = str(value or "").replace("\r", " ").replace("\n", " ")
    substitutions = (
        (
            re.compile(
                r"(?i)\b(authorization|api[_-]?key|access[_-]?key|"
                r"secret|token|password|passwd)\s*[:=]\s*[^\s,;]+"
            ),
            r"\1=<redacted>",
        ),
        (
            re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"),
            "Bearer <redacted>",
        ),
        (
            re.compile(r"(?i)(https?://)[^/@\s]+:[^/@\s]+@"),
            r"\1<redacted>@",
        ),
    )
    for pattern, replacement in substitutions:
        text = pattern.sub(replacement, text)
    return text[:limit]


def _load_json_object(path: Path, *, label: str) -> Dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ChildRequestError(f"{label}不存在或不可读") from exc
    if size <= 0:
        raise ChildRequestError(f"{label}为空")
    if size > MAX_REQUEST_BYTES and label == "请求文件":
        raise ChildRequestError("请求文件超过 64 KiB 安全上限")
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ChildRequestError(f"{label}不是有效 JSON") from exc
    if not isinstance(payload, dict):
        raise ChildRequestError(f"{label}必须是 JSON 对象")
    return payload


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _normalized_stages(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ChildRequestError("stages 必须是非空数组")
    if not all(isinstance(stage, str) for stage in value):
        raise ChildRequestError("stages 只能包含字符串")
    if len(value) != len(set(value)):
        raise ChildRequestError("stages 不能重复")
    unknown = set(value) - set(SUPPORTED_STAGES)
    if unknown:
        raise ChildRequestError(
            f"不支持的执行阶段：{', '.join(sorted(unknown))}"
        )
    # 固定依赖顺序，不能由请求改变。
    return tuple(stage for stage in SUPPORTED_STAGES if stage in value)


def _task_from_parent(parent_path: Path, task_id: str) -> Dict[str, Any]:
    database_path = parent_path / "group_store" / "group_tasks.sqlite3"
    if database_path.is_file():
        from utils.group_task_store import GroupTaskStore

        task = GroupTaskStore(database_path).get_task(
            task_id,
            with_stages=False,
        )
        if task is not None:
            return task

    parent_metadata = _load_json_object(
        parent_path / "project_metadata.json",
        label="父组项目描述",
    )
    for task in parent_metadata.get("group_tasks", []):
        if str(task.get("task_id") or "") == task_id:
            return dict(task)
    raise ChildRequestError("父组项目中不存在指定 task_id")


def validate_request(payload: Dict[str, Any]) -> ValidatedChildRequest:
    """验证请求，并证明目标目录正是父组任务记录的子项目。"""

    unexpected = set(payload) - ALLOWED_REQUEST_FIELDS
    if unexpected:
        raise ChildRequestError(
            f"请求包含不允许的字段：{', '.join(sorted(unexpected))}"
        )
    missing = REQUIRED_REQUEST_FIELDS - set(payload)
    if missing:
        raise ChildRequestError(
            f"请求缺少字段：{', '.join(sorted(missing))}"
        )
    if payload.get("schema_version") != REQUEST_SCHEMA_VERSION:
        raise ChildRequestError(
            f"schema_version 必须为 {REQUEST_SCHEMA_VERSION}"
        )

    task_id = payload.get("task_id")
    farm_code = payload.get("farm_code")
    raw_project_path = payload.get("project_path")
    for field_name, value in (
        ("task_id", task_id),
        ("farm_code", farm_code),
        ("project_path", raw_project_path),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ChildRequestError(f"{field_name} 必须是非空字符串")
    try:
        task_id = str(uuid.UUID(task_id))
    except (ValueError, AttributeError) as exc:
        raise ChildRequestError("task_id 不是有效 UUID") from exc
    farm_code = farm_code.strip()
    service_staff = payload.get("service_staff", "")
    if not isinstance(service_staff, str):
        raise ChildRequestError("service_staff 必须是字符串")
    service_staff = service_staff.strip()
    if len(service_staff) > 100 or any(
        ord(character) < 32 for character in service_staff
    ):
        raise ChildRequestError("service_staff 格式无效")

    requested_path = Path(raw_project_path)
    if not requested_path.is_absolute():
        raise ChildRequestError("project_path 必须是绝对路径")
    try:
        project_path = requested_path.resolve(strict=True)
    except OSError as exc:
        raise ChildRequestError("project_path 不存在或不可访问") from exc
    if not project_path.is_dir():
        raise ChildRequestError("project_path 不是目录")

    child_metadata = _load_json_object(
        project_path / "project_metadata.json",
        label="子项目描述",
    )
    if child_metadata.get("project_type") != "group_child":
        raise ChildRequestError("project_path 不是牧场组子项目")

    raw_parent = child_metadata.get("parent_group")
    if not isinstance(raw_parent, str) or not raw_parent.strip():
        raise ChildRequestError("子项目缺少 parent_group")
    relative_parent = Path(raw_parent)
    if relative_parent.is_absolute():
        raise ChildRequestError("parent_group 必须使用相对路径")
    try:
        parent_path = (project_path / relative_parent).resolve(strict=True)
    except OSError as exc:
        raise ChildRequestError("父组项目不存在或不可访问") from exc

    parent_metadata = _load_json_object(
        parent_path / "project_metadata.json",
        label="父组项目描述",
    )
    if parent_metadata.get("project_type") != "multi_farm_group":
        raise ChildRequestError("parent_group 不是牧场组项目")

    task = _task_from_parent(parent_path, task_id)
    task_farm_code = str(task.get("farm_code") or "").strip()
    if task_farm_code != farm_code:
        raise ChildRequestError("farm_code 与父组任务不一致")

    relative_child = Path(str(task.get("relative_path") or ""))
    if (
        not relative_child.parts
        or relative_child.is_absolute()
        or ".." in relative_child.parts
    ):
        raise ChildRequestError("父组任务的子项目路径不安全")
    try:
        expected_child_path = (parent_path / relative_child).resolve(strict=True)
        farm_projects_path = (parent_path / "farm_projects").resolve(strict=True)
    except OSError as exc:
        raise ChildRequestError("父组任务指定的子项目不存在") from exc
    if not _is_relative_to(expected_child_path, farm_projects_path):
        raise ChildRequestError("父组任务的子项目不在 farm_projects 目录")
    if project_path != expected_child_path:
        raise ChildRequestError("project_path 与父组 task 描述不一致")

    child_task_id = str(child_metadata.get("group_task_id") or "")
    child_farm_code = str(child_metadata.get("group_farm_code") or "").strip()
    if child_task_id != task_id:
        raise ChildRequestError("子项目 group_task_id 与请求不一致")
    if child_farm_code != farm_code:
        raise ChildRequestError("子项目 group_farm_code 与请求不一致")

    farms = child_metadata.get("farms")
    if not isinstance(farms, list) or len(farms) != 1:
        raise ChildRequestError("子项目必须且只能描述一个牧场")
    metadata_farm_code = str(
        farms[0].get("code") or farms[0].get("farmCode") or ""
    ).strip()
    if metadata_farm_code != farm_code:
        raise ChildRequestError("子项目牧场编号与请求不一致")

    data_source = str(
        child_metadata.get("data_source")
        or child_metadata.get("interface_source")
        or task.get("source_system")
        or ""
    ).strip()
    if not data_source:
        raise ChildRequestError("子项目缺少数据源描述")

    from core.group_tasks.dataset_plan import (
        normalize_dataset_selection,
    )

    task_mode = str(parent_metadata.get("task_mode") or "analysis")
    is_local = str(task.get("source_kind") or "api") == "local"
    parent_selection_explicit = bool(
        parent_metadata.get(
            "dataset_selection_explicit",
            "dataset_selection" in parent_metadata,
        )
    )
    task_metadata = task.get("metadata") or {}
    task_selection_explicit = bool(
        task_metadata.get(
            "dataset_selection_explicit",
            "dataset_selection" in task_metadata,
        )
    )
    child_selection_explicit = bool(
        child_metadata.get(
            "dataset_selection_explicit",
            "dataset_selection" in child_metadata,
        )
    )
    if not (
        parent_selection_explicit
        == task_selection_explicit
        == child_selection_explicit
    ):
        raise ChildRequestError("父任务、子任务与子项目的数据集选择标记不一致")
    try:
        parent_selection = normalize_dataset_selection(
            parent_metadata.get("dataset_selection"),
            task_mode=task_mode,
            has_local_farms=is_local,
        )
        task_selection = normalize_dataset_selection(
            task_metadata.get("dataset_selection"),
            task_mode=task_mode,
            has_local_farms=is_local,
        )
        child_selection = normalize_dataset_selection(
            child_metadata.get("dataset_selection"),
            task_mode=task_mode,
            has_local_farms=is_local,
        )
    except ValueError as exc:
        raise ChildRequestError("牧场组数据集选择无效") from exc
    if not (
        parent_selection == task_selection == child_selection
    ):
        raise ChildRequestError("父任务、子任务与子项目的数据集选择不一致")

    return ValidatedChildRequest(
        task_id=task_id,
        farm_code=farm_code,
        farm_name=str(
            task.get("farm_name")
            or farms[0].get("name")
            or farm_code
        ),
        project_path=project_path,
        parent_group_path=parent_path,
        data_source=data_source,
        dataset_selection=parent_selection,
        stages=_normalized_stages(payload.get("stages")),
        service_staff=service_staff,
    )


def load_and_validate_request(request_path: Path) -> ValidatedChildRequest:
    payload = _load_json_object(Path(request_path), label="请求文件")
    return validate_request(payload)


def _valid_xlsx(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = set(archive.namelist())
            if (
                "[Content_Types].xml" not in names
                or "xl/workbook.xml" not in names
            ):
                return False
            archive.read("[Content_Types].xml")
            archive.read("xl/workbook.xml")
    except (OSError, zipfile.BadZipFile, KeyError, RuntimeError):
        return False
    return True


def _artifact_paths(
    request: ValidatedChildRequest,
    stage: str,
    worker_result: Dict[str, Any],
) -> List[Path]:
    if stage == "analysis":
        artifacts = [request.project_path / item for item in ANALYSIS_ARTIFACTS]
    else:
        result_path = str(worker_result.get("excel_path") or "").strip()
        artifacts = [Path(result_path)] if result_path else []
        if not artifacts:
            reports = [
                path
                for path in (request.project_path / "reports").glob(
                    "育种分析综合报告_*.xlsx"
                )
                if _valid_xlsx(path)
            ]
            if reports:
                artifacts = [max(reports, key=lambda path: path.stat().st_mtime)]
    invalid = [path for path in artifacts if not _valid_xlsx(path)]
    if not artifacts or invalid:
        names = ", ".join(path.name for path in (invalid or artifacts))
        raise ChildExecutionError(
            f"{stage} 阶段未生成完整有效的 Excel 产物"
            + (f"：{names}" if names else "")
        )
    for path in artifacts:
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise ChildExecutionError(f"无法核验产物：{path.name}") from exc
        if not _is_relative_to(resolved, request.project_path):
            raise ChildExecutionError("子任务产物位于子项目目录之外")
    return artifacts


def _default_worker_factory(*args: Any, **kwargs: Any) -> Any:
    from gui.auto_report_worker import AutoReportWorker

    return AutoReportWorker(*args, **kwargs)


def execute_request(
    request_path: Path,
    *,
    worker_factory: Optional[Callable[..., Any]] = None,
    output_stream: Optional[TextIO] = None,
) -> Dict[str, Any]:
    """执行一个已落盘请求；返回值同时会作为最后一条 JSON 事件输出。"""

    protocol_stream = output_stream or sys.stdout
    emitter = JsonLineEmitter(protocol_stream)
    request = load_and_validate_request(Path(request_path))
    worker_factory = worker_factory or _default_worker_factory

    standardized_input = (
        request.project_path
        / "standardized_data"
        / "processed_cow_data.xlsx"
    )
    if not _valid_xlsx(standardized_input):
        raise ChildExecutionError("子项目缺少有效的标准化母牛数据")

    completed_stages: List[str] = []
    relative_artifacts: List[str] = []
    warnings: List[Dict[str, str]] = []

    # 保留协议流对象，之后即使临时重定向 sys.stdout，进度事件仍只写
    # 入原始协议流。
    with contextlib.redirect_stdout(_DiscardingTextIO()):
        for stage in request.stages:
            from core.group_tasks.stage_policy import (
                commit_child_stage,
                invalidate_stage_and_downstream,
                stage_manifest_path,
            )

            # 新尝试一旦开始，旧清单只能作为历史审计材料，不能继续代表
            # 当前结果；旧结果文件本身保留，便于诊断和失败恢复。
            invalidate_stage_and_downstream(
                request.project_path,
                stage,
            )
            emitter.emit(
                "stage_started",
                task_id=request.task_id,
                farm_code=request.farm_code,
                stage=stage,
            )
            worker = worker_factory(
                None,
                [
                    {
                        "code": request.farm_code,
                        "name": request.farm_name,
                    }
                ],
                request.project_path,
                False,
                service_staff=request.service_staff or None,
                data_source=request.data_source,
                local_farms=[],
                reliability_mode=True,
                group_batch_mode=True,
                dataset_selection=request.dataset_selection,
            )

            def relay(
                value: Any,
                message: Any = "",
                *,
                current_stage: str = stage,
            ) -> None:
                try:
                    progress = max(0, min(100, int(value)))
                except (TypeError, ValueError):
                    progress = 0
                emitter.emit(
                    "progress",
                    task_id=request.task_id,
                    farm_code=request.farm_code,
                    stage=current_stage,
                    progress=progress,
                    message=_safe_error_message(message, limit=500),
                )

            worker.progress.connect(relay)
            worker_result = worker.execute(
                download=False,
                analysis=stage == "analysis",
                excel=stage == "child_excel",
                ppt=False,
            )
            if not isinstance(worker_result, dict):
                raise ChildExecutionError("分析工作线程返回了无效结果")

            stage_failures = [
                (str(name), _safe_error_message(error))
                for name, error in worker_result.get("failed_items", [])
            ]
            if stage == "analysis":
                essential_failures = [
                    (name, error)
                    for name, error in stage_failures
                    if name in ESSENTIAL_ANALYSIS_ITEMS
                ]
                if essential_failures:
                    raise ChildExecutionError(
                        "；".join(
                            f"{name}: {error}"
                            for name, error in essential_failures
                        )
                    )
            elif stage_failures:
                raise ChildExecutionError(
                    "；".join(
                        f"{name}: {error}" for name, error in stage_failures
                    )
                )

            stage_artifacts = _artifact_paths(
                request,
                stage,
                worker_result,
            )
            stage_manifest = commit_child_stage(
                request.project_path,
                stage,
                expected_task_id=request.task_id,
                expected_farm_code=request.farm_code,
                report_path=(
                    stage_artifacts[0]
                    if stage == "child_excel"
                    else None
                ),
            )
            for path in stage_artifacts:
                relative = path.resolve().relative_to(
                    request.project_path
                ).as_posix()
                if relative not in relative_artifacts:
                    relative_artifacts.append(relative)
            warnings.extend(
                {"item": name, "message": error}
                for name, error in stage_failures
                if stage == "analysis" and name not in ESSENTIAL_ANALYSIS_ITEMS
            )
            completed_stages.append(stage)
            emitter.emit(
                "stage_completed",
                task_id=request.task_id,
                farm_code=request.farm_code,
                stage=stage,
                artifacts=[
                    path.resolve()
                    .relative_to(request.project_path)
                    .as_posix()
                    for path in stage_artifacts
                ],
                manifest=stage_manifest_path(stage).as_posix(),
                config_fingerprint=stage_manifest[
                    "config_fingerprint"
                ],
            )

    result = {
        "success": True,
        "task_id": request.task_id,
        "farm_code": request.farm_code,
        "completed_stages": completed_stages,
        "artifacts": relative_artifacts,
        "warnings": warnings,
    }
    emitter.emit("result", **result)
    return result


def main(
    argv: Optional[Iterable[str]] = None,
    *,
    worker_factory: Optional[Callable[..., Any]] = None,
    output_stream: Optional[TextIO] = None,
) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    emitter = JsonLineEmitter(output_stream or sys.stdout)
    if len(arguments) != 1:
        emitter.emit(
            "result",
            success=False,
            error="用法：python -m core.group_tasks.child_runner REQUEST_JSON",
        )
        return 2
    try:
        execute_request(
            Path(arguments[0]),
            worker_factory=worker_factory,
            output_stream=output_stream,
        )
    except Exception as exc:
        emitter.emit(
            "result",
            success=False,
            error=_safe_error_message(exc),
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
