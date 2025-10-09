"""
立即执行数据合并：将genomic文件的_score列合并到detail文件
"""

import pandas as pd
from pathlib import Path
import shutil
from datetime import datetime

# 测试项目路径
test_project = Path("/Users/bozhenwang/GeneticImprove/ll_2025_10_06_17_13")
detail_path = test_project / "analysis_results" / "processed_cow_data_key_traits_detail.xlsx"
genomic_path = test_project / "analysis_results" / "processed_cow_data_key_traits_scores_genomic.xlsx"

print("="*60)
print("立即执行数据合并")
print("="*60)

# 1. 备份原文件
backup_path = detail_path.parent / f"processed_cow_data_key_traits_detail_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
print(f"\n步骤1: 备份原文件...")
shutil.copy(detail_path, backup_path)
print(f"✓ 备份保存到: {backup_path.name}")

# 2. 读取文件
print(f"\n步骤2: 读取文件...")
df_detail = pd.read_excel(detail_path)
df_genomic = pd.read_excel(genomic_path)
print(f"✓ Detail文件: {len(df_detail)}行, {len(df_detail.columns)}列")
print(f"✓ Genomic文件: {len(df_genomic)}行, {len(df_genomic.columns)}列")

# 3. 提取_score列
print(f"\n步骤3: 提取母牛育种值列...")
score_columns = [col for col in df_genomic.columns if col.endswith('_score') or col.endswith('_score_source')]
print(f"✓ 找到{len(score_columns)}个育种值相关列")
print(f"  示例: {score_columns[:5]}")

# 4. 合并数据
print(f"\n步骤4: 合并数据...")
score_columns_with_id = ['cow_id'] + score_columns
df_scores = df_genomic[score_columns_with_id]
df_merged = df_detail.merge(df_scores, on='cow_id', how='left')
print(f"✓ 合并后: {len(df_merged)}行, {len(df_merged.columns)}列")

# 5. 验证合并结果
print(f"\n步骤5: 验证合并结果...")
print(f"数据示例（前3行）:")
sample_cols = ['cow_id', '是否在场', 'NM$_score', 'TPI_score', 'MILK_score']
print(df_merged[sample_cols].head(3))

print(f"\n非空值统计:")
for col in ['NM$_score', 'TPI_score', 'MILK_score', 'FAT_score', 'PROT_score']:
    if col in df_merged.columns:
        non_null = df_merged[col].notna().sum()
        print(f"  {col}: {non_null}/{len(df_merged)} ({non_null/len(df_merged)*100:.1f}%)")

# 6. 保存合并后的文件
print(f"\n步骤6: 保存合并后的文件...")
df_merged.to_excel(detail_path, index=False, engine='openpyxl')
print(f"✓ 已保存到: {detail_path}")

print("\n" + "="*60)
print("✅ 数据合并完成！")
print("="*60)
print(f"\n现在processed_cow_data_key_traits_detail.xlsx包含:")
print(f"  - 原有列: {len(df_detail.columns)}个")
print(f"  - 新增母牛育种值列: {len(score_columns)}个")
print(f"  - 总计: {len(df_merged.columns)}列")
print(f"\n备份文件: {backup_path.name}")
