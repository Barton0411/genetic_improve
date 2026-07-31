from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.auto_analysis_runner import run_bull_index, run_cow_index  # noqa: E402
from core.breeding_calc.index_calculation import IndexCalculation  # noqa: E402
from core.group_tasks.feature_policy import (  # noqa: E402
    FeaturePolicyError,
    normalize_feature_parameters,
)
from core.group_tasks.feature_runner import (  # noqa: E402
    ValidatedFeatureRequest,
    _execute_operation,
)
from gui.main_window import MainWindow  # noqa: E402


WEIGHT_NAME = "同名自定义权重"
WEIGHT_SNAPSHOT = {"DPR": 35.0, "NM$": 65.0}


class GroupIndexSnapshotCaptureTests(unittest.TestCase):
    def test_group_start_freezes_selected_weight_values_for_both_index_tabs(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            project_path = Path(temporary_dir)
            metadata = {
                "dataset_selection": {"herd": True, "breeding": True},
                "group_tasks": [
                    {
                        "task_id": "task-a",
                        "included_in_summary": True,
                    }
                ],
            }

            for operation in ("cow_index", "bull_index"):
                with self.subTest(operation=operation):
                    window = SimpleNamespace(
                        selected_project_path=project_path,
                        is_group_project=True,
                        _group_batch_is_running=lambda: False,
                        _on_group_feature_finished=MagicMock(),
                        _on_group_feature_error=MagicMock(),
                    )
                    dialog = MagicMock()
                    worker = MagicMock()

                    with (
                        patch(
                            "gui.main_window.FileManager.load_project_metadata",
                            return_value=metadata,
                        ),
                        patch(
                            "core.breeding_calc.index_calculation."
                            "IndexCalculation.load_weights",
                            return_value={
                                WEIGHT_NAME: dict(WEIGHT_SNAPSHOT)
                            },
                        ),
                        patch(
                            "gui.main_window.ProgressDialog",
                            return_value=dialog,
                        ),
                        patch(
                            "gui.group_feature_analysis_worker."
                            "GroupFeatureAnalysisWorker",
                            return_value=worker,
                        ) as worker_type,
                    ):
                        MainWindow.start_group_feature_analysis(
                            window,
                            operation=operation,
                            parameters={"weight_name": WEIGHT_NAME},
                            title="指数测试",
                        )

                    worker_type.assert_called_once_with(
                        project_path,
                        operation,
                        {
                            "weight_name": WEIGHT_NAME,
                            "weight_values": dict(WEIGHT_SNAPSHOT),
                        },
                    )
                    worker.start.assert_called_once_with()


class FeatureIndexSnapshotTests(unittest.TestCase):
    def test_index_feature_rejects_name_without_value_snapshot(self):
        with self.assertRaises(FeaturePolicyError):
            normalize_feature_parameters(
                "cow_index",
                {"weight_name": WEIGHT_NAME},
            )

    def test_feature_runner_passes_snapshot_to_each_index_operation(self):
        progress = MagicMock()
        for operation, target, extra_kwargs in (
            (
                "cow_index",
                "core.auto_analysis_runner.run_cow_index",
                {},
            ),
            (
                "bull_index",
                "core.auto_analysis_runner.run_bull_index",
                {"allow_missing_bull_upload": False},
            ),
        ):
            with self.subTest(operation=operation):
                request = ValidatedFeatureRequest(
                    task_id="task-a",
                    farm_code="001",
                    farm_name="测试牧场",
                    project_path=Path("/tmp/child-project"),
                    parent_group_path=Path("/tmp/group-project"),
                    dataset_selection={"herd": True, "breeding": True},
                    operation=operation,
                    parameters={
                        "weight_name": WEIGHT_NAME,
                        "weight_values": dict(WEIGHT_SNAPSHOT),
                    },
                )
                with patch(target, return_value=(True, "ok")) as runner:
                    self.assertEqual(
                        _execute_operation(request, progress),
                        (True, "ok"),
                    )

                runner.assert_called_once_with(
                    request.project_path,
                    WEIGHT_NAME,
                    progress,
                    weight_values=WEIGHT_SNAPSHOT,
                    **extra_kwargs,
                )


class AutoAnalysisIndexSnapshotTests(unittest.TestCase):
    def test_auto_runners_forward_snapshot_to_index_calculation(self):
        progress = MagicMock()
        for runner, process_method, extra_kwargs in (
            (run_cow_index, "process_cow_index", {}),
            (
                run_bull_index,
                "process_bull_index",
                {"allow_missing_bull_upload": False},
            ),
        ):
            with self.subTest(process_method=process_method):
                with patch(
                    "core.breeding_calc.index_calculation.IndexCalculation"
                ) as calculation_type:
                    calculation = calculation_type.return_value
                    getattr(calculation, process_method).return_value = (
                        True,
                        "ok",
                    )
                    result = runner(
                        Path("/tmp/child-project"),
                        WEIGHT_NAME,
                        progress,
                        weight_values=dict(WEIGHT_SNAPSHOT),
                        **extra_kwargs,
                    )

                self.assertEqual(result, (True, "ok"))
                call = getattr(calculation, process_method).call_args
                self.assertEqual(call.args[1], WEIGHT_NAME)
                self.assertIs(call.args[2], progress)
                self.assertEqual(
                    call.kwargs["weight_values"],
                    WEIGHT_SNAPSHOT,
                )
                for key, value in extra_kwargs.items():
                    self.assertEqual(call.kwargs[key], value)


class IndexCalculationSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.project_path = Path(self.temporary_dir.name)
        (self.project_path / "standardized_data").mkdir()
        (self.project_path / "analysis_results").mkdir()

    def tearDown(self):
        self.temporary_dir.cleanup()

    @staticmethod
    def _capture_saved_frame(calculation):
        captured = {}

        def save(frame, *_args, **_kwargs):
            captured["frame"] = frame.copy()
            return True

        calculation.save_results_with_retry = MagicMock(side_effect=save)
        return captured

    def test_cow_index_uses_snapshot_without_reloading_same_name(self):
        (
            self.project_path
            / "standardized_data"
            / "processed_cow_data.xlsx"
        ).touch()
        pd.DataFrame(
            {
                "cow_id": ["001", "002"],
                "NM$_score": [100.0, 50.0],
                "TPI_score": [-1000.0, 1000.0],
            }
        ).to_excel(
            self.project_path
            / "analysis_results"
            / "processed_cow_data_key_traits_scores_pedigree.xlsx",
            index=False,
        )

        calculation = IndexCalculation()
        calculation.load_weights = MagicMock(
            side_effect=AssertionError(
                "传入快照后不得按同名配置重新加载权重"
            )
        )
        captured = self._capture_saved_frame(calculation)

        success, message = calculation.process_cow_index(
            SimpleNamespace(selected_project_path=self.project_path),
            WEIGHT_NAME,
            weight_values={"NM$": 100.0},
        )

        self.assertTrue(success, message)
        calculation.load_weights.assert_not_called()
        result = captured["frame"]
        self.assertEqual(
            result[f"{WEIGHT_NAME}_index"].tolist(),
            [100.0, 50.0],
        )
        self.assertEqual(result["ranking"].tolist(), [1, 2])

    def test_bull_index_uses_snapshot_without_reloading_same_name(self):
        pd.DataFrame(
            {"bull_id": ["B1", "B2"]}
        ).to_excel(
            self.project_path
            / "standardized_data"
            / "processed_bull_data.xlsx",
            index=False,
        )

        calculation = IndexCalculation()
        calculation.load_weights = MagicMock(
            side_effect=AssertionError(
                "传入快照后不得按同名配置重新加载权重"
            )
        )
        calculation.init_db_connection = MagicMock(return_value=True)
        calculation.query_bull_traits_batch = MagicMock(
            return_value={
                "B1": ({"NM$": 200.0, "TPI": -1000.0}, True),
                "B2": ({"NM$": 50.0, "TPI": 1000.0}, True),
            }
        )
        captured = self._capture_saved_frame(calculation)

        success, message = calculation.process_bull_index(
            SimpleNamespace(
                selected_project_path=self.project_path,
                username="tester",
            ),
            WEIGHT_NAME,
            weight_values={"NM$": 100.0},
            allow_missing_bull_upload=False,
        )

        self.assertTrue(success, message)
        calculation.load_weights.assert_not_called()
        result = captured["frame"]
        self.assertEqual(
            result[f"{WEIGHT_NAME}_index"].tolist(),
            [200.0, 50.0],
        )
        self.assertEqual(result["ranking"].tolist(), [1, 2])


if __name__ == "__main__":
    unittest.main()
