import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from core.breeding_calc.generate_key_traits_analysis import (
    generate_key_traits_analysis_result,
)
from core.breeding_calc.generate_pedigree_analysis import (
    generate_pedigree_analysis_result,
)
from core.breeding_calc.traits_calculation import TraitsCalculation
from core.auto_analysis_runner import _build_farm_abnormal_stats
from core.data.processor import add_farm_lineage_columns
from core.data.yqn_data_converter import YQNDataConverter
from core.excel_report.data_collectors.used_bulls_summary_collector import (
    UsedBullsSummaryCollector,
)


class FarmLineageOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = Path(self.temp_dir.name)
        (self.project_path / "analysis_results").mkdir()
        metadata = {
            "is_merged": True,
            "data_source": "伊起牛",
            "farms": [
                {"code": "1001", "name": "一牧", "cow_count": 2},
                {"code": "2002", "name": "二牧", "cow_count": 2},
            ],
        }
        (self.project_path / "project_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_farm_lineage_infers_prefix_and_keeps_text_codes(self):
        frame = pd.DataFrame(
            {
                "cow_id": ["1001123", "2002456"],
                "牧场编号": ["1001.0", ""],
                "value": [1, 2],
            }
        )

        result = add_farm_lineage_columns(
            frame, self.project_path, animal_id_column="cow_id"
        )

        self.assertEqual(result["牧场编号"].tolist(), ["1001", "2002"])
        self.assertEqual(result["牧场名称"].tolist(), ["一牧", "二牧"])
        self.assertEqual(result.columns[-2:].tolist(), ["牧场编号", "牧场名称"])

    def test_yqn_breeding_merge_preserves_farm_source(self):
        merged = YQNDataConverter.merge_breeding_records(
            [
                ("1001", {"data": {"rows": [{"earNum": "123"}]}}),
                ("2002", {"data": {"rows": [{"earNum": "456"}]}}),
            ]
        )

        self.assertEqual(
            [(row["farmCode"], row["earNum"]) for row in merged],
            [("1001", "1001123"), ("2002", "2002456")],
        )

    def test_key_traits_keeps_original_sheets_and_adds_farm_sheets(self):
        rows = []
        for farm_code, _farm_name, score_offset in [
            ("1001", "一牧", 0),
            ("2002", "二牧", 100),
        ]:
            for year in [2025, 2026]:
                rows.append(
                    {
                        "cow_id": f"{farm_code}{year}",
                        "sex": "母",
                        "是否在场": "是",
                        "birth_year": year,
                        "NM$_score": 200 + score_offset + year - 2025,
                        "TPI_score": 2200 + score_offset + year - 2025,
                    }
                )
        pd.DataFrame(rows).to_excel(
            self.project_path
            / "analysis_results"
            / "processed_cow_data_key_traits_final.xlsx",
            index=False,
        )

        self.assertTrue(generate_key_traits_analysis_result(self.project_path))
        output = (
            self.project_path / "analysis_results" / "关键育种性状分析结果.xlsx"
        )
        with pd.ExcelFile(output) as workbook:
            self.assertEqual(
                workbook.sheet_names[:6],
                [
                    "在群母牛年份汇总",
                    "全部母牛年份汇总",
                    "在群母牛NM$分布",
                    "全部母牛NM$分布",
                    "在群母牛TPI分布",
                    "全部母牛TPI分布",
                ],
            )
            self.assertIn("分牧场在群年份汇总", workbook.sheet_names)
            per_farm = pd.read_excel(workbook, sheet_name="分牧场在群年份汇总")
            totals = per_farm[per_farm["出生年份"] == "在群母牛总计"]
            self.assertEqual(totals["头数"].sum(), 4)

    def test_pedigree_adds_per_farm_summary(self):
        rows = []
        for farm_code, _farm_name in [("1001", "一牧"), ("2002", "二牧")]:
            rows.append(
                {
                    "cow_id": f"{farm_code}2026",
                    "sex": "母",
                    "breed": "荷斯坦",
                    "是否在场": "是",
                    "birth_year": 2026,
                    "sire_identified": True,
                    "mgs_identified": True,
                    "mmgs_identified": False,
                }
            )
        pd.DataFrame(rows).to_excel(
            self.project_path
            / "analysis_results"
            / "processed_cow_data_key_traits_detail.xlsx",
            index=False,
        )

        self.assertTrue(generate_pedigree_analysis_result(self.project_path))
        output = self.project_path / "analysis_results" / "系谱识别分析结果.xlsx"
        with pd.ExcelFile(output) as workbook:
            self.assertEqual(workbook.sheet_names[0], "Sheet1")
            self.assertIn("分牧场汇总", workbook.sheet_names)
            farm_summary = pd.read_excel(workbook, sheet_name="分牧场汇总")
            totals = farm_summary[
                (farm_summary["是否在场"] == "总计")
                & (farm_summary["birth_year_group"].astype(str) == "2026")
            ]
            self.assertEqual(totals["头数"].sum(), 2)

    def test_sire_yearly_farm_output_is_separate(self):
        calculation = TraitsCalculation()
        calculation.get_default_values = lambda traits: {
            trait: 0 for trait in traits
        }
        source = pd.DataFrame(
            {
                "birth_year": [2025] * 20 + [2026] * 20,
                "sire_identified": [True] * 40,
                "sire_NM$": list(range(20)) + list(range(20, 40)),
                "sire_TPI": list(range(2000, 2020)) + list(range(2020, 2040)),
                "牧场编号": ["1001"] * 20 + ["2002"] * 20,
                "牧场名称": ["一牧"] * 20 + ["二牧"] * 20,
            }
        )
        output = (
            self.project_path
            / "analysis_results"
            / "sire_traits_mean_by_cow_birth_year_by_farm.xlsx"
        )

        self.assertTrue(
            calculation.process_yearly_data_by_farm_from_df(
                source, output, ["NM$", "TPI"]
            )
        )
        with pd.ExcelFile(output) as workbook:
            self.assertEqual(workbook.sheet_names, ["NM$", "TPI"])
            nm_data = pd.read_excel(workbook, sheet_name="NM$")
            self.assertEqual(nm_data["牧场编号"].astype(str).nunique(), 2)

    def test_farm_columns_are_not_treated_as_bull_traits(self):
        collector = UsedBullsSummaryCollector(self.project_path)
        frame = pd.DataFrame(
            {
                "耳号": ["1001123"],
                "冻精编号": ["001HO00001"],
                "配种日期": [pd.Timestamp("2026-01-01")],
                "配种年份": [2026],
                "冻精类型": ["普通冻精"],
                "牧场编号": ["1001"],
                "牧场名称": ["一牧"],
                "NM$": [500],
            }
        )
        self.assertEqual(collector._identify_trait_columns(frame), ["NM$"])

    def test_bull_usage_collector_keeps_farm_columns_out_of_traits(self):
        from core.excel_report.data_collectors.bull_usage_collector import (
            collect_bull_usage_summary_data,
        )

        analysis_folder = self.project_path / "analysis_results"
        analysis_folder.mkdir(parents=True, exist_ok=True)

        breeding_df = pd.DataFrame(
            {
                "耳号": ["1001", "2001"],
                "父号": ["S1", "S2"],
                "冻精编号": ["B1", "B2"],
                "配种日期": ["2026-01-01", "2026-02-01"],
                "冻精类型": ["常规", "性控"],
                "牧场编号": ["100", "200"],
                "牧场名称": ["甲牧场", "乙牧场"],
            }
        )
        breeding_df.to_excel(
            analysis_folder / "processed_breeding_data.xlsx", index=False
        )

        traits_df = breeding_df.copy()
        traits_df["NM$"] = [500.5, 600.5]
        traits_df.to_excel(
            analysis_folder / "processed_mated_bull_traits.xlsx", index=False
        )

        result = collect_bull_usage_summary_data(analysis_folder)

        self.assertEqual(result["trait_columns"], ["NM$"])
        self.assertEqual(
            list(result["breeding_detail"].columns[:2]),
            ["牧场编号", "牧场名称"],
        )

    def test_report_detail_builders_keep_farm_columns(self):
        from openpyxl import Workbook
        from core.excel_report.sheet_builders.sheet2_detail_builder import (
            Sheet2DetailBuilder,
        )
        from core.excel_report.sheet_builders.sheet3_detail_builder import (
            Sheet3DetailBuilder,
        )
        from core.excel_report.sheet_builders.sheet4_detail_builder import (
            Sheet4DetailBuilder,
        )
        from core.excel_report.sheet_builders.sheet7_builder import Sheet7Builder

        class NoOpStyleManager:
            @staticmethod
            def apply_header_style(_cell):
                pass

            @staticmethod
            def apply_data_style(_cell, _alignment):
                pass

        frame = pd.DataFrame(
            {
                "牧场编号": ["1001"],
                "牧场名称": ["一牧"],
                "cow_id": ["1001123"],
                "是否在场": ["是"],
                "NM$_score": [500.25],
                "自定义_index": [88.5],
                "ranking": [1],
            }
        )
        breeding_frame = pd.DataFrame(
            {
                "牧场编号": ["1001"],
                "牧场名称": ["一牧"],
                "母牛号": ["1001123"],
                "配种公牛号": ["B1"],
            }
        )

        workbook = Workbook()
        workbook.remove(workbook.active)
        builders_and_data = [
            (Sheet2DetailBuilder, {"detail_all": frame}),
            (Sheet3DetailBuilder, {"detail_df": frame}),
            (Sheet4DetailBuilder, {"detail_df": frame}),
            (Sheet7Builder, {"data": breeding_frame}),
        ]
        for builder_class, data in builders_and_data:
            builder_class(
                workbook, NoOpStyleManager(), chart_builder=None
            ).build(data)

        for worksheet in workbook.worksheets:
            headers = [
                cell.value
                for cell in worksheet[1]
                if cell.value is not None
            ]
            self.assertEqual(headers[:2], ["牧场编号", "牧场名称"])

    def test_inbreeding_abnormal_stats_can_be_split_by_farm(self):
        abnormal = pd.DataFrame(
            {
                "牧场编号": ["1001", "1001", "2002"],
                "牧场名称": ["一牧", "一牧", "二牧"],
                "异常类型": ["HH1", "HH1", "近交系数过高"],
            }
        )
        result = _build_farm_abnormal_stats(abnormal)
        self.assertEqual(result["数量"].sum(), 3)
        self.assertEqual(result["牧场编号"].nunique(), 2)


if __name__ == "__main__":
    unittest.main()
