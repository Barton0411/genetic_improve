"""
测试Sheet 2: 系谱识别分析
"""

from pathlib import Path
import logging
import sys
from openpyxl import Workbook
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.excel_report.data_collectors import collect_pedigree_data
from core.excel_report.sheet_builders import Sheet2Builder
from core.excel_report.formatters import StyleManager, ChartBuilder


def test_sheet2():
    """测试Sheet 2生成"""
    # 使用测试项目
    test_project = Path("/Users/bozhenwang/GeneticImprove/测试3_2025_07_30_16_21")
    analysis_folder = test_project / "analysis_results"

    if not analysis_folder.exists():
        print(f"❌ 测试项目不存在: {test_project}")
        return False

    print(f"使用测试项目: {test_project}")
    print("=" * 60)

    try:
        # 1. 收集Sheet 2数据
        print("Step 1: 收集系谱识别分析数据...")
        pedigree_data = collect_pedigree_data(analysis_folder)

        print(f"✓ 数据收集完成")
        print(f"  - 汇总数据行数: {len(pedigree_data.get('summary', []))}行")
        print(f"  - 明细数据行数: {len(pedigree_data.get('detail', []))}行")
        print(f"  - 总头数: {pedigree_data.get('total_stats', {}).get('total_count', 0)}头")
        print(f"  - 父号识别率: {pedigree_data.get('total_stats', {}).get('sire_rate', 0)}%")
        print(f"  - 外祖父识别率: {pedigree_data.get('total_stats', {}).get('mgs_rate', 0)}%")
        print(f"  - 外曾外祖父识别率: {pedigree_data.get('total_stats', {}).get('mggs_rate', 0)}%")

        # 2. 创建Excel workbook
        print("\nStep 2: 创建Excel工作簿...")
        wb = Workbook()
        wb.remove(wb.active)  # 删除默认sheet
        print("✓ 工作簿创建完成")

        # 3. 初始化样式和图表构建器
        print("\nStep 3: 初始化样式管理器...")
        style_manager = StyleManager()
        chart_builder = ChartBuilder()
        print("✓ 样式管理器初始化完成")

        # 4. 构建Sheet 2
        print("\nStep 4: 构建Sheet 2...")
        builder2 = Sheet2Builder(wb, style_manager, chart_builder)
        builder2.build(pedigree_data)
        print("✓ Sheet 2构建完成")

        # 5. 保存文件
        print("\nStep 5: 保存Excel文件...")
        output_folder = test_project / "analysis_results"
        output_folder.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"测试_Sheet2_{timestamp}.xlsx"
        output_path = output_folder / filename

        wb.save(output_path)
        print(f"✓ Excel文件已保存: {output_path}")

        print("=" * 60)
        print(f"✓ Sheet 2测试成功!")
        print(f"\n请查看文件确认以下内容:")
        print("  1. ✓ 汇总表（按出生年份）")
        print("  2. ✓ 3个饼图（父号/外祖父/外曾外祖父识别情况）")
        print("  3. ✓ 明细表")
        print("  4. ✓ 识别率<80%标红")
        print("  5. ✓ 合计行加粗浅蓝色背景")
        print("=" * 60)
        return True

    except Exception as e:
        print("=" * 60)
        print(f"✗ Sheet 2测试出错: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return False


if __name__ == "__main__":
    test_sheet2()
