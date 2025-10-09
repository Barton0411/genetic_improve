"""
测试Sheet 1生成
"""

from pathlib import Path
import logging
import sys

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.excel_report.generator import ExcelReportGenerator


def test_sheet1():
    """测试Sheet 1生成"""
    # 使用测试项目
    test_project = Path("/Users/bozhenwang/GeneticImprove/ll_2025_10_06_17_13")

    if not test_project.exists():
        print(f"❌ 测试项目不存在: {test_project}")
        return False

    print(f"使用测试项目: {test_project}")
    print("=" * 60)

    try:
        # 创建生成器
        generator = ExcelReportGenerator(test_project)

        # 生成报告
        success, result = generator.generate()

        if success:
            print("=" * 60)
            print(f"✓ Sheet 1测试成功!")
            print(f"报告文件: {result}")
            print("=" * 60)
            return True
        else:
            print("=" * 60)
            print(f"✗ Sheet 1测试失败: {result}")
            print("=" * 60)
            return False

    except Exception as e:
        print("=" * 60)
        print(f"✗ Sheet 1测试出错: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return False


if __name__ == "__main__":
    test_sheet1()
