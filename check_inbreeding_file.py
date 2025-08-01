"""检查近交系数文件的详细内容"""

import pandas as pd
from pathlib import Path

# 用户的近交系数文件
file_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15/analysis_results/备选公牛_近交系数及隐性基因分析结果_20250729_165444.xlsx")

if file_path.exists():
    df = pd.read_excel(file_path)
    print("文件列名:")
    for i, col in enumerate(df.columns):
        print(f"{i+1}. {col}")
        
    print(f"\n总列数: {len(df.columns)}")
    print(f"总行数: {len(df)}")
    
    # 检查是否有近交系数相关列
    print("\n可能的近交系数列:")
    for col in df.columns:
        if '近交' in col or 'inbreed' in col.lower() or '系数' in col:
            print(f"  - {col}")
            
    # 检查是否有隐性基因相关列
    print("\n可能的隐性基因列:")
    gene_cols = []
    for col in df.columns:
        if any(gene in col for gene in ['HH', 'MW', 'BLAD', 'CVM', '隐性', 'defect', 'gene']):
            gene_cols.append(col)
            print(f"  - {col}")
            
    # 显示前2行数据
    print("\n前2行数据:")
    print(df[df.columns[:10]].head(2))  # 只显示前10列