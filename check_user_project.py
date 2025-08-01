"""检查用户新项目的数据结构"""

import pandas as pd
from pathlib import Path

# 用户的新项目路径
project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")

print("=== 检查用户项目数据 ===\n")

# 1. 检查analysis_results目录
analysis_dir = project_path / "analysis_results"
if analysis_dir.exists():
    print("1. analysis_results目录文件:")
    for f in analysis_dir.glob("*.xlsx"):
        print(f"   {f.name}")
else:
    print("1. ❌ analysis_results目录不存在")
    
# 2. 检查standardized_data目录
standard_dir = project_path / "standardized_data"
if standard_dir.exists():
    print("\n2. standardized_data目录文件:")
    for f in standard_dir.glob("*.xlsx"):
        print(f"   {f.name}")
        
    # 检查processed_bull_data.xlsx
    bull_file = standard_dir / "processed_bull_data.xlsx"
    if bull_file.exists():
        print("\n3. processed_bull_data.xlsx内容:")
        df = pd.read_excel(bull_file)
        print(f"   列名: {list(df.columns)}")
        print(f"   行数: {len(df)}")
        if len(df) > 0:
            print("   前2行:")
            print(df.head(2))
else:
    print("\n2. ❌ standardized_data目录不存在")
    
# 3. 查找近交系数相关文件
print("\n4. 查找近交系数相关文件:")
if analysis_dir.exists():
    # 查找各种可能的文件名模式
    patterns = [
        "*近交*",
        "*inbreeding*",
        "*隐性基因*",
        "*genetic*defect*",
        "备选公牛*"
    ]
    
    found_files = set()
    for pattern in patterns:
        files = list(analysis_dir.glob(pattern))
        found_files.update(files)
        
    if found_files:
        for f in sorted(found_files):
            print(f"   找到: {f.name}")
            # 检查文件内容
            try:
                df = pd.read_excel(f)
                print(f"      列名: {list(df.columns)[:5]}...")  # 只显示前5个列名
                print(f"      行数: {len(df)}")
            except:
                pass
    else:
        print("   ❌ 未找到近交系数或隐性基因相关文件")