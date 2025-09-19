"""测试分配逻辑"""

import pandas as pd
import numpy as np
from pathlib import Path
from core.matching.cycle_based_matcher import CycleBasedMatcher
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)

def create_test_data():
    """创建测试数据"""
    # 创建测试母牛数据
    cows = []
    for i in range(10):
        cow = {
            'cow_id': f'cow_{i:03d}',
            'group': '第1周期（后备牛）',
            'Combine Index Score': 100 + i * 10,
            # 创建有效公牛列表
            '常规_valid_bulls': str([
                {'bull_id': f'bull_regular_{j:02d}',
                 'inbreeding_coeff': 2.0,
                 'gene_status': '安全'}
                for j in range(3)
            ]),
            '性控_valid_bulls': str([
                {'bull_id': f'bull_sexed_{j:02d}',
                 'inbreeding_coeff': 2.0,
                 'gene_status': '安全'}
                for j in range(3)
            ])
        }
        cows.append(cow)

    recommendations_df = pd.DataFrame(cows)

    # 创建公牛数据
    bulls = []
    # 常规公牛
    for i in range(3):
        bulls.append({
            'bull_id': f'bull_regular_{i:02d}',
            'classification': '常规',
            '支数': 10 + i * 5,  # 10, 15, 20
            'Bull Index Score': 200 + i * 10
        })
    # 性控公牛
    for i in range(3):
        bulls.append({
            'bull_id': f'bull_sexed_{i:02d}',
            'classification': '性控',
            '支数': 5 + i * 3,  # 5, 8, 11
            'Bull Index Score': 250 + i * 10
        })

    bull_df = pd.DataFrame(bulls)

    return recommendations_df, bull_df

def test_allocation():
    """测试分配"""
    print("=" * 60)
    print("测试选配分配逻辑")
    print("=" * 60)

    # 创建测试数据
    recommendations_df, bull_df = create_test_data()

    print("\n测试数据:")
    print(f"- 母牛数: {len(recommendations_df)}")
    print(f"- 公牛数: {len(bull_df)}")
    print("\n公牛库存:")
    for _, bull in bull_df.iterrows():
        print(f"  {bull['bull_id']}: {bull['classification']} - {bull['支数']}支")

    # 创建matcher
    matcher = CycleBasedMatcher()

    # 加载数据（模拟）
    matcher.recommendations_df = recommendations_df
    matcher.bull_data = bull_df

    # 初始化库存
    matcher.bull_inventory = {}
    for _, bull in bull_df.iterrows():
        matcher.bull_inventory[str(bull['bull_id'])] = int(bull['支数'])

    # 初始化公牛得分
    matcher.bull_scores = {}
    for _, bull in bull_df.iterrows():
        matcher.bull_scores[str(bull['bull_id'])] = bull['Bull Index Score']

    print("\n开始分配测试...")
    print("-" * 40)

    # 执行分配
    selected_groups = ['第1周期（后备牛）']
    result = matcher.perform_allocation(selected_groups)

    if not result.empty:
        print(f"\n分配结果: 共分配 {len(result)} 头母牛")

        # 统计各列的分配情况
        allocation_cols = ['1选常规', '2选常规', '3选常规', '1选性控', '2选性控', '3选性控']

        print("\n各选择的分配统计:")
        for col in allocation_cols:
            if col in result.columns:
                non_empty = result[col].notna().sum()
                print(f"  {col}: {non_empty}/{len(result)} 已分配")

                # 统计每头公牛的分配数量
                if non_empty > 0:
                    value_counts = result[col].value_counts()
                    for bull_id, count in value_counts.items():
                        print(f"    - {bull_id}: {count}头")

        # 获取分配汇总
        summary = matcher.get_allocation_summary()
        print("\n分配汇总:")
        print(summary.to_string())

        # 保存结果用于检查
        output_file = Path("test_allocation_result.xlsx")
        result.to_excel(output_file, index=False)
        print(f"\n结果已保存至: {output_file}")
    else:
        print("分配失败：无结果")

if __name__ == "__main__":
    test_allocation()