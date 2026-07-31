"""从慧牧云重新下载并串行完成一个牧场组的正式验收。

脚本只复用既有牧场组的选择清单和用户导入的备选公牛文件，不复用
任何牛群、配种、标准化或分析结果。登录令牌由应用现有安全缓存读取，
不会写入验收目录或控制台。
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from PyQt6.QtCore import QCoreApplication

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.hmy_api_client import HMYApiClient
from gui.multi_farm_task_worker import MultiFarmTaskWorker
from utils.file_manager import FileManager


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} 不是 JSON 对象")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _selected_farms(selection_group: Path) -> List[Dict[str, Any]]:
    metadata = _load_json(selection_group / "project_metadata.json")
    if metadata.get("project_type") != "multi_farm_group":
        raise ValueError("选择来源不是牧场组项目")
    if metadata.get("data_source") != "慧牧云":
        raise ValueError("选择来源不是慧牧云牧场组")

    included_codes = {
        str(task.get("farm_code") or "").strip()
        for task in metadata.get("group_tasks", [])
        if task.get("included_in_summary", True)
    }
    farms = []
    for source in metadata.get("farms", []):
        farm = dict(source)
        code = str(
            farm.get("code")
            or farm.get("farmCode")
            or farm.get("api_farmcode")
            or ""
        ).strip()
        if code and code in included_codes:
            farm.pop("task_id", None)
            farms.append(farm)
    if not farms:
        raise ValueError("选择来源没有可验收的牧场")
    if len({str(farm.get("code") or "") for farm in farms}) != len(farms):
        raise ValueError("牧场选择清单存在重复编码")
    return farms


def _write_result(group_path: Path, payload: Dict[str, Any]) -> Path:
    result_path = group_path / "group_store" / "fresh_acceptance_run.json"
    FileManager._write_json_atomic(result_path, payload)
    return result_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-group", type=Path, required=True)
    parser.add_argument("--destination-base", type=Path, required=True)
    parser.add_argument("--bull-file", type=Path, required=True)
    args = parser.parse_args()

    selection_group = args.selection_group.expanduser().resolve(strict=True)
    destination_base = args.destination_base.expanduser().resolve()
    bull_file = args.bull_file.expanduser().resolve(strict=True)
    if bull_file.suffix.lower() != ".xlsx" or bull_file.stat().st_size <= 0:
        raise ValueError("备选公牛文件不是有效的 xlsx 文件")

    farms = _selected_farms(selection_group)
    destination_base.mkdir(parents=True, exist_ok=True)
    group_path = FileManager.create_group_project(
        destination_base,
        farms,
        data_source="慧牧云",
        task_mode="analysis",
    )
    metadata = FileManager.load_project_metadata(group_path)
    for task in metadata.get("group_tasks", []):
        child_path = group_path / str(task["relative_path"])
        target = child_path / "standardized_data" / "processed_bull_data.xlsx"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bull_file, target)

    console = sys.__stdout__
    outcome: Dict[str, Any] = {}
    last_progress = {"value": -1, "message": ""}

    def write_line(message: str) -> None:
        console.write(message.rstrip() + "\n")
        console.flush()

    def on_progress(value: Any, message: Any) -> None:
        try:
            numeric = max(0, min(100, int(value)))
        except (TypeError, ValueError):
            numeric = 0
        safe_message = " ".join(str(message or "").split())[:300]
        if (
            numeric >= last_progress["value"] + 2
            or safe_message != last_progress["message"]
            or numeric in (0, 100)
        ):
            timestamp = datetime.now().strftime("%H:%M:%S")
            write_line(f"[{timestamp}] {numeric:3d}% {safe_message}")
            last_progress.update(value=numeric, message=safe_message)

    def on_finished(result: Dict[str, Any]) -> None:
        outcome["finished"] = result
        write_line(
            "运行结束：完成 "
            f"{len(result.get('completed') or [])} 个，"
            f"失败 {len(result.get('failed') or [])} 个。"
        )

    def on_error(message: str) -> None:
        outcome["error"] = str(message)
        write_line("运行异常：牧场组工作线程未完成。")

    app = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])
    client = HMYApiClient()
    worker = MultiFarmTaskWorker(
        client,
        farms,
        group_path,
        data_source="慧牧云",
        service_staff="",
        full_analysis=True,
    )
    worker.progress.connect(on_progress)
    worker.finished.connect(on_finished)
    worker.error.connect(on_error)

    write_line(f"新建正式验收组：{group_path}")
    write_line(f"牧场数：{len(farms)}；备选公牛文件摘要：{_sha256(bull_file)[:16]}")
    with open(os.devnull, "w", encoding="utf-8") as sink:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            worker.run()
    del app

    finished = outcome.get("finished") or {}
    failed = list(finished.get("failed") or [])
    summary_error = str(finished.get("summary_error") or "")
    success = bool(
        finished
        and not failed
        and not summary_error
        and finished.get("excel_path")
        and not outcome.get("error")
    )
    result_payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "group_path": str(group_path),
        "farm_count": len(farms),
        "completed_count": len(finished.get("completed") or []),
        "failed_count": len(failed),
        "summary_error": summary_error,
        "group_excel": str(finished.get("excel_path") or ""),
        "bull_file_sha256": _sha256(bull_file),
        "error": str(outcome.get("error") or ""),
    }
    result_path = _write_result(group_path, result_payload)
    write_line(f"验收运行记录：{result_path}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
