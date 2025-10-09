"""
测试Excel报告按钮功能
（不启动GUI，只测试导入和方法调用）
"""

from pathlib import Path
import sys

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_excel_import():
    """测试是否能正确导入Excel报告生成器"""
    try:
        from core.excel_report import ExcelReportGenerator
        print("✓ ExcelReportGenerator导入成功")
        return True
    except Exception as e:
        print(f"✗ ExcelReportGenerator导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_excel_generation():
    """测试Excel报告生成功能"""
    test_project = Path("/Users/bozhenwang/GeneticImprove/ll_2025_10_06_17_13")

    if not test_project.exists():
        print(f"✗ 测试项目不存在: {test_project}")
        return False

    try:
        from core.excel_report import ExcelReportGenerator

        # 创建分析结果文件夹
        analysis_folder = test_project / "分析结果"
        analysis_folder.mkdir(exist_ok=True)

        # 创建必需的占位文件（空文件）
        required_files = [
            "系谱识别分析结果.xlsx",
            "关键育种性状分析结果.xlsx"
        ]

        print("创建必需的占位文件...")
        for filename in required_files:
            file_path = analysis_folder / filename
            if not file_path.exists():
                # 创建空的Excel文件
                import pandas as pd
                df = pd.DataFrame()
                df.to_excel(file_path, index=False)
                print(f"  创建: {filename}")

        print("\n开始生成Excel报告...")
        generator = ExcelReportGenerator(test_project)
        success, result = generator.generate()

        if success:
            print(f"\n✓ Excel报告生成成功!")
            print(f"文件位置: {result}")
            return True
        else:
            print(f"\n✗ Excel报告生成失败: {result}")
            return False

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("测试Excel报告按钮功能")
    print("=" * 60)

    print("\n1. 测试模块导入...")
    if not test_excel_import():
        sys.exit(1)

    print("\n2. 测试Excel报告生成...")
    if not test_excel_generation():
        sys.exit(1)

    print("\n" + "=" * 60)
    print("所有测试通过! ✓")
    print("=" * 60)
