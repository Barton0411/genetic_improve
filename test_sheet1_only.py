"""
测试Sheet 1独立生成（不需要其他分析文件）
"""

from pathlib import Path
import logging
import sys
from openpyxl import Workbook

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.excel_report.data_collectors import collect_farm_info
from core.excel_report.sheet_builders import Sheet1Builder
from core.excel_report.formatters import StyleManager, ChartBuilder
from datetime import datetime


def test_sheet1_only():
    """测试Sheet 1独立生成"""
    # 使用测试项目
    test_project = Path("/Users/bozhenwang/GeneticImprove/ll_2025_10_06_17_13")

    if not test_project.exists():
        print(f"❌ 测试项目不存在: {test_project}")
        return False

    print(f"使用测试项目: {test_project}")
    print("=" * 60)

    try:
        # 1. 收集Sheet 1数据
        print("Step 1: 收集牧场基础信息数据...")
        farm_data = collect_farm_info(test_project)
        print(f"✓ 数据收集完成")
        print(f"  - 牧场名称: {farm_data['basic_info'].get('farm_name')}")
        print(f"  - 在场母牛: {farm_data['herd_structure'].get('total_count')}头")
        print(f"  - 成母牛: {farm_data['herd_structure'].get('lactating_count')}头")
        print(f"  - 后备牛: {farm_data['herd_structure'].get('heifer_count')}头")
        print(f"  - 平均胎次: {farm_data['herd_structure'].get('avg_lactation')}")

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

        # 4. 构建Sheet 1
        print("\nStep 4: 构建Sheet 1...")
        builder = Sheet1Builder(wb, style_manager, chart_builder)
        builder.build(farm_data)
        print("✓ Sheet 1构建完成")

        # 5. 保存文件
        print("\nStep 5: 保存Excel文件...")
        output_folder = test_project / "分析结果"
        output_folder.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"测试_Sheet1_{timestamp}.xlsx"
        output_path = output_folder / filename

        wb.save(output_path)
        print(f"✓ Excel文件已保存: {output_path}")

        print("=" * 60)
        print(f"✓ Sheet 1测试成功!")
        print(f"请查看文件: {output_path}")
        print("=" * 60)
        return True

    except Exception as e:
        print("=" * 60)
        print(f"✗ Sheet 1测试出错: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return False


if __name__ == "__main__":
    test_sheet1_only()
