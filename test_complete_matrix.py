"""
测试完整的矩阵生成（包括近交系数和隐性基因）
"""

from pathlib import Path
from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator
import logging
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def test_complete_matrix():
    # 项目路径
    project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")
    
    print("=== 测试完整矩阵生成 ===\n")
    
    # 创建生成器
    generator = MatrixRecommendationGenerator(project_path)
    
    # 加载数据
    print("1. 加载数据...")
    if not generator.load_data():
        print("❌ 数据加载失败")
        return
        
    print("✅ 所有数据加载成功")
    
    # 生成矩阵
    print("\n2. 生成配对矩阵...")
    matrices = generator.generate_matrices()
    
    print(f"\n生成了 {len(matrices)} 个矩阵:")
    for name in matrices.keys():
        print(f"  - {name}")
    
    # 检查近交系数矩阵
    print("\n3. 近交系数矩阵检查:")
    inbreeding_matrix = matrices.get('常规_近交系数')
    if inbreeding_matrix is not None:
        # 统计非零值
        non_zero_count = 0
        max_value = 0
        for col in inbreeding_matrix.columns:
            for val in inbreeding_matrix[col]:
                if val != '0.000%':
                    non_zero_count += 1
                    # 解析百分比值
                    num_val = float(val.replace('%', ''))
                    if num_val > max_value:
                        max_value = num_val
        
        print(f"  非零值数量: {non_zero_count}/{inbreeding_matrix.size}")
        print(f"  最大近交系数: {max_value}%")
    
    # 检查隐性基因矩阵
    print("\n4. 隐性基因矩阵检查:")
    genetic_matrix = matrices.get('常规_隐性基因')
    if genetic_matrix is not None:
        risk_count = (genetic_matrix == 'Risk').sum().sum()
        safe_count = (genetic_matrix == 'Safe').sum().sum()
        print(f"  Risk数量: {risk_count}")
        print(f"  Safe数量: {safe_count}")
        
        # 如果有风险，显示一些例子
        if risk_count > 0:
            print("\n  风险配对示例:")
            for cow_id in genetic_matrix.index[:100]:  # 检查前100头母牛
                for bull_id in genetic_matrix.columns:
                    if genetic_matrix.loc[cow_id, bull_id] == 'Risk':
                        print(f"    母牛 {cow_id} x 公牛 {bull_id}")
                        if risk_count > 3:
                            break
                if risk_count > 3:
                    break
    
    # 保存结果
    output_file = project_path / "analysis_results" / "complete_test_matrices.xlsx"
    print(f"\n5. 保存结果到: {output_file.name}")
    if generator.save_matrices(matrices, output_file):
        print("✅ 保存成功")
    else:
        print("❌ 保存失败")

if __name__ == "__main__":
    test_complete_matrix()