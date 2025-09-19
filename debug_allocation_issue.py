"""调试分配问题"""

import pandas as pd
from pathlib import Path
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_allocation():
    """调试为什么常规冻精没有分配"""

    # 假设我们有一个测试项目
    # 首先检查是否有推荐报告
    possible_paths = [
        "analysis_results/individual_mating_report.xlsx",
        "standardized_data/individual_mating_report.xlsx",
        "test_project/analysis_results/individual_mating_report.xlsx",
    ]

    report_file = None
    for path in possible_paths:
        p = Path(path)
        if p.exists():
            report_file = p
            break

    if not report_file:
        print("未找到推荐报告文件")
        print("\n让我们创建一个简单的测试来追踪问题...")

        # 创建测试数据
        from core.matching.cycle_based_matcher import CycleBasedMatcher

        # 创建简单的测试数据
        test_recommendations = pd.DataFrame([
            {
                'cow_id': 'cow_001',
                'group': '第1周期（后备牛）',
                'Combine Index Score': 100,
                # 关键：添加 常规_valid_bulls 列
                '常规_valid_bulls': str([
                    {'bull_id': 'bull_reg_01', 'inbreeding_coeff': 2.0},
                    {'bull_id': 'bull_reg_02', 'inbreeding_coeff': 2.5}
                ]),
                '性控_valid_bulls': str([
                    {'bull_id': 'bull_sex_01', 'inbreeding_coeff': 2.0},
                    {'bull_id': 'bull_sex_02', 'inbreeding_coeff': 2.5}
                ])
            }
        ])

        print("\n测试数据列：")
        print(test_recommendations.columns.tolist())

        # 检查关键列
        print("\n检查关键列是否存在：")
        print(f"'常规_valid_bulls' 列存在: {'常规_valid_bulls' in test_recommendations.columns}")
        print(f"'性控_valid_bulls' 列存在: {'性控_valid_bulls' in test_recommendations.columns}")

        if '常规_valid_bulls' in test_recommendations.columns:
            val = test_recommendations['常规_valid_bulls'].iloc[0]
            print(f"\n常规_valid_bulls 的值: {val}")
            print(f"类型: {type(val)}")

            # 尝试解析
            import ast
            try:
                parsed = ast.literal_eval(val)
                print(f"解析后: {parsed}")
                print(f"包含 {len(parsed)} 头公牛")
            except:
                print("解析失败")
    else:
        # 分析实际报告
        print(f"找到报告文件: {report_file}")
        df = pd.read_excel(report_file)

        print(f"\n报告统计:")
        print(f"总行数: {len(df)}")
        print(f"总列数: {len(df.columns)}")

        print("\n列名列表:")
        for col in df.columns:
            print(f"  - {col}")

        print("\n检查关键列:")
        for col in ['常规_valid_bulls', '性控_valid_bulls']:
            if col in df.columns:
                non_empty = df[col].notna().sum()
                print(f"  ✓ {col}: 存在，{non_empty}/{len(df)} 非空")

                if non_empty > 0:
                    # 找第一个非空值
                    first_val = df[df[col].notna()][col].iloc[0]
                    print(f"    第一个值: {str(first_val)[:200]}...")
                    print(f"    类型: {type(first_val)}")
            else:
                print(f"  ✗ {col}: 不存在！")

        # 检查分配结果列
        print("\n检查分配结果列:")
        result_cols = ['1选常规', '2选常规', '3选常规', '1选性控', '2选性控', '3选性控']
        for col in result_cols:
            if col in df.columns:
                non_empty = df[col].notna().sum()
                print(f"  {col}: {non_empty}/{len(df)} 已分配")
            else:
                print(f"  {col}: 列不存在")

if __name__ == "__main__":
    debug_allocation()