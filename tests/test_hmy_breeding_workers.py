"""慧牧云创建项目与自动报告流程的配种记录接入测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from gui.auto_report_worker import AutoReportWorker
from gui.farm_selection_page import HMYDataDownloadWorker


class FakeHMYClient:
    def __init__(self, fail_breeding: bool = False):
        self.fail_breeding = fail_breeding
        self.herd_calls = []
        self.breeding_calls = []

    def get_farm_herd(self, farm_code):
        self.herd_calls.append(farm_code)
        return {
            "code": 200,
            "count": 1,
            "farmName": "0101001测试牧场",
            "data": [
                {
                    "farmCode": farm_code,
                    "farmName": "0101001测试牧场",
                    "cowId": "1001",
                    "sire": "001HO10001",
                }
            ],
        }

    def get_breeding_records(self, farm_code):
        self.breeding_calls.append(farm_code)
        if self.fail_breeding:
            raise RuntimeError("temporary upstream failure")
        return {
            "code": 200,
            "count": 1,
            "farmName": "0101001测试牧场",
            "data": [
                {
                    "farmCode": farm_code,
                    "farmName": "0101001测试牧场",
                    "cowId": "1001",
                    "siren": "291HO23025",
                    "eventDate": "2026-07-01",
                }
            ],
        }


def _fake_standardize_cows(input_files, project_path, **_kwargs):
    output = Path(project_path) / "standardized_data" / "processed_cow_data.xlsx"
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "cow_id": ["1001"],
            "sire": ["001HO10001"],
            "牧场编号": ["1100110001"],
            "牧场名称": ["测试牧场"],
        }
    ).to_excel(output, index=False)
    return output


def _fake_standardize_breeding(input_files, project_path, **_kwargs):
    output = (
        Path(project_path)
        / "standardized_data"
        / "processed_breeding_data.xlsx"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "耳号": ["1001"],
            "父号": ["001HO10001"],
            "冻精编号": ["291HO23025"],
            "配种日期": ["2026-07-01"],
            "冻精类型": ["未知"],
            "牧场编号": ["1100110001"],
            "牧场名称": ["测试牧场"],
        }
    ).to_excel(output, index=False)
    return output


class HMYBreedingWorkerTests(unittest.TestCase):
    def setUp(self):
        self.farms = [{"code": "1100110001", "name": "本地占位名称"}]

    def test_create_project_worker_downloads_and_standardizes_breeding(self):
        client = FakeHMYClient()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            worker = HMYDataDownloadWorker(
                client,
                [dict(self.farms[0])],
                project,
            )
            finished = []
            errors = []
            worker.finished.connect(finished.append)
            worker.error.connect(errors.append)

            with (
                patch(
                    "gui.farm_selection_page.upload_and_standardize_cow_data",
                    side_effect=_fake_standardize_cows,
                ),
                patch(
                    "gui.farm_selection_page.upload_and_standardize_breeding_data",
                    side_effect=_fake_standardize_breeding,
                ),
                patch(
                    "core.data.composite_farm_manager.finalize_composite_project"
                ),
            ):
                worker.run()

            self.assertFalse(errors)
            self.assertEqual(len(finished), 1)
            self.assertEqual(client.breeding_calls, ["1100110001"])
            self.assertTrue(
                (project / "raw_data" / "breeding_records.xlsx").exists()
            )
            self.assertTrue(
                (
                    project
                    / "standardized_data"
                    / "processed_breeding_data.xlsx"
                ).exists()
            )

    def test_create_project_worker_keeps_cow_flow_when_breeding_fails(self):
        client = FakeHMYClient(fail_breeding=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            worker = HMYDataDownloadWorker(
                client,
                [dict(self.farms[0])],
                project,
            )
            finished = []
            errors = []
            worker.finished.connect(finished.append)
            worker.error.connect(errors.append)

            with (
                patch(
                    "gui.farm_selection_page.upload_and_standardize_cow_data",
                    side_effect=_fake_standardize_cows,
                ),
                patch(
                    "core.data.composite_farm_manager.finalize_composite_project"
                ),
            ):
                worker.run()

            self.assertFalse(errors)
            self.assertEqual(len(finished), 1)
            self.assertFalse(
                (
                    project
                    / "standardized_data"
                    / "processed_breeding_data.xlsx"
                ).exists()
            )

    def test_auto_report_phase_exposes_breeding_to_later_analyses(self):
        client = FakeHMYClient()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            worker = AutoReportWorker(
                client,
                [dict(self.farms[0])],
                project,
                data_source="慧牧云",
            )

            with (
                patch(
                    "core.data.uploader.upload_and_standardize_cow_data",
                    side_effect=_fake_standardize_cows,
                ),
                patch(
                    "core.data.uploader.upload_and_standardize_breeding_data",
                    side_effect=_fake_standardize_breeding,
                ),
                patch(
                    "core.data.composite_farm_manager.finalize_composite_project"
                ),
            ):
                worker._phase_download_and_standardize_hmy()

            self.assertIn(
                "配种记录下载与标准化",
                worker.results["success_items"],
            )
            self.assertTrue(
                (
                    project
                    / "standardized_data"
                    / "processed_breeding_data.xlsx"
                ).exists()
            )


if __name__ == "__main__":
    unittest.main()
