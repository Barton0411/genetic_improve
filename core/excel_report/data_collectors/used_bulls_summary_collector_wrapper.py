"""
Sheet 8数据收集包装器
整合UsedBullsSummaryCollector和图表分组配置
"""

from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def collect_used_bulls_summary_data(analysis_folder: Path) -> dict:
    """
    收集Sheet 8所需的所有数据

    Args:
        analysis_folder: analysis_results文件夹路径

    Returns:
        包含以下键的字典:
        - summary_data: 汇总表数据 (DataFrame)
        - progress_data: 性状进展数据 (DataFrame)
        - trait_columns: 性状列列表
        - year_range: 年份范围列表
        - scatter_data_all: 全部配种记录散点图数据
        - scatter_data_12m: 近12个月配种记录散点图数据
        - chart_groups: 折线图分组配置列表
    """
    try:
        # 1. 使用数据收集器收集原始数据
        from .used_bulls_summary_collector import UsedBullsSummaryCollector

        collector = UsedBullsSummaryCollector(analysis_folder.parent)  # project_path
        raw_data = collector.collect()

        # 2. 获取图表分组配置
        from ..config.trait_chart_groups import get_chart_groups_for_traits

        trait_columns = raw_data.get('trait_columns', [])
        chart_groups = get_chart_groups_for_traits(trait_columns)

        logger.info(f"Sheet 8数据收集完成: {len(trait_columns)}个性状, {len(chart_groups)}个图表组")

        # 3. 合并数据
        result = {
            **raw_data,  # 包含所有原始数据
            'chart_groups': chart_groups  # 添加图表分组配置
        }

        return result

    except Exception as e:
        logger.error(f"收集Sheet 8数据失败: {e}", exc_info=True)
        return {}
