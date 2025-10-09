"""完整测试Sheet 2生成"""

from pathlib import Path
from openpyxl import Workbook
from core.excel_report.data_collectors.pedigree_collector import collect_pedigree_data
from core.excel_report.sheet_builders.sheet2_builder import Sheet2Builder
from core.excel_report.formatters.style_manager import StyleManager
from core.excel_report.formatters.chart_builder import ChartBuilder

# 测试项目路径
test_project = Path("/Users/bozhenwang/GeneticImprove/ll_2025_10_06_17_13")
analysis_folder = test_project / "分析结果"

print("="*60)
print("测试Sheet 2完整生成...")
print("="*60)

# 1. 收集数据
print("\n步骤1: 收集数据...")
data = collect_pedigree_data(analysis_folder)
print(f"✓ 汇总数据: {len(data['summary'])}行")
print(f"✓ 在群母牛明细: {len(data['detail_active'])}行")
print(f"✓ 全群母牛明细: {len(data['detail_all'])}行")
print(f"✓ 饼图统计 - 在群母牛: {data['total_stats']['total_count']}头")
print(f"  - 父号识别: {data['total_stats']['sire_identified']}头 ({data['total_stats']['sire_rate']}%)")
print(f"  - 外祖父识别: {data['total_stats']['mgs_identified']}头 ({data['total_stats']['mgs_rate']}%)")

# 2. 创建Excel工作簿
print("\n步骤2: 创建Excel工作簿...")
wb = Workbook()
wb.remove(wb.active)  # 删除默认sheet

# 3. 构建Sheet 2
print("\n步骤3: 构建Sheet 2...")
style_manager = StyleManager()
chart_builder = ChartBuilder()
builder = Sheet2Builder(wb, style_manager, chart_builder)
builder.build(data)
print("✓ Sheet 2构建完成")

# 4. 保存文件
output_file = Path("/tmp/test_sheet2_output.xlsx")
wb.save(output_file)
print(f"\n✓ 测试文件已保存: {output_file}")
print("\n请打开文件检查:")
print("  1. 标题是否包含'（在群母牛）'")
print("  2. 饼图数据是否正确（父号识别: 602/665 = 90.5%）")
print("  3. 饼图大小是否为7.5×7.5cm")
print("  4. 是否有两个明细表：在群母牛(665行) 和 全群母牛(1853行)")
