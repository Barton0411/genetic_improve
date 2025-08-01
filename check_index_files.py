"""
检查公牛和母牛指数计算结果文件
"""

import pandas as pd
from pathlib import Path

# 项目路径
project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")

# 1. 检查公牛指数文件
print("=== 公牛指数文件 (processed_index_bull_scores.xlsx) ===\n")
bull_file = project_path / "analysis_results" / "processed_index_bull_scores.xlsx"
if bull_file.exists():
    bull_df = pd.read_excel(bull_file)
    print(f"数据形状: {bull_df.shape}")
    print(f"\n列名: {bull_df.columns.tolist()}")
    
    # 显示前3行
    print(f"\n前3行数据:")
    print(bull_df.head(3).to_string())
    
    # 查找包含 index 或 score 的列
    index_cols = [col for col in bull_df.columns if 'index' in col.lower() or 'score' in col.lower()]
    print(f"\n可能的得分列: {index_cols}")
else:
    print("文件不存在")

# 2. 检查母牛指数文件
print("\n\n=== 母牛指数文件 (processed_index_cow_index_scores.xlsx) ===\n")
cow_file = project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
if cow_file.exists():
    cow_df = pd.read_excel(cow_file)
    print(f"数据形状: {cow_df.shape}")
    print(f"\n列名 (前20个): {cow_df.columns.tolist()[:20]}")
    
    # 显示前3行部分列
    print(f"\n前3行数据 (部分列):")
    display_cols = ['cow_id', 'breed', 'group'] + [col for col in cow_df.columns if 'index' in col.lower()][:5]
    display_cols = [col for col in display_cols if col in cow_df.columns]
    print(cow_df[display_cols].head(3).to_string())
    
    # 查找包含 index 或 score 的列
    index_cols = [col for col in cow_df.columns if 'index' in col.lower() or 'score' in col.lower()]
    print(f"\n可能的得分列: {index_cols}")
else:
    print("文件不存在")