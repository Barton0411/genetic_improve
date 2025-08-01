"""
测试基于周期的选配分配器
"""

import sys
from pathlib import Path
import pandas as pd
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.matching.cycle_based_matcher import CycleBasedMatcher

def test_cycle_matcher():
    """测试周期分配器"""
    
    # 项目路径
    project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")
    
    print("=== 测试基于周期的选配分配器 ===\n")
    
    # 1. 加载推荐数据
    recommendations_file = project_path / "analysis_results" / "individual_mating_report.xlsx"
    if not recommendations_file.exists():
        print("❌ 未找到推荐报告文件")
        return
        
    recommendations_df = pd.read_excel(recommendations_file)
    print(f"✅ 加载了 {len(recommendations_df)} 条推荐记录")
    
    # 检查分组信息
    groups = recommendations_df['group'].value_counts()
    print("\n分组信息:")
    for group, count in groups.items():
        print(f"  {group}: {count} 头")
        
    # 2. 创建分配器
    matcher = CycleBasedMatcher()
    
    # 3. 加载数据
    bull_data_path = project_path / "standardized_data" / "processed_bull_data.xlsx"
    if not matcher.load_data(recommendations_df, bull_data_path):
        print("\n❌ 数据加载失败")
        
        # 检查是否库存都是0
        if matcher.check_zero_inventory():
            print("\n⚠️  所有公牛的冻精支数都为0，请先设置冻精库存")
            
            # 显示当前库存
            inventory = matcher.get_inventory_summary()
            print("\n当前库存情况:")
            print(inventory)
            
            # 模拟设置库存
            print("\n模拟设置库存...")
            # 这里应该通过UI让用户输入
            test_inventory = {
                '007HO16284': 100,
                '007HO16385': 50,
                '151HO04449': 20,
                '007HO16443': 80,
                '151HO04311': 40,
                '001HO09154': 60,
                '001HO09162': 30,
                '001HO09174': 10
            }
            
            # 更新库存
            for bull_id, count in test_inventory.items():
                if bull_id in matcher.bull_inventory:
                    matcher.bull_inventory[bull_id] = count
                    
            print("✅ 已设置测试库存")
            
    # 显示库存情况
    print("\n库存情况:")
    inventory_df = matcher.get_inventory_summary()
    print(inventory_df)
    
    # 4. 选择要分配的分组（选择周期组）
    all_groups = recommendations_df['group'].dropna().unique().tolist()
    cycle_groups = [g for g in all_groups if isinstance(g, str) and '周期' in g]
    
    print(f"\n选择分配的周期组: {cycle_groups}")
    
    # 5. 执行分配
    print("\n开始执行分配...")
    
    def progress_callback(msg, progress):
        print(f"  {msg} - {progress}%")
        
    result_df = matcher.perform_allocation(cycle_groups, progress_callback)
    
    print(f"\n✅ 分配完成，共分配 {len(result_df)} 头母牛")
    
    # 6. 显示分配汇总
    print("\n分配汇总:")
    summary_df = matcher.get_allocation_summary()
    print(summary_df)
    
    # 7. 保存结果
    output_file = project_path / "analysis_results" / "cycle_based_allocation.xlsx"
    if matcher.save_allocation_result(result_df, output_file):
        print(f"\n✅ 分配结果已保存至: {output_file}")
        
    # 8. 分析分配结果
    print("\n分配结果分析:")
    for semen_type in ['常规', '性控']:
        print(f"\n{semen_type}冻精1选分配:")
        col = f"1选{semen_type}"
        if col in result_df.columns:
            distribution = result_df[col].value_counts()
            for bull_id, count in distribution.items():
                if pd.notna(bull_id):
                    print(f"  {bull_id}: {count} 头")
                    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_cycle_matcher()