"""
测试选配分配比例是否正确
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator
from core.matching.cycle_based_matcher import CycleBasedMatcher

def create_test_data():
    """创建测试数据"""
    # 创建测试母牛数据（30头）
    cow_data = []
    for i in range(30):
        cow_data.append({
            'cow_id': f'C{i+1:03d}',
            'group': f'第{(i//10)+1}周期',  # 每10头一个周期
            'Combine Index Score': 2800 - i * 10,  # 递减的指数
            'sex': '母',
            '是否在场': '是'
        })
    cow_df = pd.DataFrame(cow_data)
    
    # 创建测试公牛数据
    bull_data = [
        # 性控公牛
        {'bull_id': 'S1', 'classification': '性控', 'semen_count': 60, 'Index Score': 3000},
        {'bull_id': 'S2', 'classification': '性控', 'semen_count': 30, 'Index Score': 2900},
        {'bull_id': 'S3', 'classification': '性控', 'semen_count': 10, 'Index Score': 2800},
        # 常规公牛  
        {'bull_id': 'R1', 'classification': '常规', 'semen_count': 100, 'Index Score': 2950},
        {'bull_id': 'R2', 'classification': '常规', 'semen_count': 80, 'Index Score': 2850},
        {'bull_id': 'R3', 'classification': '常规', 'semen_count': 20, 'Index Score': 2750},
    ]
    bull_df = pd.DataFrame(bull_data)
    
    return cow_df, bull_df

def create_mock_recommendations(cow_df, bull_df):
    """创建模拟的推荐数据"""
    recommendations = []
    
    for _, cow in cow_df.iterrows():
        row = cow.to_dict()
        cow_score = cow['Combine Index Score']
        
        # 为每种类型生成有效公牛列表（模拟所有公牛都满足约束）
        for semen_type in ['常规', '性控']:
            bulls = bull_df[bull_df['classification'] == semen_type]
            valid_bulls = []
            
            for _, bull in bulls.iterrows():
                bull_score = bull['Index Score']
                offspring_score = 0.5 * (cow_score + bull_score)
                valid_bulls.append({
                    'bull_id': bull['bull_id'],
                    'bull_score': bull_score,
                    'offspring_score': offspring_score,
                    'inbreeding_coeff': 0.02,  # 假设都是2%
                    'gene_status': 'Safe',
                    'meets_constraints': True,
                    'semen_count': bull['semen_count']
                })
            
            # 按后代得分排序
            valid_bulls.sort(key=lambda x: x['offspring_score'], reverse=True)
            
            row[f'{semen_type}_valid_bulls'] = valid_bulls
            
            # 填充前3选显示
            for i in range(1, 4):
                if i <= len(valid_bulls):
                    bull_info = valid_bulls[i-1]
                    row[f'推荐{semen_type}冻精{i}选'] = bull_info['bull_id']
                    row[f'{semen_type}冻精{i}近交系数'] = "2.00%"
                    row[f'{semen_type}冻精{i}隐性基因情况'] = "Safe"
                    row[f'{semen_type}冻精{i}得分'] = bull_info['offspring_score']
                    
        recommendations.append(row)
        
    return pd.DataFrame(recommendations)

def test_allocation_ratio():
    """测试分配比例"""
    print("=== 测试选配分配比例 ===\n")
    
    # 1. 创建测试数据
    print("1. 创建测试数据...")
    cow_df, bull_df = create_test_data()
    print(f"   母牛: {len(cow_df)}头")
    print(f"   公牛: {len(bull_df)}头")
    
    # 打印公牛信息和预期比例
    print("\n2. 公牛库存和预期比例:")
    for semen_type in ['性控', '常规']:
        bulls = bull_df[bull_df['classification'] == semen_type]
        total = bulls['semen_count'].sum()
        print(f"\n   {semen_type}冻精:")
        for _, bull in bulls.iterrows():
            ratio = bull['semen_count'] / total * 100
            expected_cows = int(30 * bull['semen_count'] / total)
            print(f"     {bull['bull_id']}: {bull['semen_count']}支 ({ratio:.1f}%) → 预期分配{expected_cows}头母牛")
    
    # 2. 创建模拟推荐
    print("\n3. 生成模拟推荐...")
    recommendations = create_mock_recommendations(cow_df, bull_df)
    
    # 保存公牛数据
    bull_data_path = Path("test_bull_data.xlsx")
    bull_df.to_excel(bull_data_path, index=False)
    
    # 3. 执行分配
    print("\n4. 执行选配分配...")
    matcher = CycleBasedMatcher()
    matcher.load_data(recommendations, bull_data_path)
    
    # 选择所有分组
    all_groups = recommendations['group'].unique().tolist()
    allocation_result = matcher.perform_allocation(all_groups)
    
    # 4. 分析分配结果
    print("\n5. 分配结果分析:")
    
    # 统计每个公牛的实际分配
    for choice in ['1选', '2选', '3选']:
        print(f"\n   === {choice}分配情况 ===")
        
        for semen_type in ['性控', '常规']:
            col_name = f"{choice}{semen_type}"
            if col_name in allocation_result.columns:
                usage = allocation_result[col_name].value_counts()
                
                print(f"\n   {semen_type}冻精{choice}:")
                bulls = bull_df[bull_df['classification'] == semen_type]
                total = bulls['semen_count'].sum()
                
                for bull_id in bulls['bull_id']:
                    count = usage.get(bull_id, 0)
                    bull_info = bulls[bulls['bull_id'] == bull_id].iloc[0]
                    expected_ratio = bull_info['semen_count'] / total * 100
                    actual_ratio = count / 30 * 100
                    
                    print(f"     {bull_id}: 分配{count}头 ({actual_ratio:.1f}%) "
                          f"[预期: {expected_ratio:.1f}%]")
    
    # 5. 显示汇总
    print("\n6. 公牛使用汇总:")
    summary = matcher.get_allocation_summary()
    print(summary.to_string(index=False))
    
    # 清理测试文件
    bull_data_path.unlink()
    
    print("\n=== 测试完成 ===")

def main():
    """主函数"""
    try:
        test_allocation_ratio()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()