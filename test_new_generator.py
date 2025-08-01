"""
测试新的推荐生成器是否能正确加载文件
"""

import sys
from pathlib import Path
import pandas as pd

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator

def test_new_generator():
    """测试新的推荐生成器"""
    
    # 设置项目路径
    project_path = Path("/Users/Shared/Files From d.localized/projects/mating/genetic_projects/测试-基因组检测数据上传_2024_12_25_16_14")
    
    print("=== 测试新的推荐生成器 ===\n")
    
    # 1. 初始化生成器
    print("1. 初始化推荐生成器...")
    generator = MatrixRecommendationGenerator()
    
    # 2. 检查前置条件
    print("\n2. 检查前置条件...")
    prerequisites_ok, message = generator.check_prerequisites(project_path)
    if prerequisites_ok:
        print(f"✅ 前置条件检查通过")
        if hasattr(generator, 'inbreeding_analysis_file'):
            print(f"   找到分析文件: {generator.inbreeding_analysis_file.name}")
    else:
        print(f"❌ {message}")
        return
        
    # 3. 加载数据
    print("\n3. 加载数据...")
    try:
        if generator.load_data(project_path):
            print(f"✅ 数据加载成功")
            print(f"   母牛数量: {len(generator.cow_data) if generator.cow_data is not None else 0}")
            print(f"   公牛数量: {len(generator.bull_data) if generator.bull_data is not None else 0}")
            
            # 检查近交系数数据
            if generator.inbreeding_data is not None:
                print(f"\n4. 近交系数数据:")
                print(f"   记录数: {len(generator.inbreeding_data)}")
                print(f"   列名: {list(generator.inbreeding_data.columns)}")
                if len(generator.inbreeding_data) > 0:
                    print(f"   示例数据:")
                    print(generator.inbreeding_data.head(3))
                    
            # 检查隐性基因数据
            if generator.genetic_defect_data is not None:
                print(f"\n5. 隐性基因数据:")
                print(f"   记录数: {len(generator.genetic_defect_data)}")
                print(f"   列名: {list(generator.genetic_defect_data.columns)}")
                if len(generator.genetic_defect_data) > 0:
                    print(f"   示例数据:")
                    print(generator.genetic_defect_data.head(3))
                    
        else:
            print("❌ 数据加载失败")
            
    except Exception as e:
        print(f"❌ 加载出错: {e}")
        import traceback
        traceback.print_exc()
        
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_new_generator()