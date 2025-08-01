"""
调试矩阵生成器的数据问题
"""

import pandas as pd
from pathlib import Path

# 项目路径
project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")

# 1. 检查母牛数据
print("=== 检查母牛数据 ===")
cow_file = project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
cow_df = pd.read_excel(cow_file)
print(f"母牛数据列: {cow_df.columns.tolist()}")
print(f"\n前3头母牛的得分:")
for col in ['Combine Index Score', 'Index Score', 'index_score']:
    if col in cow_df.columns:
        print(f"{col}: {cow_df[col].head(3).tolist()}")

# 2. 检查公牛数据
print("\n=== 检查公牛数据 ===")
bull_file = project_path / "standardized_data" / "processed_bull_data.xlsx"
bull_df = pd.read_excel(bull_file)
print(f"公牛数据列: {bull_df.columns.tolist()}")
print(f"\n公牛信息:")
print(bull_df[['bull_id', 'classification']].to_string())

# 检查公牛得分列
for col in ['Index Score', 'index_score', 'TPI', 'NM$']:
    if col in bull_df.columns:
        print(f"\n{col}: {bull_df[col].tolist()}")

# 3. 检查近交系数数据
print("\n=== 检查近交系数数据 ===")
inbreeding_files = list(project_path.glob("**/备选公牛_近交系数及隐性基因分析结果_*.xlsx"))
if inbreeding_files:
    latest_file = max(inbreeding_files, key=lambda x: x.stat().st_mtime)
    print(f"使用文件: {latest_file.name}")
    inbreeding_df = pd.read_excel(latest_file)
    print(f"数据形状: {inbreeding_df.shape}")
    print(f"列名: {inbreeding_df.columns.tolist()[:10]}...")
    
    # 检查近交系数值
    for col in ['近交系数', '后代近交系数']:
        if col in inbreeding_df.columns:
            non_zero = inbreeding_df[inbreeding_df[col] != 0]
            print(f"\n{col} 非零值数量: {len(non_zero)}")
            if len(non_zero) > 0:
                print(f"示例: {non_zero[col].head(3).tolist()}")