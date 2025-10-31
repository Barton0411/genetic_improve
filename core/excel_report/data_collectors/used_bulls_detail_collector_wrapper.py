"""
Sheet 9数据收集包装器
整合UsedBullsDetailCollector
"""

from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def collect_used_bulls_detail_data(analysis_folder) -> dict:
    """
    收集Sheet 9所需的所有数据

    Args:
        analysis_folder: analysis_results文件夹路径（字符串或Path对象）

    Returns:
        包含以下键的字典:
        - yearly_details: 字典，键为年份，值为该年的公牛明细DataFrame
        - trait_columns: 性状列列表
        - year_range: 年份范围列表（倒序）
    """
    try:
        # 使用数据收集器收集数据
        from .used_bulls_detail_collector import UsedBullsDetailCollector

        # 确保analysis_folder是Path对象
        analysis_path = Path(analysis_folder) if isinstance(analysis_folder, str) else analysis_folder
        collector = UsedBullsDetailCollector(analysis_path.parent)  # project_path
        data = collector.collect()

        logger.info(f"Sheet 9数据收集完成: {len(data.get('year_range', []))}年数据")

        return data

    except Exception as e:
        logger.error(f"收集Sheet 9数据失败: {e}", exc_info=True)
        return {}
