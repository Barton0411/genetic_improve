"""调试valid_bulls列的问题"""

import pandas as pd
from pathlib import Path
import ast

# 检查MatrixRecommendationGenerator生成的推荐
project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/强润_2025_09_19_12_43")

# 首先，让我们模拟一下MatrixRecommendationGenerator是否会在某个地方保存中间结果
# 检查是否有推荐文件包含valid_bulls列
print("=" * 60)
print("查找包含valid_bulls的文件")
print("=" * 60)

# 检查standardized_data目录
std_path = project_path / "standardized_data"
if std_path.exists():
    for f in std_path.glob("*.xlsx"):
        try:
            df = pd.read_excel(f)
            cols = [c for c in df.columns if 'valid_bulls' in c.lower()]
            if cols:
                print(f"\n文件: {f.name}")
                print(f"  包含列: {cols}")
                for col in cols:
                    non_empty = df[col].notna().sum()
                    print(f"  {col}: {non_empty}/{len(df)} 非空")
        except:
            pass

# 让我们直接测试ast.literal_eval的行为
print("\n" + "=" * 60)
print("测试ast.literal_eval的行为")
print("=" * 60)

test_cases = [
    ("空列表", "[]"),
    ("包含数据的列表", "[{'bull_id': 'test', 'score': 100}]"),
    ("包含nan的字符串", "[{'bull_id': 'test', 'score': nan}]"),
    ("Python的nan对象", str([{'bull_id': 'test', 'score': float('nan')}]))
]

for name, test_str in test_cases:
    print(f"\n测试: {name}")
    print(f"  输入: {test_str[:100]}")
    try:
        result = ast.literal_eval(test_str)
        print(f"  结果: 成功，得到 {type(result)}")
    except Exception as e:
        print(f"  结果: 失败 - {e}")

# 最后，让我们看看实际load_data的行为
print("\n" + "=" * 60)
print("测试CycleBasedMatcher.load_data")
print("=" * 60)

from core.matching.cycle_based_matcher import CycleBasedMatcher

# 创建matcher实例
matcher = CycleBasedMatcher()

# 尝试加载数据
report_file = project_path / "analysis_results" / "individual_mating_report.xlsx"
bull_file = project_path / "standardized_data" / "processed_bull_data.xlsx"

if report_file.exists() and bull_file.exists():
    print(f"报告文件: {report_file.name}")
    print(f"公牛文件: {bull_file.name}")
    
    # 读取报告文件
    df = pd.read_excel(report_file)
    
    # 检查是否有valid_bulls列
    valid_bulls_cols = [c for c in df.columns if 'valid_bulls' in c]
    print(f"\n报告文件中的valid_bulls列: {valid_bulls_cols}")
    
    if not valid_bulls_cols:
        # 如果没有valid_bulls列，说明加载的是已经分配后的文件
        print("\n注意：这个文件可能是分配后的结果，不包含valid_bulls列")
        print("需要找到分配前的推荐文件")
else:
    print("文件不存在")
