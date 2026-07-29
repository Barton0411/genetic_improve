"""牧场组阶段提交清单测试。"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import xlsxwriter

from core.group_tasks import stage_manifest as stage_manifest_module
from core.group_tasks.stage_manifest import (
    StageManifestError,
    commit_stage_manifest,
    compute_config_fingerprint,
    compute_xlsx_identifier_multiset,
    validate_stage_manifest,
)


def _write_cows(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(path))
    sheet = workbook.add_worksheet("母牛")
    sheet.write_row(0, 0, ["cow_id", "牧场编号", "指数"])
    for row_index, row in enumerate(rows, start=1):
        sheet.write_row(row_index, 0, row)
    workbook.close()


def _write_cows_with_formatted_blank_tail(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(path))
    sheet = workbook.add_worksheet("母牛")
    sheet.write_row(0, 0, ["cow_id", "牧场编号", "指数"])
    for row_index, row in enumerate(rows, start=1):
        sheet.write_row(row_index, 0, row)
    blank_format = workbook.add_format({"bg_color": "#FFFFFF"})
    sheet.set_row(20, None, blank_format)
    workbook.close()


class GroupStageManifestTests(unittest.TestCase):
    def test_commit_and_validate_tracks_relative_files_and_xlsx_structure(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir) / "child"
            source = root / "standardized_data" / "cows.xlsx"
            output = root / "analysis_results" / "index.xlsx"
            _write_cows(
                source,
                [("001", "F01", 1), ("002", "F01", 2), ("002", "F01", 3)],
            )
            _write_cows(
                output,
                [("001", "F01", 10), ("002", "F01", 20), ("002", "F01", 30)],
            )
            config = {"index": "TPI", "weights": {"milk": 0.4}}
            manifest_path = (
                root / "analysis_results" / ".manifests" / "analysis.json"
            )

            manifest = commit_stage_manifest(
                root,
                manifest_path,
                task_id="task-001",
                farm_code="F01",
                stage="analysis",
                config=config,
                inputs={"cow_input": source},
                outputs={"index_output": output},
                cow_id_sources={
                    "cow_input": {"columns": ["cow_id", "牛号"]},
                    "index_output": "cow_id",
                },
            )

            self.assertEqual(manifest["status"], "committed")
            self.assertEqual(
                manifest["config_fingerprint"],
                compute_config_fingerprint(config),
            )
            serialized = json.dumps(manifest, ensure_ascii=False)
            self.assertNotIn(str(root), serialized)
            self.assertEqual(
                manifest["inputs"][0]["relative_path"],
                "standardized_data/cows.xlsx",
            )
            self.assertEqual(
                manifest["outputs"][0]["xlsx"]["sheets"][0]["max_row"],
                4,
            )
            self.assertIsInstance(manifest["inputs"][0]["mtime_ns"], int)
            self.assertGreaterEqual(manifest["inputs"][0]["mtime_ns"], 0)
            multiset = manifest["inputs"][0]["cow_id_multiset"]
            self.assertEqual(multiset["identifier_count"], 3)
            self.assertEqual(multiset["blank_count"], 0)

            result = validate_stage_manifest(
                root,
                manifest_path,
                expected_task_id="task-001",
                expected_farm_code="F01",
                expected_stage="analysis",
                expected_config=config,
            )
            self.assertTrue(result["valid"])
            self.assertEqual(result["status"], "valid")
            self.assertEqual(result["issues"], [])
            self.assertEqual(len(result["artifact_stats"]), 2)

    def test_full_checks_content_while_stat_uses_size_and_mtime(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir) / "child"
            root.mkdir()
            source = root / "source.txt"
            output = root / "output.txt"
            source.write_text("source", encoding="utf-8")
            output.write_text("alpha", encoding="utf-8")
            manifest_path = root / "stage.json"
            manifest = commit_stage_manifest(
                root,
                manifest_path,
                task_id="task-a",
                farm_code="F01",
                stage="analysis",
                config={},
                inputs={"source": source},
                outputs={"output": output},
            )

            with patch(
                "core.group_tasks.stage_manifest.stream_sha256",
                side_effect=AssertionError("stat 模式不应读取文件内容"),
            ):
                self.assertTrue(
                    validate_stage_manifest(
                        root,
                        manifest_path,
                        verification="stat",
                    )["valid"]
                )

            original_mtime = manifest["outputs"][0]["mtime_ns"]
            output.write_text("bravo", encoding="utf-8")
            os.utime(output, ns=(original_mtime, original_mtime))
            full = validate_stage_manifest(
                root,
                manifest_path,
                verification="full",
            )
            self.assertFalse(full["valid"])
            self.assertIn(
                "artifact_hash_mismatch",
                {issue["code"] for issue in full["issues"]},
            )

    def test_stat_detects_size_and_mtime_changes_without_hashing(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir) / "child"
            root.mkdir()
            source = root / "source.txt"
            output = root / "output.txt"
            source.write_text("source", encoding="utf-8")
            output.write_text("output", encoding="utf-8")
            manifest_path = root / "stage.json"

            for change, expected_code in (
                ("mtime", "artifact_mtime_mismatch"),
                ("size", "artifact_size_mismatch"),
            ):
                with self.subTest(change=change):
                    manifest = commit_stage_manifest(
                        root,
                        manifest_path,
                        task_id="task-a",
                        farm_code="F01",
                        stage="analysis",
                        config={},
                        inputs={"source": source},
                        outputs={"output": output},
                    )
                    if change == "mtime":
                        stored = manifest["outputs"][0]["mtime_ns"]
                        os.utime(output, ns=(stored + 1, stored + 1))
                    else:
                        output.write_text("output-expanded", encoding="utf-8")
                    with patch(
                        "core.group_tasks.stage_manifest.stream_sha256",
                        side_effect=AssertionError(
                            "stat 模式不应读取文件内容"
                        ),
                    ):
                        result = validate_stage_manifest(
                            root,
                            manifest_path,
                            verification="stat",
                        )
                    self.assertFalse(result["valid"])
                    self.assertIn(
                        expected_code,
                        {issue["code"] for issue in result["issues"]},
                    )
                    output.write_text("output", encoding="utf-8")

    def test_stat_falls_back_to_full_for_legacy_manifest_without_mtime(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir) / "child"
            root.mkdir()
            source = root / "source.txt"
            output = root / "output.txt"
            source.write_text("source", encoding="utf-8")
            output.write_text("output", encoding="utf-8")
            manifest_path = root / "stage.json"
            manifest = commit_stage_manifest(
                root,
                manifest_path,
                task_id="task-a",
                farm_code="F01",
                stage="analysis",
                config={},
                inputs={"source": source},
                outputs={"output": output},
            )
            for artifact in manifest["inputs"] + manifest["outputs"]:
                artifact.pop("mtime_ns")
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )

            with patch(
                "core.group_tasks.stage_manifest.stream_sha256",
                wraps=stage_manifest_module.stream_sha256,
            ) as hash_file:
                result = validate_stage_manifest(
                    root,
                    manifest_path,
                    verification="stat",
                )
            self.assertTrue(result["valid"])
            self.assertEqual(hash_file.call_count, 2)

    def test_validation_reports_identity_config_and_artifact_changes(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir) / "child"
            source = root / "source.xlsx"
            output = root / "output.xlsx"
            _write_cows(source, [("001", "F01", 1)])
            _write_cows(output, [("001", "F01", 2)])
            manifest_path = root / "stage.json"
            commit_stage_manifest(
                root,
                manifest_path,
                task_id="task-a",
                farm_code="F01",
                stage="analysis",
                config={"version": 1},
                inputs={"source": source},
                outputs={"output": output},
            )

            identity = validate_stage_manifest(
                root,
                manifest_path,
                expected_task_id="task-b",
                expected_farm_code="F01",
                expected_stage="analysis",
            )
            self.assertEqual(identity["status"], "identity_mismatch")

            config = validate_stage_manifest(
                root,
                manifest_path,
                expected_config={"version": 2},
            )
            self.assertEqual(config["status"], "config_mismatch")

            _write_cows(output, [("999", "F01", 99), ("888", "F01", 88)])
            changed = validate_stage_manifest(root, manifest_path)
            self.assertEqual(changed["status"], "artifact_mismatch")
            self.assertIn(
                "artifact_hash_mismatch",
                {issue["code"] for issue in changed["issues"]},
            )
            self.assertIn(
                "xlsx_structure_mismatch",
                {issue["code"] for issue in changed["issues"]},
            )

    def test_missing_output_and_invalid_manifest_have_clear_statuses(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir) / "child"
            source = root / "source.xlsx"
            output = root / "output.xlsx"
            _write_cows(source, [("001", "F01", 1)])
            _write_cows(output, [("001", "F01", 2)])
            manifest_path = root / "stage.json"
            commit_stage_manifest(
                root,
                manifest_path,
                task_id="task-a",
                farm_code="F01",
                stage="analysis",
                config={},
                inputs={"source": source},
                outputs={"output": output},
            )
            output.unlink()
            missing = validate_stage_manifest(root, manifest_path)
            self.assertEqual(missing["status"], "artifact_missing")

            manifest_path.write_text("{bad-json", encoding="utf-8")
            invalid = validate_stage_manifest(root, manifest_path)
            self.assertEqual(invalid["status"], "manifest_invalid")

            absent = validate_stage_manifest(root, root / "absent.json")
            self.assertEqual(absent["status"], "manifest_missing")

    def test_manifest_is_atomic_and_rejects_paths_outside_project(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            base = Path(temporary_dir)
            root = base / "child"
            root.mkdir()
            outside = base / "outside.xlsx"
            output = root / "output.xlsx"
            _write_cows(outside, [("001", "F01", 1)])
            _write_cows(output, [("001", "F01", 2)])
            manifest_path = root / "stage.json"
            manifest_path.write_text('{"old": true}', encoding="utf-8")

            with self.assertRaises(StageManifestError):
                commit_stage_manifest(
                    root,
                    manifest_path,
                    task_id="task-a",
                    farm_code="F01",
                    stage="analysis",
                    config={},
                    inputs={"outside": outside},
                    outputs={"output": output},
                )
            self.assertEqual(
                json.loads(manifest_path.read_text(encoding="utf-8")),
                {"old": True},
            )
            self.assertFalse(
                list(root.glob(f".{manifest_path.name}.*.tmp"))
            )

    def test_identifier_multiset_is_order_independent_and_counts_duplicates(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            first = root / "first.xlsx"
            second = root / "second.xlsx"
            third = root / "third.xlsx"
            _write_cows(
                first,
                [("001", "F01", 1), ("002", "F01", 2), ("002", "F01", 3)],
            )
            _write_cows(
                second,
                [("002", "F01", 3), ("001", "F01", 1), ("002", "F01", 2)],
            )
            _write_cows(
                third,
                [("001", "F01", 1), ("002", "F01", 2)],
            )

            first_state = compute_xlsx_identifier_multiset(first, "cow_id")
            second_state = compute_xlsx_identifier_multiset(second, "cow_id")
            third_state = compute_xlsx_identifier_multiset(third, "cow_id")
            self.assertEqual(
                first_state["fingerprint"],
                second_state["fingerprint"],
            )
            self.assertNotEqual(
                first_state["fingerprint"],
                third_state["fingerprint"],
            )
            self.assertEqual(first_state["identifier_count"], 3)

    def test_identifier_multiset_ignores_formatted_blank_tail_and_none_config_validates(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            source = root / "source.xlsx"
            output = root / "output.xlsx"
            _write_cows_with_formatted_blank_tail(
                source,
                [("001", "F01", 1), ("002", "F01", 2)],
            )
            _write_cows(output, [("001", "F01", 3), ("002", "F01", 4)])
            state = compute_xlsx_identifier_multiset(source, "cow_id")
            self.assertEqual(state["row_count"], 2)
            self.assertEqual(state["blank_count"], 0)

            manifest_path = root / "stage.json"
            commit_stage_manifest(
                root,
                manifest_path,
                task_id="task-a",
                farm_code="F01",
                stage="analysis",
                config=None,
                inputs={"source": source},
                outputs={"output": output},
            )
            result = validate_stage_manifest(
                root,
                manifest_path,
                expected_config=None,
            )
            self.assertTrue(result["valid"])
