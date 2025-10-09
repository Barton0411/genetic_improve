"""测试Sheet 2修改后的功能"""

from pathlib import Path
from core.excel_report.data_collectors.pedigree_collector import collect_pedigree_data

# 测试项目路径
test_project = Path("/Users/bozhenwang/GeneticImprove/ll_2025_10_06_17_13")
analysis_folder = test_project / "分析结果"

print("="*60)
print("测试数据收集...")
print("="*60)

data = collect_pedigree_data(analysis_folder)

print("\n1. 汇总数据:")
print(data['summary'])

print("\n2. 饼图统计数据:")
stats = data['total_stats']
print(f"  在群母牛总数: {stats['total_count']}")
print(f"  父号已识别: {stats['sire_identified']} ({stats['sire_rate']}%)")
print(f"  父号未识别: {stats['sire_unidentified']}")
print(f"  外祖父已识别: {stats['mgs_identified']} ({stats['mgs_rate']}%)")
print(f"  外祖父未识别: {stats['mgs_unidentified']}")
print(f"  外曾外祖父已识别: {stats['mggs_identified']} ({stats['mggs_rate']}%)")
print(f"  外曾外祖父未识别: {stats['mggs_unidentified']}")

print(f"\n3. 在群母牛明细数据: {len(data['detail_active'])}行")
print(f"   前3行预览:")
print(data['detail_active'][['cow_id', '是否在场', 'sire_identified', 'mgs_identified', 'mmgs_identified']].head(3))

print(f"\n4. 全群母牛明细数据: {len(data['detail_all'])}行")
print(f"   前3行预览:")
print(data['detail_all'][['cow_id', '是否在场', 'sire_identified', 'mgs_identified', 'mmgs_identified']].head(3))
print(f"   在场统计: {(data['detail_all']['是否在场'] == '是').sum()}头")
print(f"   离场统计: {(data['detail_all']['是否在场'] == '否').sum()}头")
