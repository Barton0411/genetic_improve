"""
调试近交系数查找逻辑
"""

import pandas as pd
from pathlib import Path

# 加载数据
project_path = Path('/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15')
files = list(project_path.glob('**/备选公牛_近交系数及隐性基因分析结果_*.xlsx'))
file = max(files, key=lambda x: x.stat().st_mtime)
df = pd.read_excel(file)

# 测试查找
test_cow = '24115'
test_bull = '007HO16284'

print(f"查找母牛 {test_cow} 和公牛 {test_bull} 的记录")

# 尝试不同的列名
cow_cols = ['母牛号', 'dam_id', 'cow_id']
bull_cols = ['原始备选公牛号', '备选公牛号', '公牛号', 'sire_id', 'bull_id']

# 找到实际的列名
cow_col = next((col for col in cow_cols if col in df.columns), None)
bull_col = next((col for col in bull_cols if col in df.columns), None)

print(f"\n使用列: 母牛列='{cow_col}', 公牛列='{bull_col}'")

# 测试查找
if cow_col and bull_col:
    # 先看看母牛的所有记录
    cow_records = df[df[cow_col].astype(str) == test_cow]
    print(f"\n母牛 {test_cow} 的记录数: {len(cow_records)}")
    
    if len(cow_records) > 0:
        print(f"该母牛对应的公牛号:")
        for _, row in cow_records.iterrows():
            print(f"  {bull_col}: {row[bull_col]}, 后代近交系数: {row['后代近交系数']}")
    
    # 查找特定配对
    mask = (df[cow_col].astype(str) == test_cow) & (df[bull_col].astype(str) == test_bull)
    matched = df[mask]
    
    print(f"\n配对查找结果: 找到 {len(matched)} 条记录")
    if len(matched) > 0:
        for _, row in matched.iterrows():
            print(f"  后代近交系数: {row['后代近交系数']}")
    else:
        # 检查为什么没找到
        print(f"\n调试信息:")
        print(f"母牛 {test_cow} 存在: {test_cow in df[cow_col].astype(str).values}")
        print(f"公牛 {test_bull} 存在: {test_bull in df[bull_col].astype(str).values}")
        
        # 查看该母牛的原始备选公牛号
        if len(cow_records) > 0:
            print(f"\n该母牛记录中的原始备选公牛号:")
            unique_bulls = cow_records['原始备选公牛号'].unique()
            print(unique_bulls)