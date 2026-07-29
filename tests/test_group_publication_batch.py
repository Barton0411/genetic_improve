from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import xlsxwriter

from core.group_report.publication_batch import (
    GroupReportPublicationBatch,
    GroupReportPublicationError,
    publish_current_group_report_pointer,
    validate_current_group_report_pointer,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _write_xlsx(path: Path, value: str = "ok") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(path))
    worksheet = workbook.add_worksheet("Sheet1")
    worksheet.write(0, 0, value)
    workbook.close()


class _Candidate:
    def __init__(
        self,
        project: Path,
        *,
        selection_revision: int,
        label: str,
    ):
        self.project = project
        self.basis = {
            "selection_revision": selection_revision,
            "selection_scope": [label],
            "tasks": [],
        }
        self.basis_sha256 = _canonical_sha256(self.basis)
        self.batch = GroupReportPublicationBatch(
            project,
            publication_basis_sha256=self.basis_sha256,
            selection_revision=selection_revision,
        )
        _write_xlsx(self.batch.excel_path, f"summary-{label}")

        detail_package = self.batch.detail_root / "details"
        ranked = detail_package / "ranked.xlsx"
        reconciliation = detail_package / "reconciliation.xlsx"
        _write_xlsx(ranked, f"ranked-{label}")
        _write_xlsx(reconciliation, f"reconciliation-{label}")
        self.detail_manifest_path = detail_package / "manifest.json"
        self.detail_manifest_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "counts": {
                        "tasks_in_scope": 1,
                        "source_files_read": 1,
                        "source_files_with_problem": 0,
                        "source_rows": 1,
                        "valid_ranked_rows": 1,
                        "unranked_rows": 0,
                        "ranked_exported_rows": 1,
                        "reconciliation_exported_rows": 1,
                        "unranked_reason_counts": {},
                        "long_field_count": 0,
                        "long_field_chunk_count": 0,
                    },
                    "sources": [
                        {
                            "source_key": f"source-{label}",
                            "status": "read",
                            "rows_read": 1,
                        }
                    ],
                    "volumes": {
                        "ranked": [
                            {
                                "path": ranked.name,
                                "bytes": ranked.stat().st_size,
                                "sha256": _sha256(ranked),
                                "data_rows": 1,
                                "volume": 1,
                                "column_part": 1,
                                "column_parts": 1,
                                "rows_per_volume": 100,
                                "first_rank": 1,
                                "last_rank": 1,
                            }
                        ],
                        "reconciliation": [
                            {
                                "path": reconciliation.name,
                                "bytes": reconciliation.stat().st_size,
                                "sha256": _sha256(reconciliation),
                                "data_rows": 1,
                                "volume": 1,
                                "column_part": 1,
                                "column_parts": 1,
                                "rows_per_volume": 100,
                                "first_rank": 1,
                                "last_rank": 1,
                            }
                        ],
                        "long_fields": [],
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        self.batch.inventory_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "counts": {
                        "total_files": 0,
                        "valid_files": 0,
                        "invalid_files": 0,
                        "tasks_with_scan_errors": 0,
                    },
                    "files": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.snapshot_path = (
            project / "group_store" / f"snapshot-{label}.json"
        )
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self.snapshot_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "kind": "group_summary_publication_inputs",
                    "basis_sha256": self.basis_sha256,
                    "basis": self.basis,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.ranked_path = ranked
        self.reconciliation_path = reconciliation

    def read_detail_manifest(self):
        return json.loads(
            self.detail_manifest_path.read_text(encoding="utf-8")
        )

    def write_detail_manifest(self, value):
        self.detail_manifest_path.write_text(
            json.dumps(value, ensure_ascii=False),
            encoding="utf-8",
        )

    def finalize(self):
        return self.batch.finalize_candidate(
            excel_path=self.batch.excel_path,
            detail_manifest_path=self.detail_manifest_path,
            inventory_path=self.batch.inventory_path,
            publication_snapshot_path=self.snapshot_path,
        )


class GroupReportPublicationBatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary_dir.name) / "group"
        (self.project / "reports").mkdir(parents=True)
        (self.project / "group_store").mkdir()

    def tearDown(self):
        self.temporary_dir.cleanup()

    def _visible_packages(self):
        return sorted(
            path.resolve()
            for path in (self.project / "reports").iterdir()
            if path.is_dir() and not path.name.startswith(".")
        )

    def _publish(self, candidate: _Candidate):
        published = candidate.finalize()
        pointer = publish_current_group_report_pointer(
            self.project,
            published=published,
            selection_revision=candidate.batch.selection_revision,
            publication_basis_sha256=candidate.basis_sha256,
        )
        return published, pointer

    def test_all_artifacts_are_validated_before_one_visible_rename(self):
        candidate = _Candidate(
            self.project,
            selection_revision=7,
            label="complete",
        )
        self.assertEqual(self._visible_packages(), [])
        self.assertTrue(candidate.batch.staging_path.name.startswith("."))

        published = candidate.finalize()
        visible = self._visible_packages()
        self.assertEqual(visible, [published["package_path"]])
        self.assertFalse(candidate.batch.staging_path.exists())
        self.assertFalse(
            (self.project / "group_store" / "current_group_report.json").exists()
        )

        manifest = json.loads(
            published["batch_manifest_path"].read_text(encoding="utf-8")
        )
        copied_snapshot = published["publication_snapshot_path"]
        self.assertTrue(copied_snapshot.is_file())
        self.assertEqual(
            manifest["publication_snapshot"]["sha256"],
            _sha256(copied_snapshot),
        )
        pointer = publish_current_group_report_pointer(
            self.project,
            published=published,
            selection_revision=7,
            publication_basis_sha256=candidate.basis_sha256,
        )
        validated = validate_current_group_report_pointer(self.project)
        self.assertEqual(pointer["selection_revision"], 7)
        self.assertEqual(
            pointer["batch_manifest_sha256"],
            _sha256(published["batch_manifest_path"]),
        )
        self.assertEqual(
            pointer["excel_sha256"],
            _sha256(published["excel_path"]),
        )
        self.assertEqual(
            validated["package_path"],
            published["package_path"],
        )

    def test_each_required_artifact_blocks_visible_package_when_invalid(self):
        mutators = {
            "excel": lambda item: item.batch.excel_path.write_bytes(b"bad"),
            "detail": lambda item: item.ranked_path.write_bytes(b"bad"),
            "inventory": lambda item: item.batch.inventory_path.write_text(
                '{"status":"partial","counts":{},"files":[]}',
                encoding="utf-8",
            ),
            "snapshot": lambda item: item.snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "group_summary_publication_inputs",
                        "basis_sha256": "0" * 64,
                        "basis": item.basis,
                    }
                ),
                encoding="utf-8",
            ),
        }
        for label, mutate in mutators.items():
            with self.subTest(label=label):
                project = self.project / label
                (project / "reports").mkdir(parents=True)
                (project / "group_store").mkdir()
                candidate = _Candidate(
                    project,
                    selection_revision=1,
                    label=label,
                )
                mutate(candidate)
                with self.assertRaises(GroupReportPublicationError):
                    candidate.finalize()
                visible = [
                    path
                    for path in (project / "reports").iterdir()
                    if path.is_dir() and not path.name.startswith(".")
                ]
                self.assertEqual(visible, [])
                self.assertTrue(candidate.batch.staging_path.is_dir())

    def test_detail_count_invariants_block_publication(self):
        mutators = {
            "source_partition": lambda counts: counts.update(
                {"source_rows": 2}
            ),
            "reason_total": lambda counts: counts.update(
                {
                    "source_rows": 2,
                    "unranked_rows": 1,
                    "reconciliation_exported_rows": 2,
                    "unranked_reason_counts": {},
                }
            ),
        }
        for label, mutate in mutators.items():
            with self.subTest(label=label):
                project = self.project / label
                (project / "reports").mkdir(parents=True)
                (project / "group_store").mkdir()
                candidate = _Candidate(
                    project,
                    selection_revision=1,
                    label=label,
                )
                manifest = candidate.read_detail_manifest()
                mutate(manifest["counts"])
                manifest["sources"][0]["rows_read"] = 2
                manifest["volumes"]["reconciliation"][0][
                    "data_rows"
                ] = 2
                candidate.write_detail_manifest(manifest)
                with self.assertRaises(GroupReportPublicationError):
                    candidate.finalize()
                self.assertEqual(
                    [
                        path
                        for path in (project / "reports").iterdir()
                        if path.is_dir()
                        and not path.name.startswith(".")
                    ],
                    [],
                )

    def test_missing_column_part_blocks_publication(self):
        candidate = _Candidate(
            self.project,
            selection_revision=8,
            label="missing-column-part",
        )
        manifest = candidate.read_detail_manifest()
        manifest["volumes"]["ranked"][0]["column_parts"] = 2
        candidate.write_detail_manifest(manifest)

        with self.assertRaisesRegex(
            GroupReportPublicationError,
            "字段分片未完整覆盖",
        ):
            candidate.finalize()
        self.assertEqual(self._visible_packages(), [])

    def test_column_part_with_missing_rows_blocks_publication(self):
        candidate = _Candidate(
            self.project,
            selection_revision=10,
            label="short-column-part",
        )
        second_part = (
            candidate.detail_manifest_path.parent / "ranked-part-2.xlsx"
        )
        _write_xlsx(second_part, "ranked-part-2")
        manifest = candidate.read_detail_manifest()
        manifest["volumes"]["ranked"][0]["column_parts"] = 2
        manifest["volumes"]["ranked"].append(
            {
                "path": second_part.name,
                "bytes": second_part.stat().st_size,
                "sha256": _sha256(second_part),
                "data_rows": 0,
                "volume": 1,
                "column_part": 2,
                "column_parts": 2,
                "rows_per_volume": 100,
                "first_rank": None,
                "last_rank": None,
            }
        )
        candidate.write_detail_manifest(manifest)

        with self.assertRaisesRegex(
            GroupReportPublicationError,
            "累计行数不一致",
        ):
            candidate.finalize()
        self.assertEqual(self._visible_packages(), [])

    def test_missing_long_field_chunk_blocks_publication(self):
        candidate = _Candidate(
            self.project,
            selection_revision=9,
            label="missing-long-chunk",
        )
        long_volume = (
            candidate.detail_manifest_path.parent / "long-fields.xlsx"
        )
        _write_xlsx(long_volume, "long-field-chunk")
        manifest = candidate.read_detail_manifest()
        manifest["counts"]["long_field_count"] = 1
        manifest["counts"]["long_field_chunk_count"] = 2
        manifest["volumes"]["long_fields"] = [
            {
                "path": long_volume.name,
                "bytes": long_volume.stat().st_size,
                "sha256": _sha256(long_volume),
                "data_rows": 1,
                "volume": 1,
                "column_part": 1,
                "column_parts": 1,
                "rows_per_volume": 100,
                "first_rank": None,
                "last_rank": None,
            }
        ]
        candidate.write_detail_manifest(manifest)

        with self.assertRaisesRegex(
            GroupReportPublicationError,
            "累计行数不一致",
        ):
            candidate.finalize()
        self.assertEqual(self._visible_packages(), [])

    def test_logically_incomplete_detail_package_is_not_reused(self):
        candidate = _Candidate(
            self.project,
            selection_revision=11,
            label="invalid-resume",
        )
        self.assertIsNotNone(
            candidate.batch.load_completed_detail("details")
        )
        manifest = candidate.read_detail_manifest()
        manifest["counts"]["long_field_count"] = 1
        manifest["counts"]["long_field_chunk_count"] = 2
        candidate.write_detail_manifest(manifest)

        self.assertIsNone(
            candidate.batch.load_completed_detail("details")
        )

    def test_interrupted_directory_publish_keeps_old_pointer_and_resumes(self):
        old = _Candidate(
            self.project,
            selection_revision=1,
            label="old",
        )
        old_published, _old_pointer = self._publish(old)
        pointer_path = (
            self.project / "group_store" / "current_group_report.json"
        )
        old_pointer_bytes = pointer_path.read_bytes()
        old_pointer_sha = _sha256(pointer_path)

        new = _Candidate(
            self.project,
            selection_revision=2,
            label="new",
        )
        real_replace = os.replace

        def interrupt_staging_rename(source, target):
            if Path(source) == new.batch.staging_path:
                raise OSError("模拟目录提升时中断")
            return real_replace(source, target)

        with patch(
            "core.group_report.publication_batch.os.replace",
            side_effect=interrupt_staging_rename,
        ):
            with self.assertRaisesRegex(OSError, "模拟目录提升时中断"):
                new.finalize()

        self.assertEqual(pointer_path.read_bytes(), old_pointer_bytes)
        self.assertEqual(_sha256(pointer_path), old_pointer_sha)
        validated_old = validate_current_group_report_pointer(self.project)
        self.assertEqual(
            validated_old["package_path"],
            old_published["package_path"],
        )
        self.assertTrue(new.batch.staging_path.is_dir())
        self.assertTrue(new.batch.batch_manifest_path.is_file())
        self.assertEqual(self._visible_packages(), [old_published["package_path"]])

        resumed = GroupReportPublicationBatch(
            self.project,
            publication_basis_sha256=new.basis_sha256,
            selection_revision=2,
        )
        self.assertEqual(resumed.staging_path, new.batch.staging_path)
        new_published = resumed.finalize_candidate(
            excel_path=resumed.excel_path,
            detail_manifest_path=new.detail_manifest_path,
            inventory_path=resumed.inventory_path,
            publication_snapshot_path=new.snapshot_path,
        )
        # 候选目录出现后，唯一正式指针仍然指向旧包。
        self.assertEqual(pointer_path.read_bytes(), old_pointer_bytes)
        self.assertEqual(
            validate_current_group_report_pointer(self.project)[
                "package_path"
            ],
            old_published["package_path"],
        )
        publish_current_group_report_pointer(
            self.project,
            published=new_published,
            selection_revision=2,
            publication_basis_sha256=new.basis_sha256,
        )
        self.assertEqual(
            validate_current_group_report_pointer(self.project)[
                "package_path"
            ],
            new_published["package_path"],
        )

    def test_interrupted_pointer_replace_keeps_old_pointer_valid(self):
        old = _Candidate(
            self.project,
            selection_revision=1,
            label="pointer-old",
        )
        old_published, _ = self._publish(old)
        pointer_path = (
            self.project / "group_store" / "current_group_report.json"
        )
        old_pointer_bytes = pointer_path.read_bytes()

        new = _Candidate(
            self.project,
            selection_revision=2,
            label="pointer-new",
        )
        new_published = new.finalize()
        real_replace = os.replace

        def interrupt_pointer_replace(source, target):
            if Path(target).resolve() == pointer_path.resolve():
                raise OSError("模拟指针切换中断")
            return real_replace(source, target)

        with patch(
            "core.group_report.publication_batch.os.replace",
            side_effect=interrupt_pointer_replace,
        ):
            with self.assertRaisesRegex(OSError, "模拟指针切换中断"):
                publish_current_group_report_pointer(
                    self.project,
                    published=new_published,
                    selection_revision=2,
                    publication_basis_sha256=new.basis_sha256,
                )
        self.assertEqual(pointer_path.read_bytes(), old_pointer_bytes)
        self.assertEqual(
            validate_current_group_report_pointer(self.project)[
                "package_path"
            ],
            old_published["package_path"],
        )
        self.assertFalse(
            list(
                pointer_path.parent.glob(
                    f".{pointer_path.name}.*.tmp"
                )
            )
        )

    def test_pointer_rejects_revision_or_excel_tampering(self):
        candidate = _Candidate(
            self.project,
            selection_revision=3,
            label="tamper",
        )
        published = candidate.finalize()
        with self.assertRaisesRegex(
            GroupReportPublicationError,
            "selection_revision",
        ):
            publish_current_group_report_pointer(
                self.project,
                published=published,
                selection_revision=4,
                publication_basis_sha256=candidate.basis_sha256,
            )
        self.assertFalse(
            (self.project / "group_store" / "current_group_report.json").exists()
        )

        published["excel_path"].write_bytes(b"tampered")
        with self.assertRaises(GroupReportPublicationError):
            publish_current_group_report_pointer(
                self.project,
                published=published,
                selection_revision=3,
                publication_basis_sha256=candidate.basis_sha256,
            )
        self.assertFalse(
            (self.project / "group_store" / "current_group_report.json").exists()
        )


if __name__ == "__main__":
    unittest.main()
