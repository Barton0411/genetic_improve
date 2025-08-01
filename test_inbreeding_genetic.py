"""
测试近交系数和隐性基因数据处理
"""

import pandas as pd
from pathlib import Path
import shutil

# 项目路径
project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")

print("=== 测试近交系数和隐性基因数据 ===\n")

# 1. 检查文件是否存在
files = list(project_path.glob("**/备选公牛_近交系数及隐性基因分析结果_*.xlsx"))
if files:
    latest_file = max(files, key=lambda x: x.stat().st_mtime)
    print(f"找到文件: {latest_file.name}")
    
    # 读取数据
    df = pd.read_excel(latest_file)
    print(f"数据形状: {df.shape}")
    print(f"列数: {len(df.columns)}")
    
    # 检查必要列
    print("\n必要列检查:")
    required_cols = ['母牛号', '原始备选公牛号', '后代近交系数']
    for col in required_cols:
        exists = col in df.columns
        print(f"  {col}: {'✓' if exists else '✗'}")
    
    # 检查隐性基因列
    print("\n隐性基因列:")
    defect_genes = ['HH1', 'HH2', 'HH3', 'HH4', 'HH5', 'HH6', 
                   'MW', 'BLAD', 'CVM', 'DUMPS', 'Citrullinemia',
                   'Brachyspina', 'Factor XI', 'Mulefoot']
    found_genes = [gene for gene in defect_genes if gene in df.columns]
    print(f"  找到 {len(found_genes)} 个隐性基因列: {found_genes[:5]}...")
    
    # 统计近交系数
    if '后代近交系数' in df.columns:
        print("\n近交系数统计:")
        non_zero = df[df['后代近交系数'] != '0.00%']
        print(f"  非零记录数: {len(non_zero)}/{len(df)}")
        
        # 转换为数值并统计
        values = []
        for val in df['后代近交系数']:
            if isinstance(val, str) and '%' in val:
                values.append(float(val.replace('%', '')))
        if values:
            print(f"  范围: {min(values)}% - {max(values)}%")
            print(f"  平均值: {sum(values)/len(values):.3f}%")
    
    # 统计隐性基因风险
    if 'HH1' in df.columns:
        print("\n隐性基因风险统计 (HH1):")
        print(df['HH1'].value_counts().head())
        
else:
    print("❌ 未找到备选公牛_近交系数及隐性基因分析结果文件")
    print("请先进行「备选公牛近交和隐性基因分析」")

# 2. 测试没有文件的情况
print("\n\n=== 测试缺少文件的情况 ===")
from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator
import logging

logging.basicConfig(level=logging.ERROR, format='%(levelname)s - %(message)s')

# 创建临时项目目录
temp_path = Path("/tmp/test_no_inbreeding")
temp_path.mkdir(exist_ok=True)
(temp_path / "analysis_results").mkdir(exist_ok=True)

# 复制必要文件
for file in ['processed_index_cow_index_scores.xlsx', 'processed_index_bull_scores.xlsx']:
    src = project_path / "analysis_results" / file
    if src.exists():
        shutil.copy(src, temp_path / "analysis_results" / file)

# 复制公牛数据
(temp_path / "standardized_data").mkdir(exist_ok=True)
bull_file = project_path / "standardized_data" / "processed_bull_data.xlsx"
if bull_file.exists():
    shutil.copy(bull_file, temp_path / "standardized_data" / "processed_bull_data.xlsx")

# 测试加载（应该失败）
generator = MatrixRecommendationGenerator(temp_path)
if not generator.load_data():
    print("\n✓ 正确检测到缺少近交系数文件")
else:
    print("\n✗ 未能检测到缺少文件")

# 清理
shutil.rmtree(temp_path)