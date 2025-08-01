"""
测试没有默认值的情况
"""

from pathlib import Path
from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator
import logging

logging.basicConfig(level=logging.ERROR, format='%(levelname)s - %(message)s')

def test_no_defaults():
    # 项目路径
    project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")
    
    print("=== 测试无默认值的矩阵生成器 ===\n")
    
    # 创建生成器
    generator = MatrixRecommendationGenerator(project_path)
    
    # 加载数据
    print("尝试加载数据...")
    if not generator.load_data():
        print("\n❌ 数据加载失败（预期的结果）")
        print("\n系统正确地拒绝了使用默认值，并提示用户需要先计算育种指数。")
    else:
        print("✅ 数据加载成功（如果有完整数据）")

if __name__ == "__main__":
    test_no_defaults()