"""
测试灵活的指数列识别
"""

import pandas as pd
from pathlib import Path

# 检查母牛数据中的列
project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")
cow_file = project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"

if cow_file.exists():
    cow_df = pd.read_excel(cow_file)
    
    print("=== 母牛数据列分析 ===\n")
    print(f"总列数: {len(cow_df.columns)}")
    
    # 查找包含 index 的列
    index_cols = [col for col in cow_df.columns if '_index' in col.lower() or 'index' in col.lower()]
    print(f"\n包含 'index' 的列: {index_cols}")
    
    # 应用过滤规则
    excluded_keywords = ['date', 'time', 'id', 'name', 'type']
    score_cols = [col for col in index_cols if not any(
        exclude in col.lower() for exclude in excluded_keywords
    )]
    
    print(f"\n过滤后的得分列: {score_cols}")
    
    # 显示这些列的数据类型和示例值
    print("\n得分列详情:")
    for col in score_cols:
        dtype = cow_df[col].dtype
        non_null_count = cow_df[col].notna().sum()
        sample_values = cow_df[col].dropna().head(3).tolist() if non_null_count > 0 else []
        print(f"  {col}:")
        print(f"    - 数据类型: {dtype}")
        print(f"    - 非空值数量: {non_null_count}/{len(cow_df)}")
        print(f"    - 示例值: {sample_values}")