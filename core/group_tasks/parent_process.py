"""牧场组子进程的父端协议工具。

本模块只负责创建无凭据请求、选择开发/打包启动命令和解析 JSONL；
实际进程生命周期与界面状态更新由后续 GUI 接入层负责。
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional, Union

from core.group_tasks.child_runner import (
    ALLOWED_REQUEST_FIELDS,
    REQUEST_SCHEMA_VERSION,
    validate_request,
)


MAX_PROTOCOL_LINE_BYTES = 1024 * 1024
PROTOCOL_EVENT_TYPES = {
    "stage_started",
    "progress",
    "stage_completed",
    "result",
}


class ChildProtocolError(RuntimeError):
    """父子进程 JSONL 协议不合法。"""


def build_child_request(
    parent_group_path: Union[Path, str],
    task_id: str,
    stages: Iterable[str],
    *,
    service_staff: str = "",
) -> Dict[str, Any]:
    """从父组任务真值构造请求，不接受调用方传入牧场路径或凭据。"""

    parent_path = Path(parent_group_path).resolve(strict=True)
    try:
        normalized_task_id = str(uuid.UUID(str(task_id)))
    except (ValueError, AttributeError) as exc:
        raise ValueError("task_id 不是有效 UUID") from exc

    database_path = parent_path / "group_store" / "group_tasks.sqlite3"
    if database_path.is_file():
        from utils.group_task_store import GroupTaskStore

        task = GroupTaskStore(database_path).get_task(
            normalized_task_id,
            with_stages=False,
        )
    else:
        task = None
        metadata_path = parent_path / "project_metadata.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("父组项目描述不可读") from exc
        for candidate in metadata.get("group_tasks", []):
            if str(candidate.get("task_id") or "") == normalized_task_id:
                task = candidate
                break
    if not task:
        raise ValueError("父组项目中不存在指定 task_id")

    relative_path = Path(str(task.get("relative_path") or ""))
    child_path = (parent_path / relative_path).resolve(strict=True)
    request = {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "task_id": normalized_task_id,
        "farm_code": str(task.get("farm_code") or ""),
        "project_path": str(child_path),
        "stages": list(stages),
        "service_staff": str(service_staff or "").strip(),
    }
    if set(request) != ALLOWED_REQUEST_FIELDS:
        raise AssertionError("内部请求字段与子进程协议不一致")
    # 复用子端全部归属校验，防止父端生成一个随后才会被拒绝的请求。
    validate_request(request)
    return request


def write_child_request(
    parent_group_path: Union[Path, str],
    task_id: str,
    stages: Iterable[str],
    *,
    service_staff: str = "",
) -> Path:
    """在父组内部原子写入权限收紧的临时请求文件。"""

    parent_path = Path(parent_group_path).resolve(strict=True)
    request = build_child_request(
        parent_path,
        task_id,
        stages,
        service_staff=service_staff,
    )
    request_dir = parent_path / "group_store" / "child_requests"
    request_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{request['task_id']}-{uuid.uuid4().hex}.json"
    target = request_dir / filename
    temporary = request_dir / f".{filename}.tmp"
    data = json.dumps(
        request,
        ensure_ascii=False,
        separators=(",", ":"),
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
            # Windows 的权限模型可能不完整支持 POSIX mode。
            pass
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def build_child_command(
    request_path: Union[Path, str],
    *,
    executable: Optional[Union[Path, str]] = None,
    frozen: Optional[bool] = None,
) -> list[str]:
    """为源码环境或 PyInstaller 应用选择正确的子进程命令。"""

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
            "--group-child-runner",
            str(request),
        ]
    source_entrypoint = Path(__file__).resolve().parents[2] / "main.py"
    if not source_entrypoint.is_file():
        raise RuntimeError("找不到源码环境 main.py 子进程入口")
    return [
        executable_path,
        str(source_entrypoint),
        "--group-child-runner",
        str(request),
    ]


def parse_jsonl_line(line: Union[bytes, str]) -> Dict[str, Any]:
    """严格解析一条子进程 JSONL 事件。"""

    raw = line.encode("utf-8") if isinstance(line, str) else bytes(line)
    if len(raw) > MAX_PROTOCOL_LINE_BYTES:
        raise ChildProtocolError("子进程协议行超过 1 MiB 上限")
    try:
        text = raw.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ChildProtocolError("子进程协议不是 UTF-8") from exc
    if not text:
        raise ChildProtocolError("子进程协议出现空行")
    try:
        event = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ChildProtocolError("子进程输出不是有效 JSON") from exc
    if not isinstance(event, dict):
        raise ChildProtocolError("子进程事件必须是 JSON 对象")
    event_type = event.get("type")
    if event_type not in PROTOCOL_EVENT_TYPES:
        raise ChildProtocolError("子进程事件 type 不受支持")
    if event_type == "progress":
        progress = event.get("progress")
        if (
            isinstance(progress, bool)
            or not isinstance(progress, (int, float))
            or progress < 0
            or progress > 100
        ):
            raise ChildProtocolError("progress 必须在 0 到 100 之间")
    if event_type == "result" and not isinstance(
        event.get("success"),
        bool,
    ):
        raise ChildProtocolError("result 事件缺少布尔 success")
    return event


def parse_jsonl_lines(
    lines: Iterable[Union[bytes, str]],
) -> Iterator[Dict[str, Any]]:
    """逐条解析已按行切分的协议输出。"""

    for line in lines:
        yield parse_jsonl_line(line)
