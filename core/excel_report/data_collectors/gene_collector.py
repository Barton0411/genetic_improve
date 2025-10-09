"""
隐性基因分析数据收集器
收集Sheet 5所需的所有数据
TODO: 待实现
"""

from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def collect_gene_data(analysis_folder: Path) -> dict:
    """
    收集隐性基因分析数据

    Args:
        analysis_folder: 分析结果文件夹路径

    Returns:
        数据字典
    """
    logger.warning("gene_collector尚未实现")
    return {}
