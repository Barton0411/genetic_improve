"""测试完整的选配流程"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_complete_flow():
    """测试从推荐生成到分配的完整流程"""

    print("=" * 60)
    print("测试完整选配流程")
    print("=" * 60)

    # 1. 创建测试项目结构
    project_path = Path("test_project")
    project_path.mkdir(exist_ok=True)
    (project_path / "standardized_data").mkdir(exist_ok=True)
    (project_path / "analysis_results").mkdir(exist_ok=True)

    # 2. 创建母牛数据
    cow_data = pd.DataFrame([
        {
            'cow_id': f'cow_{i:03d}',
            'Index Score': 100 + i * 10,
            'Combine Index Score': 100 + i * 10,
            'lac': 1,
            'breed': 'Holstein'
        }
        for i in range(10)
    ])

    # 保存母牛数据
    cow_file = project_path / "standardized_data" / "processed_cow_index_scores.xlsx"
    cow_data.to_excel(cow_file, index=False)
    print(f"\n创建母牛数据: {len(cow_data)} 头")

    # 3. 创建公牛数据（包含常规和性控）
    bull_data = pd.DataFrame([
        # 常规公牛
        {'bull_id': 'bull_reg_01', 'classification': '常规', '支数': 20, 'Index Score': 200, 'Bull Index Score': 200},
        {'bull_id': 'bull_reg_02', 'classification': '常规', '支数': 30, 'Index Score': 210, 'Bull Index Score': 210},
        {'bull_id': 'bull_reg_03', 'classification': '常规', '支数': 40, 'Index Score': 220, 'Bull Index Score': 220},
        # 性控公牛
        {'bull_id': 'bull_sex_01', 'classification': '性控', '支数': 10, 'Index Score': 250, 'Bull Index Score': 250},
        {'bull_id': 'bull_sex_02', 'classification': '性控', '支数': 15, 'Index Score': 260, 'Bull Index Score': 260},
        {'bull_id': 'bull_sex_03', 'classification': '性控', '支数': 20, 'Index Score': 270, 'Bull Index Score': 270},
    ])

    # 保存公牛数据
    bull_file = project_path / "standardized_data" / "processed_bull_data.xlsx"
    bull_data.to_excel(bull_file, index=False)
    print(f"创建公牛数据: {len(bull_data)} 头")
    print("  常规公牛:", len(bull_data[bull_data['classification'] == '常规']))
    print("  性控公牛:", len(bull_data[bull_data['classification'] == '性控']))

    # 4. 创建近交系数数据（所有配对都低于阈值）
    inbreeding_data = []
    for cow in cow_data['cow_id']:
        for bull in bull_data['bull_id']:
            inbreeding_data.append({
                'cow_id': cow,
                'bull_id': bull,
                'inbreeding_coeff': np.random.uniform(1.0, 3.0)  # 低于6.25%阈值
            })

    inbreeding_df = pd.DataFrame(inbreeding_data)
    inbreeding_file = project_path / "analysis_results" / "inbreeding_matrix.xlsx"
    inbreeding_df.to_excel(inbreeding_file, index=False)
    print(f"创建近交系数数据: {len(inbreeding_df)} 对")

    # 5. 使用MatrixRecommendationGenerator生成推荐
    print("\n步骤1: 生成推荐矩阵...")
    from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator

    generator = MatrixRecommendationGenerator(project_path)
    generator.inbreeding_threshold = 0.0625  # 6.25%
    generator.control_defect_genes = False

    # 加载数据
    generator.load_data()

    try:
        matrices = generator.generate_matrices()
        recommendations_df = matrices.get('推荐汇总', pd.DataFrame())

        if recommendations_df.empty:
            print("错误：推荐汇总为空")
            return

        print(f"  生成推荐: {len(recommendations_df)} 头母牛")

        # 添加分组信息
        recommendations_df['group'] = '第1周期（后备牛）'

        # 保存推荐报告
        report_file = project_path / "analysis_results" / "individual_mating_report.xlsx"
        recommendations_df.to_excel(report_file, index=False)
        print(f"  保存至: {report_file}")

        # 检查关键列
        print("\n  检查推荐报告列:")
        for col in ['常规_valid_bulls', '性控_valid_bulls']:
            if col in recommendations_df.columns:
                non_empty = recommendations_df[col].notna().sum()
                print(f"    {col}: {non_empty}/{len(recommendations_df)} 非空")
            else:
                print(f"    {col}: 不存在！")

    except Exception as e:
        print(f"生成推荐失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 6. 使用CycleBasedMatcher进行分配
    print("\n步骤2: 执行分配...")
    from core.matching.cycle_based_matcher import CycleBasedMatcher

    matcher = CycleBasedMatcher()

    # 加载数据
    if not matcher.load_data(recommendations_df, bull_file):
        print("加载数据失败")
        return

    # 设置参数
    matcher.inbreeding_threshold = 6.25
    matcher.control_defect_genes = False

    # 执行分配
    selected_groups = ['第1周期（后备牛）']
    allocation_df = matcher.perform_allocation(selected_groups)

    if allocation_df.empty:
        print("分配失败：结果为空")
        return

    print(f"  分配完成: {len(allocation_df)} 头母牛")

    # 检查分配结果
    print("\n  检查分配结果:")
    result_cols = ['1选常规', '2选常规', '3选常规', '1选性控', '2选性控', '3选性控']
    for col in result_cols:
        if col in allocation_df.columns:
            non_empty = allocation_df[col].notna().sum()
            print(f"    {col}: {non_empty}/{len(allocation_df)} 已分配")
        else:
            print(f"    {col}: 列不存在！")

    # 保存分配结果
    allocation_file = project_path / "analysis_results" / "individual_allocation_result.xlsx"
    allocation_df.to_excel(allocation_file, index=False)
    print(f"\n分配结果已保存至: {allocation_file}")

    # 获取分配汇总
    summary = matcher.get_allocation_summary()
    print("\n分配汇总:")
    print(summary.to_string())

    return allocation_df

if __name__ == "__main__":
    result = test_complete_flow()