"""
测试使用公牛指数文件
"""

from pathlib import Path
from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def test_with_bull_index():
    # 项目路径
    project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")
    
    print("=== 测试使用公牛指数文件 ===\n")
    
    # 创建生成器
    generator = MatrixRecommendationGenerator(project_path)
    
    # 加载数据
    print("加载数据...")
    if generator.load_data():
        print("✅ 数据加载成功！")
        
        # 检查公牛数据
        if 'Index Score' in generator.bull_data.columns:
            print(f"\n公牛指数数据:")
            print(generator.bull_data[['bull_id', 'classification', 'Index Score']].to_string())
        
        # 生成矩阵
        print("\n生成配对矩阵...")
        matrices = generator.generate_matrices()
        
        # 保存结果
        output_file = project_path / "analysis_results" / "test_with_index_matrices.xlsx"
        if generator.save_matrices(matrices, output_file):
            print(f"\n✅ 矩阵已保存至: {output_file}")
            
            # 检查结果
            if '常规_后代得分' in matrices:
                score_matrix = matrices['常规_后代得分']
                print(f"\n后代得分范围: {score_matrix.min().min()} - {score_matrix.max().max()}")
                
    else:
        print("❌ 数据加载失败")

if __name__ == "__main__":
    test_with_bull_index()