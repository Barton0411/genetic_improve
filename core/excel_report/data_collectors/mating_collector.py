"""
个体选配结果数据收集器
收集Sheet 11所需的所有数据
"""

from pathlib import Path
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def collect_mating_data(analysis_folder) -> dict:
    """
    收集个体选配结果数据

    Args:
        analysis_folder: 分析结果文件夹路径（字符串或Path对象）

    Returns:
        数据字典，包含:
        - mating_details: 选配推荐明细DataFrame
        - mating_summary: 选配统计摘要
    """
    # 确保是Path对象
    analysis_path = Path(analysis_folder) if isinstance(analysis_folder, str) else analysis_folder

    # 选配数据是可选的
    mating_file = analysis_path / "个体选配报告.xlsx"
    if not mating_file.exists():
        logger.info("个体选配报告不存在，跳过Sheet 11")
        return None

    try:
        logger.info("开始收集个体选配数据...")

        # 读取选配结果
        df = pd.read_excel(mating_file, sheet_name="选配结果")
        logger.info(f"读取到 {len(df)} 条选配记录")

        # 收集统计摘要
        summary = _calculate_mating_summary(df)

        result = {
            'mating_details': df,
            'mating_summary': summary
        }

        logger.info("✓ 个体选配数据收集完成")
        return result

    except Exception as e:
        logger.error(f"收集个体选配数据失败: {e}", exc_info=True)
        return None


def _calculate_mating_summary(df: pd.DataFrame) -> dict:
    """
    计算选配统计摘要

    Args:
        df: 选配明细DataFrame

    Returns:
        统计摘要字典
    """
    summary = {
        'total_cows': len(df),
        'has_sexed_recommendation': (df['1选性控'].notna()).sum(),
        'has_regular_recommendation': (df['1选常规'].notna()).sum(),
        'groups': {},
        'parity_distribution': {}
    }

    # 按分组统计
    if '分组' in df.columns:
        group_stats = df.groupby('分组').agg({
            '母牛号': 'count',
            '1选性控': lambda x: x.notna().sum(),
            '1选常规': lambda x: x.notna().sum()
        }).to_dict('index')

        summary['groups'] = {
            group: {
                'count': stats['母牛号'],
                'sexed_count': stats['1选性控'],
                'regular_count': stats['1选常规']
            }
            for group, stats in group_stats.items()
        }

    # 按胎次统计
    if '胎次' in df.columns:
        parity_stats = df.groupby('胎次').agg({
            '母牛号': 'count',
            '1选性控': lambda x: x.notna().sum(),
            '1选常规': lambda x: x.notna().sum()
        }).to_dict('index')

        summary['parity_distribution'] = {
            parity: {
                'count': stats['母牛号'],
                'sexed_count': stats['1选性控'],
                'regular_count': stats['1选常规']
            }
            for parity, stats in parity_stats.items()
        }

    return summary
