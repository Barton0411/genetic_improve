"""在一次性子进程中执行一个牧场的一项页面分析。"""

from __future__ import annotations

import contextlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, TextIO

from core.group_tasks.child_runner import (
    REQUEST_SCHEMA_VERSION,
    ChildExecutionError,
    ChildRequestError,
    JsonLineEmitter,
    _DiscardingTextIO,
    _load_json_object,
    _safe_error_message,
    validate_request,
)
from core.group_tasks.feature_policy import (
    FEATURE_TITLES,
    capture_feature_output_state,
    commit_feature_manifest,
    discard_feature_manifest,
    feature_prerequisite,
    invalidate_before_feature_run,
    manifest_artifacts,
    normalize_feature_parameters,
    validate_feature_manifest,
)


MAX_FEATURE_REQUEST_BYTES = 128 * 1024
ALLOWED_FEATURE_REQUEST_FIELDS = {
    "schema_version",
    "task_id",
    "farm_code",
    "project_path",
    "operation",
    "parameters",
}
REQUIRED_FEATURE_REQUEST_FIELDS = ALLOWED_FEATURE_REQUEST_FIELDS


@dataclass(frozen=True)
class ValidatedFeatureRequest:
    task_id: str
    farm_code: str
    farm_name: str
    project_path: Path
    parent_group_path: Path
    dataset_selection: dict[str, bool]
    operation: str
    parameters: dict[str, Any]


def validate_feature_request(
    payload: Mapping[str, Any],
) -> ValidatedFeatureRequest:
    if not isinstance(payload, Mapping):
        raise ChildRequestError("请求必须是 JSON 对象")
    unexpected = set(payload) - ALLOWED_FEATURE_REQUEST_FIELDS
    if unexpected:
        raise ChildRequestError(
            "请求包含不允许的字段：" + "、".join(sorted(unexpected))
        )
    missing = REQUIRED_FEATURE_REQUEST_FIELDS - set(payload)
    if missing:
        raise ChildRequestError(
            "请求缺少字段：" + "、".join(sorted(missing))
        )
    operation = payload.get("operation")
    if not isinstance(operation, str) or not operation.strip():
        raise ChildRequestError("operation 必须是非空字符串")
    operation = operation.strip()
    try:
        parameters = normalize_feature_parameters(
            operation,
            payload.get("parameters"),
        )
    except Exception as exc:
        raise ChildRequestError(str(exc)) from exc

    # 复用主子任务协议的完整父子目录归属、task_id、farm_code 和数据集
    # 选择交叉校验；页面功能请求本身仍不接受任何凭据。
    base_request = {
        "schema_version": payload.get("schema_version"),
        "task_id": payload.get("task_id"),
        "farm_code": payload.get("farm_code"),
        "project_path": payload.get("project_path"),
        "stages": ["analysis"],
        "service_staff": "",
    }
    validated = validate_request(base_request)
    return ValidatedFeatureRequest(
        task_id=validated.task_id,
        farm_code=validated.farm_code,
        farm_name=validated.farm_name,
        project_path=validated.project_path,
        parent_group_path=validated.parent_group_path,
        dataset_selection=validated.dataset_selection,
        operation=operation,
        parameters=parameters,
    )


def load_and_validate_feature_request(
    request_path: Path,
) -> ValidatedFeatureRequest:
    path = Path(request_path)
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ChildRequestError("请求文件不存在或不可读") from exc
    if size > MAX_FEATURE_REQUEST_BYTES:
        raise ChildRequestError("请求文件超过 128 KiB 安全上限")
    return validate_feature_request(
        _load_json_object(path, label="请求文件")
    )


def _execute_operation(
    request: ValidatedFeatureRequest,
    progress_callback,
) -> tuple[bool, str]:
    from core.auto_analysis_runner import (
        run_bull_index,
        run_bull_traits,
        run_cow_index,
        run_cow_self_inbreeding_analysis,
        run_cow_traits,
        run_inbreeding_analysis,
        run_mated_bull_traits,
    )

    project = request.project_path
    parameters = request.parameters
    if request.operation == "cow_traits":
        return run_cow_traits(
            project,
            parameters["traits"],
            progress_callback,
        )
    if request.operation == "bull_traits":
        return run_bull_traits(
            project,
            parameters["traits"],
            progress_callback,
            allow_missing_bull_upload=False,
        )
    if request.operation == "mated_bull_traits":
        return run_mated_bull_traits(
            project,
            parameters["traits"],
            progress_callback,
        )
    if request.operation == "cow_index":
        return run_cow_index(
            project,
            parameters["weight_name"],
            progress_callback,
            weight_values=parameters["weight_values"],
        )
    if request.operation == "bull_index":
        return run_bull_index(
            project,
            parameters["weight_name"],
            progress_callback,
            weight_values=parameters["weight_values"],
            allow_missing_bull_upload=False,
        )
    if request.operation == "cow_self_inbreeding":
        return run_cow_self_inbreeding_analysis(
            project,
            progress_callback,
        )
    analysis_type = (
        "mated"
        if request.operation == "mated_inbreeding"
        else "candidate"
    )
    return run_inbreeding_analysis(
        project,
        analysis_type,
        progress_callback,
        allow_missing_bull_upload=False,
    )


