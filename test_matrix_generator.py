"""
测试矩阵推荐生成器
"""

from pathlib import Path
from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator
import logging

logging.basicConfig(level=logging.INFO)

def test_matrix_generator():
    # 项目路径
    project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")
    
    print("=== 测试矩阵推荐生成器 ===\n")
    
    # 创建生成器
    generator = MatrixRecommendationGenerator(project_path)
    
    # 加载数据
    print("加载数据...")
    if not generator.load_data():
        print("❌ 数据加载失败")
        return
        
    print("✅ 数据加载成功")
    
    # 生成矩阵
    print("\n生成配对矩阵...")
    matrices = generator.generate_matrices()
    
    print(f"\n生成了 {len(matrices)} 个矩阵：")
    for name, df in matrices.items():
        print(f"  - {name}: {df.shape}")
        
    # 保存结果
    output_file = project_path / "analysis_results" / "test_mating_matrices.xlsx"
    print(f"\n保存到: {output_file}")
    
    if generator.save_matrices(matrices, output_file):
        print("✅ 保存成功")
        
        # 显示部分结果
        if '常规_后代得分' in matrices:
            print("\n常规冻精后代得分矩阵（前5行5列）：")
            print(matrices['常规_后代得分'].iloc[:5, :5])
            
        if '推荐汇总' in matrices:
            print(f"\n推荐汇总包含 {len(matrices['推荐汇总'])} 头母牛")
            print("前3条记录：")
            print(matrices['推荐汇总'][['cow_id', '推荐常规冻精1选', '常规冻精1近交系数']].head(3))
    else:
        print("❌ 保存失败")

if __name__ == "__main__":
    test_matrix_generator()