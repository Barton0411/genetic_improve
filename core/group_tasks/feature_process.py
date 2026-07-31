"""页面功能子进程的父端请求与启动命令。"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping

from core.group_tasks.feature_policy import normalize_feature_parameters
from core.group_tasks.feature_runner import (
    ALLOWED_FEATURE_REQUEST_FIELDS,
    validate_feature_request,
)
from core.group_tasks.parent_process import build_child_request


def build_feature_request(
    parent_group_path: Path | str,
    task_id: str,
    operation: str,
    parameters: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """从父任务真值生成无凭据请求，不接受调用方指定子项目路径。"""
    parent = Path(parent_group_path).resolve(strict=True)
    identity = build_child_request(
        parent,
        task_id,
        ["analysis"],
        service_staff="",
    )
    request = {
        "schema_version": identity["schema_version"],
        "task_id": identity["task_id"],
        "farm_code": identity["farm_code"],
        "project_path": identity["project_path"],
        "operation": str(operation or "").strip(),
        "parameters": normalize_feature_parameters(
            str(operation or "").strip(),
            parameters,
        ),
    }
    if set(request) != ALLOWED_FEATURE_REQUEST_FIELDS:
        raise AssertionError("内部功能请求字段与子进程协议不一致")
    validate_feature_request(request)
    return request


def write_feature_request(
    parent_group_path: Path | str,
    task_id: str,
    operation: str,
    parameters: Mapping[str, Any] | None,
) -> Path:
    parent = Path(parent_group_path).resolve(strict=True)
    request = build_feature_request(
        parent,
        task_id,
        operation,
        parameters,
    )
    request_dir = parent / "group_store" / "feature_requests"
    request_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{request['task_id']}-{uuid.uuid4().hex}.json"
    target = request_dir / filename
    temporary = request_dir / f".{filename}.tmp"
    data = json.dumps(
        request,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
    finally:
        temporary.unlink(missing_ok=True)
    return target


def build_feature_command(
    request_path: Path | str,
    *,
    executable: Path | str | None = None,
    frozen: bool | None = None,
) -> list[str]:
    request = Path(request_path).resolve(strict=True)
    if not request.is_file():
        raise ValueError("request_path 必须是文件")
    executable_path = str(executable or sys.executable)
    is_frozen = bool(
        getattr(sys, "frozen", False) if frozen is None else frozen
    )
    if is_frozen:
        return [
            executable_path,
            "--group-feature-runner",
            str(request),
        ]
    entrypoint = Path(__file__).resolve().parents[2] / "main.py"
    if not entrypoint.is_file():
        raise RuntimeError("找不到源码环境 main.py 子进程入口")
    return [
        executable_path,
        str(entrypoint),
        "--group-feature-runner",
        str(request),
    ]
