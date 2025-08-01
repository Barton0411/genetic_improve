"""
手动生成新的个体选配推荐报告
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator

def generate_new_report():
    """生成新的推荐报告"""
    
    # 设置项目路径
    project_path = Path("/Users/Shared/Files From d.localized/projects/mating/genetic_projects/测试-基因组检测数据上传_2024_12_25_16_14")
    
    print("=== 生成新的个体选配推荐报告 ===\n")
    
    # 1. 初始化生成器
    print("1. 初始化推荐生成器...")
    generator = MatrixRecommendationGenerator()
    
    # 2. 检查前置条件
    print("\n2. 检查前置条件...")
    prerequisites_ok, message = generator.check_prerequisites(project_path)
    if not prerequisites_ok:
        print(f"❌ {message}")
        print("继续使用安全默认值...")
        
    # 3. 加载数据
    print("\n3. 加载数据...")
    if not generator.load_data(project_path):
        print("❌ 数据加载失败")
        return
        
    print(f"✅ 数据加载成功: {len(generator.cow_data)}头母牛, {len(generator.bull_data)}头公牛")
    
    # 4. 生成推荐
    print("\n4. 生成选配推荐...")
    
    def progress_callback(message, progress):
        print(f"  {message} - {progress}%")
        
    recommendations = generator.generate_complete_recommendations(
        inbreeding_threshold=0.03125,  # 3.125%
        control_defect_genes=True,
        progress_callback=progress_callback
    )
    
    print(f"\n✅ 生成推荐完成: {len(recommendations)}条记录")
    
    # 5. 保存结果
    output_file = project_path / "analysis_results" / "individual_mating_report.xlsx"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\n5. 保存推荐报告...")
    if generator.save_recommendations(recommendations, output_file):
        print(f"✅ 报告已保存至: {output_file}")
        
        # 显示部分数据
        print("\n6. 报告预览:")
        print(f"   总记录数: {len(recommendations)}")
        print(f"   列名: {list(recommendations.columns[:10])}...")  # 只显示前10个列名
        
        # 检查是否包含valid_bulls数据
        if '常规_valid_bulls' in recommendations.columns:
            print("\n   ✅ 包含valid_bulls数据")
            # 显示第一条记录的valid_bulls
            first_row = recommendations.iloc[0]
            if first_row['常规_valid_bulls'] is not None:
                print(f"   示例 - 常规valid_bulls数量: {len(first_row['常规_valid_bulls'])}")
            if first_row['性控_valid_bulls'] is not None:
                print(f"   示例 - 性控valid_bulls数量: {len(first_row['性控_valid_bulls'])}")
        else:
            print("\n   ❌ 未找到valid_bulls数据")
            
    else:
        print("❌ 保存失败")
        
    print("\n=== 完成 ===")

if __name__ == "__main__":
    generate_new_report()