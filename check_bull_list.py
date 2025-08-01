"""
检查公牛列表
"""

import pandas as pd
from pathlib import Path

project_path = Path("/Users/bozhenwang/Documents/GeneticImprove/测试2_2025_07_29_15_15")

# 加载标准化公牛数据
bull_file = project_path / "standardized_data" / "processed_bull_data.xlsx"
bull_data = pd.read_excel(bull_file)

print("=== 公牛列表 ===")
print(f"总数: {len(bull_data)}")
print("\n公牛ID列表:")
for _, bull in bull_data.iterrows():
    print(f"  {bull['bull_id']} - {bull['classification']}")
    
# 检查是否包含风险公牛
risk_bulls = ['001HO09174', '001HO09162', '001HO09154']
print(f"\n风险公牛是否在列表中:")
for rb in risk_bulls:
    exists = rb in bull_data['bull_id'].values
    print(f"  {rb}: {'是' if exists else '否'}")