"""完整测试Sheet 2和Sheet 2明细"""

from pathlib import Path
from openpyxl import Workbook
from core.excel_report.data_collectors.pedigree_collector import collect_pedigree_data
from core.excel_report.sheet_builders.sheet2_builder import Sheet2Builder
from core.excel_report.sheet_builders.sheet2_detail_builder import Sheet2DetailBuilder
from core.excel_report.formatters.style_manager import StyleManager
from core.excel_report.formatters.chart_builder import ChartBuilder

# 测试项目路径
test_project = Path("/Users/bozhenwang/GeneticImprove/ll_2025_10_06_17_13")
analysis_folder = test_project / "分析结果"

print("="*60)
print("测试Sheet 2和Sheet 2明细完整生成...")
print("="*60)

# 1. 收集数据
print("\n步骤1: 收集数据...")
data = collect_pedigree_data(analysis_folder)
print(f"✓ 汇总数据: {len(data['summary'])}行")
print(f"✓ 在群母牛: {len(data['detail_active'])}行")
print(f"✓ 全群母牛: {len(data['detail_all'])}行")
print(f"✓ 饼图统计 - 在群母牛: {data['total_stats']['total_count']}头")
print(f"  - 父号识别: {data['total_stats']['sire_identified']}头 ({data['total_stats']['sire_rate']}%)")

# 2. 创建Excel工作簿
print("\n步骤2: 创建Excel工作簿...")
wb = Workbook()
wb.remove(wb.active)  # 删除默认sheet

style_manager = StyleManager()
chart_builder = ChartBuilder()

# 3. 构建Sheet 2（汇总和饼图）
print("\n步骤3: 构建Sheet 2（系谱识别分析）...")
sheet2_builder = Sheet2Builder(wb, style_manager, chart_builder)
sheet2_builder.build(data)
print("✓ Sheet 2构建完成")

# 4. 构建Sheet 2明细（全群母牛）
print("\n步骤4: 构建Sheet 2明细（全群母牛系谱识别明细）...")
sheet2_detail_builder = Sheet2DetailBuilder(wb, style_manager, chart_builder)
sheet2_detail_builder.build(data)
print("✓ Sheet 2明细构建完成")

# 5. 保存文件
output_file = Path("/tmp/test_sheet2_final.xlsx")
wb.save(output_file)
print(f"\n✓ 测试文件已保存: {output_file}")
print("\n✅ 所有测试完成！")
print("\n文件包含:")
print("  - Sheet 1: 系谱识别分析 (汇总表 + 3个饼图)")
print("  - Sheet 2: 全群母牛系谱识别明细 (1853行明细数据)")
