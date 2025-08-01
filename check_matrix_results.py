"""
检查生成的矩阵结果
"""

import pandas as pd

# 检查生成的矩阵
file = '/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15/analysis_results/test_mating_matrices.xlsx'

# 查看近交系数矩阵
df = pd.read_excel(file, '常规_近交系数', index_col=0)
print('常规_近交系数矩阵统计:')
print(f'形状: {df.shape}')

# 统计非零值
non_zero_count = 0
for col in df.columns:
    mask = df[col] != '0.000%'
    non_zero = df[mask][col]
    if len(non_zero) > 0:
        non_zero_count += len(non_zero)
        print(f'\n{col} 有 {len(non_zero)} 个非零值')
        print(f'示例: {list(non_zero.head(3))}')
        
print(f'\n总计非零值: {non_zero_count}')

# 查看隐性基因矩阵
df = pd.read_excel(file, '常规_隐性基因', index_col=0)
print('\n\n常规_隐性基因矩阵统计:')
risk_count = (df == 'Risk').sum().sum()
safe_count = (df == 'Safe').sum().sum()
print(f'Risk数量: {risk_count}')
print(f'Safe数量: {safe_count}')

# 检查是否有其他值
unique_values = set()
for col in df.columns:
    unique_values.update(df[col].unique())
print(f'所有唯一值: {unique_values}')