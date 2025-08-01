"""
检查原始近交系数数据
"""

import pandas as pd
from pathlib import Path

project_path = Path('/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15')
files = list(project_path.glob('**/备选公牛_近交系数及隐性基因分析结果_*.xlsx'))
if files:
    file = max(files, key=lambda x: x.stat().st_mtime)
    df = pd.read_excel(file)
    
    print('近交系数数据文件:', file.name)
    print('数据形状:', df.shape)
    print('列名:', df.columns.tolist()[:15])
    
    # 检查后代近交系数
    if '后代近交系数' in df.columns:
        # 找非零值
        mask = df['后代近交系数'] != '0.00%'
        non_zero = df[mask]
        print(f'\n后代近交系数非零记录数: {len(non_zero)}')
        if len(non_zero) > 0:
            print('\n示例记录:')
            sample = non_zero.head(5)
            for _, row in sample.iterrows():
                print(f'  母牛: {row["母牛号"]}, 公牛: {row["备选公牛号"]}, 近交系数: {row["后代近交系数"]}')
                
    # 检查一个特定母牛的所有记录
    test_cow = '24115'
    cow_records = df[df['母牛号'] == test_cow]
    print(f'\n母牛 {test_cow} 的记录数: {len(cow_records)}')
    if len(cow_records) > 0:
        print('前5条记录:')
        for _, row in cow_records.head().iterrows():
            print(f'  公牛: {row["备选公牛号"]}, 近交系数: {row["后代近交系数"]}')
    
    # 检查隐性基因
    print('\n隐性基因列:', [col for col in df.columns if col in ['HH1', 'HH2', 'HH3', 'HH4', 'HH5', 'HH6']])
    
    # 检查HH1的值
    if 'HH1' in df.columns:
        print('\nHH1值分布:')
        print(df['HH1'].value_counts().head())