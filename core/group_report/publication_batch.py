"""牧场组报告包的可恢复构建与原子发布。

所有派生结果先写入按输入快照指纹命名的隐藏目录。只有汇总 Excel、完整
明细、文件清单及其相互校验全部通过后，才把整个目录一次性提升为可见
报告包，并以一个很小的 ``current_group_report.json`` 原子指针登记当前
正式版本。

报告包目录是不可变的。失败或中断只会留下隐藏 ``.resume`` 目录，后续
相同输入可继续使用；不会在 ``reports`` 根目录散落看似正式的半成品。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


BATCH_SCHEMA_VERSION = 1
CURRENT_POINTER_SCHEMA_VERSION = 1
SNAPSHOT_SCHEMA_VERSION = 1
SNAPSHOT_KIND = "group_summary_publication_inputs"
EXCEL_MAX_DATA_ROWS = 1_048_575


class GroupReportPublicationError(RuntimeError):
    """报告包不满足正式发布条件。"""


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _valid_sha256(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if len(text) != 64:
        return False
    try:
        int(text, 16)
    except ValueError:
        return False
    return True


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        # Windows、部分网络盘和沙盒文件系统不支持目录 fsync。
        pass


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
        _fsync_directory(path.parent)
    finally:
        if descriptor_open:
            try:
                os.close(descriptor)
            except OSError:
                pass
        temporary.unlink(missing_ok=True)


def _atomic_copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    descriptor_open = True
    try:
        with source.open("rb") as input_stream, os.fdopen(
            descriptor,
            "wb",
        ) as output_stream:
            descriptor_open = False
            shutil.copyfileobj(input_stream, output_stream, 1024 * 1024)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    finally:
        if descriptor_open:
            try:
                os.close(descriptor)
            except OSError:
                pass
        temporary.unlink(missing_ok=True)


def _reject_symlink_chain(root: Path, candidate: Path, label: str) -> None:
    """拒绝 root 以下任一现存路径组件为符号链接。"""
    try:
        relative = candidate.absolute().relative_to(root.absolute())
    except ValueError as exc:
        raise GroupReportPublicationError(f"{label}超出报告目录") from exc
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise GroupReportPublicationError(f"{label}不能经过符号链接")


def _inside(root: Path, path: Path, label: str) -> Path:
    root = root.resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise GroupReportPublicationError(
            f"{label}超出报告批次目录"
        ) from exc
    _reject_symlink_chain(root, candidate, label)
    return resolved


def _read_json(path: Path, label: str) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GroupReportPublicationError(f"{label}无法读取") from exc
    if not isinstance(value, dict):
        raise GroupReportPublicationError(f"{label}根节点不是对象")
    return value


def _validate_xlsx_archive(path: Path, label: str) -> None:
    if (
        not path.is_file()
        or path.stat().st_size <= 0
        or not zipfile.is_zipfile(path)
    ):
        raise GroupReportPublicationError(f"{label}结构无效")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            members = archive.namelist()
            required = {
                "[Content_Types].xml",
                "xl/workbook.xml",
            }
            if not required.issubset(members):
                raise GroupReportPublicationError(
                    f"{label}缺少必需 XLSX 结构"
                )
            bad_member = archive.testzip()
            if bad_member is not None:
                raise GroupReportPublicationError(
                    f"{label} CRC 校验失败: {bad_member}"
                )
    except zipfile.BadZipFile as exc:
        raise GroupReportPublicationError(f"{label}结构无效") from exc


def _safe_relative_inside(root: Path, value: Any, label: str) -> Path:
    text = str(value or "").strip()
    relative = Path(text)
    if (
        not text
        or relative.is_absolute()
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise GroupReportPublicationError(f"{label}不是安全相对路径")
    return _inside(root, root / relative, label)


def _validate_internal_file_entry(
    package: Path,
    entry: Any,
    label: str,
    *,
    xlsx: bool = False,
) -> Path:
    if not isinstance(entry, dict):
        raise GroupReportPublicationError(f"{label}记录无效")
    path = _safe_relative_inside(
        package,
        entry.get("relative_path"),
        label,
    )
    try:
        expected_bytes = int(entry.get("bytes", -1))
    except (TypeError, ValueError) as exc:
        raise GroupReportPublicationError(f"{label}大小记录无效") from exc
    expected_sha = str(entry.get("sha256") or "").lower()
    if (
        expected_bytes < 0
        or not _valid_sha256(expected_sha)
        or not path.is_file()
        or path.stat().st_size != expected_bytes
        or _sha256(path) != expected_sha
    ):
        raise GroupReportPublicationError(f"{label}大小或 SHA-256 不一致")
    if xlsx:
        _validate_xlsx_archive(path, label)
    return path


def _validate_package_manifest(
    project: Path,
    package: Path,
    manifest_path: Path,
    *,
    expected_manifest_sha256: Optional[str] = None,
    expected_selection_revision: Optional[int] = None,
    expected_basis_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    reports_root = (project / "reports").resolve()
    package = _inside(reports_root, package, "报告包")
    if package.parent != reports_root or package.name.startswith("."):
        raise GroupReportPublicationError(
            "正式报告包必须是 reports 下的非隐藏直接子目录"
        )
    manifest_path = _inside(package, manifest_path, "报告包 manifest")
    if manifest_path != package / "batch_manifest.json":
        raise GroupReportPublicationError("报告包 manifest 路径不固定")
    manifest_sha256 = _sha256(manifest_path)
    if (
        expected_manifest_sha256 is not None
        and manifest_sha256
        != str(expected_manifest_sha256 or "").strip().lower()
    ):
        raise GroupReportPublicationError(
            "报告包 manifest SHA-256 不一致"
        )
    manifest = _read_json(manifest_path, "报告包 manifest")
    if (
        manifest.get("schema_version") != BATCH_SCHEMA_VERSION
        or manifest.get("kind") != "multi_farm_group_report_package"
        or manifest.get("status") != "complete"
    ):
        raise GroupReportPublicationError("报告包 manifest 类型或状态无效")
    try:
        revision = int(manifest["selection_revision"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GroupReportPublicationError(
            "报告包 manifest 缺少有效 selection_revision"
        ) from exc
    basis_sha256 = str(
        manifest.get("publication_basis_sha256") or ""
    ).lower()
    if not _valid_sha256(basis_sha256):
        raise GroupReportPublicationError(
            "报告包 manifest 发布摘要无效"
        )
    if (
        expected_selection_revision is not None
        and revision != int(expected_selection_revision)
    ):
        raise GroupReportPublicationError(
            "报告包 selection_revision 与发布请求不一致"
        )
    if (
        expected_basis_sha256 is not None
        and basis_sha256
        != str(expected_basis_sha256 or "").strip().lower()
    ):
        raise GroupReportPublicationError(
            "报告包输入摘要与发布请求不一致"
        )

    excel_path = _validate_internal_file_entry(
        package,
        manifest.get("excel"),
        "汇总 Excel",
        xlsx=True,
    )
    detail_manifest_path = _validate_internal_file_entry(
        package,
        manifest.get("detail"),
        "完整明细 manifest",
    )
    inventory_path = _validate_internal_file_entry(
        package,
        manifest.get("inventory"),
        "结果文件清单",
    )
    snapshot_path = _validate_internal_file_entry(
        package,
        manifest.get("publication_snapshot"),
        "发布快照",
    )

    detail_manifest = _read_json(
        detail_manifest_path,
        "完整明细 manifest",
    )
    if detail_manifest.get("status") != "complete":
        raise GroupReportPublicationError("完整明细 manifest 状态无效")
    detail_root = detail_manifest_path.parent
    for kind in ("ranked", "reconciliation", "long_fields"):
        entries = detail_manifest.get("volumes", {}).get(kind)
        if not isinstance(entries, list):
            raise GroupReportPublicationError(
                f"完整明细缺少 {kind} 分卷"
            )
        for entry in entries:
            if not isinstance(entry, dict):
                raise GroupReportPublicationError("完整明细分卷记录无效")
            volume_entry = {
                "relative_path": entry.get("path"),
                "bytes": entry.get("bytes"),
                "sha256": entry.get("sha256"),
            }
            _validate_internal_file_entry(
                detail_root,
                volume_entry,
                "完整明细分卷",
                xlsx=True,
            )

    inventory = _read_json(inventory_path, "结果文件清单")
    if inventory.get("status") != "complete":
        raise GroupReportPublicationError("结果文件清单状态无效")
    snapshot = _read_json(snapshot_path, "发布快照")
    snapshot_basis = snapshot.get("basis")
    try:
        snapshot_revision = int(
            snapshot_basis.get("selection_revision", -1)
            if isinstance(snapshot_basis, dict)
            else -1
        )
    except (TypeError, ValueError) as exc:
        raise GroupReportPublicationError(
            "报告包内发布快照 selection_revision 无效"
        ) from exc
    if (
        snapshot.get("schema_version") != SNAPSHOT_SCHEMA_VERSION
        or snapshot.get("kind") != SNAPSHOT_KIND
        or not isinstance(snapshot_basis, dict)
        or _canonical_sha256(snapshot_basis) != basis_sha256
        or str(snapshot.get("basis_sha256") or "").lower() != basis_sha256
        or snapshot_revision != revision
    ):
        raise GroupReportPublicationError("报告包内发布快照校验失败")
    return {
        "manifest": manifest,
        "manifest_sha256": manifest_sha256,
        "selection_revision": revision,
        "publication_basis_sha256": basis_sha256,
        "excel_path": excel_path,
        "excel_sha256": _sha256(excel_path),
        "detail_manifest_path": detail_manifest_path,
        "inventory_path": inventory_path,
        "snapshot_path": snapshot_path,
    }


class GroupReportPublicationBatch:
    """一个与冻结输入快照绑定的报告构建批次。"""

    def __init__(
        self,
        project_path: Path,
        *,
        publication_basis_sha256: str,
        selection_revision: int,
    ):
        self.project_path = Path(project_path).resolve()
        self.reports_root = self.project_path / "reports"
        self.reports_root.mkdir(parents=True, exist_ok=True)
        basis = str(publication_basis_sha256 or "").strip().lower()
        if len(basis) != 64:
            raise ValueError("publication_basis_sha256 必须是 SHA-256")
        try:
            int(basis, 16)
        except ValueError as exc:
            raise ValueError(
                "publication_basis_sha256 必须是 SHA-256"
            ) from exc
        self.publication_basis_sha256 = basis
        self.selection_revision = int(selection_revision)
        self.staging_path = (
            self.reports_root
            / f".group_report_{basis[:20]}.resume"
        )
        self.detail_root = self.staging_path / "完整明细"
        self.inventory_path = self.staging_path / "牧场组结果文件清单.json"
        self.excel_path = self.staging_path / "牧场组育种分析汇总报告.xlsx"
        self.batch_manifest_path = self.staging_path / "batch_manifest.json"
        self.state_path = self.staging_path / "batch_state.json"
        self.staging_path.mkdir(parents=False, exist_ok=True)
        self.detail_root.mkdir(parents=True, exist_ok=True)
        self._initialize_state()

    def _initialize_state(self) -> None:
        expected = {
            "schema_version": BATCH_SCHEMA_VERSION,
            "publication_basis_sha256": self.publication_basis_sha256,
            "selection_revision": self.selection_revision,
        }
        if self.state_path.is_file():
            current = _read_json(self.state_path, "报告批次状态")
            for key, value in expected.items():
                if current.get(key) != value:
                    raise GroupReportPublicationError(
                        "隐藏恢复目录与当前发布输入不一致"
                    )
            return
        _atomic_write_json(
            self.state_path,
            {
                **expected,
                "batch_id": str(uuid.uuid4()),
                "created_at": _utc_now(),
                "status": "building",
            },
        )

    def load_completed_detail(
        self,
        package_name: str,
    ) -> Optional[Dict[str, Any]]:
        """验证并复用相同输入上次已经完成的全量明细包。"""
        package_path = self.detail_root / str(package_name)
        manifest_path = package_path / "manifest.json"
        if not manifest_path.is_file():
            return None
        manifest = _read_json(manifest_path, "完整明细 manifest")
        if manifest.get("status") != "complete":
            return None
        try:
            # “文件还在且哈希相同”并不足以证明可复用；分片缺列、
            # 长字段少块或来源计数矛盾也必须触发重建。
            self._validate_detail(manifest_path)
        except GroupReportPublicationError:
            return None
        result = dict(manifest)
        result["package_path"] = str(package_path)
        result["manifest_path"] = str(manifest_path)
        result["manifest_sha256"] = _sha256(manifest_path)
        result["resumed_complete_package"] = True
        copied_volumes: Dict[str, list[Dict[str, Any]]] = {}
        for kind in ("ranked", "reconciliation", "long_fields"):
            copied_volumes[kind] = []
            for source in manifest["volumes"][kind]:
                entry = dict(source)
                entry["absolute_path"] = str(
                    package_path / str(entry["path"])
                )
                copied_volumes[kind].append(entry)
        result["volumes"] = copied_volumes
        return result

    def _validate_excel(self, path: Path) -> Dict[str, Any]:
        path = _inside(self.staging_path, path, "汇总 Excel")
        _validate_xlsx_archive(path, "汇总 Excel")
        return {
            "relative_path": path.relative_to(self.staging_path).as_posix(),
            "bytes": int(path.stat().st_size),
            "sha256": _sha256(path),
        }

    def _validate_detail(
        self,
        detail_manifest_path: Path,
    ) -> Dict[str, Any]:
        manifest_path = _inside(
            self.staging_path,
            detail_manifest_path,
            "完整明细 manifest",
        )
        manifest = _read_json(manifest_path, "完整明细 manifest")
        if manifest.get("status") != "complete":
            raise GroupReportPublicationError("完整明细尚未通过全量核对")
        package_path = manifest_path.parent
        volume_count = 0
        volume_rows = 0
        seen_paths = set()
        rows_by_kind_and_part: Dict[str, Dict[int, int]] = {
            "ranked": {},
            "reconciliation": {},
            "long_fields": {},
        }
        entries_by_kind_and_part: Dict[
            str, Dict[int, list[Dict[str, Any]]]
        ] = {
            "ranked": {},
            "reconciliation": {},
            "long_fields": {},
        }
        declared_parts_by_kind: Dict[str, set[int]] = {
            "ranked": set(),
            "reconciliation": set(),
            "long_fields": set(),
        }
        for kind in ("ranked", "reconciliation", "long_fields"):
            values = manifest.get("volumes", {}).get(kind)
            if not isinstance(values, list):
                raise GroupReportPublicationError(
                    f"完整明细缺少 {kind} 分卷清单"
                )
            for entry in values:
                if not isinstance(entry, dict):
                    raise GroupReportPublicationError("完整明细分卷记录无效")
                relative_value = str(entry.get("path") or "")
                if not relative_value or relative_value in seen_paths:
                    raise GroupReportPublicationError(
                        "完整明细分卷路径为空或重复"
                    )
                seen_paths.add(relative_value)
                path = _inside(
                    package_path,
                    package_path / relative_value,
                    "完整明细分卷",
                )
                if not path.is_file():
                    raise GroupReportPublicationError(
                        f"完整明细分卷不存在: {path.name}"
                    )
                if path.stat().st_size != int(entry.get("bytes", -1)):
                    raise GroupReportPublicationError(
                        f"完整明细分卷大小不一致: {path.name}"
                    )
                if _sha256(path) != str(entry.get("sha256") or ""):
                    raise GroupReportPublicationError(
                        f"完整明细分卷 SHA-256 不一致: {path.name}"
                    )
                _validate_xlsx_archive(path, f"完整明细分卷 {path.name}")
                try:
                    data_rows = int(entry.get("data_rows", -1))
                    column_part = int(entry.get("column_part", 1))
                    column_parts = int(entry.get("column_parts", 1))
                    volume_number = int(entry.get("volume", -1))
                    rows_per_volume = int(
                        entry.get("rows_per_volume", -1)
                    )
                except (TypeError, ValueError) as exc:
                    raise GroupReportPublicationError(
                        "完整明细分卷行数记录无效"
                    ) from exc
                if (
                    data_rows < 0
                    or data_rows > EXCEL_MAX_DATA_ROWS
                    or column_part < 1
                    or column_parts < 1
                    or column_part > column_parts
                    or volume_number < 1
                    or rows_per_volume < 1
                    or rows_per_volume > EXCEL_MAX_DATA_ROWS
                    or data_rows > rows_per_volume
                ):
                    raise GroupReportPublicationError(
                        "完整明细分卷行数、卷号或字段分片无效"
                    )
                volume_count += 1
                volume_rows += data_rows
                declared_parts_by_kind[kind].add(column_parts)
                rows_by_kind_and_part[kind][column_part] = (
                    rows_by_kind_and_part[kind].get(column_part, 0)
                    + data_rows
                )
                entries_by_kind_and_part[kind].setdefault(
                    column_part,
                    [],
                ).append(entry)
        counts = manifest.get("counts")
        if not isinstance(counts, dict):
            raise GroupReportPublicationError("完整明细缺少 counts")

        def required_count(name: str) -> int:
            try:
                value = int(counts[name])
            except (KeyError, TypeError, ValueError) as exc:
                raise GroupReportPublicationError(
                    f"完整明细缺少有效计数 {name}"
                ) from exc
            if value < 0:
                raise GroupReportPublicationError(
                    f"完整明细计数 {name} 不能为负数"
                )
            return value

        source_rows = required_count("source_rows")
        ranked_rows = required_count("valid_ranked_rows")
        unranked_rows = required_count("unranked_rows")
        tasks_in_scope = required_count("tasks_in_scope")
        source_files_read = required_count("source_files_read")
        ranked_exported = required_count("ranked_exported_rows")
        reconciliation_exported = required_count(
            "reconciliation_exported_rows"
        )
        source_problems = required_count("source_files_with_problem")
        long_field_count = required_count("long_field_count")
        long_field_chunk_count = required_count(
            "long_field_chunk_count"
        )
        if source_problems:
            raise GroupReportPublicationError(
                "完整明细仍包含来源文件异常"
            )
        if tasks_in_scope <= 0:
            raise GroupReportPublicationError(
                "完整明细没有纳入任何牧场任务"
            )
        sources = manifest.get("sources")
        if not isinstance(sources, list):
            raise GroupReportPublicationError(
                "完整明细缺少来源文件清单"
            )
        if not (
            tasks_in_scope
            == source_files_read
            == len(sources)
        ):
            raise GroupReportPublicationError(
                "完整明细纳入任务数、已读来源数与来源清单不一致"
            )
        source_keys = set()
        source_rows_from_sources = 0
        for source in sources:
            if not isinstance(source, dict):
                raise GroupReportPublicationError(
                    "完整明细来源文件记录无效"
                )
            source_key = str(source.get("source_key") or "")
            if not source_key or source_key in source_keys:
                raise GroupReportPublicationError(
                    "完整明细来源键为空或重复"
                )
            source_keys.add(source_key)
            if source.get("status") != "read":
                raise GroupReportPublicationError(
                    "完整明细来源文件状态未全部通过"
                )
            try:
                rows_read = int(source.get("rows_read", -1))
            except (TypeError, ValueError) as exc:
                raise GroupReportPublicationError(
                    "完整明细来源文件行数无效"
                ) from exc
            if rows_read < 0:
                raise GroupReportPublicationError(
                    "完整明细来源文件行数不能为负数"
                )
            source_rows_from_sources += rows_read
        if source_rows_from_sources != source_rows:
            raise GroupReportPublicationError(
                "完整明细各来源行数合计与源行数不一致"
            )
        if source_rows != ranked_rows + unranked_rows:
            raise GroupReportPublicationError(
                "完整明细源行数不等于有效排名与未排名行数之和"
            )
        reason_counts = counts.get("unranked_reason_counts")
        if not isinstance(reason_counts, dict):
            raise GroupReportPublicationError(
                "完整明细缺少未排名原因计数"
            )
        reason_total = 0
        for reason, raw_count in reason_counts.items():
            if not str(reason or "").strip():
                raise GroupReportPublicationError(
                    "完整明细存在空的未排名原因"
                )
            try:
                reason_count = int(raw_count)
            except (TypeError, ValueError) as exc:
                raise GroupReportPublicationError(
                    "完整明细未排名原因计数无效"
                ) from exc
            if reason_count < 0:
                raise GroupReportPublicationError(
                    "完整明细未排名原因计数不能为负数"
                )
            reason_total += reason_count
        if reason_total != unranked_rows:
            raise GroupReportPublicationError(
                "完整明细未排名原因合计与未排名行数不一致"
            )

        def validate_parts(kind: str, expected_rows: int) -> None:
            totals = rows_by_kind_and_part[kind]
            declared_values = declared_parts_by_kind[kind]
            if not totals:
                if expected_rows:
                    raise GroupReportPublicationError(
                        f"完整明细 {kind} 缺少分卷"
                    )
                return
            if len(declared_values) != 1:
                raise GroupReportPublicationError(
                    f"完整明细 {kind} 的字段分片总数声明不一致"
                )
            declared_total = next(iter(declared_values))
            expected_parts = set(range(1, declared_total + 1))
            if set(totals) != expected_parts:
                raise GroupReportPublicationError(
                    f"完整明细 {kind} 的字段分片未完整覆盖 1.."
                    f"{declared_total}"
                )
            for column_part in sorted(totals):
                entries = sorted(
                    entries_by_kind_and_part[kind][column_part],
                    key=lambda item: int(item["volume"]),
                )
                actual_volumes = [
                    int(item["volume"]) for item in entries
                ]
                expected_volumes = list(
                    range(1, len(entries) + 1)
                )
                if actual_volumes != expected_volumes:
                    raise GroupReportPublicationError(
                        f"完整明细 {kind} 字段分片 {column_part} "
                        "卷号不连续"
                    )
                if totals[column_part] != expected_rows:
                    raise GroupReportPublicationError(
                        f"完整明细 {kind} 字段分片 {column_part} "
                        "累计行数不一致"
                    )
                if kind == "ranked":
                    next_rank = 1
                    for entry in entries:
                        data_rows = int(entry["data_rows"])
                        first_rank = entry.get("first_rank")
                        last_rank = entry.get("last_rank")
                        if data_rows == 0:
                            if first_rank is not None or last_rank is not None:
                                raise GroupReportPublicationError(
                                    "空排名分卷不应记录排名边界"
                                )
                            continue
                        try:
                            first_rank = int(first_rank)
                            last_rank = int(last_rank)
                        except (TypeError, ValueError) as exc:
                            raise GroupReportPublicationError(
                                "完整排名分卷缺少有效排名边界"
                            ) from exc
                        if (
                            first_rank != next_rank
                            or last_rank
                            != next_rank + data_rows - 1
                        ):
                            raise GroupReportPublicationError(
                                "完整排名分卷排名边界不连续"
                            )
                        next_rank = last_rank + 1

        validate_parts("ranked", ranked_rows)
        validate_parts("reconciliation", source_rows)
        validate_parts("long_fields", long_field_chunk_count)
        if not (
            ranked_rows == ranked_exported
        ):
            raise GroupReportPublicationError(
                "完整排名 manifest 行数对账不一致"
            )
        if not (
            source_rows == reconciliation_exported
        ):
            raise GroupReportPublicationError(
                "完整源行对账 manifest 行数不一致"
            )
        if (
            (long_field_count == 0) != (long_field_chunk_count == 0)
            or long_field_count > long_field_chunk_count
        ):
            raise GroupReportPublicationError(
                "超长字段数量与完整内容分块数量不一致"
            )
        return {
            "relative_path": manifest_path.relative_to(
                self.staging_path
            ).as_posix(),
            "bytes": int(manifest_path.stat().st_size),
            "sha256": _sha256(manifest_path),
            "volume_count": volume_count,
            "volume_rows_including_column_parts": volume_rows,
            "counts": counts,
        }

    def _validate_inventory(self, inventory_path: Path) -> Dict[str, Any]:
        path = _inside(
            self.staging_path,
            inventory_path,
            "结果文件清单",
        )
        manifest = _read_json(path, "结果文件清单")
        if manifest.get("status") != "complete":
            raise GroupReportPublicationError("结果文件清单尚未通过校验")
        counts = manifest.get("counts")
        files = manifest.get("files")
        if not isinstance(counts, dict) or not isinstance(files, list):
            raise GroupReportPublicationError(
                "结果文件清单缺少 counts 或 files"
            )
        try:
            total_files = int(counts["total_files"])
            valid_files = int(counts["valid_files"])
            invalid_files = int(counts["invalid_files"])
            scan_errors = int(counts.get("tasks_with_scan_errors", 0))
        except (KeyError, TypeError, ValueError) as exc:
            raise GroupReportPublicationError(
                "结果文件清单计数无效"
            ) from exc
        if (
            total_files != len(files)
            or valid_files != total_files
            or invalid_files != 0
            or scan_errors != 0
        ):
            raise GroupReportPublicationError(
                "结果文件清单计数未通过完整性校验"
            )
        seen_paths = set()
        for entry in files:
            if not isinstance(entry, dict):
                raise GroupReportPublicationError(
                    "结果文件清单记录无效"
                )
            relative_value = str(entry.get("relative_path") or "")
            if not relative_value or relative_value in seen_paths:
                raise GroupReportPublicationError(
                    "结果文件清单路径为空或重复"
                )
            seen_paths.add(relative_value)
            artifact = _inside(
                self.project_path,
                self.project_path / relative_value,
                "结果文件清单产物",
            )
            if (
                not artifact.is_file()
                or artifact.stat().st_size != int(entry.get("bytes", -1))
                or _sha256(artifact) != str(entry.get("sha256") or "")
                or not bool(entry.get("xlsx_valid"))
            ):
                raise GroupReportPublicationError(
                    f"结果文件清单产物已变化或无效: {artifact.name}"
                )
            _validate_xlsx_archive(
                artifact,
                f"结果文件清单产物 {artifact.name}",
            )
        return {
            "relative_path": path.relative_to(self.staging_path).as_posix(),
            "bytes": int(path.stat().st_size),
            "sha256": _sha256(path),
            "counts": counts,
        }

    def _validate_and_copy_snapshot(
        self,
        publication_snapshot_path: Path,
    ) -> Dict[str, Any]:
        snapshot = Path(publication_snapshot_path)
        if snapshot.is_symlink():
            raise GroupReportPublicationError("发布快照不能是符号链接")
        snapshot = snapshot.resolve()
        try:
            source_relative = snapshot.relative_to(self.project_path)
        except ValueError as exc:
            raise GroupReportPublicationError(
                "发布快照超出牧场组项目目录"
            ) from exc
        if not snapshot.is_file():
            raise GroupReportPublicationError("发布快照不存在")
        value = _read_json(snapshot, "发布快照")
        if (
            value.get("schema_version") != SNAPSHOT_SCHEMA_VERSION
            or value.get("kind") != SNAPSHOT_KIND
        ):
            raise GroupReportPublicationError("发布快照类型或版本无效")
        basis = value.get("basis")
        if not isinstance(basis, dict):
            raise GroupReportPublicationError("发布快照缺少稳定 basis")
        basis_sha256 = str(value.get("basis_sha256") or "").lower()
        if (
            not _valid_sha256(basis_sha256)
            or _canonical_sha256(basis) != basis_sha256
        ):
            raise GroupReportPublicationError(
                "发布快照 basis SHA-256 校验失败"
            )
        if basis_sha256 != self.publication_basis_sha256:
            raise GroupReportPublicationError(
                "发布快照与报告批次输入摘要不一致"
            )
        try:
            snapshot_revision = int(basis["selection_revision"])
        except (KeyError, TypeError, ValueError) as exc:
            raise GroupReportPublicationError(
                "发布快照缺少有效 selection_revision"
            ) from exc
        if snapshot_revision != self.selection_revision:
            raise GroupReportPublicationError(
                "发布快照与报告批次选择版本不一致"
            )

        copied_path = self.staging_path / "publication_snapshot.json"
        source_sha256 = _sha256(snapshot)
        _atomic_copy_file(snapshot, copied_path)
        if _sha256(copied_path) != source_sha256:
            raise GroupReportPublicationError("发布快照复制后 SHA-256 不一致")
        return {
            "relative_path": copied_path.relative_to(
                self.staging_path
            ).as_posix(),
            "bytes": int(copied_path.stat().st_size),
            "sha256": source_sha256,
            "basis_sha256": basis_sha256,
            "selection_revision": snapshot_revision,
            "source_relative_path": source_relative.as_posix(),
        }

    def finalize_candidate(
        self,
        *,
        excel_path: Path,
        detail_manifest_path: Path,
        inventory_path: Path,
        publication_snapshot_path: Path,
    ) -> Dict[str, Any]:
        """校验全部派生产物并一次性提升整个不可变报告包。"""
        state = _read_json(self.state_path, "报告批次状态")
        excel = self._validate_excel(excel_path)
        detail = self._validate_detail(detail_manifest_path)
        inventory = self._validate_inventory(inventory_path)
        snapshot = self._validate_and_copy_snapshot(
            publication_snapshot_path
        )

        batch_manifest = {
            "schema_version": BATCH_SCHEMA_VERSION,
            "kind": "multi_farm_group_report_package",
            "status": "complete",
            "publication_state": (
                "validated_candidate; formal only when referenced by "
                "group_store/current_group_report.json"
            ),
            "batch_id": state.get("batch_id"),
            "completed_at": _utc_now(),
            "selection_revision": self.selection_revision,
            "publication_basis_sha256": self.publication_basis_sha256,
            "publication_snapshot": snapshot,
            "excel": excel,
            "detail": detail,
            "inventory": inventory,
        }
        _atomic_write_json(self.batch_manifest_path, batch_manifest)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = (
            f"牧场组报告包_{timestamp}_{self.publication_basis_sha256[:8]}"
        )
        final_path = self.reports_root / base_name
        suffix = 2
        while final_path.exists():
            final_path = self.reports_root / f"{base_name}_{suffix}"
            suffix += 1
        # staging 与 final 在同一 reports 目录，目录 rename 是正式包唯一
        # 的可见性边界。此行之前 Excel、明细、inventory、snapshot 和
        # batch manifest 已全部落盘、校验且 fsync。
        _fsync_directory(self.staging_path)
        os.replace(self.staging_path, final_path)
        _fsync_directory(self.reports_root)

        final_manifest = final_path / self.batch_manifest_path.name
        return {
            "package_path": final_path,
            "batch_manifest_path": final_manifest,
            "batch_manifest_sha256": _sha256(final_manifest),
            "excel_path": final_path / excel["relative_path"],
            "detail_manifest_path": final_path / detail["relative_path"],
            "inventory_path": final_path / inventory["relative_path"],
            "publication_snapshot_path": (
                final_path / snapshot["relative_path"]
            ),
            "detail": detail,
            "inventory": inventory,
        }


def publish_current_group_report_pointer(
    project_path: Path,
    *,
    published: Dict[str, Any],
    selection_revision: int,
    publication_basis_sha256: str,
) -> Dict[str, Any]:
    """以原子小指针登记当前正式报告包。

    目录提升完成但指针尚未写入时，即使程序崩溃，也只会留下一个未登记
    的候选包；界面和后续逻辑只认这个指针，不会把候选包误当正式结果。
    """
    project = Path(project_path).resolve()
    package = Path(published["package_path"]).resolve()
    manifest = Path(published["batch_manifest_path"]).resolve()
    expected_manifest_sha256 = str(
        published.get("batch_manifest_sha256") or ""
    ).lower()
    validated = _validate_package_manifest(
        project,
        package,
        manifest,
        expected_manifest_sha256=expected_manifest_sha256,
        expected_selection_revision=int(selection_revision),
        expected_basis_sha256=publication_basis_sha256,
    )
    excel = validated["excel_path"]
    published_excel = Path(published["excel_path"]).resolve()
    if published_excel != excel:
        raise GroupReportPublicationError(
            "发布结果中的 Excel 路径与 batch manifest 不一致"
        )
    package_relative = package.relative_to(project)
    manifest_relative = manifest.relative_to(project)
    excel_relative = excel.relative_to(project)

    pointer = {
        "schema_version": CURRENT_POINTER_SCHEMA_VERSION,
        "kind": "current_multi_farm_group_report",
        "published_at": _utc_now(),
        "selection_revision": validated["selection_revision"],
        "publication_basis_sha256": validated[
            "publication_basis_sha256"
        ],
        "package_relative_path": package_relative.as_posix(),
        "batch_manifest_relative_path": manifest_relative.as_posix(),
        "batch_manifest_sha256": validated["manifest_sha256"],
        "excel_relative_path": excel_relative.as_posix(),
        "excel_sha256": validated["excel_sha256"],
    }
    pointer_path = (
        project / "group_store" / "current_group_report.json"
    )
    _atomic_write_json(pointer_path, pointer)
    result = dict(pointer)
    result["pointer_path"] = pointer_path
    result["pointer_sha256"] = _sha256(pointer_path)
    return result


def validate_current_group_report_pointer(
    project_path: Path,
) -> Dict[str, Any]:
    """验证唯一正式指针及其绑定的不可变报告包。"""

    project = Path(project_path).resolve()
    pointer_path = project / "group_store" / "current_group_report.json"
    pointer = _read_json(pointer_path, "当前牧场组报告指针")
    if (
        pointer.get("schema_version") != CURRENT_POINTER_SCHEMA_VERSION
        or pointer.get("kind") != "current_multi_farm_group_report"
    ):
        raise GroupReportPublicationError("当前牧场组报告指针类型无效")
    try:
        selection_revision = int(pointer["selection_revision"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GroupReportPublicationError(
            "当前牧场组报告指针 selection_revision 无效"
        ) from exc
    basis_sha256 = str(
        pointer.get("publication_basis_sha256") or ""
    ).lower()
    manifest_sha256 = str(
        pointer.get("batch_manifest_sha256") or ""
    ).lower()
    excel_sha256 = str(pointer.get("excel_sha256") or "").lower()
    if not all(
        _valid_sha256(value)
        for value in (basis_sha256, manifest_sha256, excel_sha256)
    ):
        raise GroupReportPublicationError("当前牧场组报告指针摘要无效")

    package = _safe_relative_inside(
        project,
        pointer.get("package_relative_path"),
        "当前报告包",
    )
    manifest = _safe_relative_inside(
        project,
        pointer.get("batch_manifest_relative_path"),
        "当前报告包 manifest",
    )
    excel = _safe_relative_inside(
        project,
        pointer.get("excel_relative_path"),
        "当前汇总 Excel",
    )
    validated = _validate_package_manifest(
        project,
        package,
        manifest,
        expected_manifest_sha256=manifest_sha256,
        expected_selection_revision=selection_revision,
        expected_basis_sha256=basis_sha256,
    )
    if validated["excel_path"] != excel:
        raise GroupReportPublicationError(
            "当前指针 Excel 路径与 batch manifest 不一致"
        )
    if validated["excel_sha256"] != excel_sha256:
        raise GroupReportPublicationError(
            "当前指针 Excel SHA-256 不一致"
        )
    result = dict(pointer)
    result.update(
        {
            "pointer_path": pointer_path,
            "pointer_sha256": _sha256(pointer_path),
            "package_path": package,
            "batch_manifest_path": manifest,
            "excel_path": excel,
        }
    )
    return result


__all__ = [
    "GroupReportPublicationBatch",
    "GroupReportPublicationError",
    "publish_current_group_report_pointer",
    "validate_current_group_report_pointer",
]
