"""
配种记录-近交系数分析数据收集器 v1.2
收集Sheet 6所需的所有数据：配种记录-近交系数分析
"""

from pathlib import Path
import logging
from datetime import datetime, timedelta
import pandas as pd
import glob

logger = logging.getLogger(__name__)


def collect_breeding_inbreeding_data(analysis_folder: Path) -> dict:
    """
    收集配种记录中的近交系数分析数据 (Sheet 6 v1.2)

    Args:
        analysis_folder: 分析结果文件夹路径

    Returns:
        数据字典:
        {
            'all_years_distribution': {  # 全部年份近交系数分布
                'intervals': ['< 3.125%', '3.125% - 6.25%', '6.25% - 12.5%', '> 12.5%'],
                'counts': [856, 285, 98, 11],
                'ratios': [0.685, 0.228, 0.078, 0.009],
                'risk_levels': ['低', '中', '高', '极高'],
                'total': 1250
            },
            'recent_12m_distribution': {...},  # 近12个月分布（格式同上）
            'date_range': {               # 近12个月的日期范围
                'start': '2023-10-10',
                'end': '2024-10-10'
            },
            'yearly_trend': [  # 按年份趋势
                {
                    'year': 2020,
                    'total_count': 245,
                    'avg_inbreeding': 0.0482,
                    'high_risk_count': 28,
                    'high_risk_ratio': 0.114
                },
                ...
            ]
        }
    """
    try:
        # 1. 查找最新的已配公牛分析结果文件
        pattern = str(analysis_folder / "已配公牛_近交系数及隐性基因分析结果_*.xlsx")
        files = glob.glob(pattern)

        if not files:
            logger.warning(f"未找到已配公牛分析结果文件: {pattern}")
            return {}

        # 按文件名时间戳排序
        latest_file = max(files, key=lambda x: Path(x).name)
        logger.info(f"读取文件: {latest_file}")

        # 2. 读取数据
        df = pd.read_excel(latest_file)

        # 确保有必要的列
        if '后代近交系数' not in df.columns:
            logger.warning("文件中缺少'后代近交系数'列")
            return {}

        if '配种日期' not in df.columns:
            logger.warning("文件中缺少'配种日期'列")
            return {}

        # 转换配种日期为datetime类型
        df['配种日期'] = pd.to_datetime(df['配种日期'], errors='coerce')

        # 转换后代近交系数为float（去除百分号）
        df['后代近交系数_float'] = df['后代近交系数'].apply(_parse_percentage)

        # 3. 统计全部年份的分布
        all_years_distribution = _analyze_inbreeding_distribution(df)

        # 4. 筛选近12个月的数据
        today = datetime.now()
        twelve_months_ago = today - timedelta(days=365)
        recent_df = df[df['配种日期'] >= twelve_months_ago].copy()

        # 5. 统计近12个月的分布
        recent_12m_distribution = _analyze_inbreeding_distribution(recent_df)

        # 6. 计算日期范围
        if len(recent_df) > 0 and recent_df['配种日期'].notna().any():
            min_date = recent_df['配种日期'].min()
            max_date = recent_df['配种日期'].max()
            date_range = {
                'start': min_date.strftime('%Y-%m-%d') if pd.notna(min_date) else '',
                'end': max_date.strftime('%Y-%m-%d') if pd.notna(max_date) else ''
            }
        else:
            date_range = {'start': '', 'end': ''}

        # 7. 按年份统计趋势
        yearly_trend = _analyze_yearly_trend(df)

        return {
            'all_years_distribution': all_years_distribution,
            'recent_12m_distribution': recent_12m_distribution,
            'date_range': date_range,
            'yearly_trend': yearly_trend
        }

    except Exception as e:
        logger.error(f"收集近交系数数据时发生错误: {e}", exc_info=True)
        return {}


