"""牧场组子项目正式产物的低内存完整清单。

正式完整性只以各阶段 ``committed`` manifest 中登记的 outputs 为准。
这些受管产物按块复核 SHA256；XLSX 的 Sheet 结构直接复用提交时已记录的
结构，避免对超大工作簿做第二次 ZIP/XML 全量解析。

``standardized_data``、``analysis_results`` 和 ``reports`` 中当前可见、
但未被阶段 manifest 管理的 XLSX 仍会出现在索引中，并明确标记
``managed=false``。它们不做内容哈希或结构解析，也不参与正式发布判定；
隐藏、锁文件和明确的临时文件则完全忽略。
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from xml.etree import ElementTree


EXCEL_MAX_ROWS = 1_048_576
EXCEL_MAX_COLUMNS = 16_384

CATEGORY_LABELS = {
    "standardized_data": "标准化数据",
    "analysis_results": "分析结果",
    "reports": "报告",
}
CATEGORY_ORDER = tuple(CATEGORY_LABELS)
STAGE_ORDER = ("data", "analysis", "child_excel")
STAGE_MANIFEST_DIRECTORY = Path("group_store") / "stage_manifests"

_CELL_REFERENCE = re.compile(r"^\$?([A-Za-z]{1,3})\$?([1-9][0-9]*)$")
_RELATIONSHIP_ID = (
    "{http://schemas.openxmlformats.org/officeDocument/2006/"
    "relationships}id"
)
_MAIN_SPREADSHEET_NAMESPACE = (
    "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
)
_STRICT_SPREADSHEET_NAMESPACE = (
    "http://purl.oclc.org/ooxml/spreadsheetml/main"
)
_SUPPORTED_SHEET_RELATIONSHIPS = {
    "worksheet",
    "chartsheet",
    "dialogsheet",
    "macrosheet",
}


def _progress(
    callback: Optional[Callable[[int, str], None]],
    value: int,
    message: str,
) -> None:
    if callback is not None:
        callback(max(0, min(100, int(value))), str(message))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    descriptor_open = True
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor_open = False
            json.dump(
                payload,
                stream,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if descriptor_open:
            try:
                os.close(descriptor)
            except OSError:
                pass
        temporary_path.unlink(missing_ok=True)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _column_number(column_letters: str) -> int:
    value = 0
    for character in column_letters.upper():
        value = value * 26 + ord(character) - ord("A") + 1
    return value


def _cell_position(reference: str) -> Tuple[int, int]:
    match = _CELL_REFERENCE.fullmatch(str(reference or "").strip())
    if match is None:
        raise ValueError(f"无效单元格引用: {reference!r}")
    column = _column_number(match.group(1))
    row = int(match.group(2))
    if row > EXCEL_MAX_ROWS or column > EXCEL_MAX_COLUMNS:
        raise ValueError(f"单元格引用超出 Excel 上限: {reference!r}")
    return row, column


def _dimension_extent(reference: str) -> Tuple[int, int]:
    """返回工作表 dimension 引用覆盖的最大行列。"""
    text = str(reference or "").strip()
    if not text:
        return 0, 0
    references = text.split(":")
    if len(references) > 2:
        raise ValueError(f"无效工作表维度: {reference!r}")
    positions = [_cell_position(item) for item in references]
    return (
        max(position[0] for position in positions),
        max(position[1] for position in positions),
    )


def _relationship_target(target: str) -> str:
    """把 workbook relationship target 规范化为 ZIP 内部路径。"""
    text = str(target or "").replace("\\", "/").strip()
    if not text:
        raise ValueError("工作表 relationship target 为空")
    if text.startswith("/"):
        normalized = posixpath.normpath(text.lstrip("/"))
    else:
        normalized = posixpath.normpath(posixpath.join("xl", text))
    if normalized == ".." or normalized.startswith("../"):
        raise ValueError(f"工作表 relationship target 越界: {target!r}")
    return normalized


def _relationship_kind(relationship_type: str) -> str:
    return str(relationship_type or "").rstrip("/").rsplit("/", 1)[-1]


def _inspect_sheet_xml(
    archive: zipfile.ZipFile,
    member_name: str,
    sheet_kind: str,
) -> Dict:
    """读取 sheet 声明边界；缺少 dimension 时才流式扫描单元格。

    XLSX 的 ZIP CRC 已由调用方完整校验。正常工作簿的 ``dimension`` 位于
    ``sheetData`` 之前，因此通常只需读取 XML 开头即可得到 max_row 和
    max_column；这避免为了两个边界值解析数百万个单元格。
    """
    declared_dimension = ""
    declared_max_row = 0
    declared_max_column = 0
    physical_max_row = 0
    physical_max_column = 0
    cell_count = 0
    parser = ElementTree.XMLPullParser(events=("start", "end"))

    with archive.open(member_name, "r") as stream:
        while True:
            chunk = stream.read(64 * 1024)
            if not chunk:
                break
            parser.feed(chunk)
            for event, element in parser.read_events():
                local_name = _local_name(element.tag)
                if event == "start":
                    if local_name == "dimension":
                        declared_dimension = str(
                            element.attrib.get("ref", "")
                        )
                        if not declared_dimension:
                            raise ValueError("工作表 dimension 缺少 ref 属性")
                        (
                            declared_max_row,
                            declared_max_column,
                        ) = _dimension_extent(declared_dimension)
                        return {
                            "kind": sheet_kind,
                            "max_row": declared_max_row,
                            "max_column": declared_max_column,
                            "physical_max_row": None,
                            "physical_max_column": None,
                            "declared_dimension": declared_dimension,
                            "cell_count": None,
                            "extent_source": "declared_dimension",
                        }
                    if local_name == "row":
                        row_reference = element.attrib.get("r")
                        if row_reference:
                            row_number = int(row_reference)
                            if not 1 <= row_number <= EXCEL_MAX_ROWS:
                                raise ValueError(
                                    "工作表行号超出 Excel 上限: "
                                    f"{row_reference!r}"
                                )
                            physical_max_row = max(
                                physical_max_row,
                                row_number,
                            )
                    elif local_name == "c":
                        cell_reference = element.attrib.get("r")
                        if not cell_reference:
                            raise ValueError(
                                "工作表存在缺少 r 属性的单元格"
                            )
                        row, column = _cell_position(cell_reference)
                        physical_max_row = max(physical_max_row, row)
                        physical_max_column = max(
                            physical_max_column,
                            column,
                        )
                        cell_count += 1
                else:
                    element.clear()
        parser.close()

    return {
        "kind": sheet_kind,
        "max_row": max(physical_max_row, declared_max_row),
        "max_column": max(physical_max_column, declared_max_column),
        "physical_max_row": physical_max_row,
        "physical_max_column": physical_max_column,
        "declared_dimension": declared_dimension,
        "cell_count": cell_count,
        "extent_source": "scanned_cells",
    }


def inspect_xlsx_structure(path: Path) -> Dict:
    """轻量检查一个 XLSX，并返回按工作簿顺序排列的 sheet 结构。"""
    path = Path(path)
    sheets: List[Dict] = []
    try:
        with zipfile.ZipFile(path, "r") as archive:
            members = archive.namelist()
            if len(members) != len(set(members)):
                raise ValueError("XLSX ZIP 中存在重复成员路径")

            required_members = {
                "[Content_Types].xml",
                "_rels/.rels",
                "xl/workbook.xml",
                "xl/_rels/workbook.xml.rels",
            }
            missing_members = sorted(required_members.difference(members))
            if missing_members:
                raise ValueError(
                    "XLSX 缺少必要结构: " + ", ".join(missing_members)
                )

            corrupt_member = archive.testzip()
            if corrupt_member is not None:
                raise ValueError(f"XLSX ZIP 成员 CRC 校验失败: {corrupt_member}")

            with archive.open("xl/_rels/workbook.xml.rels", "r") as stream:
                relationship_root = ElementTree.parse(stream).getroot()
            relationships = {}
            for element in relationship_root.iter():
                if _local_name(element.tag) != "Relationship":
                    continue
                relationship_id = element.attrib.get("Id")
                if not relationship_id:
                    continue
                relationships[relationship_id] = {
                    "target": element.attrib.get("Target", ""),
                    "target_mode": element.attrib.get("TargetMode", ""),
                    "type": element.attrib.get("Type", ""),
                }

            with archive.open("xl/workbook.xml", "r") as stream:
                workbook_root = ElementTree.parse(stream).getroot()
            workbook_namespace = workbook_root.tag.split("}", 1)[0].lstrip("{")
            if workbook_namespace not in {
                _MAIN_SPREADSHEET_NAMESPACE,
                _STRICT_SPREADSHEET_NAMESPACE,
            }:
                raise ValueError(
                    f"不支持的 SpreadsheetML 命名空间: "
                    f"{workbook_namespace!r}"
                )

            for sheet_element in workbook_root.iter():
                if _local_name(sheet_element.tag) != "sheet":
                    continue
                sheet_name = str(sheet_element.attrib.get("name", ""))
                relationship_id = sheet_element.attrib.get(_RELATIONSHIP_ID)
                if relationship_id is None:
                    # Strict OOXML 使用不同的 relationships 命名空间。
                    relationship_id = next(
                        (
                            value
                            for key, value in sheet_element.attrib.items()
                            if _local_name(key) == "id"
                        ),
                        None,
                    )
                relationship = relationships.get(str(relationship_id or ""))
                if relationship is None:
                    raise ValueError(
                        f"工作表 {sheet_name!r} 缺少 relationship"
                    )
                if str(relationship["target_mode"]).casefold() == "external":
                    raise ValueError(
                        f"工作表 {sheet_name!r} 使用外部 relationship"
                    )
                sheet_kind = _relationship_kind(relationship["type"])
                if sheet_kind not in _SUPPORTED_SHEET_RELATIONSHIPS:
                    raise ValueError(
                        f"工作表 {sheet_name!r} 的 relationship 类型不受支持: "
                        f"{sheet_kind!r}"
                    )
                member_name = _relationship_target(relationship["target"])
                if member_name not in members:
                    raise ValueError(
                        f"工作表 {sheet_name!r} 的 XML 不存在: {member_name}"
                    )
                sheet_structure = _inspect_sheet_xml(
                    archive,
                    member_name,
                    sheet_kind,
                )
                sheet_structure.update(
                    {
                        "name": sheet_name,
                        "state": str(
                            sheet_element.attrib.get("state", "visible")
                        ),
                        "xml_path": member_name,
                    }
                )
                sheets.append(sheet_structure)

            if not sheets:
                raise ValueError("XLSX 工作簿不包含任何 sheet")
    except Exception as exc:
        return {
            "valid": False,
            "sheet_count": len(sheets),
            "sheets": sheets,
            "error": f"{type(exc).__name__}: {str(exc)[:500]}",
        }

    return {
        "valid": True,
        "sheet_count": len(sheets),
        "sheets": sheets,
        "error": "",
    }


def _iter_xlsx_files(directory: Path) -> Iterable[Path]:
    """按稳定顺序递归枚举 XLSX，不跟随目录符号链接。"""
    for root, directory_names, file_names in os.walk(
        directory,
        topdown=True,
        followlinks=False,
    ):
        directory_names[:] = sorted(
            name
            for name in directory_names
            if not name.startswith(".")
        )
        for file_name in sorted(file_names):
            if _is_ignored_xlsx_name(file_name):
                continue
            path = Path(root) / file_name
            if path.suffix.casefold() == ".xlsx":
                yield path


def _is_ignored_xlsx_name(file_name: str) -> bool:
    """排除 Office 锁文件、隐藏文件和明确的中间态工作簿。"""
    lowered = str(file_name or "").casefold()
    if lowered.startswith((".", "~$")):
        return True
    return lowered.endswith(
        (
            ".tmp.xlsx",
            ".temp.xlsx",
            ".part.xlsx",
            ".partial.xlsx",
            ".inprogress.xlsx",
            ".lock.xlsx",
        )
    )


def _safe_output_path(child_path: Path, relative_path: object) -> Path:
    text = str(relative_path or "")
    if not text or "\\" in text:
        raise ValueError("阶段 manifest 包含无效输出路径")
    pure = PurePosixPath(text)
    if pure.is_absolute() or any(
        part in {"", ".", ".."} for part in pure.parts
    ):
        raise ValueError("阶段 manifest 包含不安全输出路径")
    if not pure.parts or pure.parts[0] not in CATEGORY_LABELS:
        raise ValueError(
            "阶段正式输出不在 standardized_data、analysis_results 或 "
            f"reports 中: {text}"
        )
    candidate = child_path.joinpath(*pure.parts)
    resolved_child = child_path.resolve()
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(resolved_child)
    except ValueError as exc:
        raise ValueError("阶段 manifest 输出路径超出子项目目录") from exc
    if candidate.is_symlink():
        raise ValueError("阶段 manifest 输出文件是符号链接")
    return candidate


class GroupArtifactInventory:
    """创建牧场组正式受管产物和未受管 XLSX 浏览索引。"""

    def __init__(
        self,
        project_path: Path,
        *,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ):
        self.project_path = Path(project_path).resolve()
        self.progress_callback = progress_callback

    def _load_tasks(self) -> List[Dict]:
        database_path = (
            self.project_path / "group_store" / "group_tasks.sqlite3"
        )
        if database_path.is_file():
            # SQLite 是新牧场组的实时状态源，可避免排除/重新纳入后读取到
            # project_metadata.json 中的旧快照。
            from utils.group_task_store import GroupTaskStore

            return GroupTaskStore(database_path).list_tasks()
        metadata_path = self.project_path / "project_metadata.json"
        with metadata_path.open("r", encoding="utf-8") as stream:
            metadata = json.load(stream)
        tasks = metadata.get("group_tasks", [])
        if not isinstance(tasks, list):
            raise ValueError("project_metadata.json 的 group_tasks 不是列表")
        return tasks

    def _child_path(self, task: Dict) -> Path:
        value = task.get("relative_path") or task.get("child_path")
        if not value:
            raise ValueError("子项目缺少 relative_path")
        path = Path(value)
        if not path.is_absolute():
            path = self.project_path / path
        # 只规范化 ``..``，不解析符号链接。验收或迁移项目可能用父目录
        # 内的子项目链接复用真实项目；它仍是父项目明确列出的子项目。
        normalized = Path(os.path.abspath(path))
        try:
            normalized.relative_to(self.project_path)
        except ValueError as exc:
            raise ValueError("子项目路径超出牧场组目录") from exc
        return normalized

    def _base_entry(
        self,
        task: Dict,
        child_path: Path,
        category: str,
        path: Path,
    ) -> Dict:
        try:
            relative_path = path.relative_to(self.project_path).as_posix()
        except ValueError:
            relative_path = ""
        try:
            category_relative_path = path.relative_to(
                child_path / category
            ).as_posix()
        except ValueError:
            category_relative_path = path.name

        entry = {
            "task_id": str(task.get("task_id") or ""),
            "farm_code": str(task.get("farm_code") or ""),
            "farm_name": str(task.get("farm_name") or ""),
            "child_relative_path": child_path.relative_to(
                self.project_path
            ).as_posix(),
            "category": category,
            "category_label": CATEGORY_LABELS[category],
            "relative_path": relative_path,
            "category_relative_path": category_relative_path,
            "file_name": path.name,
            "bytes": 0,
            "sha256": "",
            "xlsx_valid": None,
            "validation_error": "",
            "sheet_count": 0,
            "sheet_dimensions": "",
            "sheets": [],
        }
        return entry

    def _managed_xlsx_entry(
        self,
        task: Dict,
        child_path: Path,
        stage: str,
        manifest_relative_path: str,
        expected: Dict,
    ) -> Tuple[Dict, List[str]]:
        relative_output = str(expected.get("relative_path") or "")
        category = (
            PurePosixPath(relative_output).parts[0]
            if relative_output
            else "analysis_results"
        )
        path = child_path / Path(*PurePosixPath(relative_output).parts)
        entry = self._base_entry(
            task,
            child_path,
            category
            if category in CATEGORY_LABELS
            else "analysis_results",
            path,
        )
        entry.update(
            {
                "managed": True,
                "stage": stage,
                "logical_name": str(
                    expected.get("logical_name") or ""
                ),
                "manifest_relative_path": manifest_relative_path,
                "xlsx_valid": False,
            }
        )
        issues: List[str] = []

        try:
            path = _safe_output_path(child_path, relative_output)
            entry["category"] = PurePosixPath(relative_output).parts[0]
            entry["category_label"] = CATEGORY_LABELS[entry["category"]]
            before = path.stat()
            entry["bytes"] = int(before.st_size)
            expected_size = int(expected.get("size_bytes", -1))
            if expected_size != int(before.st_size):
                issues.append("文件大小与 committed manifest 不一致")

            current_sha256 = _sha256(path)
            entry["sha256"] = current_sha256
            expected_sha256 = str(expected.get("sha256") or "")
            if (
                len(expected_sha256) != 64
                or expected_sha256 != current_sha256
            ):
                issues.append("文件 SHA-256 与 committed manifest 不一致")

            structure = expected.get("xlsx")
            if not isinstance(structure, dict) or not structure.get("valid"):
                issues.append("committed manifest 缺少有效 XLSX 结构")
                structure = {"sheet_count": 0, "sheets": []}
            entry["sheet_count"] = int(
                structure.get("sheet_count", 0) or 0
            )
            entry["sheets"] = list(structure.get("sheets", []) or [])
            entry["sheet_dimensions"] = "；".join(
                f"{sheet['name']}:{sheet['max_row']}×{sheet['max_column']}"
                for sheet in entry["sheets"]
            )
            after = path.stat()
            if (
                before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
            ):
                issues.append("扫描期间文件发生变化")
        except Exception as exc:
            issues.append(f"{type(exc).__name__}: {str(exc)[:500]}")
        entry["xlsx_valid"] = not issues
        entry["validation_error"] = "；".join(dict.fromkeys(issues))
        return entry, issues

    def _unmanaged_xlsx_entry(
        self,
        task: Dict,
        child_path: Path,
        category: str,
        path: Path,
    ) -> Dict:
        entry = self._base_entry(task, child_path, category, path)
        entry.update(
            {
                "managed": False,
                "stage": "",
                "logical_name": "",
                "manifest_relative_path": "",
                "validation_error": (
                    "未受阶段 committed manifest 管理，"
                    "未参与正式完整性校验"
                ),
            }
        )
        try:
            entry["bytes"] = int(path.stat().st_size)
        except OSError as exc:
            entry["validation_error"] += (
                f"；无法读取文件属性: {type(exc).__name__}: {exc}"
            )
        return entry

    @staticmethod
    def _required_stages(task: Dict) -> Tuple[str, ...]:
        stages = task.get("stages")
        if isinstance(stages, dict):
            return tuple(
                stage
                for stage in STAGE_ORDER
                if (
                    stage in stages
                    and isinstance(stages[stage], dict)
                    and stages[stage].get("required", True)
                )
            )
        configured = task.get("required_stages")
        if isinstance(configured, (list, tuple)):
            return tuple(
                stage for stage in STAGE_ORDER if stage in configured
            )
        return STAGE_ORDER

    def _load_stage_manifest(
        self,
        task: Dict,
        child_path: Path,
        stage: str,
    ) -> Tuple[str, List[Dict]]:
        manifest_relative_path = (
            STAGE_MANIFEST_DIRECTORY / f"{stage}.json"
        ).as_posix()
        manifest_path = child_path / manifest_relative_path
        if not manifest_path.is_file():
            raise FileNotFoundError(
                f"{stage} 阶段 committed manifest 不存在"
            )
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{stage} 阶段 manifest 根节点不是对象")
        if payload.get("schema_version") != 1:
            raise ValueError(f"{stage} 阶段 manifest 版本不受支持")
        if payload.get("status") != "committed":
            raise ValueError(f"{stage} 阶段 manifest 尚未 committed")
        expected_identity = {
            "task_id": str(task.get("task_id") or ""),
            "farm_code": str(task.get("farm_code") or ""),
            "stage": stage,
        }
        for key, expected_value in expected_identity.items():
            if str(payload.get(key) or "") != expected_value:
                raise ValueError(
                    f"{stage} 阶段 manifest 身份不一致: {key}"
                )
        outputs = payload.get("outputs")
        if (
            not isinstance(outputs, list)
            or not outputs
            or any(not isinstance(item, dict) for item in outputs)
        ):
            raise ValueError(f"{stage} 阶段 manifest outputs 无效")
        for output in outputs:
            logical_name = str(output.get("logical_name") or "").strip()
            relative_path = str(output.get("relative_path") or "").strip()
            sha256 = str(output.get("sha256") or "").strip()
            try:
                size_bytes = int(output.get("size_bytes", -1))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{stage} 阶段 manifest 输出大小无效"
                ) from exc
            if (
                output.get("kind") != "output"
                or not logical_name
                or not relative_path
                or size_bytes < 0
                or re.fullmatch(r"[0-9a-f]{64}", sha256) is None
            ):
                raise ValueError(
                    f"{stage} 阶段 manifest 输出记录无效"
                )
        return manifest_relative_path, list(outputs)

    def build(
        self,
        *,
        tasks: Optional[Sequence[Dict]] = None,
        manifest_path: Optional[Path] = None,
    ) -> Dict:
        """扫描所有纳入汇总的任务并原子生成 JSON manifest。"""
        selected_tasks = [
            dict(task)
            for task in (tasks if tasks is not None else self._load_tasks())
            if task.get("included_in_summary", True)
        ]
        output_path = Path(
            manifest_path
            or self.project_path / "reports" / "全部结果文件清单.json"
        )
        if not output_path.is_absolute():
            output_path = self.project_path / output_path

        files: List[Dict] = []
        unmanaged_files: List[Dict] = []
        task_entries: List[Dict] = []
        task_issues: List[Dict] = []
        category_counts = {category: 0 for category in CATEGORY_ORDER}
        category_bytes = {category: 0 for category in CATEGORY_ORDER}
        unmanaged_category_counts = {
            category: 0 for category in CATEGORY_ORDER
        }
        unmanaged_category_bytes = {
            category: 0 for category in CATEGORY_ORDER
        }
        managed_output_count = 0
        managed_non_xlsx_output_count = 0
        total_tasks = max(len(selected_tasks), 1)

        for task_index, task in enumerate(selected_tasks):
            task_id = str(task.get("task_id") or "")
            farm_code = str(task.get("farm_code") or "")
            farm_name = str(task.get("farm_name") or "")
            task_file_start = len(files)
            task_unmanaged_start = len(unmanaged_files)
            task_output_count = 0
            issues: List[str] = []
            child_relative_path = str(
                task.get("relative_path") or task.get("child_path") or ""
            )
            _progress(
                self.progress_callback,
                5 + int(85 * task_index / total_tasks),
                f"检查牧场结果：{farm_name or farm_code or task_id}",
            )

            try:
                child_path = self._child_path(task)
                child_relative_path = child_path.relative_to(
                    self.project_path
                ).as_posix()
                if not child_path.is_dir():
                    raise FileNotFoundError(f"子项目目录不存在: {child_path}")

                managed_paths = set()
                for stage in self._required_stages(task):
                    try:
                        (
                            manifest_relative_path,
                            outputs,
                        ) = self._load_stage_manifest(
                            task,
                            child_path,
                            stage,
                        )
                    except Exception as exc:
                        issues.append(
                            f"{type(exc).__name__}: {str(exc)[:500]}"
                        )
                        continue

                    for expected in outputs:
                        task_output_count += 1
                        managed_output_count += 1
                        relative_output = str(
                            expected.get("relative_path") or ""
                        )
                        try:
                            path = _safe_output_path(
                                child_path,
                                relative_output,
                            )
                            canonical = path.resolve().as_posix()
                            if canonical in managed_paths:
                                raise ValueError(
                                    "正式输出被多个阶段 manifest 重复登记: "
                                    f"{relative_output}"
                                )
                            managed_paths.add(canonical)
                        except Exception as exc:
                            issues.append(
                                f"{type(exc).__name__}: {str(exc)[:500]}"
                            )
                            if Path(relative_output).suffix.casefold() != ".xlsx":
                                continue

                        if Path(relative_output).suffix.casefold() == ".xlsx":
                            entry, entry_issues = self._managed_xlsx_entry(
                                task,
                                child_path,
                                stage,
                                manifest_relative_path,
                                expected,
                            )
                            files.append(entry)
                            category = entry["category"]
                            category_counts[category] += 1
                            category_bytes[category] += int(entry["bytes"])
                            issues.extend(entry_issues)
                        else:
                            managed_non_xlsx_output_count += 1
                            try:
                                path = _safe_output_path(
                                    child_path,
                                    relative_output,
                                )
                                before = path.stat()
                                if int(
                                    expected.get("size_bytes", -1)
                                ) != int(before.st_size):
                                    issues.append(
                                        "非 XLSX 正式输出大小与 committed "
                                        f"manifest 不一致: {relative_output}"
                                    )
                                if str(
                                    expected.get("sha256") or ""
                                ) != _sha256(path):
                                    issues.append(
                                        "非 XLSX 正式输出 SHA-256 与 committed "
                                        f"manifest 不一致: {relative_output}"
                                    )
                                after = path.stat()
                                if (
                                    before.st_size != after.st_size
                                    or before.st_mtime_ns
                                    != after.st_mtime_ns
                                ):
                                    issues.append(
                                        "扫描期间非 XLSX 正式输出发生变化: "
                                        f"{relative_output}"
                                    )
                            except Exception as exc:
                                issues.append(
                                    f"{type(exc).__name__}: "
                                    f"{str(exc)[:500]}"
                                )

                for category in CATEGORY_ORDER:
                    category_path = child_path / category
                    if not category_path.is_dir():
                        continue
                    for path in _iter_xlsx_files(category_path):
                        if path.resolve().as_posix() in managed_paths:
                            continue
                        entry = self._unmanaged_xlsx_entry(
                            task,
                            child_path,
                            category,
                            path,
                        )
                        unmanaged_files.append(entry)
                        unmanaged_category_counts[category] += 1
                        unmanaged_category_bytes[category] += int(
                            entry["bytes"]
                        )
            except Exception as exc:
                issues.append(f"{type(exc).__name__}: {str(exc)[:500]}")

            issue = "；".join(dict.fromkeys(issues))
            if issue:
                task_issues.append(
                    {
                        "task_id": task_id,
                        "farm_code": farm_code,
                        "farm_name": farm_name,
                        "child_relative_path": child_relative_path,
                        "error": issue,
                    }
                )

            task_files = files[task_file_start:]
            task_unmanaged_files = unmanaged_files[task_unmanaged_start:]
            task_entries.append(
                {
                    "task_id": task_id,
                    "farm_code": farm_code,
                    "farm_name": farm_name,
                    "child_relative_path": child_relative_path,
                    "managed_output_count": task_output_count,
                    "file_count": len(task_files),
                    "managed_file_count": len(task_files),
                    "unmanaged_file_count": len(task_unmanaged_files),
                    "index_file_count": (
                        len(task_files) + len(task_unmanaged_files)
                    ),
                    "valid_file_count": sum(
                        bool(entry["xlsx_valid"]) for entry in task_files
                    ),
                    "invalid_file_count": sum(
                        not bool(entry["xlsx_valid"]) for entry in task_files
                    ),
                    "bytes": sum(int(entry["bytes"]) for entry in task_files),
                    "scan_error": issue,
                }
            )

        valid_file_count = sum(bool(entry["xlsx_valid"]) for entry in files)
        invalid_file_count = len(files) - valid_file_count
        status = (
            "complete"
            if invalid_file_count == 0 and not task_issues
            else "partial"
        )
        manifest = {
            "schema_version": 1,
            "status": status,
            "generated_at": _utc_now(),
            "project_path": self.project_path.as_posix(),
            "counts": {
                "included_tasks": len(selected_tasks),
                "scanned_tasks": len(task_entries),
                "tasks_with_scan_errors": len(task_issues),
                "total_files": len(files),
                "valid_files": valid_file_count,
                "invalid_files": invalid_file_count,
                "total_bytes": sum(int(entry["bytes"]) for entry in files),
                "managed_outputs": managed_output_count,
                "managed_non_xlsx_outputs": managed_non_xlsx_output_count,
                "unmanaged_files": len(unmanaged_files),
                "unmanaged_bytes": sum(
                    int(entry["bytes"]) for entry in unmanaged_files
                ),
                "index_files": len(files) + len(unmanaged_files),
                "by_category": {
                    category: {
                        "label": CATEGORY_LABELS[category],
                        "files": category_counts[category],
                        "bytes": category_bytes[category],
                        "unmanaged_files": unmanaged_category_counts[
                            category
                        ],
                        "unmanaged_bytes": unmanaged_category_bytes[
                            category
                        ],
                    }
                    for category in CATEGORY_ORDER
                },
            },
            "index_columns": [
                {"key": "task_id", "label": "任务ID"},
                {"key": "farm_code", "label": "牧场编号"},
                {"key": "farm_name", "label": "牧场名称"},
                {"key": "category_label", "label": "类别"},
                {"key": "managed", "label": "受管产物"},
                {"key": "stage", "label": "阶段"},
                {"key": "logical_name", "label": "逻辑名称"},
                {"key": "relative_path", "label": "相对路径"},
                {"key": "bytes", "label": "字节数"},
                {"key": "sha256", "label": "SHA256"},
                {"key": "xlsx_valid", "label": "XLSX结构有效"},
                {"key": "validation_error", "label": "校验错误"},
                {"key": "sheet_count", "label": "Sheet数"},
                {"key": "sheet_dimensions", "label": "Sheet行列范围"},
            ],
            "tasks": task_entries,
            "task_issues": task_issues,
            "files": files,
            "unmanaged_files": unmanaged_files,
        }

        _progress(self.progress_callback, 95, "写入全部结果文件清单")
        _write_json_atomic(output_path, manifest)
        result = dict(manifest)
        result["manifest_path"] = output_path.as_posix()
        result["manifest_sha256"] = _sha256(output_path)
        _progress(self.progress_callback, 100, "全部结果文件清单已完成")
        return result


def build_group_artifact_inventory(
    project_path: Path,
    *,
    tasks: Optional[Sequence[Dict]] = None,
    manifest_path: Optional[Path] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Dict:
    """函数式入口，便于牧场组主报告生成器直接调用。"""
    return GroupArtifactInventory(
        project_path,
        progress_callback=progress_callback,
    ).build(
        tasks=tasks,
        manifest_path=manifest_path,
    )


__all__ = [
    "CATEGORY_LABELS",
    "GroupArtifactInventory",
    "build_group_artifact_inventory",
    "inspect_xlsx_structure",
]
