#!/usr/bin/env python3
"""创建公牛指数文件 processed_index_bull_scores.xlsx"""

import pandas as pd
import numpy as np
from pathlib import Path

# 项目路径
project_path = Path('/Users/bozhenwang/projects/mating/genetic_improve/genetic_projects/测试项目')
analysis_results_dir = project_path / "analysis_results"

# 创建目录（如果不存在）
analysis_results_dir.mkdir(exist_ok=True)

# 读取现有的公牛数据
bull_file = project_path / "standardized_data" / "processed_bull_data.xlsx"
bull_df = pd.read_excel(bull_file)

# 创建公牛指数数据
bull_index_data = []

# 为现有的8头公牛添加指数数据
for _, row in bull_df.head(8).iterrows():
    bull_id = row['bull_id']
    # 模拟指数数据
    bull_index_data.append({
        'bull_id': bull_id,
        'breeding_index': np.random.randint(2500, 3500),
        'milk_index': np.random.randint(500, 1500),
        'protein_index': np.random.randint(30, 60),
        'fat_index': np.random.randint(30, 60),
        'Index Score': np.random.randint(2800, 3200)  # 总指数
    })

# 添加您提到的4头公牛（如果它们不在原始数据中）
specific_bulls = ['151HO04984', '011HO11963', '551HO04669', '511HO12206']
existing_bulls = set(bull_df['bull_id'])

for bull_id in specific_bulls:
    if bull_id not in existing_bulls:
        bull_index_data.append({
            'bull_id': bull_id,
            'breeding_index': np.random.randint(2800, 3300),
            'milk_index': np.random.randint(800, 1300),
            'protein_index': np.random.randint(35, 55),
            'fat_index': np.random.randint(35, 55),
            'Index Score': np.random.randint(2900, 3100)
        })

# 创建DataFrame并保存
index_df = pd.DataFrame(bull_index_data)
output_file = analysis_results_dir / "processed_index_bull_scores.xlsx"
index_df.to_excel(output_file, index=False)

print(f"✓ 已创建公牛指数文件: {output_file}")
print(f"\n文件包含 {len(index_df)} 头公牛的指数数据：")
print(index_df[['bull_id', 'Index Score']].to_string())

# 验证特定的公牛
print(f"\n您提到的4头公牛状态：")
for bull_id in specific_bulls:
    if bull_id in index_df['bull_id'].values:
        score = index_df[index_df['bull_id'] == bull_id]['Index Score'].values[0]
        print(f"  {bull_id}: Index Score = {score}")
    else:
        print(f"  {bull_id}: 未包含在文件中")