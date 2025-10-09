"""
测试Sheet 1 v2（包含所有修改）
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

from core.excel_report.data_collectors import collect_farm_info
from core.excel_report.sheet_builders import Sheet1Builder, Sheet1ABuilder
from core.excel_report.formatters import StyleManager, ChartBuilder


def test_sheet1_v2():
    """测试Sheet 1 v2版本"""
    # 使用测试项目
    test_project = Path("/Users/bozhenwang/GeneticImprove/ll_2025_10_06_17_13")

    if not test_project.exists():
        print(f"❌ 测试项目不存在: {test_project}")
        return False

    print(f"使用测试项目: {test_project}")
    print("=" * 60)

    try:
        # 1. 收集Sheet 1数据（带服务人员信息）
        print("Step 1: 收集牧场基础信息数据...")
        service_staff = "10086 测试员"  # 模拟工号和姓名
        farm_data = collect_farm_info(test_project, service_staff)

        print(f"✓ 数据收集完成")
        print(f"  - 牧场名称: {farm_data['basic_info'].get('farm_name')}")
        print(f"  - 服务人员: {farm_data['basic_info'].get('service_staff')}")
        print(f"  - 在场母牛: {farm_data['herd_structure'].get('total_count')}头")
        print(f"  - 成母牛: {farm_data['herd_structure'].get('lactating_count')}头")
        print(f"  - 后备牛: {farm_data['herd_structure'].get('heifer_count')}头")
        print(f"  - 平均胎次: {farm_data['herd_structure'].get('avg_lactation')}")
        print(f"  - 平均泌乳天数: {farm_data['herd_structure'].get('avg_dim')}天")
        print(f"  - 母牛数据详情: {farm_data['upload_summary'].get('cow_data_detail', 'N/A')}")

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
        builder1 = Sheet1Builder(wb, style_manager, chart_builder)
        builder1.build(farm_data)
        print("✓ Sheet 1构建完成")

        # 5. 构建Sheet 1A（牧场牛群原始数据）
        print("\nStep 5: 构建Sheet 1A...")
        builder1a = Sheet1ABuilder(wb, style_manager, chart_builder)
        builder1a.build({
            'raw_file_path': farm_data.get('raw_cow_data')
        })
        print("✓ Sheet 1A构建完成")

        # 6. 保存文件
        print("\nStep 6: 保存Excel文件...")
        output_folder = test_project / "分析结果"
        output_folder.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"测试_Sheet1_v2_{timestamp}.xlsx"
        output_path = output_folder / filename

        wb.save(output_path)
        print(f"✓ Excel文件已保存: {output_path}")

        print("=" * 60)
        print(f"✓ Sheet 1 v2测试成功!")
        print(f"\n请查看文件确认以下修改:")
        print("  1. ✓ Sheet 1A: 直接复制原始Excel文件")
        print("  2. ✓ Sheet 1: 纵向布局（表 -> 饼图 -> 柱状图）")
        print("  3. ✓ 饼图: 3D饼图，更大更美观")
        print("  4. ✓ 柱状图: 3D柱状图，更大更美观")
        print("  5. ✓ 上传数据统计: 正确显示备选公牛、体型外貌、基因组数据数量")
        print("  6. ✓ 图表无重叠，垂直排列")
        print("=" * 60)
        return True

    except Exception as e:
        print("=" * 60)
        print(f"✗ Sheet 1 v2测试出错: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return False


if __name__ == "__main__":
    test_sheet1_v2()
