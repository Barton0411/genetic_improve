"""
PPT报告工具函数
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def safe_read_excel(file_path: Path, sheet_name: Optional[str] = None) -> Optional[pd.DataFrame]:
    """
    安全地读取Excel文件

    Args:
        file_path: Excel文件路径
        sheet_name: Sheet名称，None表示读取第一个Sheet

    Returns:
        DataFrame或None
    """
    try:
        if not file_path.exists():
            logger.warning(f"文件不存在: {file_path}")
            return None

        if sheet_name:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
        else:
            df = pd.read_excel(file_path)

        logger.info(f"成功读取: {file_path.name} ({len(df)}行)")
        return df

    except Exception as e:
        logger.error(f"读取Excel失败 {file_path}: {e}")
        return None


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    格式化百分比

    Args:
        value: 数值 (0-1)
        decimals: 小数位数

    Returns:
        格式化的百分比字符串
    """
    if pd.isna(value):
        return "-"
    return f"{value * 100:.{decimals}f}%"


def format_number(value: float, decimals: int = 0) -> str:
    """
    格式化数字

    Args:
        value: 数值
        decimals: 小数位数

    Returns:
        格式化的数字字符串
    """
    if pd.isna(value):
        return "-"
    return f"{value:,.{decimals}f}"


def calculate_distribution(data: pd.Series, bins: list) -> Tuple[list, list]:
    """
    计算数据分布

    Args:
        data: 数据Series
        bins: 分段阈值列表

    Returns:
        (bin_labels, counts)
    """
    try:
        counts, bin_edges = np.histogram(data.dropna(), bins=bins)
        bin_labels = []
        for i in range(len(bin_edges) - 1):
            if i == 0:
                bin_labels.append(f"<{bin_edges[i+1]:.0f}")
            elif i == len(bin_edges) - 2:
                bin_labels.append(f"≥{bin_edges[i]:.0f}")
            else:
                bin_labels.append(f"{bin_edges[i]:.0f}-{bin_edges[i+1]:.0f}")

        return bin_labels, counts.tolist()

    except Exception as e:
        logger.error(f"计算分布失败: {e}")
        return [], []


def get_risk_level_color(risk_level: str) -> str:
    """
    根据风险等级返回颜色

    Args:
        risk_level: 风险等级 (safe/low/medium/high)

    Returns:
        十六进制颜色代码
    """
    color_map = {
        'safe': '#70AD47',  # 绿色
        'low': '#FFC000',  # 黄色
        'medium': '#FF6600',  # 橙色
        'high': '#C00000',  # 红色
        'very_high': '#800000',  # 深红
    }
    return color_map.get(risk_level.lower(), '#808080')


def categorize_inbreeding(value: float) -> str:
    """
    近交系数分类

    Args:
        value: 近交系数

    Returns:
        风险等级
    """
    if pd.isna(value):
        return 'unknown'
    if value < 0.03125:
        return 'safe'
    elif value < 0.0625:
        return 'low'
    elif value < 0.125:
        return 'medium'
    else:
        return 'high'


def categorize_gene_risk(value: float) -> str:
    """
    基因风险分类

    Args:
        value: 基因纯合风险

    Returns:
        风险等级
    """
    if pd.isna(value):
        return 'unknown'
    if value < 0.03125:
        return 'safe'
    elif value < 0.0625:
        return 'low'
    elif value < 0.125:
        return 'medium'
    else:
        return 'high'


def get_top_n(df: pd.DataFrame, column: str, n: int = 20, ascending: bool = False) -> pd.DataFrame:
    """
    获取Top N数据

    Args:
        df: 数据DataFrame
        column: 排序列
        n: Top N数量
        ascending: 是否升序

    Returns:
        Top N的DataFrame
    """
    try:
        return df.nlargest(n, column) if not ascending else df.nsmallest(n, column)
    except Exception as e:
        logger.error(f"获取Top N失败: {e}")
        return pd.DataFrame()


def calculate_statistics(df: pd.DataFrame, columns: list) -> dict:
    """
    计算统计信息

    Args:
        df: 数据DataFrame
        columns: 需要统计的列

    Returns:
        统计字典
    """
    stats = {}
    for col in columns:
        if col in df.columns:
            stats[col] = {
                'mean': df[col].mean(),
                'median': df[col].median(),
                'std': df[col].std(),
                'min': df[col].min(),
                'max': df[col].max(),
                'count': df[col].count()
            }
    return stats


def find_excel_report(reports_folder: Path) -> Optional[Path]:
    """
    查找最新的Excel综合报告

    Args:
        reports_folder: 报告文件夹路径

    Returns:
        报告文件路径或None
    """
    try:
        excel_files = list(reports_folder.glob("育种分析综合报告_*.xlsx"))
        if not excel_files:
            logger.warning(f"未找到Excel报告: {reports_folder}")
            return None

        # 按修改时间排序，返回最新的
        latest_file = max(excel_files, key=lambda p: p.stat().st_mtime)
        logger.info(f"找到Excel报告: {latest_file.name}")
        return latest_file

    except Exception as e:
        logger.error(f"查找Excel报告失败: {e}")
        return None
