"""
公牛使用分析数据收集器
收集Sheet 8所需的所有数据：已用公牛性状汇总分析

重要更新：
- 从processed_breeding_data.xlsx读取所有配种记录（包括未识别公牛）
- 从processed_mated_bull_traits.xlsx读取性状数据作为查找表
- 左连接确保所有配种记录都显示，即使没有性状
"""

from pathlib import Path
import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def collect_bull_usage_summary_data(analysis_folder: Path) -> dict:
    """
    收集已用公牛性状汇总数据（Sheet 8 + Sheet 9）

    数据源：
    1. processed_breeding_data.xlsx - 所有配种记录（包括未识别公牛）
    2. processed_mated_bull_traits.xlsx - 性状数据（用于左连接）

    Args:
        analysis_folder: 分析结果文件夹路径

    Returns:
        数据字典，包含：
        - breeding_df: 所有配种记录（含性状）
        - trait_columns: 性状列名列表（动态识别）
        - year_type_summary: 表1 - 按年份+类型汇总
        - overall_summary: 表2 - 总体汇总（按公牛）
        - year_bull_summary: 表3 - 按年份+公牛汇总
        - breeding_detail: 配种事件明细（用于Sheet 9）
        - all_years: 数据中的所有年份
    """
    try:
        # 1. 读取配种记录（所有记录，包括未识别的）
        breeding_file = analysis_folder / "processed_breeding_data.xlsx"
        if not breeding_file.exists():
            logger.warning(f"配种记录文件不存在: {breeding_file}")
            return {}

        logger.info(f"读取配种记录数据: {breeding_file}")
        breeding_df = pd.read_excel(breeding_file)

        if breeding_df.empty:
            logger.warning("配种记录数据为空")
            return {}

        logger.info(f"✓ 读取到 {len(breeding_df)} 条配种记录")

        # 2. 读取性状数据（用作查找表）
        traits_file = analysis_folder / "processed_mated_bull_traits.xlsx"
        traits_df = None

        if traits_file.exists():
            logger.info(f"读取性状数据: {traits_file}")
            traits_df = pd.read_excel(traits_file)
            logger.info(f"✓ 读取到 {len(traits_df)} 条性状记录")
        else:
            logger.warning(f"性状文件不存在: {traits_file}，将只统计使用次数")

        # 3. 合并数据：配种记录 左连接 性状数据
        merged_df = _merge_breeding_and_traits(breeding_df, traits_df)
        logger.info(f"✓ 合并后数据: {len(merged_df)} 条")

        # 定义固定列（非性状列）
        fixed_columns = ['耳号', '父号', '冻精编号', '配种日期', '冻精类型', '配种年份']

        # 动态识别性状列
        if traits_df is not None and not traits_df.empty:
            trait_columns = [col for col in merged_df.columns if col not in fixed_columns]
            logger.info(f"✓ 识别到 {len(trait_columns)} 个性状列")
        else:
            trait_columns = []
            logger.info("✓ 无性状数据，仅统计使用次数")

        # 过滤掉冻精编号为空的记录
        df_valid = merged_df[merged_df['冻精编号'].notna() & (merged_df['冻精编号'] != '')].copy()
        logger.info(f"✓ 有效配种记录: {len(df_valid)} 条（冻精编号非空）")

        # 获取所有年份（排序）
        if '配种年份' in df_valid.columns:
            all_years = sorted(df_valid['配种年份'].dropna().unique(), reverse=True)
            logger.info(f"✓ 数据包含年份: {all_years}")
        else:
            logger.warning("配种年份列不存在")
            all_years = []

        # 4. 生成汇总数据
        # 表1: 按年份+类型汇总
        year_type_summary = _summarize_by_year_and_type(df_valid, trait_columns)

        # 表2: 总体汇总（按公牛）
        overall_summary = _summarize_overall(df_valid, trait_columns)

        # 表3: 按年份+公牛汇总
        year_bull_summary = _summarize_by_year_and_bull(df_valid, trait_columns)

        # 配种事件明细（用于Sheet 9）
        breeding_detail = _prepare_breeding_detail(df_valid, trait_columns)

        return {
            'breeding_df': merged_df,
            'trait_columns': trait_columns,
            'year_type_summary': year_type_summary,
            'overall_summary': overall_summary,
            'year_bull_summary': year_bull_summary,
            'breeding_detail': breeding_detail,
            'all_years': all_years
        }

    except Exception as e:
        logger.error(f"收集已用公牛性状汇总数据失败: {e}", exc_info=True)
        return {}


