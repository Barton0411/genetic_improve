from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.acceptance_scope_checks import validate_child_scope_artifacts


def _write(path: Path, frame: pd.DataFrame, *, sheet_name: str = "Sheet1"):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_excel(path, sheet_name=sheet_name, index=False)


def _write_multi_sheet(path: Path, sheets: dict[str, pd.DataFrame]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=sheet_name, index=False)


def _check_by_name(checks, name):
    return next(check for check in checks if check["lineage"] == name)


class AcceptanceScopeChecksTests(unittest.TestCase):
    def _base_project(self, root: Path) -> Path:
        child = root / "child"
        standardized = child / "standardized_data"
        analysis = child / "analysis_results"
        cows = pd.DataFrame(
            [
                {
                    "cow_id": "DAIRY-IN",
                    "breed": "荷斯坦",
                    "sex": "母",
                    "是否在场": "是",
                },
                {
                    "cow_id": "DAIRY-LEFT",
                    "breed": "中国荷斯坦",
                    "sex": "母",
                    "是否在场": "否",
                },
                {
                    "cow_id": "BEEF-IN",
                    "breed": "安格斯",
                    "sex": "母",
                    "是否在场": "是",
                },
                {
                    "cow_id": "MALE-IN",
                    "breed": "荷斯坦",
                    "sex": "公",
                    "是否在场": "是",
                },
            ]
        )
        _write(standardized / "processed_cow_data.xlsx", cows)
        _write(
            standardized / "processed_bull_data.xlsx",
            pd.DataFrame(
                [
                    {
                        "bull_id": "001HO00001",
                        "semen_type": "常规",
                        "支数": 10,
                    },
                    {
                        "bull_id": "002HO00002",
                        "semen_type": "性控",
                        "支数": 10,
                    },
                ]
            ),
        )
        index = cows.copy()
        index["Combine Index Score"] = [1.0, 2.0, 3.0, 4.0]
        _write(analysis / "processed_index_cow_index_scores.xlsx", index)
        _write_multi_sheet(
            analysis / "母牛近交系数分析结果.xlsx",
            {
                "配对明细表": pd.DataFrame(
                    {"母牛号": ["DAIRY-IN", "DAIRY-LEFT"]}
                )
            },
        )
        candidate_rows = [
            {"母牛号": cow, "备选公牛号": bull}
            for cow in ("DAIRY-IN",)
            for bull in ("001HO00001", "002HO00002")
        ]
        _write_multi_sheet(
            analysis / "备选公牛_近交系数及隐性基因分析结果.xlsx",
            {"配对明细表": pd.DataFrame(candidate_rows)},
        )
        matching_scope = ["DAIRY-IN", "BEEF-IN"]
        _write_multi_sheet(
            analysis / "个体选配推荐矩阵.xlsx",
            {"推荐汇总": pd.DataFrame({"cow_id": matching_scope})},
        )
        _write_multi_sheet(
            analysis / "个体选配报告.xlsx",
            {"选配结果": pd.DataFrame({"母牛号": matching_scope})},
        )
        return child

    def _add_breeding(self, child: Path) -> None:
        raw = pd.DataFrame(
            [
                {
                    "耳号": "DAIRY-IN",
                    "配种日期": "2026-07-01 08:30:00",
                    "冻精编号": "1HO1",
                    "冻精类型": "普通冻精",
                },
                {
                    "耳号": "DAIRY-LEFT",
                    "配种日期": "2026-07-02 09:30:00",
                    "冻精编号": "2HO2",
                    "冻精类型": "性控冻精",
                },
                {
                    "耳号": "BEEF-IN",
                    "配种日期": "2026-07-03 10:30:00",
                    "冻精编号": "3HO3",
                    "冻精类型": "普通冻精",
                },
            ]
        )
        processed = pd.DataFrame(
            [
                {
                    "耳号": "DAIRY-IN",
                    "配种日期": "2026-07-01 08:30:00",
                    "冻精编号": "001HO00001",
                    "冻精类型": "普通冻精",
                },
                {
                    "耳号": "DAIRY-LEFT",
                    "配种日期": "2026-07-02 09:30:00",
                    "冻精编号": "002HO00002",
                    "冻精类型": "性控冻精",
                },
                {
                    "耳号": "BEEF-IN",
                    "配种日期": "2026-07-03 10:30:00",
                    "冻精编号": "003HO00003",
                    "冻精类型": "普通冻精",
                },
            ]
        )
        _write(child / "raw_data" / "breeding_records.xlsx", raw)
        _write(
            child / "standardized_data" / "processed_breeding_data.xlsx",
            processed,
        )
        _write_multi_sheet(
            child
            / "analysis_results"
            / "已配公牛_近交系数及隐性基因分析结果.xlsx",
            {
                "配对明细表": pd.DataFrame(
                    [
                        {
                            "母牛号": "DAIRY-IN",
                            "配种日期": "2026-07-01 08:30:00",
                            "配种公牛号": "001HO00001",
                        },
                        {
                            "母牛号": "DAIRY-LEFT",
                            "配种日期": "2026-07-02 09:30:00",
                            "配种公牛号": "002HO00002",
                        },
                    ]
                )
            },
        )

    def test_complete_scopes_pass_and_do_not_expose_business_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            child = self._base_project(Path(temporary))
            self._add_breeding(child)

            checks = validate_child_scope_artifacts(child)

            for name in (
                "breeding_business_key",
                "cow_self_scope",
                "candidate_cartesian_scope",
                "mated_business_key_scope",
                "matching_scope",
            ):
                self.assertTrue(_check_by_name(checks, name)["passed"], name)
            serialized = json.dumps(checks, ensure_ascii=False)
            for identifier in (
                "DAIRY-IN",
                "DAIRY-LEFT",
                "BEEF-IN",
                "001HO00001",
                "002HO00002",
            ):
                self.assertNotIn(identifier, serialized)

    def test_breeding_business_key_finds_same_count_wrong_bull(self):
        with tempfile.TemporaryDirectory() as temporary:
            child = self._base_project(Path(temporary))
            self._add_breeding(child)
            processed_path = (
                child
                / "standardized_data"
                / "processed_breeding_data.xlsx"
            )
            processed = pd.read_excel(processed_path)
            processed.loc[0, "冻精编号"] = "009HO00009"
            _write(processed_path, processed)

            check = _check_by_name(
                validate_child_scope_artifacts(child),
                "breeding_business_key",
            )

            self.assertFalse(check["passed"])
            self.assertEqual(check["expected_rows"], check["actual_rows"])
            self.assertEqual(check["missing_rows"], 1)
            self.assertEqual(check["unexpected_rows"], 1)

    def test_candidate_cartesian_finds_one_missing_pair(self):
        with tempfile.TemporaryDirectory() as temporary:
            child = self._base_project(Path(temporary))
            candidate_path = (
                child
                / "analysis_results"
                / "备选公牛_近交系数及隐性基因分析结果.xlsx"
            )
            _write_multi_sheet(
                candidate_path,
                {
                    "配对明细表": pd.DataFrame(
                        [
                            {
                                "母牛号": "DAIRY-IN",
                                "备选公牛号": "001HO00001",
                            }
                        ]
                    )
                },
            )

            check = _check_by_name(
                validate_child_scope_artifacts(child),
                "candidate_cartesian_scope",
            )

            self.assertFalse(check["passed"])
            self.assertEqual(check["expected_cartesian_rows"], 2)
            self.assertEqual(check["actual_rows"], 1)
            self.assertEqual(check["missing_rows"], 1)

    def test_mated_scope_uses_full_business_key_and_dairy_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            child = self._base_project(Path(temporary))
            self._add_breeding(child)
            result_path = (
                child
                / "analysis_results"
                / "已配公牛_近交系数及隐性基因分析结果.xlsx"
            )
            result = pd.read_excel(result_path, sheet_name="配对明细表")
            result.loc[1, "配种日期"] = "2026-07-09 09:30:00"
            _write_multi_sheet(result_path, {"配对明细表": result})

            check = _check_by_name(
                validate_child_scope_artifacts(child),
                "mated_business_key_scope",
            )

            self.assertFalse(check["passed"])
            # 离场奶牛历史仍在范围内，肉牛配种记录不在范围内。
            self.assertEqual(check["expected_rows"], 2)
            self.assertEqual(check["actual_rows"], 2)
            self.assertEqual(check["missing_rows"], 1)
            self.assertEqual(check["unexpected_rows"], 1)

    def test_matching_scope_checks_matrix_and_final_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            child = self._base_project(Path(temporary))
            report_path = (
                child / "analysis_results" / "个体选配报告.xlsx"
            )
            _write_multi_sheet(
                report_path,
                {"选配结果": pd.DataFrame({"母牛号": ["DAIRY-IN"]})},
            )

            check = _check_by_name(
                validate_child_scope_artifacts(child),
                "matching_scope",
            )

            self.assertFalse(check["passed"])
            self.assertEqual(check["expected_rows"], 2)
            self.assertEqual(check["matrix_missing_rows"], 0)
            self.assertEqual(check["report_missing_rows"], 1)


if __name__ == "__main__":
    unittest.main()
