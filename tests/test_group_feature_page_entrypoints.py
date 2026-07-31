from __future__ import annotations

import os
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.breeding_calc.bull_traits_calc import BullKeyTraitsPage  # noqa: E402
from core.breeding_calc.cow_traits_calc import CowKeyTraitsPage  # noqa: E402
from core.breeding_calc.index_page import IndexCalculationPage  # noqa: E402
from core.breeding_calc.mated_bull_traits_calc import (  # noqa: E402
    MatedBullKeyTraitsPage,
)
from core.inbreeding.inbreeding_page import InbreedingPage  # noqa: E402


class _GroupMainWindow:
    is_group_project = True

    def __init__(self):
        self.start_group_feature_analysis = MagicMock()

    @property
    def selected_project_path(self):
        raise AssertionError("牧场组入口不应读取父项目的单场文件路径")


class GroupTraitPageEntryTests(unittest.TestCase):
    def test_trait_pages_pass_exact_selected_traits_before_local_checks(self):
        cases = (
            (
                CowKeyTraitsPage.start_cow_traits_calculation,
                "core.breeding_calc.cow_traits_calc.ProgressDialog",
                "cow_traits",
                "在群母牛关键育种性状分析",
            ),
            (
                BullKeyTraitsPage.start_bull_traits_calculation,
                None,
                "bull_traits",
                "备选公牛关键育种性状分析",
            ),
            (
                MatedBullKeyTraitsPage.start_mated_bull_traits_calculation,
                "core.breeding_calc.mated_bull_traits_calc.ProgressDialog",
                "mated_bull_traits",
                "已配公牛关键育种性状分析",
            ),
        )
        selected_traits = ["NM$", "TPI", "MILK"]

        for method, progress_target, operation, title in cases:
            with self.subTest(operation=operation):
                main_window = _GroupMainWindow()
                page = SimpleNamespace(
                    get_main_window=lambda: main_window,
                    get_selected_traits=lambda: list(selected_traits),
                )

                progress_context = (
                    patch(progress_target)
                    if progress_target
                    else nullcontext(MagicMock())
                )
                with progress_context as progress_dialog:
                    method(page)

                main_window.start_group_feature_analysis.assert_called_once_with(
                    operation=operation,
                    parameters={"traits": selected_traits},
                    title=title,
                )
                progress_dialog.assert_not_called()

    def test_trait_pages_reject_empty_selection_before_group_start(self):
        cases = (
            (
                CowKeyTraitsPage.start_cow_traits_calculation,
                "core.breeding_calc.cow_traits_calc.QMessageBox.warning",
            ),
            (
                BullKeyTraitsPage.start_bull_traits_calculation,
                "core.breeding_calc.bull_traits_calc.QMessageBox.warning",
            ),
            (
                MatedBullKeyTraitsPage.start_mated_bull_traits_calculation,
                "core.breeding_calc.mated_bull_traits_calc.QMessageBox.warning",
            ),
        )

        for method, warning_target in cases:
            with self.subTest(method=method.__name__):
                main_window = _GroupMainWindow()
                page = SimpleNamespace(
                    get_main_window=lambda: main_window,
                    get_selected_traits=lambda: [],
                )

                with patch(warning_target) as warning:
                    method(page)

                warning.assert_called_once()
                self.assertIn("至少选择一个性状", warning.call_args.args[2])
                main_window.start_group_feature_analysis.assert_not_called()


class GroupIndexPageEntryTests(unittest.TestCase):
    def test_index_pages_pass_selected_weight_name_before_local_checks(self):
        cases = (
            (
                IndexCalculationPage.calculate_cow_index,
                "cow_index",
                "母牛群指数计算排名",
            ),
            (
                IndexCalculationPage.calculate_bull_index,
                "bull_index",
                "备选公牛指数计算排名",
            ),
        )

        for method, operation, title in cases:
            with self.subTest(operation=operation):
                main_window = _GroupMainWindow()
                page = SimpleNamespace(
                    current_weight_name="自定义高产权重",
                    get_main_window=lambda: main_window,
                )

                with patch(
                    "core.breeding_calc.index_page.ProgressDialog"
                ) as progress_dialog:
                    method(page)

                main_window.start_group_feature_analysis.assert_called_once_with(
                    operation=operation,
                    parameters={"weight_name": "自定义高产权重"},
                    title=title,
                )
                progress_dialog.assert_not_called()


class GroupInbreedingPageEntryTests(unittest.TestCase):
    def test_inbreeding_tabs_map_to_distinct_operations_without_local_files(self):
        cases = (
            (
                "cow_self",
                "cow_self_inbreeding",
                "母牛近交系数及隐性基因分析",
            ),
            (
                "mated",
                "mated_inbreeding",
                "已配公牛近交系数及隐性基因分析",
            ),
            (
                "candidate",
                "candidate_inbreeding",
                "备选公牛近交系数及隐性基因分析",
            ),
        )

        for analysis_type, operation, title in cases:
            with self.subTest(analysis_type=analysis_type):
                main_window = _GroupMainWindow()
                page = SimpleNamespace(
                    get_main_window=lambda: main_window,
                    get_project_path=MagicMock(
                        side_effect=AssertionError(
                            "牧场组入口不应检查父项目文件"
                        )
                    ),
                )

                with patch(
                    "core.inbreeding.inbreeding_page.ProgressDialog"
                ) as progress_dialog:
                    InbreedingPage.start_analysis(page, analysis_type)

                main_window.start_group_feature_analysis.assert_called_once_with(
                    operation=operation,
                    parameters={},
                    title=title,
                )
                page.get_project_path.assert_not_called()
                progress_dialog.assert_not_called()


if __name__ == "__main__":
    unittest.main()
