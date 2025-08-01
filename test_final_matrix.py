"""
最终测试完整矩阵生成
"""

from pathlib import Path
from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator
import logging
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def test_final_matrix():
    # 项目路径
    project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")
    
    print("=== 最终测试完整矩阵生成 ===\n")
    
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
    
    # 检查常规冻精矩阵
    print("\n3. 常规冻精矩阵检查:")
    if '常规_隐性基因' in matrices:
        genetic_matrix = matrices['常规_隐性基因']
        risk_count = (genetic_matrix == 'Risk').sum().sum()
        safe_count = (genetic_matrix == 'Safe').sum().sum()
        print(f"  Risk数量: {risk_count}")
        print(f"  Safe数量: {safe_count}")
        print(f"  总数: {genetic_matrix.size}")
    
    # 检查性控冻精矩阵
    print("\n4. 性控冻精矩阵检查:")
    if '性控_隐性基因' in matrices:
        genetic_matrix = matrices['性控_隐性基因']
        risk_count = (genetic_matrix == 'Risk').sum().sum()
        safe_count = (genetic_matrix == 'Safe').sum().sum()
        print(f"  Risk数量: {risk_count}")
        print(f"  Safe数量: {safe_count}")
        print(f"  总数: {genetic_matrix.size}")
        
        # 如果有风险，显示详细信息
        if risk_count > 0:
            print("\n  风险配对详情:")
            # 查找所有风险配对
            risk_pairs = []
            for cow_id in genetic_matrix.index:
                for bull_id in genetic_matrix.columns:
                    if genetic_matrix.loc[cow_id, bull_id] == 'Risk':
                        risk_pairs.append((cow_id, bull_id))
            
            # 统计每头公牛的风险配对数
            from collections import Counter
            bull_risk_counts = Counter([pair[1] for pair in risk_pairs])
            print(f"\n  各公牛的风险配对数:")
            for bull_id, count in bull_risk_counts.items():
                print(f"    {bull_id}: {count}个风险配对")
            
            # 显示前几个风险配对
            print(f"\n  前5个风险配对示例:")
            for i, (cow_id, bull_id) in enumerate(risk_pairs[:5]):
                print(f"    {i+1}. 母牛 {cow_id} x 公牛 {bull_id}")
    
    # 检查推荐汇总
    print("\n5. 推荐汇总检查:")
    summary = matrices['推荐汇总']
    print(f"  总母牛数: {len(summary)}")
    
    # 检查是否有母牛因为隐性基因风险而没有性控推荐
    no_sexed_count = 0
    for _, row in summary.iterrows():
        if pd.isna(row.get('推荐性控冻精1选', '')) or row.get('推荐性控冻精1选', '') == '':
            no_sexed_count += 1
    
    print(f"  没有性控推荐的母牛数: {no_sexed_count}")
    
    if no_sexed_count > 0:
        # 检查原因
        print(f"\n  分析没有性控推荐的原因:")
        # 查找22159号母牛
        cow_22159 = summary[summary['cow_id'] == '22159']
        if not cow_22159.empty:
            print(f"    以22159号母牛为例:")
            row = cow_22159.iloc[0]
            for i in range(1, 4):
                bull_id = row.get(f'推荐性控冻精{i}选', '')
                if bull_id:
                    print(f"      性控{i}选: {bull_id}")
                else:
                    print(f"      性控{i}选: 无（可能因为所有性控公牛都有隐性基因风险）")
    
    # 保存结果
    output_file = project_path / "analysis_results" / "final_test_matrices.xlsx"
    print(f"\n6. 保存结果到: {output_file.name}")
    if generator.save_matrices(matrices, output_file):
        print("✅ 保存成功")
        print(f"\n文件路径: {output_file}")
    else:
        print("❌ 保存失败")

if __name__ == "__main__":
    test_final_matrix()