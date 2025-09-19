"""检查valid_bulls列的生成"""

from pathlib import Path
import pandas as pd
from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_valid_bulls_generation():
    """检查推荐生成器是否正确生成valid_bulls列"""

    # 创建测试项目路径
    project_path = Path(".")

    # 创建生成器
    generator = MatrixRecommendationGenerator(project_path)

    # 模拟一些测试数据
    # 创建母牛数据
    cow_data = pd.DataFrame([
        {'cow_id': f'cow_{i:03d}', 'Combine Index Score': 100 + i * 10, 'Index Score': 100 + i * 10}
        for i in range(5)
    ])
    generator.cow_data = cow_data

    # 创建公牛数据
    bull_data = pd.DataFrame([
        {'bull_id': f'bull_regular_{i:02d}', 'classification': '常规', '支数': 10 + i * 5,
         'Bull Index Score': 200 + i * 10, 'Index Score': 200 + i * 10}
        for i in range(3)
    ] + [
        {'bull_id': f'bull_sexed_{i:02d}', 'classification': '性控', '支数': 5 + i * 3,
         'Bull Index Score': 250 + i * 10, 'Index Score': 250 + i * 10}
        for i in range(3)
    ])
    generator.bull_data = bull_data

    # 模拟近交系数数据
    inbreeding_data = []
    for cow in cow_data['cow_id']:
        for bull in bull_data['bull_id']:
            inbreeding_data.append({
                'cow_id': cow,
                'bull_id': bull,
                'inbreeding_coeff': 2.0  # 低于阈值
            })
    generator.inbreeding_df = pd.DataFrame(inbreeding_data)

    # 设置参数
    generator.inbreeding_threshold = 0.0625  # 6.25%
    generator.control_defect_genes = False

    # 生成推荐汇总
    try:
        # 生成完整矩阵（包含推荐汇总）
        matrices = generator.generate_matrices()
        recommendations = matrices.get('推荐汇总', pd.DataFrame())

        print("=" * 60)
        print("推荐汇总生成结果")
        print("=" * 60)
        print(f"\n总行数: {len(recommendations)}")
        print(f"总列数: {len(recommendations.columns)}")

        print("\n列名列表:")
        for col in recommendations.columns:
            print(f"  - {col}")

        # 检查关键列
        print("\n关键列检查:")
        for col in ['常规_valid_bulls', '性控_valid_bulls']:
            if col in recommendations.columns:
                non_empty = recommendations[col].notna().sum()
                print(f"  ✓ {col}: 存在，{non_empty}/{len(recommendations)} 非空")
                if non_empty > 0:
                    first_val = recommendations[recommendations[col].notna()][col].iloc[0]
                    print(f"    示例: {str(first_val)[:100]}...")
            else:
                print(f"  ✗ {col}: 不存在")

        # 保存结果用于检查
        output_file = Path("test_recommendations.xlsx")
        recommendations.to_excel(output_file, index=False)
        print(f"\n结果已保存至: {output_file}")

        return recommendations

    except Exception as e:
        logger.error(f"生成推荐汇总失败: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    check_valid_bulls_generation()