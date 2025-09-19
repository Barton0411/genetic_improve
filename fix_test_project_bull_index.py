#!/usr/bin/env python3
"""为测试项目创建公牛指数文件，确保正确识别有数据的公牛"""

import pandas as pd
from pathlib import Path

# 测试项目路径
test_project = Path('/Users/bozhenwang/projects/mating/genetic_improve/genetic_projects/测试项目')
analysis_dir = test_project / 'analysis_results'
analysis_dir.mkdir(exist_ok=True)

# 读取公牛数据
bull_file = test_project / 'standardized_data' / 'processed_bull_data.xlsx'
if bull_file.exists():
    bull_df = pd.read_excel(bull_file)

    # 创建公牛指数数据
    index_data = []
    for _, row in bull_df.iterrows():
        bull_id = row['bull_id']

        # 为前8头公牛（原始数据）添加指数
        if not bull_id.startswith('REG_NO_DATA') and not bull_id.startswith('SEX_NO_DATA'):
            index_data.append({
                'bull_id': bull_id,
                'semen_type': row.get('semen_type', ''),
                'classification': row.get('classification', ''),
                '支数': row.get('支数', 0),
                'NM$': 500 + len(bull_id) * 10,  # 模拟数据
                'NM$权重_index': 300 + len(bull_id) * 20,  # 模拟数据
                'ranking': len(index_data) + 1
            })

    # 如果没有找到有效的公牛，添加示例数据
    if not index_data:
        print("警告：没有找到有效的公牛数据，添加示例数据")
        index_data = [
            {'bull_id': '151HO04984', 'classification': '常规', '支数': 200, 'NM$权重_index': 757.0, 'ranking': 1},
            {'bull_id': '011HO11963', 'classification': '常规', '支数': 200, 'NM$权重_index': 222.0, 'ranking': 2},
            {'bull_id': '551HO04669', 'classification': '性控', '支数': 200, 'NM$权重_index': 725.0, 'ranking': 3},
            {'bull_id': '511HO12206', 'classification': '性控', '支数': 200, 'NM$权重_index': 278.0, 'ranking': 4},
        ]

    # 创建并保存文件
    index_df = pd.DataFrame(index_data)
    output_file = analysis_dir / 'processed_index_bull_scores.xlsx'
    index_df.to_excel(output_file, index=False)

    print(f"✓ 已创建公牛指数文件: {output_file}")
    print(f"\n包含 {len(index_df)} 头公牛的指数数据:")
    print(index_df[['bull_id', 'classification', '支数', 'NM$权重_index']].to_string())
else:
    print(f"错误：未找到公牛数据文件 {bull_file}")