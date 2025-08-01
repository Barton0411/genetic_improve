"""
测试改进版选配功能
"""

import sys
from pathlib import Path
import pandas as pd

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator
from core.matching.cycle_based_matcher import CycleBasedMatcher
from core.matching.group_preview_updater import GroupPreviewUpdater
from PyQt6.QtWidgets import QMessageBox, QApplication

def test_improved_matching():
    """测试改进版选配功能"""
    
    # 设置项目路径
    project_path = Path("/Users/Shared/Files From d.localized/projects/mating/genetic_projects/测试-基因组检测数据上传_2024_12_25_16_14")
    
    print("=== 测试改进版选配功能 ===\n")
    
    # 1. 初始化推荐生成器
    print("1. 检查前置条件...")
    generator = MatrixRecommendationGenerator()
    
    # 检查前置条件
    prerequisites_ok, message = generator.check_prerequisites(project_path)
    if not prerequisites_ok:
        print(f"❌ {message}")
        
        # 模拟用户确认
        response = input("\n是否进行近交系数和隐性基因分析？(y/n): ")
        if response.lower() == 'y':
            print("跳转到近交系数和隐性基因分析...")
            # 这里应该调用相应的分析函数
            return
        else:
            return
            
    print("✅ 前置条件检查通过")
    
    # 2. 加载数据
    print("\n2. 加载数据...")
    if not generator.load_data(project_path):
        print("❌ 数据加载失败")
        return
        
    print(f"✅ 数据加载成功: {len(generator.cow_data)}头母牛, {len(generator.bull_data)}头公牛")
    
    # 3. 生成推荐
    print("\n3. 生成选配推荐...")
    recommendations = generator.generate_complete_recommendations(
        inbreeding_threshold=0.03125,  # 3.125%
        control_defect_genes=True,
        progress_callback=lambda msg, prog: print(f"  {msg} - {prog}%")
    )
    
    print(f"✅ 生成推荐完成")
    
    # 保存推荐报告
    output_path = project_path / "analysis_results" / "个体选配推荐报告.xlsx"
    generator.save_recommendations(recommendations, output_path)
    print(f"✅ 推荐报告已保存: {output_path}")
    
    # 4. 执行选配分配
    print("\n4. 执行选配分配...")
    matcher = CycleBasedMatcher()
    
    # 加载数据
    bull_data_path = project_path / "standardized_data" / "processed_bull_data.xlsx"
    if not matcher.load_data(recommendations, bull_data_path):
        print("❌ 分配器数据加载失败")
        return
        
    # 选择要分配的分组
    all_groups = recommendations['group'].unique().tolist()
    print(f"\n可用分组: {all_groups}")
    
    # 这里默认选择所有分组
    selected_groups = all_groups
    
    # 执行分配
    allocation_result = matcher.perform_allocation(
        selected_groups=selected_groups,
        progress_callback=lambda msg, prog: print(f"  {msg} - {prog}%")
    )
    
    print(f"✅ 分配完成: {len(allocation_result)}头母牛")
    
    # 保存分配结果
    allocation_path = project_path / "analysis_results" / "个体选配分配结果.xlsx"
    matcher.save_allocation_result(allocation_result, allocation_path)
    print(f"✅ 分配结果已保存: {allocation_path}")
    
    # 5. 显示分配汇总
    print("\n5. 分配汇总:")
    summary = matcher.get_allocation_summary()
    print(summary.to_string(index=False))
    
    # 6. 测试分组预览更新
    print("\n6. 分组预览示例:")
    
    # 加载公牛数据
    bull_data = pd.read_excel(bull_data_path)
    
    # 创建预览更新器
    updater = GroupPreviewUpdater(allocation_result, bull_data)
    
    # 显示第一个分组的汇总
    if selected_groups:
        first_group = selected_groups[0]
        group_summary = updater.get_group_summary(first_group)
        
        print(f"\n分组 '{first_group}' 汇总:")
        print(f"  母牛数量: {group_summary['母牛数量']}")
        print(f"  平均指数: {group_summary['平均指数']:.2f}")
        print(f"  使用公牛数: {group_summary['使用公牛数']}")
        
        print("\n  公牛使用情况:")
        for bull_info in group_summary['公牛使用情况'][:5]:  # 只显示前5个
            print(f"    {bull_info['公牛ID']} ({bull_info['类型']}): "
                  f"使用{bull_info['使用次数']}次, "
                  f"剩余{bull_info['剩余支数']}支")
                  
        # 导出分组预览
        preview_path = project_path / "analysis_results" / f"分组预览_{first_group}.xlsx"
        if updater.export_group_preview(first_group, str(preview_path)):
            print(f"\n✅ 分组预览已导出: {preview_path}")
            
    print("\n=== 测试完成 ===")

def main():
    """主函数"""
    # 创建QApplication（某些功能可能需要）
    app = QApplication(sys.argv) if not QApplication.instance() else QApplication.instance()
    
    try:
        test_improved_matching()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()