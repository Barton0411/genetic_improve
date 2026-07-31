from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from core.excel_report.data_collectors.candidate_bulls_genes_collector import (
    collect_candidate_bulls_genes_data,
)
from core.excel_report.data_collectors.candidate_bulls_inbreeding_collector import (
    collect_candidate_bulls_inbreeding_data,
)


class CandidateBullsCollectorDeduplicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.project_folder = Path(self.temporary_dir.name)
        self.analysis_folder = self.project_folder / "analysis_results"
        standardized_folder = self.project_folder / "standardized_data"
        self.analysis_folder.mkdir()
        standardized_folder.mkdir()

        # 第一、二行是同一配对，只是历史 Excel 中的数值/空格格式不同。
        # 第三行用于确认不同母牛不误删，第四行用于确认不同公牛不误删。
        result_rows = pd.DataFrame(
            {
                "母牛号": [1001, " 1001.0 ", 1002, 1001],
                "父号": ["SIRE-1", "SIRE-1", "SIRE-2", "SIRE-1"],
                "原始父号": ["", "", "", ""],
                "备选公牛号": [2001, "2001.0", 2001, 2002],
                "原始备选公牛号": [
                    "BULL-1",
                    "BULL-1",
                    "BULL-1",
                    "BULL-2",
                ],
                "近交系数": ["0.00%"] * 4,
                "后代近交系数": ["8.00%", "8.00%", "2.00%", "1.00%"],
                "HH1": ["高风险", "高风险", "-", "-"],
                "HH1(母)": ["C", "C", "F", "C"],
                "HH1(公)": ["C", "C", "C", "F"],
            }
        )
        result_rows.to_excel(
            self.analysis_folder
            / "备选公牛_近交系数及隐性基因分析结果_历史.xlsx",
            index=False,
            engine="openpyxl",
        )

        pd.DataFrame(
            {
                # 前两行是同一母牛的 Excel 数字/文本形式；collector
                # 合并前必须先按规范化牛号去重，不能把配对重新放大。
                "cow_id": [1001, "1001.0", 1002],
                "是否在场": ["是", "是", "是"],
                "sex": ["母", "母", "母"],
                "lac": [1, 1, 0],
            }
        ).to_excel(
            standardized_folder / "processed_cow_data.xlsx",
            index=False,
            engine="openpyxl",
        )

    def tearDown(self):
        self.temporary_dir.cleanup()

    @staticmethod
    def _bulls_by_id(result: dict) -> dict:
        return {bull["bull_id"]: bull for bull in result["bulls"]}

    def test_inbreeding_counts_each_normalized_pair_once(self):
        with self.assertLogs(
            "core.excel_report.data_collectors."
            "candidate_bulls_inbreeding_collector",
            level="WARNING",
        ) as captured:
            result = collect_candidate_bulls_inbreeding_data(
                self.analysis_folder,
                self.project_folder,
            )

        bulls = self._bulls_by_id(result)
        self.assertEqual(set(bulls), {"2001", "2002"})
        self.assertEqual(bulls["2001"]["mature_cow_count"], 1)
        self.assertEqual(bulls["2001"]["heifer_count"], 1)
        self.assertEqual(bulls["2001"]["total_cow_count"], 2)
        self.assertEqual(
            bulls["2001"]["high_risk_summary"]["total_count"],
            1,
        )
        self.assertEqual(bulls["2002"]["total_cow_count"], 1)
        self.assertEqual(
            sum(bull["total_cow_count"] for bull in bulls.values()),
            3,
        )

        warning = "\n".join(captured.output)
        self.assertIn("1 条重复配对记录", warning)
        self.assertIn("1 条空或重复母牛档案", warning)
        self.assertNotIn("1001", warning)
        self.assertNotIn("2001", warning)

    def test_gene_counts_each_normalized_pair_once(self):
        with self.assertLogs(
            "core.excel_report.data_collectors."
            "candidate_bulls_genes_collector",
            level="WARNING",
        ) as captured:
            result = collect_candidate_bulls_genes_data(
                self.analysis_folder,
                self.project_folder,
            )

        bulls = self._bulls_by_id(result)
        self.assertEqual(set(bulls), {"2001", "2002"})
        self.assertEqual(bulls["2001"]["mature_cow_count"], 1)
        self.assertEqual(bulls["2001"]["heifer_count"], 1)
        self.assertEqual(bulls["2001"]["total_cow_count"], 2)
        self.assertEqual(
            bulls["2001"]["gene_summary"][0]["total_homozygous"],
            1,
        )
        self.assertEqual(
            bulls["2001"]["total_risk"]["total_homozygous"],
            1,
        )
        self.assertEqual(bulls["2002"]["total_cow_count"], 1)
        self.assertEqual(
            sum(bull["total_cow_count"] for bull in bulls.values()),
            3,
        )

        warning = "\n".join(captured.output)
        self.assertIn("1 条重复配对记录", warning)
        self.assertIn("1 条空或重复母牛档案", warning)
        self.assertNotIn("1001", warning)
        self.assertNotIn("2001", warning)


if __name__ == "__main__":
    unittest.main()
