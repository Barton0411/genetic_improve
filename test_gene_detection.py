"""
测试隐性基因风险检测
"""

import pandas as pd
from pathlib import Path

# 加载数据
project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")
files = list(project_path.glob("**/备选公牛_近交系数及隐性基因分析结果_*.xlsx"))
latest_file = max(files, key=lambda x: x.stat().st_mtime)
df = pd.read_excel(latest_file)

print("=== 隐性基因状态分析 ===\n")

# 检查所有隐性基因列的值
defect_genes = ['HH1', 'HH2', 'HH3', 'HH4', 'HH5', 'HH6', 
               'MW', 'BLAD', 'CVM', 'DUMPS', 'Citrullinemia',
               'Brachyspina', 'Factor XI', 'Mulefoot']

for gene in defect_genes:
    if gene in df.columns:
        print(f"\n{gene} 列的唯一值:")
        unique_values = df[gene].value_counts()
        for value, count in unique_values.items():
            print(f"  '{value}': {count}")
        
        # 检查是否有风险值
        risk_values = ['NO safe', 'unsafe', 'tc', 'TC', 'no safe', 'risk', 'Risk']
        risk_count = 0
        for risk_val in risk_values:
            mask = df[gene].astype(str).str.lower() == risk_val.lower()
            risk_count += mask.sum()
        
        if risk_count > 0:
            print(f"  ⚠️ 发现 {risk_count} 个风险记录")
            
# 检查特定配对的隐性基因状态
print("\n\n=== 示例配对检查 ===")
sample_cow = '24115'
sample_bull = '007HO16284'

mask = (df['母牛号'].astype(str) == sample_cow) & (df['原始备选公牛号'].astype(str) == sample_bull)
if mask.any():
    row = df[mask].iloc[0]
    print(f"母牛 {sample_cow} x 公牛 {sample_bull}:")
    print(f"  后代近交系数: {row['后代近交系数']}")
    
    # 检查各隐性基因
    for gene in ['HH1', 'HH2', 'HH3', 'HH4', 'HH5', 'HH6']:
        if gene in row:
            print(f"  {gene}: {row[gene]}")
else:
    print(f"未找到配对 {sample_cow} x {sample_bull}")