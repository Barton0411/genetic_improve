# Excel数据源状态与PPT使用策略

基于示例文件 `/Users/bozhenwang/GeneticImprove/sheet8_2025_10_12_13_13/reports/育种分析综合报告_20251104_180856.xlsx` 与 `core/excel_report` 现有逻辑，对 20 个 Sheet 的规模与用途整理如下。列 “是否动态” 表示数据量会随项目变化；“PPT是否必需” 指该 Sheet 是否需要在 PPT 中展示汇总内容（明细页默认只用于钻取，除非另有需求）。

| Key | Sheet 名称 | 列数 (示例) | 是否动态 | 明细/汇总 | PPT 是否必需 | 说明 |
| --- | ---------- | ----------- | -------- | ---------- | ------------- | ---- |
| farm_info | 牧场基础信息 | 14 | 否 | 汇总 | 是 | 封面、目录、Part2 标题使用；含牧场名、服务人、总头数等固定字段。|
| raw_data | 牧场牛群原始数据 | 54 | 是 | 明细 | 否 | 全量牛只档案（>4k 行），用于统计但不会直接在 PPT 中展示。|
| pedigree_analysis | 系谱识别分析 | 8 | 是 | 汇总 | 是 | 按出生年份统计识别率，作为 Part3 图表主数据。|
| pedigree_detail | 全群母牛系谱识别明细 | 25 | 是 | 明细 | 否 | 不在PPT展示 |
| traits_yearly | 年份汇总与性状进展 | 70 | 是 | 汇总 | 是 | 内含年度头数与 TPI/NM$ 趋势，可绘制折线或对比图。|
| traits_summary | 育种性状明细 | 36 | 是 | 明细 | 否 | 不在PPT展示 |
| traits_index_distribution | 育种指数分布分析 | 12 | 是 | 汇总 | 是 | 提供综合指数区间分布，用于 Part4。|
| traits_tpi | TPI分布分析 | 12 | 是 | 汇总 | 是 | TPI 区间柱状/折线。|
| traits_nm | NM$分布分析 | 12 | 是 | 汇总 | 是 | NM$ 区间柱状/折线。|
| cow_index_rank | 母牛指数排名明细 | 38 | 是 | 明细 | 否 | 不在PPT展示 |
| breeding_genes | 配种记录-隐性基因分析 | 10 | 是 | 汇总 | 是 | 统计不同隐性基因的配次/纯合率，生成饼图或柱图。|
| breeding_inbreeding | 配种记录-近交系数分析 | 4 | 是 | 汇总 | 是 | 近交区间分布，用于 Part6 图表。|
| breeding_detail | 配种记录-隐性基因及近交系数明细 | 57 | 是 | 明细 | 否 | 不在PPT展示 |
| used_bulls_summary | 已用公牛性状汇总 | 18 | 是 | 汇总 | 是 | 按年份统计配次/指数，作为 Part7 已用公牛图表。|
| used_bulls_detail | 已用公牛性状明细 | 19 | 是 | 明细 | 是 | 可提取 TOP 使用公牛列表；需要全部展示，若性状太多或牛太多需要分表或分行 |
| candidate_bulls_rank | 备选公牛排名 | 11 | 是 | 明细 | 是 | 输出优质冻精排名和关键指标，生成备选公牛页。|
| candidate_bulls_genes | 备选公牛-隐性基因分析 | 7 | 是 | 汇总 | 是 | 备选公牛隐性基因风险汇总。|
| candidate_bulls_inbreeding | 备选公牛-近交系数分析 | 12 | 是 | 汇总 | 是 | 备选公牛后代 F 值分布。|
| candidate_bulls_detail | 备选公牛-明细表 | 56 | 是 | 明细 | 否 | 不在PPT展示 |
| mating_results | 个体选配推荐结果 | 2（摘要区块） | 是 | 汇总+明细 | 只展示摘要\汇总部分的 | 包含选配统计、推荐列表，需分页导入 PPT。|

> 注：列数来自 `pandas.parse(..., nrows=5)` 的示例统计，实际数据列可能因模板更新而变化。

## 下一步
1. 在 `DataCollector` 中按照上表继续扩展解析函数，使汇总/明细可分别处理（例如 `get_breeding_summary()` vs `get_breeding_detail()`）。
2. 对标记为 “待确认” 的明细 Sheet（`pedigree_detail`, `candidate_bulls_detail`）请确认是否需要在 PPT 展示全部或部分内容，或仅以统计形式呈现。
3. 在 PPT 构建器里依据 `detail_only` 与 `dynamic` 标记决定是否生成分页幻灯片或显示 “暂无数据”。