def _merge_breeding_and_traits(breeding_df: pd.DataFrame, traits_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    合并配种记录和性状数据

    Args:
        breeding_df: 配种记录（来自processed_breeding_data.xlsx）
        traits_df: 性状数据（来自processed_mated_bull_traits.xlsx，可选）

    Returns:
        合并后的DataFrame（左连接，保留所有配种记录）
    """
    # 确保必要列存在
    required_cols = ['冻精编号', '配种日期', '冻精类型']
    for col in required_cols:
        if col not in breeding_df.columns:
            logger.warning(f"配种记录缺少列: {col}")

    # 添加配种年份（如果不存在）
    if '配种年份' not in breeding_df.columns and '配种日期' in breeding_df.columns:
        breeding_df['配种年份'] = pd.to_datetime(breeding_df['配种日期'], errors='coerce').dt.year

    # 如果没有性状数据，直接返回配种记录
    if traits_df is None or traits_df.empty:
        return breeding_df.copy()

    # 左连接：基于冻精编号合并
    # 保留配种记录的所有列，添加性状列
    merge_key = '冻精编号'

    # 识别性状列（traits_df中除了固定列的其他列）
    fixed_cols_in_traits = ['耳号', '父号', '冻精编号', '配种日期', '冻精类型', '配种年份']
    trait_cols = [col for col in traits_df.columns if col not in fixed_cols_in_traits]

    # 只取traits_df中的冻精编号和性状列
    traits_lookup = traits_df[['冻精编号'] + trait_cols].drop_duplicates(subset=['冻精编号'])

    # 左连接
    merged = breeding_df.merge(traits_lookup, on=merge_key, how='left', suffixes=('', '_trait'))

    logger.info(f"  合并前: {len(breeding_df)} 条配种记录")
    logger.info(f"  性状查找表: {len(traits_lookup)} 个唯一公牛")
    logger.info(f"  合并后: {len(merged)} 条记录")

    return merged


def _summarize_by_year_and_type(df: pd.DataFrame, trait_columns: list) -> pd.DataFrame:
    """
    表1: 按年份和冻精类型分组汇总（宏观趋势分析）

    Args:
        df: 配种记录数据
        trait_columns: 性状列名列表

    Returns:
        汇总后的DataFrame，包含：使用年份 | 冻精类型 | 使用次数 | 各性状加权平均
    """
    if '配种年份' not in df.columns or '冻精类型' not in df.columns:
        logger.warning("缺少配种年份或冻精类型列，无法按年份+类型汇总")
        return pd.DataFrame()

    # 按配种年份和冻精类型分组
    grouped = df.groupby(['配种年份', '冻精类型'], as_index=False, dropna=False)

    summary_data = []

    for (year, semen_type), group in grouped:
        row = {
            '使用年份': int(year) if pd.notna(year) else '',
            '冻精类型': semen_type if pd.notna(semen_type) else '未知',
            '使用次数': len(group)
        }

        # 计算各性状的加权平均（按使用次数加权）
        for trait in trait_columns:
            if trait in group.columns and pd.api.types.is_numeric_dtype(group[trait]):
                valid_values = group[trait].dropna()
                if len(valid_values) > 0:
                    row[trait] = valid_values.mean()
                else:
                    row[trait] = None
            else:
                row[trait] = None

        summary_data.append(row)

    summary_df = pd.DataFrame(summary_data)

    # 按年份降序、使用次数降序排序
    if not summary_df.empty:
        summary_df = summary_df.sort_values(['使用年份', '使用次数'], ascending=[False, False])

    return summary_df


def _summarize_by_year_and_bull(df: pd.DataFrame, trait_columns: list) -> pd.DataFrame:
    """
    表3: 按年份和公牛分组汇总

    Args:
        df: 配种记录数据
        trait_columns: 性状列名列表

    Returns:
        汇总后的DataFrame，包含：使用年份 | 冻精编号 | 冻精类型 | 使用次数 | 各性状
    """
    if '配种年份' not in df.columns:
        logger.warning("缺少配种年份列，无法按年份+公牛汇总")
        return pd.DataFrame()

    # 按配种年份、冻精编号、冻精类型分组
    grouped = df.groupby(['配种年份', '冻精编号', '冻精类型'], as_index=False, dropna=False)

    summary_data = []

    for (year, naab, semen_type), group in grouped:
        row = {
            '使用年份': int(year) if pd.notna(year) else '',
            '冻精编号': naab if pd.notna(naab) else '',
            '冻精类型': semen_type if pd.notna(semen_type) else '未知',
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
            else:
                row[trait] = None

        summary_data.append(row)

    summary_df = pd.DataFrame(summary_data)

    # 按年份降序、使用次数降序排序
    if not summary_df.empty:
        summary_df = summary_df.sort_values(['使用年份', '使用次数'], ascending=[False, False])

    return summary_df


def _summarize_overall(df: pd.DataFrame, trait_columns: list) -> pd.DataFrame:
    """
    表2: 总体汇总（不分年份，按公牛）

    Args:
        df: 配种记录数据
        trait_columns: 性状列名列表

    Returns:
        汇总后的DataFrame，包含：冻精编号 | 使用次数 | 各性状
    """
    # 按冻精编号分组
    grouped = df.groupby('冻精编号', as_index=False, dropna=False)

    summary_data = []

    for naab, group in grouped:
        row = {
            '冻精编号': naab if pd.notna(naab) else '',
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
            else:
                row[trait] = None

        summary_data.append(row)

    summary_df = pd.DataFrame(summary_data)

    # 按使用次数降序排序
    if not summary_df.empty:
        summary_df = summary_df.sort_values('使用次数', ascending=False)

    return summary_df


def _prepare_breeding_detail(df: pd.DataFrame, trait_columns: list) -> pd.DataFrame:
    """
    准备配种事件明细数据（用于Sheet 9）

    Args:
        df: 配种记录数据（含性状）
        trait_columns: 性状列名列表

    Returns:
        配种明细DataFrame，包含：耳号 | 配种日期 | 冻精编号 | 冻精类型 | 配种年份 | 各性状
        按配种年份和日期排序
    """
    # 选择需要的列
    detail_columns = ['耳号', '配种日期', '冻精编号', '冻精类型', '配种年份'] + trait_columns

    # 确保所有列都存在
    available_columns = [col for col in detail_columns if col in df.columns]

    detail_df = df[available_columns].copy()

    # 按配种年份（降序）和配种日期（降序）排序
    sort_cols = []
    if '配种年份' in detail_df.columns:
        sort_cols.append('配种年份')
    if '配种日期' in detail_df.columns:
        sort_cols.append('配种日期')

    if sort_cols:
        detail_df = detail_df.sort_values(sort_cols, ascending=False)

    return detail_df


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
