"""
公牛使用分析数据收集器
收集Sheet 8所需的所有数据：已用公牛性状汇总分析
"""

from pathlib import Path
import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def collect_bull_usage_summary_data(analysis_folder: Path) -> dict:
    """
    收集已用公牛性状汇总数据（Sheet 8）

    从processed_mated_bull_traits.xlsx读取数据，按公牛分组汇总

    Args:
        analysis_folder: 分析结果文件夹路径

    Returns:
        数据字典，包含：
        - mated_bull_traits_df: 原始已配公牛性状数据
        - trait_columns: 性状列名列表（动态识别）
        - yearly_summary: 按年份和公牛汇总的数据
        - overall_summary: 总体汇总数据
        - recent_5_years: 过去5年的数据
    """
    try:
        # 读取processed_mated_bull_traits.xlsx
        mated_traits_file = analysis_folder / "processed_mated_bull_traits.xlsx"

        if not mated_traits_file.exists():
            logger.warning(f"已配公牛性状文件不存在: {mated_traits_file}")
            return {}

        logger.info(f"读取已配公牛性状数据: {mated_traits_file}")
        df = pd.read_excel(mated_traits_file)

        if df.empty:
            logger.warning("已配公牛性状数据为空")
            return {}

        logger.info(f"✓ 读取到 {len(df)} 条配种记录")

        # 定义固定列（非性状列）
        fixed_columns = ['耳号', '父号', '冻精编号', '配种日期', '冻精类型', '配种年份']

        # 动态识别性状列（所有非固定列）
        trait_columns = [col for col in df.columns if col not in fixed_columns]
        logger.info(f"✓ 识别到 {len(trait_columns)} 个性状列: {trait_columns}")

        # 确保配种年份列存在且为数值类型
        if '配种年份' not in df.columns:
            logger.warning("配种年份列不存在，无法进行年份汇总")
            return {}

        # 过滤掉冻精编号为空的记录
        df_valid = df[df['冻精编号'].notna() & (df['冻精编号'] != '')].copy()
        logger.info(f"✓ 过滤后有效记录: {len(df_valid)} 条（冻精编号非空）")

        # 按公牛和年份分组汇总
        yearly_summary = _summarize_by_year_and_bull(df_valid, trait_columns)

        # 总体汇总（不分年份）
        overall_summary = _summarize_overall(df_valid, trait_columns)

        # 获取过去5年的数据
        current_year = datetime.now().year
        recent_5_years_data = df_valid[df_valid['配种年份'] >= (current_year - 5)].copy()
        logger.info(f"✓ 过去5年（{current_year - 5}-{current_year}）数据: {len(recent_5_years_data)} 条")

        # 过去5年的汇总
        recent_5_years_summary = _summarize_overall(recent_5_years_data, trait_columns)

        return {
            'mated_bull_traits_df': df,
            'trait_columns': trait_columns,
            'yearly_summary': yearly_summary,
            'overall_summary': overall_summary,
            'recent_5_years_data': recent_5_years_data,
            'recent_5_years_summary': recent_5_years_summary,
            'current_year': current_year
        }

    except Exception as e:
        logger.error(f"收集已用公牛性状汇总数据失败: {e}", exc_info=True)
        return {}


def _summarize_by_year_and_bull(df: pd.DataFrame, trait_columns: list) -> pd.DataFrame:
    """
    按年份和公牛分组汇总

    Args:
        df: 已配公牛性状数据
        trait_columns: 性状列名列表

    Returns:
        汇总后的DataFrame
    """
    # 按配种年份和冻精编号分组
    grouped = df.groupby(['配种年份', '冻精编号'], as_index=False)

    # 汇总数据
    summary_data = []

    for (year, naab), group in grouped:
        row = {
            '配种年份': year,
            '冻精编号': naab,
            '使用次数': len(group)
        }

        # 计算各性状的均值（只统计非空值）
        for trait in trait_columns:
            if trait in group.columns:
                # 只对数值类型的列计算均值
                if pd.api.types.is_numeric_dtype(group[trait]):
                    valid_values = group[trait].dropna()
                    if len(valid_values) > 0:
                        row[trait] = valid_values.mean()
                    else:
                        row[trait] = None
                else:
                    # 非数值列，取第一个非空值
                    non_null = group[trait].dropna()
                    if len(non_null) > 0:
                        row[trait] = non_null.iloc[0]
                    else:
                        row[trait] = None

        summary_data.append(row)

    summary_df = pd.DataFrame(summary_data)

    # 按年份降序、使用次数降序排序
    if not summary_df.empty:
        summary_df = summary_df.sort_values(['配种年份', '使用次数'], ascending=[False, False])

    return summary_df


def _summarize_overall(df: pd.DataFrame, trait_columns: list) -> pd.DataFrame:
    """
    总体汇总（不分年份）

    Args:
        df: 已配公牛性状数据
        trait_columns: 性状列名列表

    Returns:
        汇总后的DataFrame
    """
    # 按冻精编号分组
    grouped = df.groupby('冻精编号', as_index=False)

    summary_data = []

    for naab, group in grouped:
        row = {
            '冻精编号': naab,
            '使用次数': len(group)
        }

        # 计算各性状的均值
        for trait in trait_columns:
            if trait in group.columns:
                if pd.api.types.is_numeric_dtype(group[trait]):
                    valid_values = group[trait].dropna()
                    if len(valid_values) > 0:
                        row[trait] = valid_values.mean()
                    else:
                        row[trait] = None
                else:
                    non_null = group[trait].dropna()
                    if len(non_null) > 0:
                        row[trait] = non_null.iloc[0]
                    else:
                        row[trait] = None

        summary_data.append(row)

    summary_df = pd.DataFrame(summary_data)

    # 按使用次数降序排序
    if not summary_df.empty:
        summary_df = summary_df.sort_values('使用次数', ascending=False)

    return summary_df


# 保留旧函数名以保持兼容性
def collect_bull_usage_data(analysis_folder: Path) -> dict:
    """
    收集公牛使用分析数据（兼容旧版本）

    Args:
        analysis_folder: 分析结果文件夹路径

    Returns:
        数据字典
    """
    return collect_bull_usage_summary_data(analysis_folder)
