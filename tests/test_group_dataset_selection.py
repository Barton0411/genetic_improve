from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from openpyxl import Workbook

from core.group_tasks.dataset_plan import (
    BREEDING_RAW_RECEIPT,
    BREEDING_STANDARDIZED_RECEIPT,
    DatasetSelectionError,
    normalize_dataset_selection,
    validate_empty_breeding_receipt,
    validate_empty_breeding_receipt_pair,
    write_empty_breeding_receipts,
)
from core.group_tasks.stage_policy import (
    StagePolicyError,
    _definition,
    _local_bundle_inputs,
    commit_child_stage,
    validate_child_stage,
)
from gui.auto_report_worker import AutoReportWorker
from gui.multi_farm_task_worker import MultiFarmTaskWorker
from utils.file_manager import FileManager


def _write_xlsx(
    path: Path,
    headers=("cow_id",),
    values=("C001",),
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(list(headers))
    worksheet.append(list(values))
    workbook.save(path)


def _remove_group_store(parent: Path) -> None:
    database = parent / "group_store" / "group_tasks.sqlite3"
    for suffix in ("", "-wal", "-shm"):
        Path(f"{database}{suffix}").unlink(missing_ok=True)


class _CountingApi:
    def __init__(self, *, hmy=True, breeding_records=None):
        self.hmy = hmy
        self.breeding_records = (
            [{"cowId": "C001"}]
            if breeding_records is None
            else list(breeding_records)
        )
        self.herd_calls = 0
        self.breeding_calls = 0
        self.stock_calls = 0

    def get_farm_herd(self, farm_code):
        self.herd_calls += 1
        return {
            "code": 200,
            "farmName": "1000001测试牧场",
            "data": [{"cowId": "C001"}],
        }

    def get_breeding_records(self, farm_code):
        self.breeding_calls += 1
        if self.hmy:
            return {"code": 200, "data": list(self.breeding_records)}
        return {
            "code": 200,
            "data": {"rows": list(self.breeding_records)},
        }

    def get_stock_detail(self, farm_code):
        self.stock_calls += 1
        return {"code": 200, "data": []}


class DatasetPlanTests(unittest.TestCase):
    def test_normalization_rules_and_legacy_default(self):
        self.assertEqual(
            normalize_dataset_selection(),
            {"herd": True, "breeding": True},
        )
        with self.assertRaises(DatasetSelectionError):
            normalize_dataset_selection(
                {"herd": False, "breeding": True},
                task_mode="analysis",
            )
        with self.assertRaises(DatasetSelectionError):
            normalize_dataset_selection(
                {"herd": False, "breeding": True},
                task_mode="data_only",
                has_local_farms=True,
            )
        with self.assertRaises(DatasetSelectionError):
            normalize_dataset_selection(
                {"herd": False, "breeding": False}
            )
        with self.assertRaises(DatasetSelectionError):
            normalize_dataset_selection(
                {"herd": 1, "breeding": False}
            )

    def test_zero_receipt_rejects_weak_types_and_invalid_time(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw, standardized = write_empty_breeding_receipts(
                root,
                data_source="伊起牛",
                farms=[{"code": "1001", "name": "测试牧场"}],
            )
            payload = json.loads(raw.read_text(encoding="utf-8"))
            payload["record_count"] = False
            raw.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            with self.assertRaises(DatasetSelectionError):
                validate_empty_breeding_receipt(raw)

            payload["record_count"] = 0
            payload["created_at"] = "not-a-time"
            raw.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            with self.assertRaises(DatasetSelectionError):
                validate_empty_breeding_receipt(raw)

            valid_payload = json.loads(
                standardized.read_text(encoding="utf-8")
            )
            raw.write_text(
                json.dumps(valid_payload, ensure_ascii=False),
                encoding="utf-8",
            )
            validate_empty_breeding_receipt_pair(
                raw,
                standardized,
                expected_data_source="伊起牛",
                expected_farm_codes=["1001"],
            )
            with self.assertRaises(DatasetSelectionError):
                validate_empty_breeding_receipt_pair(
                    raw,
                    standardized,
                    expected_data_source="伊起牛",
                    expected_farm_codes=["9999"],
                )

    def test_group_project_persists_exact_selection_everywhere(self):
        with tempfile.TemporaryDirectory() as temporary:
            selection = {"herd": True, "breeding": False}
            parent = FileManager.create_group_project(
                Path(temporary),
                [{"code": "1001", "name": "测试牧场"}],
                data_source="伊起牛",
                task_mode="analysis",
                dataset_selection=selection,
            )
            metadata = FileManager.load_project_metadata(parent)
            task = metadata["group_tasks"][0]
            child = FileManager.load_project_metadata(
                parent / task["relative_path"]
            )
            self.assertEqual(metadata["dataset_selection"], selection)
            self.assertTrue(metadata["dataset_selection_explicit"])
            self.assertEqual(
                task["metadata"]["dataset_selection"],
                selection,
            )
            self.assertEqual(child["dataset_selection"], selection)
            self.assertTrue(child["dataset_selection_explicit"])

    def test_resume_rejects_changed_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = FileManager.create_group_project(
                Path(temporary),
                [{"code": "1001", "name": "测试牧场"}],
                data_source="伊起牛",
                task_mode="analysis",
                dataset_selection={"herd": True, "breeding": False},
            )
            worker = MultiFarmTaskWorker(
                None,
                [{"code": "1001", "name": "测试牧场"}],
                parent,
                data_source="伊起牛",
                full_analysis=True,
                dataset_selection={"herd": True, "breeding": True},
            )
            with self.assertRaisesRegex(RuntimeError, "创建时不一致"):
                worker._load_and_validate_dataset_selection()


class DatasetStagePolicyTests(unittest.TestCase):
    def _child(self, root: Path, selection, task_mode="data_only"):
        parent = FileManager.create_group_project(
            root,
            [{"code": "1001", "name": "测试牧场"}],
            data_source="伊起牛",
            task_mode=task_mode,
            dataset_selection=selection,
        )
        metadata = FileManager.load_project_metadata(parent)
        task = metadata["group_tasks"][0]
        return parent / task["relative_path"], task

    def test_herd_only_ignores_stale_breeding_in_manifests(self):
        with tempfile.TemporaryDirectory() as temporary:
            child, task = self._child(
                Path(temporary),
                {"herd": True, "breeding": False},
                task_mode="analysis",
            )
            _write_xlsx(child / "raw_data" / "cow_data.xlsx")
            _write_xlsx(
                child / "standardized_data" / "processed_cow_data.xlsx"
            )
            _write_xlsx(
                child
                / "standardized_data"
                / "processed_breeding_data.xlsx",
                ("耳号", "冻精编号"),
                ("OLD", "OLD_BULL"),
            )
            data_manifest = commit_child_stage(
                child,
                "data",
                expected_task_id=task["task_id"],
                expected_farm_code="1001",
            )
            data_outputs = {
                item["relative_path"]
                for item in data_manifest["outputs"]
            }
            self.assertNotIn(
                "standardized_data/processed_breeding_data.xlsx",
                data_outputs,
            )

            for filename in (
                "processed_cow_data_key_traits_final.xlsx",
                "processed_index_cow_index_scores.xlsx",
                "关键育种性状分析结果.xlsx",
                "系谱识别分析结果.xlsx",
            ):
                _write_xlsx(child / "analysis_results" / filename)
            _write_xlsx(
                child
                / "analysis_results"
                / "processed_mated_bull_traits.xlsx"
            )
            analysis_manifest = commit_child_stage(
                child,
                "analysis",
                expected_task_id=task["task_id"],
                expected_farm_code="1001",
            )
            config = _definition(child, "analysis")["config"]
            self.assertFalse(config["capabilities"]["breeding"])
            self.assertNotIn(
                "standardized_data/processed_breeding_data.xlsx",
                config["standardized_input_set"],
            )
            self.assertNotIn(
                "analysis_results/processed_mated_bull_traits.xlsx",
                config["analysis_output_set"],
            )

    def test_breeding_only_commits_without_fabricating_cow(self):
        with tempfile.TemporaryDirectory() as temporary:
            child, task = self._child(
                Path(temporary),
                {"herd": False, "breeding": True},
            )
            _write_xlsx(
                child / "raw_data" / "breeding_records.xlsx",
                ("耳号", "冻精编号"),
                ("C001", "B001"),
            )
            _write_xlsx(
                child
                / "standardized_data"
                / "processed_breeding_data.xlsx",
                ("耳号", "冻精编号"),
                ("C001", "B001"),
            )
            commit_child_stage(
                child,
                "data",
                expected_task_id=task["task_id"],
                expected_farm_code="1001",
            )
            self.assertTrue(
                validate_child_stage(child, "data")["valid"]
            )
            self.assertFalse(
                (
                    child
                    / "standardized_data"
                    / "processed_cow_data.xlsx"
                ).exists()
            )
            with self.assertRaises(StagePolicyError):
                commit_child_stage(child, "analysis")

    def test_zero_breeding_receipt_is_a_valid_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            child, task = self._child(
                Path(temporary),
                {"herd": False, "breeding": True},
            )
            write_empty_breeding_receipts(
                child,
                data_source="伊起牛",
                farms=[{"code": "1001", "name": "测试牧场"}],
            )
            commit_child_stage(
                child,
                "data",
                expected_task_id=task["task_id"],
                expected_farm_code="1001",
            )
            self.assertTrue(
                validate_child_stage(child, "data")["valid"]
            )
            validate_empty_breeding_receipt(
                child / BREEDING_STANDARDIZED_RECEIPT
            )

    def test_legacy_project_keeps_revision_one_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            child, task = self._child(
                Path(temporary),
                None,
                task_mode="analysis",
            )
            _write_xlsx(child / "raw_data" / "cow_data.xlsx")
            _write_xlsx(
                child / "standardized_data" / "processed_cow_data.xlsx"
            )
            commit_child_stage(
                child,
                "data",
                expected_task_id=task["task_id"],
                expected_farm_code="1001",
            )
            config = _definition(child, "data")["config"]
            self.assertEqual(config["policy_revision"], 1)
            self.assertNotIn(
                "dataset_selection",
                config,
            )

    def test_local_child_rejects_breeding_only_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            child, _task = self._child(
                Path(temporary),
                {"herd": False, "breeding": True},
            )
            metadata_path = child / "project_metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["farms"][0]["source_kind"] = "local"
            FileManager._write_json_atomic(metadata_path, metadata)
            _write_xlsx(
                child / "raw_data" / "breeding_records.xlsx",
                ("耳号", "冻精编号"),
                ("C001", "B001"),
            )
            _write_xlsx(
                child
                / "standardized_data"
                / "processed_breeding_data.xlsx",
                ("耳号", "冻精编号"),
                ("C001", "B001"),
            )
            with self.assertRaises(DatasetSelectionError):
                commit_child_stage(child, "data")

    def test_herd_only_local_inputs_exclude_all_breeding_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root / "raw_data" / "input_bundle"
            for relative in (
                "input_sources/cow_original.xlsx",
                "input_sources/breeding_original.xlsx",
                "raw_data/cow_data.xlsx",
                "raw_data/breeding_records.xlsx",
                "standardized_data/processed_cow_data.xlsx",
                "standardized_data/processed_breeding_data.xlsx",
            ):
                _write_xlsx(bundle / relative)
            inputs = {
                path.relative_to(bundle).as_posix()
                for path in _local_bundle_inputs(
                    root,
                    {"herd": True, "breeding": False},
                )
            }
            self.assertIn("input_sources/cow_original.xlsx", inputs)
            self.assertIn("raw_data/cow_data.xlsx", inputs)
            self.assertNotIn(
                "input_sources/breeding_original.xlsx",
                inputs,
            )
            self.assertNotIn("raw_data/breeding_records.xlsx", inputs)
            self.assertNotIn(
                "standardized_data/processed_breeding_data.xlsx",
                inputs,
            )


class DatasetFallbackStatusTests(unittest.TestCase):
    def test_legacy_without_store_keeps_cow_only_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = FileManager.create_group_project(
                Path(temporary),
                [{"code": "1001", "name": "测试牧场"}],
                data_source="伊起牛",
                task_mode="data_only",
            )
            raw_metadata = json.loads(
                (parent / "project_metadata.json").read_text(
                    encoding="utf-8"
                )
            )
            task = raw_metadata["group_tasks"][0]
            child = parent / task["relative_path"]
            _write_xlsx(
                child
                / "standardized_data"
                / "processed_cow_data.xlsx"
            )
            _remove_group_store(parent)
            refreshed = FileManager.refresh_group_task_statuses(parent)
            self.assertEqual(
                refreshed["group_tasks"][0]["status"],
                "completed",
            )


class DatasetFinalizerTests(unittest.TestCase):
    def test_breeding_only_finalizer_removes_stale_cow_files(self):
        from core.data.composite_farm_manager import (
            finalize_breeding_only_project,
        )

        with tempfile.TemporaryDirectory() as temporary:
            parent = FileManager.create_group_project(
                Path(temporary),
                [{"code": "1001", "name": "测试牧场"}],
                data_source="伊起牛",
                task_mode="data_only",
                dataset_selection={"herd": False, "breeding": True},
            )
            metadata = FileManager.load_project_metadata(parent)
            task = metadata["group_tasks"][0]
            child = parent / task["relative_path"]
            _write_xlsx(child / "raw_data" / "cow_data.xlsx")
            _write_xlsx(
                child
                / "standardized_data"
                / "processed_cow_data.xlsx"
            )
            _write_xlsx(
                child / "raw_data" / "breeding_records.xlsx",
                ("耳号", "冻精编号"),
                ("C001", "B001"),
            )
            _write_xlsx(
                child
                / "standardized_data"
                / "processed_breeding_data.xlsx",
                ("耳号", "冻精编号"),
                ("C001", "B001"),
            )
            finalize_breeding_only_project(
                child,
                [{"code": "1001", "name": "测试牧场"}],
                "伊起牛",
                dataset_selection={"herd": False, "breeding": True},
            )
            self.assertFalse(
                (child / "raw_data" / "cow_data.xlsx").exists()
            )
            self.assertFalse(
                (
                    child
                    / "standardized_data"
                    / "processed_cow_data.xlsx"
                ).exists()
            )
            child_metadata = FileManager.load_project_metadata(child)
            self.assertEqual(
                child_metadata["dataset_selection"],
                {"herd": False, "breeding": True},
            )
            self.assertEqual(child_metadata["farms"][0]["cow_count"], 0)

    def test_finalizer_cannot_change_explicit_child_selection(self):
        from core.data.composite_farm_manager import (
            finalize_breeding_only_project,
        )

        with tempfile.TemporaryDirectory() as temporary:
            parent = FileManager.create_group_project(
                Path(temporary),
                [{"code": "1001", "name": "测试牧场"}],
                data_source="伊起牛",
                task_mode="data_only",
                dataset_selection={"herd": True, "breeding": False},
            )
            metadata = FileManager.load_project_metadata(parent)
            task = metadata["group_tasks"][0]
            child = parent / task["relative_path"]
            with self.assertRaisesRegex(ValueError, "创建时不一致"):
                finalize_breeding_only_project(
                    child,
                    [{"code": "1001", "name": "测试牧场"}],
                    "伊起牛",
                    dataset_selection={
                        "herd": False,
                        "breeding": True,
                    },
                )

    def test_explicit_zero_receipt_without_raw_copy_is_not_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = FileManager.create_group_project(
                Path(temporary),
                [{"code": "1001", "name": "测试牧场"}],
                data_source="伊起牛",
                task_mode="data_only",
                dataset_selection={"herd": False, "breeding": True},
            )
            raw_metadata = json.loads(
                (parent / "project_metadata.json").read_text(
                    encoding="utf-8"
                )
            )
            task = raw_metadata["group_tasks"][0]
            child = parent / task["relative_path"]
            raw_receipt, _standardized_receipt = (
                write_empty_breeding_receipts(
                    child,
                    data_source="伊起牛",
                    farms=[{"code": "1001", "name": "测试牧场"}],
                )
            )
            raw_receipt.unlink()
            _remove_group_store(parent)
            refreshed = FileManager.refresh_group_task_statuses(parent)
            self.assertNotEqual(
                refreshed["group_tasks"][0]["status"],
                "completed",
            )

    def test_explicit_zero_receipt_without_store_checks_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = FileManager.create_group_project(
                Path(temporary),
                [{"code": "1001", "name": "测试牧场"}],
                data_source="伊起牛",
                task_mode="data_only",
                dataset_selection={"herd": False, "breeding": True},
            )
            raw_metadata = json.loads(
                (parent / "project_metadata.json").read_text(
                    encoding="utf-8"
                )
            )
            task = raw_metadata["group_tasks"][0]
            child = parent / task["relative_path"]
            write_empty_breeding_receipts(
                child,
                data_source="伊起牛",
                farms=[{"code": "9999", "name": "错误牧场"}],
            )
            _remove_group_store(parent)
            refreshed = FileManager.refresh_group_task_statuses(parent)
            self.assertNotEqual(
                refreshed["group_tasks"][0]["status"],
                "completed",
            )

            write_empty_breeding_receipts(
                child,
                data_source="伊起牛",
                farms=[{"code": "1001", "name": "测试牧场"}],
            )
            refreshed = FileManager.refresh_group_task_statuses(parent)
            self.assertEqual(
                refreshed["group_tasks"][0]["status"],
                "completed",
            )


class AutoReportDatasetRoutingTests(unittest.TestCase):
    def _worker(self, root, api, source, selection):
        return AutoReportWorker(
            api,
            [{"code": "1001", "name": "测试牧场"}],
            root,
            False,
            data_source=source,
            group_batch_mode=True,
            dataset_selection=selection,
        )

    @staticmethod
    def _cow_upload(*, project_path, **kwargs):
        output = (
            Path(project_path)
            / "standardized_data"
            / "processed_cow_data.xlsx"
        )
        _write_xlsx(output)
        return output

    @staticmethod
    def _breeding_upload(*, project_path, **kwargs):
        output = (
            Path(project_path)
            / "standardized_data"
            / "processed_breeding_data.xlsx"
        )
        _write_xlsx(
            output,
            ("耳号", "冻精编号"),
            ("C001", "B001"),
        )
        return output

    def test_hmy_herd_only_never_calls_breeding_route(self):
        with tempfile.TemporaryDirectory() as temporary:
            api = _CountingApi(hmy=True)
            worker = self._worker(
                Path(temporary),
                api,
                "慧牧云",
                {"herd": True, "breeding": False},
            )
            with (
                patch(
                    "core.data.hmy_data_converter."
                    "HMYDataConverter.convert_herd_to_excel"
                ),
                patch(
                    "core.data.hmy_data_converter."
                    "HMYDataConverter.convert_breeding_records_to_excel"
                ) as breeding_converter,
                patch(
                    "core.data.uploader.upload_and_standardize_cow_data",
                    side_effect=self._cow_upload,
                ),
                patch(
                    "core.data.uploader."
                    "upload_and_standardize_breeding_data"
                ) as breeding_upload,
                patch(
                    "core.data.composite_farm_manager."
                    "finalize_composite_project"
                ),
            ):
                worker._phase_download_and_standardize()
            self.assertEqual(api.herd_calls, 1)
            self.assertEqual(api.breeding_calls, 0)
            self.assertEqual(api.stock_calls, 0)
            breeding_converter.assert_not_called()
            breeding_upload.assert_not_called()

    def test_yqn_breeding_only_never_calls_herd_or_stock(self):
        with tempfile.TemporaryDirectory() as temporary:
            api = _CountingApi(
                hmy=False,
                breeding_records=[{"earNum": "C001"}],
            )
            worker = self._worker(
                Path(temporary),
                api,
                "伊起牛",
                {"herd": False, "breeding": True},
            )
            with (
                patch(
                    "core.data.yqn_data_converter."
                    "YQNDataConverter.convert_breeding_records_to_excel"
                ),
                patch(
                    "core.data.yqn_data_converter."
                    "YQNDataConverter.convert_herd_to_excel"
                ) as herd_converter,
                patch(
                    "core.data.uploader."
                    "upload_and_standardize_breeding_data",
                    side_effect=self._breeding_upload,
                ) as breeding_upload,
                patch(
                    "core.data.composite_farm_manager."
                    "finalize_breeding_only_project"
                ),
            ):
                worker._phase_download_and_standardize()
            self.assertEqual(api.herd_calls, 0)
            self.assertEqual(api.breeding_calls, 1)
            self.assertEqual(api.stock_calls, 0)
            herd_converter.assert_not_called()
            self.assertFalse(
                breeding_upload.call_args.kwargs["require_cow"]
            )

    def test_selected_zero_breeding_writes_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            api = _CountingApi(hmy=True, breeding_records=[])
            worker = self._worker(
                root,
                api,
                "慧牧云",
                {"herd": False, "breeding": True},
            )
            with (
                patch(
                    "core.data.uploader."
                    "upload_and_standardize_breeding_data"
                ) as breeding_upload,
                patch(
                    "core.data.composite_farm_manager."
                    "finalize_breeding_only_project"
                ),
            ):
                worker._phase_download_and_standardize()
            breeding_upload.assert_not_called()
            self.assertTrue((root / BREEDING_RAW_RECEIPT).is_file())
            self.assertTrue(
                (root / BREEDING_STANDARDIZED_RECEIPT).is_file()
            )
            validate_empty_breeding_receipt(
                root / BREEDING_STANDARDIZED_RECEIPT
            )


class BreedingUploaderTests(unittest.TestCase):
    def test_breeding_only_standardization_passes_no_cow_dataframe(self):
        from core.data.uploader import (
            upload_and_standardize_breeding_data,
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input" / "breeding.xlsx"
            source.parent.mkdir(parents=True)
            pd.DataFrame(
                [
                    {
                        "耳号": "C001",
                        "配种日期": "2026-01-01",
                        "冻精编号": "B001",
                        "冻精类型": "普通冻精",
                    }
                ]
            ).to_excel(source, index=False)

            observed = {}

            def fake_process(
                input_file,
                project_path,
                *,
                cow_df,
                **kwargs,
            ):
                observed["cow_df"] = cow_df
                output = (
                    Path(project_path)
                    / "standardized_data"
                    / "processed_breeding_data.xlsx"
                )
                _write_xlsx(
                    output,
                    ("耳号", "冻精编号"),
                    ("C001", "B001"),
                )
                return output

            with patch(
                "core.data.uploader.process_breeding_record_file",
                side_effect=fake_process,
            ):
                output = upload_and_standardize_breeding_data(
                    [source],
                    root,
                    require_cow=False,
                )
            self.assertTrue(output.is_file())
            self.assertIsNone(observed["cow_df"])


if __name__ == "__main__":
    unittest.main()
