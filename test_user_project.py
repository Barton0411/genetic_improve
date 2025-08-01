"""测试用户新项目的推荐生成"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator

def test_user_project():
    """测试用户的新项目"""
    
    # 用户的项目路径
    project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")
    
    print("=== 测试用户项目 ===\n")
    
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
        
    # 3. 加载数据
    print("\n3. 加载数据...")
    try:
        if generator.load_data(project_path):
            print(f"✅ 数据加载成功")
            print(f"   母牛数量: {len(generator.cow_data) if generator.cow_data is not None else 0}")
            print(f"   公牛数量: {len(generator.bull_data) if generator.bull_data is not None else 0}")
            
            # 检查数据列名
            print("\n4. 公牛数据列名:")
            print(f"   {list(generator.bull_data.columns)}")
            
            print("\n5. 近交系数数据:")
            if hasattr(generator, 'inbreeding_data') and generator.inbreeding_data is not None:
                print(f"   列名: {list(generator.inbreeding_data.columns)}")
                print(f"   行数: {len(generator.inbreeding_data)}")
            else:
                print("   ❌ 未加载")
                
            print("\n6. 隐性基因数据:")
            if hasattr(generator, 'genetic_defect_data') and generator.genetic_defect_data is not None:
                print(f"   列名前10个: {list(generator.genetic_defect_data.columns[:10])}")
                print(f"   行数: {len(generator.genetic_defect_data)}")
            else:
                print("   ❌ 未加载")
                
            # 测试生成推荐
            print("\n7. 测试生成推荐...")
            # 只生成前5头母牛的推荐
            test_cows = generator.cow_data.head(5)
            generator.cow_data = test_cows
            
            def progress_callback(msg, prog):
                print(f"   {msg} - {prog}%")
                
            recommendations = generator.generate_complete_recommendations(
                inbreeding_threshold=0.03125,
                control_defect_genes=True,
                progress_callback=progress_callback
            )
            
            print(f"\n✅ 生成推荐成功: {len(recommendations)}条记录")
            
            # 检查结果
            if '常规_valid_bulls' in recommendations.columns:
                print("   ✅ 包含valid_bulls数据")
            else:
                print("   ❌ 未包含valid_bulls数据")
                
        else:
            print("❌ 数据加载失败")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_user_project()