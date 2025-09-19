#!/usr/bin/env python3
"""模拟有缺失育种数据的公牛场景"""

import pandas as pd
import numpy as np
from pathlib import Path

# 测试项目路径
project_path = Path('/Users/bozhenwang/projects/mating/genetic_improve/genetic_projects/测试项目')
bull_file = project_path / "standardized_data" / "processed_bull_data.xlsx"

# 确保文件存在
if bull_file.exists():
    # 读取现有数据
    df = pd.read_excel(bull_file)
    print(f"当前公牛数量: {len(df)}")

    # 添加一些新的公牛（模拟有库存但缺少数据的公牛）
    new_bulls = []

    # 添加5个常规冻精公牛（有库存但会缺少育种数据）
    for i in range(1, 6):
        new_bulls.append({
            'bull_id': f'REG_NO_DATA_{i:03d}',
            'semen_type': '常规冻精',
            'classification': '常规',
            '支数': np.random.randint(30, 100)
        })

    # 添加3个性控冻精公牛（有库存但会缺少育种数据）
    for i in range(1, 4):
        new_bulls.append({
            'bull_id': f'SEX_NO_DATA_{i:03d}',
            'semen_type': '性控冻精',
            'classification': '性控',
            '支数': np.random.randint(10, 50)
        })

    # 合并数据
    if new_bulls:
        new_df = pd.DataFrame(new_bulls)
        df = pd.concat([df, new_df], ignore_index=True)

        # 保存更新后的文件
        df.to_excel(bull_file, index=False)
        print(f"\n✓ 已添加 {len(new_bulls)} 头缺少育种数据的公牛")
        print("\n添加的公牛（这些公牛有库存但会缺少育种数据）:")
        for bull in new_bulls:
            print(f"  {bull['bull_id']}: {bull['classification']}冻精, 库存 {bull['支数']} 支")

        print(f"\n更新后总公牛数: {len(df)}")
else:
    print(f"错误: 文件不存在 - {bull_file}")