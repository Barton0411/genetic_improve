"""
育种性状分析数据收集器
收集Sheet 3所需的所有数据
"""

from pathlib import Path
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def collect_traits_data(analysis_folder: Path, project_folder: Path) -> dict:
    """
    收集育种性状分析数据

    Args:
        analysis_folder: 分析结果文件夹路径
        project_folder: 项目文件夹路径

    Returns:
        数据字典，包含：
        - present_summary: 在群母牛年份汇总DataFrame
        - all_summary: 全部母牛年份汇总DataFrame
        - nm_distribution_present: 在群母牛NM$分布DataFrame
        - nm_distribution_all: 全部母牛NM$分布DataFrame
        - tpi_distribution_present: 在群母牛TPI分布DataFrame
        - tpi_distribution_all: 全部母牛TPI分布DataFrame
        - comparison_farms: 对比牧场数据列表（待实现）
    """
    try:
        # 读取关键育种性状分析结果文件
        traits_file = analysis_folder / "关键育种性状分析结果.xlsx"

        if not traits_file.exists():
            logger.warning(f"关键育种性状分析结果文件不存在: {traits_file}")
            return {}

        logger.info(f"读取关键育种性状分析结果: {traits_file}")

        # 读取各个sheet
        with pd.ExcelFile(traits_file) as xls:
            present_summary = pd.read_excel(xls, sheet_name='在群母牛年份汇总')
            all_summary = pd.read_excel(xls, sheet_name='全部母牛年份汇总')
            nm_distribution_present = pd.read_excel(xls, sheet_name='在群母牛NM$分布')
            nm_distribution_all = pd.read_excel(xls, sheet_name='全部母牛NM$分布')
            tpi_distribution_present = pd.read_excel(xls, sheet_name='在群母牛TPI分布')
            tpi_distribution_all = pd.read_excel(xls, sheet_name='全部母牛TPI分布')

        logger.info("✓ 育种性状数据收集完成")

        # 读取明细数据
        detail_file = analysis_folder / "processed_cow_data_key_traits_final.xlsx"
        detail_df = None
        if detail_file.exists():
            detail_df = pd.read_excel(detail_file)
            logger.info(f"✓ 读取育种性状明细数据: {len(detail_df)}行")
        else:
            logger.warning(f"育种性状明细文件不存在: {detail_file}")

        # TODO: 读取对比牧场数据（待实现）
        comparison_farms = []

        return {
            'present_summary': present_summary,
            'all_summary': all_summary,
            'nm_distribution_present': nm_distribution_present,
            'nm_distribution_all': nm_distribution_all,
            'tpi_distribution_present': tpi_distribution_present,
            'tpi_distribution_all': tpi_distribution_all,
            'comparison_farms': comparison_farms,
            'detail_df': detail_df
        }

    except Exception as e:
        logger.error(f"收集育种性状数据失败: {e}", exc_info=True)
        return {}
