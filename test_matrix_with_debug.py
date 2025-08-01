"""
测试矩阵推荐生成器（带调试信息）
"""

from pathlib import Path
from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator
import logging

# 设置详细的日志
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')

def test_matrix_generator():
    # 项目路径
    project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")
    
    print("=== 测试矩阵推荐生成器（调试模式）===\n")
    
    # 创建生成器
    generator = MatrixRecommendationGenerator(project_path)
    
    # 加载数据
    print("加载数据...")
    if not generator.load_data():
        print("❌ 数据加载失败")
        return
        
    # 生成矩阵
    print("\n生成配对矩阵...")
    matrices = generator.generate_matrices()
    
    print(f"\n生成了 {len(matrices)} 个矩阵")
    
    # 保存结果
    output_file = project_path / "analysis_results" / "test_debug_matrices.xlsx"
    generator.save_matrices(matrices, output_file)

if __name__ == "__main__":
    test_matrix_generator()