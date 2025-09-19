"""检查选配报告的列"""

import pandas as pd
from pathlib import Path
import sys

def check_report(file_path):
    """检查报告文件的列"""
    try:
        df = pd.read_excel(file_path)

        print(f"文件: {file_path}")
        print(f"总行数: {len(df)}")
        print(f"总列数: {len(df.columns)}")

        print("\n列名列表:")
        for i, col in enumerate(df.columns, 1):
            print(f"  {i:3}. {col}")

        # 检查关键列
        print("\n关键列检查:")
        key_cols = ['常规_valid_bulls', '性控_valid_bulls',
                    '1选常规', '2选常规', '3选常规',
                    '1选性控', '2选性控', '3选性控']

        for col in key_cols:
            if col in df.columns:
                # 统计非空值
                non_empty = df[col].notna().sum()
                print(f"  ✓ {col}: 存在，{non_empty}/{len(df)} 非空")

                # 如果是valid_bulls列，显示第一个非空值的示例
                if 'valid_bulls' in col and non_empty > 0:
                    first_val = df[df[col].notna()][col].iloc[0]
                    print(f"    示例值: {str(first_val)[:100]}...")
            else:
                print(f"  ✗ {col}: 不存在")

        # 检查分组列
        if 'group' in df.columns:
            print(f"\n分组统计:")
            groups = df['group'].value_counts()
            for group, count in groups.items():
                print(f"  {group}: {count}头")

    except Exception as e:
        print(f"错误: {e}")
        return False

    return True

if __name__ == "__main__":
    # 查找最近的报告文件
    paths_to_check = [
        "analysis_results/individual_mating_report.xlsx",
        "standardized_data/individual_mating_report.xlsx",
        "*/analysis_results/individual_mating_report.xlsx",
    ]

    found = False
    for pattern in paths_to_check:
        for path in Path(".").glob(pattern):
            if path.exists():
                check_report(path)
                found = True
                break
        if found:
            break

    if not found:
        print("未找到选配报告文件")
        print("\n请先生成选配报告，然后再检查")