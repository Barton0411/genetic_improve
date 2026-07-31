"""个体选配的项目范围策略。

个体选配依赖单个牧场自己的备选公牛及冻精库存，不能把多个牧场作为
一个批次共用同一套公牛执行。牧场组子项目仍然只代表一个牧场，因此
允许用户进入子项目后单独选配。
"""

from __future__ import annotations


def individual_mating_restriction_reason(
    *,
    is_group_project: bool,
    is_merged_project: bool,
    farm_count: int = 0,
) -> str:
    """返回禁止个体选配的中文原因；空字符串表示允许。"""

    if is_group_project:
        return (
            "牧场组批量任务只处理育种分析，不执行个体选配，也不生成"
            "个体选配报告。\n\n"
            "每个牧场使用的备选公牛和冻精库存不同。请在“育种项目管理”"
            "中打开对应的单牧场子项目，再单独执行个体选配。"
        )
    if is_merged_project or int(farm_count or 0) > 1:
        return (
            "个体选配仅支持单个牧场，不能在多牧场合并项目中执行。\n\n"
            "请创建或打开单牧场项目，并使用该牧场自己的备选公牛和"
            "冻精库存进行选配。"
        )
    return ""
