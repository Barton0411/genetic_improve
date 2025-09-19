#!/usr/bin/env python3
"""修复公牛数据文件，添加缺失的库存和分类信息"""

import pandas as pd
import numpy as np
from pathlib import Path

# 找到测试项目的公牛数据文件
bull_file = Path('/Users/bozhenwang/projects/mating/genetic_improve/genetic_projects/测试项目/standardized_data/processed_bull_data.xlsx')

if bull_file.exists():
    # 读取现有数据
    df = pd.read_excel(bull_file)
    print(f"读取公牛数据文件: {bull_file}")
    print(f"原始列: {df.columns.tolist()}")
    print(f"公牛数量: {len(df)}")

    # 添加缺失的列
    if 'classification' not in df.columns:
        # 基于 semen_type 自动分类
        df['classification'] = ''
        for idx, row in df.iterrows():
            semen_type = str(row.get('semen_type', '')).strip()
            if '常规' in semen_type:
                df.at[idx, 'classification'] = '常规'
            elif '性控' in semen_type:
                df.at[idx, 'classification'] = '性控'
            else:
                # 随机分配（模拟数据）
                df.at[idx, 'classification'] = np.random.choice(['常规', '性控'], p=[0.6, 0.4])
        print("✓ 添加了 classification 列")

    if '支数' not in df.columns:
        # 添加库存支数（模拟数据）
        # 常规冻精库存多，性控冻精库存少
        df['支数'] = 0
        for idx, row in df.iterrows():
            if row['classification'] == '常规':
                # 常规冻精: 50-200支
                df.at[idx, '支数'] = np.random.randint(50, 201)
            else:
                # 性控冻精: 20-100支
                df.at[idx, '支数'] = np.random.randint(20, 101)
        print("✓ 添加了 支数 列")

    # 保存更新后的文件
    df.to_excel(bull_file, index=False)
    print(f"\n✓ 已保存更新后的文件: {bull_file}")

    # 显示统计信息
    print("\n=== 更新后的统计信息 ===")
    print(f"总公牛数: {len(df)}")

    if 'classification' in df.columns:
        print("\n分类统计:")
        for cls in df['classification'].unique():
            count = len(df[df['classification'] == cls])
            print(f"  {cls}: {count} 头")

    if '支数' in df.columns:
        print("\n库存统计:")
        for cls in df['classification'].unique():
            subset = df[df['classification'] == cls]
            total_inventory = subset['支数'].sum()
            avg_inventory = subset['支数'].mean()
            print(f"  {cls}: 总库存 {total_inventory} 支, 平均 {avg_inventory:.1f} 支/头")

        print(f"\n有库存的公牛: {len(df[df['支数'] > 0])} 头")
        print(f"无库存的公牛: {len(df[df['支数'] == 0])} 头")
else:
    print(f"错误: 文件不存在 - {bull_file}")