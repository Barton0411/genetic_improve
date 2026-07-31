from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from core.auto_analysis_runner import (
    DEFECT_GENES,
    run_cow_self_inbreeding_analysis,
)
from gui.auto_report_worker import AutoReportWorker
from utils.large_excel_writer import read_excel_identifier_safe


class _FakePedigreeDatabase:
    def __init__(self):
        self.pedigree = {
            "001": {"sire": "S1", "dam": "D1"},
        }
        self.build_calls = []

    def build_cow_pedigree(self, path, progress_callback=None):
        self.build_calls.append(Path(path))
        if progress_callback:
            progress_callback(100, "完成")
        return self.pedigree

    @staticmethod
    def standardize_animal_id(value, _id_type):
        return str(value).strip() if value is not None else ""


class _FakePathCalculator:
    def __init__(self, pedigree_db):
        self.pedigree_db = pedigree_db
        self.calls = []

    def calculate_potential_offspring_inbreeding(self, sire_id, dam_id):
        self.calls.append((sire_id, dam_id))
        return (
            0.125,
            {"A1": 0.125},
            {"A1": [("S1-A1-D1", 0.125, 1, 1, 0.0)]},
        )


class AutoCowSelfInbreedingTests(unittest.TestCase):
    def test_pure_runner_matches_manual_scope_and_fixed_output(self):
        pedigree_db = _FakePedigreeDatabase()
        calculator = _FakePathCalculator(pedigree_db)
        gene_data = {gene: "F" for gene in DEFECT_GENES}
        gene_data["HH1"] = "C"

        with tempfile.TemporaryDirectory() as temporary_dir:
            project_path = Path(temporary_dir)
            standardized = project_path / "standardized_data"
            standardized.mkdir()
            pd.DataFrame(
                [
                    {
                        "cow_id": "001",
                        "sire": "S1",
                        "dam": "D1",
                        "sex": "母",
                        "breed": "荷斯坦",
                        "birth_date": "2022-01-02",
                        "lac": 1,
                        "是否在场": "是",
                        "牧场编号": "01001",
                        "牧场名称": "一号场",
                    },
                    {
                        "cow_id": "002",
                        "sire": "S2",
                        "dam": "D2",
                        "sex": "公",
                        "breed": "荷斯坦",
                        "牧场编号": "01001",
                        "牧场名称": "一号场",
                    },
                    {
                        "cow_id": "003",
                        "sire": "S3",
                        "dam": "D3",
                        "sex": "母",
                        "breed": "西门塔尔",
                        "牧场编号": "01001",
                        "牧场名称": "一号场",
                    },
                ]
            ).to_excel(
                standardized / "processed_cow_data.xlsx",
                index=False,
            )

            with (
                patch(
                    "core.data.update_manager.get_pedigree_db",
                    return_value=pedigree_db,
                ),
                patch(
                    "core.inbreeding.path_inbreeding_calculator."
                    "PathInbreedingCalculator",
                    return_value=calculator,
                ),
                patch(
                    "core.auto_analysis_runner._query_bull_genes",
                    return_value=({"S1": gene_data}, []),
                ),
            ):
                success, message = run_cow_self_inbreeding_analysis(
                    project_path
                )

            self.assertTrue(success, message)
            self.assertIn("共 1 头母牛", message)
            self.assertEqual(calculator.calls, [("S1", "D1")])
            output = (
                project_path
                / "analysis_results"
                / "母牛近交系数分析结果.xlsx"
            )
            self.assertTrue(output.is_file())
            details = read_excel_identifier_safe(
                output,
                sheet_name="配对明细表",
            )
            abnormal = read_excel_identifier_safe(
                output,
                sheet_name="异常明细表",
            )
            stats = pd.read_excel(output, sheet_name="统计表")

        self.assertEqual(details["母牛号"].tolist(), ["001"])
        self.assertEqual(details["牧场编号"].tolist(), ["01001"])
        self.assertEqual(details.loc[0, "近交系数"], "12.500%")
        self.assertEqual(details.loc[0, "HH1"], "仅母牛父亲携带")
        self.assertCountEqual(
            abnormal["异常类型"].tolist(),
            ["HH1", "近交系数过高"],
        )
        self.assertEqual(
            dict(zip(stats["异常类型"], stats["数量"])),
            {"HH1": 1, "近交系数过高": 1},
        )

    def test_reliable_worker_runs_cow_self_task_sequentially(self):
        calls = []

        def task(name):
            def run(*_args):
                calls.append(name)
                return True, f"{name}完成"

            return run

        with tempfile.TemporaryDirectory() as temporary_dir:
            worker = AutoReportWorker(
                None,
                [{"code": "01001", "name": "一号场"}],
                Path(temporary_dir),
                reliability_mode=True,
                group_batch_mode=True,
                dataset_selection={"herd": True, "breeding": False},
            )
            with (
                patch(
                    "core.auto_analysis_runner.run_cow_traits",
                    side_effect=task("母牛性状"),
                ),
                patch(
                    "core.auto_analysis_runner."
                    "run_cow_self_inbreeding_analysis",
                    side_effect=task("母牛近交"),
                ),
                patch(
                    "core.auto_analysis_runner.run_cow_index",
                    side_effect=task("母牛指数"),
                ),
            ):
                worker._phase_analysis()

        self.assertEqual(
            calls,
            ["母牛性状", "母牛近交", "母牛指数"],
        )
        self.assertIn("母牛近交分析", worker.results["success_items"])
        self.assertEqual(worker.results["failed_items"], [])


if __name__ == "__main__":
    unittest.main()
