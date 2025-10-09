"""
测试数据合并功能
验证genomic文件中的_score列是否能正确合并到detail文件
"""

import pandas as pd
from pathlib import Path

# 测试项目路径
test_project = Path("/Users/bozhenwang/GeneticImprove/ll_2025_10_06_17_13")
detail_path = test_project / "analysis_results" / "processed_cow_data_key_traits_detail.xlsx"
genomic_path = test_project / "analysis_results" / "processed_cow_data_key_traits_scores_genomic.xlsx"

print("="*60)
print("测试数据合并功能")
print("="*60)

# 1. 检查文件是否存在
print("\n步骤1: 检查文件...")
if not detail_path.exists():
    print(f"❌ Detail文件不存在: {detail_path}")
    exit(1)
else:
    print(f"✓ Detail文件存在")

if not genomic_path.exists():
    print(f"❌ Genomic文件不存在: {genomic_path}")
    exit(1)
else:
    print(f"✓ Genomic文件存在")

# 2. 读取文件
print("\n步骤2: 读取文件...")
df_detail = pd.read_excel(detail_path)
df_genomic = pd.read_excel(genomic_path)
print(f"✓ Detail文件: {len(df_detail)}行, {len(df_detail.columns)}列")
print(f"✓ Genomic文件: {len(df_genomic)}行, {len(df_genomic.columns)}列")

# 3. 检查detail文件中是否有_score列
print("\n步骤3: 检查detail文件...")
score_cols_in_detail = [col for col in df_detail.columns if col.endswith('_score')]
print(f"Detail文件中的_score列: {len(score_cols_in_detail)}个")

if score_cols_in_detail:
    print("✅ Detail文件已包含_score列（数据合并已完成）")
    print("示例列:", score_cols_in_detail[:5])

    # 检查数据
    print("\n数据示例（前3行）:")
    sample_cols = ['cow_id', 'NM$_score', 'TPI_score', 'MILK_score']
    available_cols = [col for col in sample_cols if col in df_detail.columns]
    print(df_detail[available_cols].head(3))

    # 统计非空值
    print("\n非空值统计:")
    for col in ['NM$_score', 'TPI_score', 'MILK_score']:
        if col in df_detail.columns:
            non_null_count = df_detail[col].notna().sum()
            print(f"  {col}: {non_null_count}/{len(df_detail)} ({non_null_count/len(df_detail)*100:.1f}%)")
else:
    print("❌ Detail文件不包含_score列")
    print("\n需要手动执行合并测试...")

    # 4. 模拟合并过程
    print("\n步骤4: 模拟合并...")
    score_columns = [col for col in df_genomic.columns if col.endswith('_score') or col.endswith('_score_source')]
    print(f"Genomic文件中的_score相关列: {len(score_columns)}个")
    print("示例列:", score_columns[:10])

    score_columns_with_id = ['cow_id'] + score_columns
    df_scores = df_genomic[score_columns_with_id]

    # 合并
    df_merged = df_detail.merge(df_scores, on='cow_id', how='left')
    print(f"✓ 合并后: {len(df_merged)}行, {len(df_merged.columns)}列")

    # 检查合并结果
    print("\n合并后的数据示例（前3行）:")
    sample_cols = ['cow_id', 'NM$_score', 'TPI_score', 'MILK_score']
    available_cols = [col for col in sample_cols if col in df_merged.columns]
    print(df_merged[available_cols].head(3))

    # 统计非空值
    print("\n非空值统计:")
    for col in ['NM$_score', 'TPI_score', 'MILK_score']:
        if col in df_merged.columns:
            non_null_count = df_merged[col].notna().sum()
            print(f"  {col}: {non_null_count}/{len(df_merged)} ({non_null_count/len(df_merged)*100:.1f}%)")

    print("\n✅ 合并测试成功！")
    print("\n提示: 请在主程序中运行'关键育种性状分析'功能，")
    print("     数据合并将自动执行并保存到detail文件中。")

print("\n" + "="*60)
print("测试完成")
print("="*60)
