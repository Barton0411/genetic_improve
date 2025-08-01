"""
测试简化版推荐生成器
"""

import sys
from pathlib import Path
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.matching.simple_recommendation_generator import SimpleRecommendationGenerator

def test_simple_generator():
    """测试简化版生成器"""
    
    # 用户的项目路径
    project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")
    
    print("=== 测试简化版推荐生成器 ===\n")
    
    # 创建生成器
    generator = SimpleRecommendationGenerator()
    
    # 生成推荐
    print("开始生成推荐...")
    success = generator.generate_recommendations(project_path)
    
    if success:
        print("\n✅ 推荐生成成功！")
        output_file = project_path / "analysis_results" / "individual_mating_report.xlsx"
        print(f"报告已保存至: {output_file}")
        
        # 检查文件内容
        import pandas as pd
        df = pd.read_excel(output_file)
        print(f"\n报告信息:")
        print(f"- 记录数: {len(df)}")
        print(f"- 列数: {len(df.columns)}")
        
        # 检查是否有valid_bulls列
        if '常规_valid_bulls' in df.columns:
            print("- ✅ 包含常规_valid_bulls列")
        if '性控_valid_bulls' in df.columns:
            print("- ✅ 包含性控_valid_bulls列")
            
        # 显示前几列
        print(f"\n前10列: {list(df.columns[:10])}")
        
    else:
        print("\n❌ 推荐生成失败")
        
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_simple_generator()