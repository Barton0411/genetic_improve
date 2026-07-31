from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import xlsxwriter

from scripts.validate_multi_farm_acceptance import (
    ResultBuilder,
    _compare_projected_rows,
    _profile_first_sheet_metrics,
    _required_extra_files,
    _scan_xlsx_health,
    _validate_cow_lineage,
    _validate_detail_counts,
    _validate_three_file_lineage,
    validate_project,
    write_outputs,
)
from utils.file_manager import FileManager


def _write_table(path: Path, headers, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(path))
    worksheet = workbook.add_worksheet("Sheet1")
    worksheet.write_row(0, 0, list(headers))
    for index, row in enumerate(rows, start=1):
        worksheet.write_row(index, 0, list(row))
    workbook.close()


DETAIL_HEADERS = (
    "牧场组排名",
    "分类结果",
    "未排名原因",
    "API farmcode",
    "牧场名称",
    "子项目相对目录",
    "源文件",
    "源数据行号",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _volume_entry(path: Path, data_rows: int) -> dict:
    return {
        "path": path.name,
        "data_rows": data_rows,
        "column_part": 1,
        "column_parts": 1,
        "volume": 1,
        "rows_per_volume": 10,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _detail_manifest(
    root: Path,
    *,
    actual_ranked_rows: int = 3,
    declared_ranked_rows: int = 3,
) -> dict:
    source_path = (
        "farm_projects/opaque/analysis_results/"
        "processed_index_cow_index_scores.xlsx"
    )
    ranked_path = root / "ranked.xlsx"
    reconciliation_path = root / "all.xlsx"
    ranked_rows = [
        [
            rank,
            "有效在群排名",
            "",
            "opaque-farm",
            "测试牧场",
            "farm_projects/opaque",
            source_path,
            source_row,
        ]
        for rank, source_row in zip(
            range(1, actual_ranked_rows + 1),
            range(2, 2 + actual_ranked_rows),
        )
    ]
    reconciliation_rows = [
        [
            rank,
            "有效在群排名",
            "",
            "opaque-farm",
            "测试牧场",
            "farm_projects/opaque",
            source_path,
            source_row,
        ]
        for rank, source_row in zip(range(1, 4), range(2, 5))
    ]
    reconciliation_rows.extend(
        [
            [
                "",
                "未排名",
                "非在群母牛",
                "opaque-farm",
                "测试牧场",
                "farm_projects/opaque",
                source_path,
                source_row,
            ]
            for source_row in range(5, 7)
        ]
    )
    _write_table(ranked_path, DETAIL_HEADERS, ranked_rows)
    _write_table(
        reconciliation_path,
        DETAIL_HEADERS,
        reconciliation_rows,
    )
    return {
        "status": "complete",
        "counts": {
            "source_rows": 5,
            "valid_ranked_rows": 3,
            "unranked_rows": 2,
            "ranked_exported_rows": 3,
            "reconciliation_exported_rows": 5,
            "tasks_in_scope": 1,
            "source_files_read": 1,
            "source_files_with_problem": 0,
            "long_field_count": 0,
            "long_field_chunk_count": 0,
            "unranked_reason_counts": {"非在群母牛": 2},
        },
        "sources": [
            {
                "source_key": "opaque-source",
                "task_id": "task-a",
                "path": source_path,
                "status": "read",
                "rows_read": 5,
                "duplicate_cow_id_count": 0,
                "lineage_mismatch_rows": 0,
                "identity_match": True,
            }
        ],
        "volumes": {
            "ranked": [
                _volume_entry(ranked_path, declared_ranked_rows)
            ],
            "reconciliation": [
                _volume_entry(reconciliation_path, 5)
            ],
            "long_fields": [],
        },
    }


def _cow_lineage_fixture(
    root: Path,
    *,
    raw_rows,
    processed_rows,
) -> tuple[dict, ResultBuilder, sqlite3.Connection]:
    child = root / "child"
    raw = child / "raw_data" / "cow_data.xlsx"
    processed = child / "standardized_data" / "processed_cow_data.xlsx"
    final = (
        child
        / "analysis_results"
        / "processed_cow_data_key_traits_final.xlsx"
    )
    index = (
        child
        / "analysis_results"
        / "processed_index_cow_index_scores.xlsx"
    )
    raw_headers = [
        "耳号",
        "API farmcode",
        "牧场编号",
        "牧场名称",
        "性别",
        "共同字段",
        "父号",
        "母号",
        "外祖父",
        "外曾外祖父",
    ]
    processed_headers = [
        "cow_id",
        "API farmcode",
        "牧场编号",
        "牧场名称",
        "共同字段",
        "sire",
        "dam",
        "mgs",
        "mmgs",
    ]
    _write_table(raw, raw_headers, raw_rows)
    for path in (processed, final, index):
        _write_table(path, processed_headers, processed_rows)
    task = {
        "farm_code": "opaque-farm",
        "farm_name": "测试牧场",
        "child_path": child,
        "identity": {
            "api_farmcode": "opaque-farm",
            "farm_number": "opaque-number",
            "farm_name": "测试牧场",
            "source_system": "慧牧云",
        },
    }
    result = ResultBuilder(root)
    connection = sqlite3.connect(str(root / "cow_lineage.sqlite3"))
    return task, result, connection


class MultiFarmAcceptanceValidatorTests(unittest.TestCase):
    def test_projected_row_comparison_ignores_excel_numeric_representation(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            source = root / "source.xlsx"
            target = root / "target.xlsx"
            headers = ["cow_id", "raw_dam_id", "共同数值", "空值"]
            _write_table(
                source,
                headers,
                [["cow-a", "123.0", "1.250", ""]],
            )
            _write_table(
                target,
                headers,
                [["cow-a", 123, 1.25, None]],
            )
            connection = sqlite3.connect(str(root / "rows.sqlite3"))
            try:
                result = _compare_projected_rows(
                    source,
                    target,
                    connection=connection,
                    table="representation_equivalence",
                    target_may_be_subset=False,
                )
            finally:
                connection.close()

            self.assertEqual(result["source_rows"], 1)
            self.assertEqual(result["target_rows"], 1)
            self.assertEqual(result["target_rows_not_in_source"], 0)
            self.assertEqual(result["source_rows_not_in_target"], 0)
            self.assertEqual(result["passed"], 1)

    def test_projected_row_comparison_keeps_leading_zero_identifier_strict(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            source = root / "source.xlsx"
            target = root / "target.xlsx"
            _write_table(source, ["cow_id"], [["00123"]])
            _write_table(target, ["cow_id"], [[123]])
            connection = sqlite3.connect(str(root / "rows.sqlite3"))
            try:
                result = _compare_projected_rows(
                    source,
                    target,
                    connection=connection,
                    table="leading_zero_identity",
                    target_may_be_subset=False,
                )
            finally:
                connection.close()

            self.assertEqual(result["target_rows_not_in_source"], 1)
            self.assertEqual(result["source_rows_not_in_target"], 1)
            self.assertEqual(result["passed"], 0)

    def test_projected_row_comparison_can_exclude_intentional_group_update(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            source = root / "source.xlsx"
            target = root / "target.xlsx"
            _write_table(
                source,
                ["cow_id", "group", "sire"],
                [["cow-a", None, "001HO00123"]],
            )
            _write_table(
                target,
                ["cow_id", "group", "sire"],
                [["cow-a", "成母牛已孕牛+非性控", "001HO00123"]],
            )
            connection = sqlite3.connect(str(root / "rows.sqlite3"))
            try:
                result = _compare_projected_rows(
                    source,
                    target,
                    connection=connection,
                    table="intentional_group_update",
                    target_may_be_subset=False,
                    excluded_columns=("group",),
                )
            finally:
                connection.close()

            self.assertEqual(result["passed"], 1)
            self.assertEqual(result["shared_columns"], 2)

    def test_single_farm_yearly_by_farm_workbook_is_optional(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            child = Path(temporary_dir) / "child"
            (child / "analysis_results").mkdir(parents=True)
            files, missing_patterns = _required_extra_files(
                {"child_path": child}
            )

            self.assertNotIn(
                "sire_traits_mean_by_cow_birth_year_by_farm.xlsx",
                {path.name for path in files},
            )
            self.assertFalse(
                any("分牧场年度" in value for value in missing_patterns)
            )

    def test_nonterminal_gate_never_opens_xlsx(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            project = FileManager.create_group_project(
                Path(temporary_dir),
                [
                    {
                        "code": "1100110013",
                        "api_farmcode": "1100110013",
                        "farm_number": "0102004",
                        "name": "测试牧场",
                    }
                ],
                data_source="慧牧云",
                task_mode="analysis",
            )
            with (
                patch(
                    "scripts.validate_multi_farm_acceptance.load_workbook"
                ) as workbook,
                patch(
                    "scripts.validate_multi_farm_acceptance.validate_stage_manifest"
                ) as manifest,
            ):
                payload = validate_project(project)

            self.assertEqual(payload["status"], "blocked")
            self.assertFalse(payload["gate"]["xlsx_opened"])
            workbook.assert_not_called()
            manifest.assert_not_called()

    def test_xlsx_health_finds_formula_errors_empty_sheet_and_percent_scale(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "health.xlsx"
            workbook = xlsxwriter.Workbook(str(path))
            worksheet = workbook.add_worksheet("数据")
            percent = workbook.add_format({"num_format": "0.00%"})
            worksheet.write(0, 0, "比例")
            worksheet.write_number(1, 0, 2.5, percent)
            worksheet.write_formula(1, 1, "=#REF!")
            worksheet.write_string(2, 0, "625.00%")
            worksheet.write_string(2, 1, "#VALUE!")
            workbook.add_worksheet("空表")
            workbook.close()

            health = _scan_xlsx_health(path)

            self.assertTrue(health["valid"])
            self.assertEqual(health["empty_visible_sheets"], 1)
            self.assertEqual(health["formula_error_cells"], 1)
            self.assertEqual(health["percent_abs_gt_one_cells"], 1)
            self.assertEqual(health["text_percent_abs_gt_100_cells"], 1)
            self.assertEqual(health["literal_error_marker_cells"], 1)

    def test_metric_profile_reports_all_zero_and_decimal_observations(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "metrics.xlsx"
            _write_table(
                path,
                ["cow_id", "NM$_score", "TPI_score"],
                [["001", 0, 0], ["002", 0, 0]],
            )
            zero = _profile_first_sheet_metrics(path)
            self.assertEqual(zero["metric_columns"], 2)
            self.assertEqual(zero["metric_all_zero_columns"], 2)

            _write_table(
                path,
                ["cow_id", "NM$_score", "TPI_score"],
                [["001", 1.25, 2300], ["002", -0.75, 2200]],
            )
            decimal = _profile_first_sheet_metrics(path)
            self.assertEqual(decimal["metric_all_zero_columns"], 0)
            self.assertEqual(decimal["metric_fractional_cells"], 2)

    def test_disk_backed_lineage_detects_exact_mismatch_without_exposing_ids(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            source = root / "source.xlsx"
            middle = root / "middle.xlsx"
            target = root / "target.xlsx"
            headers = [
                "cow_id",
                "API farmcode",
                "牧场编号",
                "牧场名称",
                "性状值",
            ]
            _write_table(
                source,
                headers,
                [
                    ["0001", "1100110013", "0102004", "测试牧场", 1.25],
                    ["0002", "1100110013", "0102004", "测试牧场", 2.5],
                ],
            )
            _write_table(
                middle,
                headers,
                [["0001", "1100110013", "0102004", "测试牧场", 1.25]],
            )
            _write_table(
                target,
                headers,
                # 牛号集合完全相同，但性状值被错配；只能由整行血缘抓到。
                [["0001", "1100110013", "0102004", "测试牧场", 2.5]],
            )
            task = {
                "farm_code": "1100110013",
                "farm_name": "测试牧场",
                "identity": {
                    "api_farmcode": "1100110013",
                    "farm_number": "0102004",
                    "farm_name": "测试牧场",
                },
            }
            result = ResultBuilder(root)
            connection = sqlite3.connect(str(root / "lineage.sqlite3"))
            try:
                row = _validate_three_file_lineage(
                    task,
                    connection,
                    result,
                    lineage_name="cowtest",
                    paths=(source, middle, target),
                    id_candidates=("cow_id",),
                    require_equal=False,
                    enforce_identity=True,
                    content_pairs=((0, 1, True), (1, 2, False)),
                )
            finally:
                connection.close()

            self.assertIsNotNone(row)
            self.assertEqual(row["target_not_in_middle_rows"], 0)
            self.assertEqual(row["middle_not_in_target_rows"], 0)
            self.assertGreater(row["row_content_mismatch"], 0)
            serialized = json.dumps(
                {
                    "row": row,
                    "issues": [issue.__dict__ for issue in result.issues],
                },
                ensure_ascii=False,
            )
            self.assertNotIn("0001", serialized)
            self.assertNotIn("0002", serialized)

    def test_detail_manifest_reconciles_all_rows_and_tasks(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            manifest = _detail_manifest(root)

            result = _validate_detail_counts(
                manifest,
                included_task_ids={"task-a"},
                detail_root=root,
            )

            self.assertEqual(result["source_rows"], 5)
            self.assertEqual(result["reconciliation_rows"], 5)
            self.assertEqual(result["actual_ranked_rows"], 3)
            self.assertEqual(result["actual_reconciliation_rows"], 5)

    def test_detail_manifest_self_consistent_but_volume_short_fails(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            manifest = _detail_manifest(
                root,
                actual_ranked_rows=2,
                declared_ranked_rows=3,
            )

            with self.assertRaisesRegex(ValueError, "实际数据行数"):
                _validate_detail_counts(
                    manifest,
                    included_task_ids={"task-a"},
                    detail_root=root,
                )

    def test_raw_three_processed_one_without_rejection_audit_fails(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            raw_rows = [
                [
                    cow_id,
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    "母",
                    value,
                ]
                for cow_id, value in (
                    ("cow-a", 1),
                    ("cow-b", 2),
                    ("cow-c", 3),
                )
            ]
            processed_rows = [
                [
                    "cow-a",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    1,
                ]
            ]
            task, result, connection = _cow_lineage_fixture(
                root,
                raw_rows=raw_rows,
                processed_rows=processed_rows,
            )
            try:
                _validate_cow_lineage(root, task, connection, result)
            finally:
                connection.close()

            self.assertTrue(
                any(
                    issue.code == "cow_lineage_mismatch"
                    and issue.severity == "error"
                    for issue in result.issues
                )
            )
            self.assertEqual(
                result.lineage_rows[0][
                    "raw_to_processed_unexplained_rows"
                ],
                2,
            )

    def test_raw_processed_allowed_rejections_balance_and_pass(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            raw_rows = [
                [
                    "cow-a",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    "母",
                    1,
                ],
                [
                    "cow-b",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    "公",
                    2,
                ],
                [
                    "cow-c",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    "公",
                    3,
                ],
            ]
            processed_rows = [
                [
                    "cow-a",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    1,
                ]
            ]
            task, result, connection = _cow_lineage_fixture(
                root,
                raw_rows=raw_rows,
                processed_rows=processed_rows,
            )
            try:
                _validate_cow_lineage(root, task, connection, result)
            finally:
                connection.close()

            self.assertFalse(result.issues)
            row = result.lineage_rows[0]
            self.assertEqual(row["raw_to_processed_excluded"], 2)
            self.assertEqual(
                row["raw_to_processed_rejected_male_rows"],
                2,
            )
            self.assertEqual(
                row["raw_to_processed_rejection_balance_delta"],
                0,
            )

    def test_raw_processed_pedigree_binding_swap_fails_without_ids(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            raw_rows = [
                [
                    "cow-secret-a",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    "母",
                    1,
                    "1HO123",
                    "dam-a",
                    "2HO234",
                    "3HO345",
                ],
                [
                    "cow-secret-b",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    "母",
                    2,
                    "4HO456",
                    "dam-b",
                    "5HO567",
                    "6HO678",
                ],
            ]
            processed_rows = [
                [
                    "cow-secret-a",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    1,
                    "004HO00456",
                    "dam-b",
                    "002HO00234",
                    "003HO00345",
                ],
                [
                    "cow-secret-b",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    2,
                    "001HO00123",
                    "dam-a",
                    "005HO00567",
                    "006HO00678",
                ],
            ]
            task, result, connection = _cow_lineage_fixture(
                root,
                raw_rows=raw_rows,
                processed_rows=processed_rows,
            )
            try:
                _validate_cow_lineage(root, task, connection, result)
            finally:
                connection.close()

            row = result.lineage_rows[0]
            self.assertEqual(
                row[
                    "raw_to_processed_stable_field_compared_identifiers"
                ],
                2,
            )
            self.assertEqual(
                row[
                    "raw_to_processed_stable_field_mismatch_identifiers"
                ],
                2,
            )
            self.assertTrue(
                any(
                    issue.code == "cow_lineage_mismatch"
                    and issue.severity == "error"
                    for issue in result.issues
                )
            )
            serialized = json.dumps(
                {
                    "lineage": result.lineage_rows,
                    "issues": [
                        issue.__dict__ for issue in result.issues
                    ],
                },
                ensure_ascii=False,
            )
            self.assertNotIn("cow-secret-a", serialized)
            self.assertNotIn("cow-secret-b", serialized)
            self.assertNotIn("1HO123", serialized)
            self.assertNotIn("dam-b", serialized)

    def test_raw_naab_spelling_matches_production_canonical_format(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            raw_rows = [
                [
                    "cow-a",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    "母",
                    1,
                    "1HO123",
                    "dam-001",
                    "XK7HO456",
                    "551HO789",
                ]
            ]
            processed_rows = [
                [
                    "cow-a",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    1,
                    "001HO00123",
                    "dam-001",
                    "007HO00456",
                    "551HO00789",
                ]
            ]
            task, result, connection = _cow_lineage_fixture(
                root,
                raw_rows=raw_rows,
                processed_rows=processed_rows,
            )
            try:
                _validate_cow_lineage(root, task, connection, result)
            finally:
                connection.close()

            self.assertFalse(result.issues)
            row = result.lineage_rows[0]
            self.assertEqual(
                row[
                    "raw_to_processed_stable_field_compared_identifiers"
                ],
                1,
            )
            self.assertEqual(
                row[
                    "raw_to_processed_stable_field_mismatch_identifiers"
                ],
                0,
            )

    def test_raw_processed_pedigree_binding_aliases_and_values_pass(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            raw_rows = [
                [
                    "cow-a",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    "母",
                    1,
                    101,
                    None,
                    303.0,
                    "nan",
                ],
                [
                    "cow-b",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    "母",
                    2,
                    "201.0",
                    202,
                    "",
                    404,
                ],
            ]
            processed_rows = [
                [
                    "cow-a",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    1,
                    "101.0",
                    "",
                    "303",
                    None,
                ],
                [
                    "cow-b",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    2,
                    "201",
                    "202.0",
                    None,
                    "404.0",
                ],
            ]
            task, result, connection = _cow_lineage_fixture(
                root,
                raw_rows=raw_rows,
                processed_rows=processed_rows,
            )
            try:
                _validate_cow_lineage(root, task, connection, result)
            finally:
                connection.close()

            self.assertFalse(result.issues)
            row = result.lineage_rows[0]
            self.assertEqual(
                row[
                    "raw_to_processed_stable_field_compared_identifiers"
                ],
                2,
            )
            self.assertEqual(
                row[
                    "raw_to_processed_stable_field_mismatch_identifiers"
                ],
                0,
            )
            self.assertEqual(row["raw_stable_field_columns"], 4)
            self.assertEqual(row["processed_stable_field_columns"], 4)

    def test_raw_duplicate_cow_id_skips_stable_binding_and_counts_it(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            raw_rows = [
                [
                    "cow-duplicate",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    "母",
                    1,
                    "sire-a",
                    "dam-a",
                    "mgs-a",
                    "mmgs-a",
                ],
                [
                    "cow-duplicate",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    "母",
                    1,
                    "sire-b",
                    "dam-b",
                    "mgs-b",
                    "mmgs-b",
                ],
            ]
            processed_rows = [
                [
                    "cow-duplicate",
                    "opaque-farm",
                    "opaque-number",
                    "测试牧场",
                    1,
                    "sire-b",
                    "dam-b",
                    "mgs-b",
                    "mmgs-b",
                ]
            ]
            task, result, connection = _cow_lineage_fixture(
                root,
                raw_rows=raw_rows,
                processed_rows=processed_rows,
            )
            try:
                _validate_cow_lineage(root, task, connection, result)
            finally:
                connection.close()

            self.assertEqual(len(result.issues), 1)
            self.assertEqual(
                result.issues[0].code,
                "cow_duplicate_identity_ambiguous",
            )
            self.assertEqual(result.issues[0].severity, "warning")
            row = result.lineage_rows[0]
            self.assertEqual(
                row[
                    "raw_to_processed_stable_field_ambiguous_raw_identifiers"
                ],
                1,
            )
            self.assertEqual(
                row["raw_to_processed_stable_field_ambiguous_raw_rows"],
                2,
            )
            self.assertEqual(
                row[
                    "raw_to_processed_stable_field_compared_identifiers"
                ],
                0,
            )
            self.assertEqual(
                row[
                    "raw_to_processed_stable_field_mismatch_identifiers"
                ],
                0,
            )

    def test_output_directory_inside_project_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            project = Path(temporary_dir) / "group"
            project.mkdir()
            payload = {
                "project_path": str(project),
                "farms": [],
                "stages": [],
                "lineage": [],
                "files": [],
                "issues": [],
            }
            with self.assertRaisesRegex(ValueError, "不能位于"):
                write_outputs(payload, project / "validation")


if __name__ == "__main__":
    unittest.main()