def _parse_percentage(value) -> float:
    """
    解析百分比字符串为float

    Args:
        value: 百分比字符串（如'3.54%'）或数字

    Returns:
        float值（如0.0354）
    """
    try:
        if pd.isna(value):
            return 0.0
        if isinstance(value, str):
            # 去除百分号并转换
            return float(value.replace('%', '')) / 100.0
        return float(value)
    except:
        return 0.0


def _analyze_inbreeding_distribution(df: pd.DataFrame) -> dict:
    """
    分析近交系数分布

    Args:
        df: 配种记录DataFrame（必须包含'后代近交系数_float'列）

    Returns:
        分布数据字典
    """
    total_count = len(df)
    if total_count == 0:
        return {
            'intervals': ['< 3.125%', '3.125% - 6.25%', '6.25% - 12.5%', '> 12.5%'],
            'counts': [0, 0, 0, 0],
            'ratios': [0.0, 0.0, 0.0, 0.0],
            'risk_levels': ['低', '中', '高', '极高'],
            'total': 0
        }

    # 统计各区间数量
    count_low = len(df[df['后代近交系数_float'] < 0.03125])
    count_medium = len(df[(df['后代近交系数_float'] >= 0.03125) & (df['后代近交系数_float'] < 0.0625)])
    count_high = len(df[(df['后代近交系数_float'] >= 0.0625) & (df['后代近交系数_float'] < 0.125)])
    count_extreme = len(df[df['后代近交系数_float'] >= 0.125])

    # 计算占比
    ratio_low = count_low / total_count if total_count > 0 else 0
    ratio_medium = count_medium / total_count if total_count > 0 else 0
    ratio_high = count_high / total_count if total_count > 0 else 0
    ratio_extreme = count_extreme / total_count if total_count > 0 else 0

    return {
        'intervals': ['< 3.125%', '3.125% - 6.25%', '6.25% - 12.5%', '> 12.5%'],
        'counts': [count_low, count_medium, count_high, count_extreme],
        'ratios': [ratio_low, ratio_medium, ratio_high, ratio_extreme],
        'risk_levels': ['低', '中', '高', '极高'],
        'total': total_count
    }


def _analyze_yearly_trend(df: pd.DataFrame) -> list:
    """
    分析按年份的近交系数趋势

    Args:
        df: 配种记录DataFrame

    Returns:
        年份趋势列表，包含：
        - year: 年份
        - total_count: 总配种次数
        - high_risk_count: 高风险配种数（6.25%-12.5%）
        - high_risk_ratio: 高风险占比
        - extreme_risk_count: 极高风险配种数（>12.5%）
        - extreme_risk_ratio: 极高风险占比
    """
    # 提取年份
    df_with_year = df[df['配种日期'].notna()].copy()
    df_with_year['year'] = df_with_year['配种日期'].dt.year

    # 按年份分组统计
    yearly_stats = []
    for year in sorted(df_with_year['year'].unique()):
        year_df = df_with_year[df_with_year['year'] == year]
        total_count = len(year_df)

        # 统计高风险配种数（6.25%-12.5%）
        high_risk_count = len(year_df[(year_df['后代近交系数_float'] >= 0.0625) &
                                      (year_df['后代近交系数_float'] < 0.125)])
        high_risk_ratio = high_risk_count / total_count if total_count > 0 else 0

        # 统计极高风险配种数（>12.5%）
        extreme_risk_count = len(year_df[year_df['后代近交系数_float'] >= 0.125])
        extreme_risk_ratio = extreme_risk_count / total_count if total_count > 0 else 0

        yearly_stats.append({
            'year': int(year),
            'total_count': total_count,
            'high_risk_count': high_risk_count,
            'high_risk_ratio': high_risk_ratio,
            'extreme_risk_count': extreme_risk_count,
            'extreme_risk_ratio': extreme_risk_ratio
        })

    return yearly_stats


# 保留旧函数名以兼容
def collect_inbreeding_data(analysis_folder: Path) -> dict:
    """
    近交系数分析数据收集（v1.1兼容接口）
    重定向到v1.2的collect_breeding_inbreeding_data
    """
    return collect_breeding_inbreeding_data(analysis_folder)
