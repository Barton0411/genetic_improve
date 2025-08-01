"""
检查最终生成的矩阵结果
"""

import pandas as pd

file = '/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15/analysis_results/test_debug_matrices.xlsx'

# 检查近交系数
df = pd.read_excel(file, '常规_近交系数', index_col=0)
print('常规_近交系数矩阵:')
print(f'形状: {df.shape}')

# 统计非零值
non_zero_values = []
for col in df.columns:
    mask = df[col] != '0.000%'
    non_zero = df[mask][col]
    non_zero_values.extend(non_zero.tolist())

print(f'非零值数量: {len(non_zero_values)}')
if non_zero_values:
    # 排序找最大值
    non_zero_values.sort()
    print(f'最大值: {non_zero_values[-1]}')
    print(f'前10个非零值: {non_zero_values[:10]}')

# 显示24115的结果
if '24115' in df.index:
    print('\n母牛24115的近交系数:')
    print(df.loc['24115'])

# 检查隐性基因
df = pd.read_excel(file, '常规_隐性基因', index_col=0)
print('\n常规_隐性基因矩阵:')
risk_count = (df == 'Risk').sum().sum()
print(f'Risk数量: {risk_count}')
safe_count = (df == 'Safe').sum().sum()
print(f'Safe数量: {safe_count}')

# 检查后代得分
df = pd.read_excel(file, '常规_后代得分', index_col=0)
print('\n常规_后代得分矩阵:')
print(f'得分范围: {df.min().min()} - {df.max().max()}')