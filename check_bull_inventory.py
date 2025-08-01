"""检查公牛库存数据"""

import pandas as pd
from pathlib import Path

# 用户项目路径
bull_file = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15/standardized_data/processed_bull_data.xlsx")

if bull_file.exists():
    df = pd.read_excel(bull_file)
    print("公牛数据文件内容:")
    print(df)
    
    print("\n支数列的数据类型:", df['支数'].dtype if '支数' in df.columns else "无支数列")
    
    # 检查是否有其他可能的列名
    print("\n所有列名:", list(df.columns))