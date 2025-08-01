#!/usr/bin/env python3
"""
测试个体选配逻辑
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import sys

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def create_test_data():
    """创建测试数据"""
    print("=== 创建测试数据 ===\n")
    
    # 当前日期
    today = datetime.now()
    
    # 创建测试母牛数据
    cow_data = []
    
    # 1. 后备牛 - 不同周期
    for i in range(40):
        # 让日龄均匀分布在各个周期
        cycle = (i % 4) + 1
        if cycle == 1:
            age_days = 410  # 第1周期: 399-420
        elif cycle == 2:
            age_days = 389  # 第2周期: 378-399
        elif cycle == 3:
            age_days = 368  # 第3周期: 357-378
        else:
            age_days = 347  # 第4周期: 336-357
            
        cow_data.append({
            'cow_id': f'H{i+1:03d}',
            'breed': '荷斯坦',
            'sex': '母',
            'lac': 0,  # 后备牛
            'birth_date': today - timedelta(days=age_days),
            'calving_date': None,
            'DIM': None,
            'repro_status': '空怀',
            'services_time': i % 4,  # 0-3次配种
            'ranking': i + 1,
            '是否在场': '是'
        })
    
    # 2. 后备牛 - 已孕
    for i in range(5):
        cow_data.append({
            'cow_id': f'HP{i+1:03d}',
            'breed': '荷斯坦',
            'sex': '母',
            'lac': 0,
            'birth_date': today - timedelta(days=450),
            'calving_date': None,
            'DIM': None,
            'repro_status': '初检孕',
            'services_time': 2,
            'ranking': 50 + i,
            '是否在场': '是'
        })
    
    # 3. 后备牛 - 难孕
    for i in range(5):
        cow_data.append({
            'cow_id': f'HD{i+1:03d}',
            'breed': '荷斯坦',
            'sex': '母',
            'lac': 0,
            'birth_date': today - timedelta(days=600),  # 超过18个月
            'calving_date': None,
            'DIM': None,
            'repro_status': '空怀',
            'services_time': 5,
            'ranking': 60 + i,
            '是否在场': '是'
        })
    
    # 4. 成母牛 - 未孕
    for i in range(20):
        cow_data.append({
            'cow_id': f'M{i+1:03d}',
            'breed': '荷斯坦',
            'sex': '母',
            'lac': 2,
            'birth_date': today - timedelta(days=1000),
            'calving_date': today - timedelta(days=100),
            'DIM': 100,
            'repro_status': '空怀',
            'services_time': i % 3,
            'ranking': 70 + i,
            '是否在场': '是'
        })
    
    # 5. 成母牛 - 难孕
    for i in range(5):
        cow_data.append({
            'cow_id': f'MD{i+1:03d}',
            'breed': '荷斯坦',
            'sex': '母',
            'lac': 3,
            'birth_date': today - timedelta(days=1200),
            'calving_date': today - timedelta(days=200),  # DIM > 150
            'DIM': 200,
            'repro_status': '空怀',
            'services_time': 4,
            'ranking': 90 + i,
            '是否在场': '是'
        })
    
    cow_df = pd.DataFrame(cow_data)
    
    # 创建测试公牛数据
    bull_data = []
    
    # 性控公牛
    for i in range(3):
        bull_data.append({
            'bull_id': f'S{i+1:03d}',
            'classification': '性控',
            'semen_type': '性控',
            '支数': 100 * (i + 1),  # 100, 200, 300
            'Index Score': 3000 - i * 100
        })
    
    # 常规公牛
    for i in range(5):
        bull_data.append({
            'bull_id': f'R{i+1:03d}',
            'classification': '常规',
            'semen_type': '常规',
            '支数': 50 * (i + 1),  # 50, 100, 150, 200, 250
            'Index Score': 2800 - i * 50
        })
    
    bull_df = pd.DataFrame(bull_data)
    
    return cow_df, bull_df


def test_grouping_logic(cow_df):
    """测试分组逻辑"""
    print("\n=== 测试分组逻辑 ===\n")
    
    # 模拟分组过程
    today = datetime.now()
    
    # 初始化group列
    cow_df['group'] = None
    
    # 计算日龄和DIM
    cow_df['日龄'] = (today - cow_df['birth_date']).dt.days
    cow_df['DIM_calc'] = cow_df.apply(
        lambda x: (today - x['calving_date']).days if pd.notna(x['calving_date']) else None,
        axis=1
    )
    
    # 1. 识别特殊状态
    results = []
    
    # 后备牛已孕
    mask = (cow_df['lac'] == 0) & (cow_df['repro_status'].isin(['初检孕', '复检孕']))
    count = mask.sum()
    results.append(f"后备牛已孕牛: {count}头")
    cow_df.loc[mask, 'group'] = '后备牛已孕牛+非性控'
    
    # 后备牛难孕
    mask = (cow_df['lac'] == 0) & (cow_df['日龄'] >= 554) & (~cow_df['repro_status'].isin(['初检孕', '复检孕']))
    count = mask.sum()
    results.append(f"后备牛难孕牛: {count}头")
    cow_df.loc[mask, 'group'] = '后备牛难孕牛+非性控'
    
    # 成母牛已孕
    mask = (cow_df['lac'] > 0) & (cow_df['repro_status'].isin(['初检孕', '复检孕']))
    count = mask.sum()
    results.append(f"成母牛已孕牛: {count}头")
    cow_df.loc[mask, 'group'] = '成母牛已孕牛+非性控'
    
    # 成母牛难孕
    mask = (cow_df['lac'] > 0) & (cow_df['DIM_calc'] >= 150) & (~cow_df['repro_status'].isin(['初检孕', '复检孕']))
    count = mask.sum()
    results.append(f"成母牛难孕牛: {count}头")
    cow_df.loc[mask, 'group'] = '成母牛难孕牛+非性控'
    
    # 成母牛未孕
    mask = (cow_df['lac'] > 0) & cow_df['group'].isna()
    count = mask.sum()
    results.append(f"成母牛未孕牛: {count}头")
    cow_df.loc[mask, 'group'] = '成母牛未孕牛'
    
    # 2. 后备牛周期分组
    reserve_age = 420
    cycle_days = 21
    
    heifer_mask = (cow_df['lac'] == 0) & cow_df['group'].isna()
    for i in range(1, 5):
        cycle_start = reserve_age - cycle_days * i
        cycle_end = reserve_age - cycle_days * (i-1)
        
        mask = heifer_mask & (cow_df['日龄'] >= cycle_start) & (cow_df['日龄'] < cycle_end)
        count = mask.sum()
        results.append(f"后备牛第{i}周期: {count}头")
        cow_df.loc[mask, 'group'] = f'后备牛第{i}周期'
    
    print("分组统计:")
    for result in results:
        print(f"  {result}")
    
    return cow_df


def test_breeding_method_assignment(cow_df):
    """测试配种方式分配"""
    print("\n=== 测试配种方式分配 ===\n")
    
    # 模拟策略表
    strategy_table = {
        '后备牛A': {
            'ratio': 30,
            'breeding_methods': ['普通性控', '普通性控', '常规冻精', '常规冻精']
        },
        '后备牛B': {
            'ratio': 40,
            'breeding_methods': ['普通性控', '常规冻精', '常规冻精', '常规冻精']
        },
        '后备牛C': {
            'ratio': 30,
            'breeding_methods': ['常规冻精', '常规冻精', '常规冻精', '常规冻精']
        }
    }
    
    # 处理后备牛第1周期
    cycle_df = cow_df[cow_df['group'] == '后备牛第1周期'].copy()
    if len(cycle_df) > 0:
        # 按ranking排序
        cycle_df = cycle_df.sort_values('ranking')
        total = len(cycle_df)
        
        print(f"后备牛第1周期共{total}头，按ranking排序后分配:")
        
        cumulative = 0
        for group_name, config in strategy_table.items():
            ratio = config['ratio']
            methods = config['breeding_methods']
            
            start_idx = int(total * cumulative / 100)
            end_idx = int(total * (cumulative + ratio) / 100)
            count = end_idx - start_idx
            
            if count > 0:
                group_df = cycle_df.iloc[start_idx:end_idx]
                
                sexed_count = 0
                regular_count = 0
                
                for idx, row in group_df.iterrows():
                    services = int(row.get('services_time', 0) or 0)
                    # services表示已配种次数，下次配种使用的方法索引就是services
                    method_idx = min(services, len(methods) - 1)
                    method = methods[method_idx]
                    
                    if method in ['普通性控', '超级性控']:
                        new_group = '后备牛第1周期+性控'
                        sexed_count += 1
                    else:
                        new_group = '后备牛第1周期+非性控'
                        regular_count += 1
                    
                    cow_df.loc[idx, 'group'] = new_group
                
                print(f"  {group_name} ({ratio}%): {count}头 → 性控{sexed_count}头，非性控{regular_count}头")
            
            cumulative += ratio
    
    # 统计最终分组
    print("\n最终分组统计:")
    group_counts = cow_df['group'].value_counts()
    for group, count in group_counts.items():
        print(f"  {group}: {count}头")
    
    return cow_df


def test_allocation_logic(cow_df, bull_df):
    """测试分配逻辑"""
    print("\n\n=== 测试分配逻辑 ===\n")
    
    # 获取库存信息
    sexed_bulls = bull_df[bull_df['classification'] == '性控'].copy()
    regular_bulls = bull_df[bull_df['classification'] == '常规'].copy()
    
    print("公牛库存:")
    print("性控公牛:")
    for _, bull in sexed_bulls.iterrows():
        print(f"  {bull['bull_id']}: {bull['支数']}支")
    print("常规公牛:")
    for _, bull in regular_bulls.iterrows():
        print(f"  {bull['bull_id']}: {bull['支数']}支")
    
    # 测试一个分组的分配
    test_group = '后备牛第1周期+性控'
    group_cows = cow_df[cow_df['group'] == test_group]
    
    if len(group_cows) > 0:
        print(f"\n测试分配 {test_group} 组 ({len(group_cows)}头):")
        
        # 1选 - 性控按比例
        sexed_total = sexed_bulls['支数'].sum()
        print(f"\n1选性控分配 (总库存{sexed_total}):")
        for _, bull in sexed_bulls.iterrows():
            ratio = bull['支数'] / sexed_total
            count = int(len(group_cows) * ratio)
            print(f"  {bull['bull_id']}: {bull['支数']}/{sexed_total} = {ratio:.1%} → {count}头")
        
        # 2选 - 性控平均
        available_sexed = len(sexed_bulls[sexed_bulls['支数'] > 0])
        avg_count = len(group_cows) // available_sexed
        print(f"\n2选性控分配 (平均分配给{available_sexed}头公牛):")
        print(f"  每头公牛约: {avg_count}头")
        
        # 1选 - 常规按比例
        regular_total = regular_bulls['支数'].sum()
        print(f"\n1选常规分配 (总库存{regular_total}):")
        for _, bull in regular_bulls.iterrows():
            ratio = bull['支数'] / regular_total
            count = int(len(group_cows) * ratio)
            print(f"  {bull['bull_id']}: {bull['支数']}/{regular_total} = {ratio:.1%} → {count}头")


def main():
    """主测试函数"""
    # 创建测试数据
    cow_df, bull_df = create_test_data()
    
    print(f"创建了 {len(cow_df)} 头母牛，{len(bull_df)} 头公牛")
    
    # 测试分组
    cow_df = test_grouping_logic(cow_df)
    
    # 测试配种方式分配
    cow_df = test_breeding_method_assignment(cow_df)
    
    # 测试分配逻辑
    test_allocation_logic(cow_df, bull_df)
    
    # 保存结果供检查
    output_file = project_root / "test_mating_logic_result.xlsx"
    with pd.ExcelWriter(output_file) as writer:
        cow_df.to_excel(writer, sheet_name='母牛分组结果', index=False)
        bull_df.to_excel(writer, sheet_name='公牛数据', index=False)
    
    print(f"\n\n测试结果已保存到: {output_file}")


if __name__ == '__main__':
    main()