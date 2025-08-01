"""检查是否有冻精支数信息"""

import pandas as pd
from pathlib import Path

# 检查standardized_data目录
standard_dir = Path("/Users/Shared/Files From d.localized/projects/mating/genetic_projects/测试-基因组检测数据上传_2024_12_25_16_14/standardized_data")
print(f"standardized_data目录文件:")
for f in standard_dir.glob("*.xlsx"):
    print(f"  {f.name}")

# 检查analysis_results目录
analysis_dir = Path("/Users/Shared/Files From d.localized/projects/mating/genetic_projects/测试-基因组检测数据上传_2024_12_25_16_14/analysis_results")
print(f"\nanalysis_results目录文件:")
for f in analysis_dir.glob("*冻精*.xlsx"):
    print(f"  {f.name}")
for f in analysis_dir.glob("*semen*.xlsx"):
    print(f"  {f.name}")
for f in analysis_dir.glob("*支数*.xlsx"):
    print(f"  {f.name}")
    
# 检查是否有bull_straw_settings.xlsx
straw_file = standard_dir / "bull_straw_settings.xlsx"
if straw_file.exists():
    print(f"\n找到bull_straw_settings.xlsx:")
    df = pd.read_excel(straw_file)
    print(f"列名: {list(df.columns)}")
    print(f"前3行:")
    print(df.head(3))