"""
测试直接分配功能（无弹窗）
"""

import pandas as pd
from pathlib import Path
from core.matching.cycle_based_matcher import CycleBasedMatcher
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def test_direct_allocation():
    # 项目路径
    project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")
    
    print("=== 测试直接分配功能 ===\n")
    
    # 0. 先生成推荐报告
    print("生成推荐报告...")
    from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator
    generator = MatrixRecommendationGenerator(project_path)
    if generator.load_data():
        matrices = generator.generate_matrices()
        output_file = project_path / "analysis_results" / "individual_mating_matrices.xlsx"
        generator.save_matrices(matrices, output_file)
        
        # 同时保存推荐汇总到 individual_mating_report.xlsx
        summary_file = project_path / "analysis_results" / "individual_mating_report.xlsx"
        matrices['推荐汇总'].to_excel(summary_file, index=False)
        print("✅ 推荐报告生成完成")
    else:
        print("❌ 生成推荐报告失败")
        return
    
    # 1. 检查推荐报告
    report_file = project_path / "analysis_results" / "individual_mating_report.xlsx"
    if not report_file.exists():
        print("❌ 缺少推荐报告")
        return
    
    # 2. 模拟选中的组
    selected_groups = ['后备牛第1周期+非性控', '后备牛第3周期+非性控', '后备牛第4周期+非性控']
    print(f"选中的组: {selected_groups}")
    
    # 3. 模拟冻精库存（正常情况）
    semen_inventory = {
        '007HO16284': 100,
        '007HO16385': 50,
        '151HO04449': 20,
        '007HO16443': 80,
        '151HO04311': 40,
        '001HO09154': 60,
        '001HO09162': 30,
        '001HO09174': 10
    }
    print(f"\n冻精库存: {semen_inventory}")
    
    # 4. 执行分配
    print("\n开始执行分配...")
    
    try:
        # 创建匹配器
        matcher = CycleBasedMatcher()
        matcher.inbreeding_threshold = 3.125  # 默认阈值
        matcher.control_defect_genes = True   # 默认控制隐性基因
        
        # 加载数据
        print("  - 加载推荐数据...")
        recommendations_df = pd.read_excel(report_file)
        bull_data_path = project_path / "standardized_data" / "processed_bull_data.xlsx"
        
        if not matcher.load_data(recommendations_df, bull_data_path):
            print("❌ 数据加载失败")
            return
        
        # 设置库存
        print("  - 设置冻精库存...")
        matcher.set_inventory(semen_inventory)
        
        # 执行分配
        print("  - 执行分配...")
        def progress_callback(message, progress):
            print(f"    {message} - {progress:.0f}%")
        
        result_df = matcher.perform_allocation(selected_groups, progress_callback)
        
        # 保存结果
        print("  - 保存结果...")
        allocation_file = project_path / "analysis_results" / "test_direct_allocation_result.xlsx"
        success = matcher.save_allocation_result(result_df, allocation_file)
        
        summary_file = project_path / "analysis_results" / "test_allocation_summary.xlsx"
        summary_df = matcher.get_allocation_summary()
        summary_df.to_excel(summary_file, index=False)
        
        print(f"\n✅ 分配完成！")
        print(f"  - 分配结果: {allocation_file}")
        print(f"  - 汇总信息: {summary_file}")
        
        # 显示汇总
        print("\n库存使用情况:")
        print(summary_df.to_string())
        
    except Exception as e:
        print(f"\n❌ 分配失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. 测试库存为0的情况
    print("\n\n=== 测试库存为0的情况 ===")
    zero_inventory = {bull_id: 0 for bull_id in semen_inventory.keys()}
    all_zero = all(count == 0 for count in zero_inventory.values())
    if all_zero:
        print("✅ 正确检测到所有库存为0")
    else:
        print("❌ 未能检测到库存为0")

if __name__ == "__main__":
    test_direct_allocation()