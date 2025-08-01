"""检查近交系数文件的列名"""

import pandas as pd
from pathlib import Path

# 检查近交系数文件
inbreeding_file = Path("/Users/Shared/Files From d.localized/projects/mating/genetic_projects/测试-基因组检测数据上传_2024_12_25_16_14/analysis_results/candidate_inbreeding_coefficients.xlsx")

if inbreeding_file.exists():
    df = pd.read_excel(inbreeding_file)
    print("近交系数文件列名:")
    print(list(df.columns))
    print(f"\n前3行数据:")
    print(df.head(3))
    
# 检查隐性基因文件
defect_file = Path("/Users/Shared/Files From d.localized/projects/mating/genetic_projects/测试-基因组检测数据上传_2024_12_25_16_14/analysis_results/隐性基因筛查结果_备选公牛.xlsx")

if defect_file.exists():
    df = pd.read_excel(defect_file)
    print("\n\n隐性基因筛查文件列名:")
    print(list(df.columns))
    print(f"\n前3行数据:")
    print(df.head(3))