def execute_feature_request(
    request_path: Path,
    *,
    output_stream: TextIO | None = None,
) -> dict[str, Any]:
    protocol_stream = output_stream or sys.stdout
    emitter = JsonLineEmitter(protocol_stream)
    request = load_and_validate_feature_request(Path(request_path))

    prerequisite_state, prerequisite_message = feature_prerequisite(
        request.project_path,
        request.operation,
        dataset_selection=request.dataset_selection,
    )
    if prerequisite_state == "skipped":
        result = {
            "success": True,
            "skipped": True,
            "resumed": False,
            "task_id": request.task_id,
            "farm_code": request.farm_code,
            "operation": request.operation,
            "message": prerequisite_message,
            "artifacts": [],
        }
        emitter.emit("result", **result)
        return result
    if prerequisite_state != "ready":
        raise ChildExecutionError(prerequisite_message)

    from core.data.update_manager import get_local_db_version

    frozen_bull_library_version = get_local_db_version()

    def ensure_bull_library_unchanged() -> None:
        if get_local_db_version() != frozen_bull_library_version:
            raise ChildExecutionError(
                "公牛库版本在单牧场分析期间发生变化，"
                "已拒绝提交；请重试当前牧场"
            )

    current = validate_feature_manifest(
        request.project_path,
        request.operation,
        request.parameters,
        expected_task_id=request.task_id,
        expected_farm_code=request.farm_code,
        verification="full",
        bull_library_version=frozen_bull_library_version,
    )
    ensure_bull_library_unchanged()
    if current.get("valid"):
        result = {
            "success": True,
            "skipped": False,
            "resumed": True,
            "task_id": request.task_id,
            "farm_code": request.farm_code,
            "operation": request.operation,
            "message": "相同参数的有效结果已存在，已直接复用",
            "artifacts": manifest_artifacts(current),
        }
        emitter.emit("progress", progress=100, message=result["message"])
        emitter.emit("result", **result)
        return result

    output_baseline = capture_feature_output_state(
        request.project_path,
        request.operation,
    )
    invalidate_before_feature_run(
        request.project_path,
        request.operation,
    )
    emitter.emit(
        "stage_started",
        task_id=request.task_id,
        farm_code=request.farm_code,
        stage=f"feature:{request.operation}",
    )

    def relay(value: Any, message: Any = "") -> None:
        try:
            progress = max(0, min(100, int(value)))
        except (TypeError, ValueError):
            progress = 0
        emitter.emit(
            "progress",
            task_id=request.task_id,
            farm_code=request.farm_code,
            stage=f"feature:{request.operation}",
            progress=progress,
            message=_safe_error_message(message, limit=500),
        )

    with contextlib.redirect_stdout(_DiscardingTextIO()):
        success, message = _execute_operation(request, relay)
        if not success:
            raise ChildExecutionError(str(message or "分析未成功完成"))
        ensure_bull_library_unchanged()
        manifest = commit_feature_manifest(
            request.project_path,
            request.operation,
            request.parameters,
            expected_task_id=request.task_id,
            expected_farm_code=request.farm_code,
            bull_library_version=frozen_bull_library_version,
            output_baseline=output_baseline,
        )
        try:
            ensure_bull_library_unchanged()
        except Exception:
            discard_feature_manifest(
                request.project_path,
                request.operation,
                "bull_library_changed",
            )
            raise

    artifacts = [
        str(item.get("relative_path") or "")
        for item in manifest.get("outputs", [])
        if item.get("relative_path")
    ]
    emitter.emit(
        "stage_completed",
        task_id=request.task_id,
        farm_code=request.farm_code,
        stage=f"feature:{request.operation}",
        artifacts=artifacts,
        config_fingerprint=manifest.get("config_fingerprint", ""),
    )
    result = {
        "success": True,
        "skipped": False,
        "resumed": False,
        "task_id": request.task_id,
        "farm_code": request.farm_code,
        "operation": request.operation,
        "message": str(message or FEATURE_TITLES[request.operation] + "完成"),
        "artifacts": artifacts,
    }
    emitter.emit("result", **result)
    return result


def main(
    argv: list[str] | None = None,
    *,
    output_stream: TextIO | None = None,
) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    protocol_stream = output_stream or sys.stdout
    emitter = JsonLineEmitter(protocol_stream)
    if len(arguments) != 1:
        emitter.emit(
            "result",
            success=False,
            error="用法：--group-feature-runner <request.json>",
        )
        return 2
    try:
        execute_feature_request(
            Path(arguments[0]),
            output_stream=protocol_stream,
        )
        return 0
    except Exception as exc:
        emitter.emit(
            "result",
            success=False,
            error=_safe_error_message(exc),
        )
        return 1
    finally:
        try:
            from core.data.update_manager import reset_pedigree_db
            import gc

            reset_pedigree_db()
            gc.collect()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
