"""检查公牛数据的列名"""

import pandas as pd
from pathlib import Path

# 公牛数据文件路径
bull_file = Path("/Users/Shared/Files From d.localized/projects/mating/genetic_projects/测试-基因组检测数据上传_2024_12_25_16_14/standardized_data/processed_bull_data.xlsx")

# 读取数据
df = pd.read_excel(bull_file)

print("公牛数据列名:")
for i, col in enumerate(df.columns):
    print(f"{i+1}. {col}")
    
print(f"\n总列数: {len(df.columns)}")
print(f"总行数: {len(df)}")

# 检查是否有类似classification的列
classification_cols = [col for col in df.columns if 'class' in col.lower() or '类' in col or '性控' in str(df[col].iloc[0]) or '常规' in str(df[col].iloc[0])]
if classification_cols:
    print(f"\n可能的分类列: {classification_cols}")
    
# 显示前几行数据
print("\n前3行数据:")
print(df.head(3))