"""
测试HH5风险检测
"""

import pandas as pd
from pathlib import Path
from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator
import logging

# 设置日志级别为DEBUG
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')

# 项目路径
project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")

# 加载近交系数文件
files = list(project_path.glob("**/备选公牛_近交系数及隐性基因分析结果_*.xlsx"))
latest_file = max(files, key=lambda x: x.stat().st_mtime)
df = pd.read_excel(latest_file)

print("=== 查找HH5风险配对 ===\n")

# 找出HH5为'NO safe'的记录
risk_pairs = df[df['HH5'] == 'NO safe']
print(f"找到 {len(risk_pairs)} 个HH5风险配对")

if not risk_pairs.empty:
    # 显示前几个
    for idx, row in risk_pairs.head(3).iterrows():
        print(f"\n配对 {idx+1}:")
        print(f"  母牛号: {row['母牛号']}")
        print(f"  公牛号: {row['原始备选公牛号']}")
        print(f"  HH5状态: {row['HH5']}")
        print(f"  近交系数: {row['后代近交系数']}")
    
    # 测试矩阵生成器的检测
    print("\n\n=== 测试矩阵生成器的隐性基因检测 ===")
    
    generator = MatrixRecommendationGenerator(project_path)
    generator.load_data()
    
    # 测试第一个风险配对
    test_cow = str(risk_pairs.iloc[0]['母牛号'])
    test_bull = str(risk_pairs.iloc[0]['原始备选公牛号'])
    
    print(f"\n测试配对: 母牛 {test_cow} x 公牛 {test_bull}")
    
    # 调用检测方法
    result = generator._check_genetic_defects(test_cow, test_bull)
    print(f"检测结果: {result}")
    print(f"期望结果: Risk")
    
    if result == "Risk":
        print("\n✅ 隐性基因风险检测正常！")
    else:
        print("\n❌ 隐性基因风险检测失败！")
        
    # 生成完整矩阵并检查
    print("\n\n=== 生成完整矩阵并检查风险数量 ===")
    matrices = generator.generate_matrices()
    
    # 检查常规隐性基因矩阵
    if '常规_隐性基因' in matrices:
        genetic_matrix = matrices['常规_隐性基因']
        risk_count = (genetic_matrix == 'Risk').sum().sum()
        print(f"常规冻精矩阵中的Risk数量: {risk_count}")
        
        # 如果有风险，显示一些例子
        if risk_count > 0:
            print("\n风险配对示例:")
            count = 0
            for cow_id in genetic_matrix.index:
                for bull_id in genetic_matrix.columns:
                    if genetic_matrix.loc[cow_id, bull_id] == 'Risk':
                        print(f"  母牛 {cow_id} x 公牛 {bull_id}")
                        count += 1
                        if count >= 3:
                            break
                if count >= 3:
                    break
else:
    print("未找到HH5风险配对")