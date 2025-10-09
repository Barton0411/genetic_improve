"""
母牛指数数据收集器
收集Sheet 4所需的所有数据
"""

from pathlib import Path
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def collect_cow_index_data(analysis_folder: Path, project_folder: Path = None) -> dict:
    """
    收集母牛指数分析数据

    Args:
        analysis_folder: 分析结果文件夹路径
        project_folder: 项目文件夹路径（用于读取母牛基础数据）

    Returns:
        数据字典，包含：
        - distribution_present: 在群母牛指数分布DataFrame
        - distribution_all: 全部母牛指数分布DataFrame
        - detail_df: 指数明细数据DataFrame
    """
    analysis_folder = Path(analysis_folder)
    if project_folder:
        project_folder = Path(project_folder)

    try:
        logger.info("收集母牛指数数据...")

        # 读取母牛指数得分文件（从analysis_results读取）
        index_file = analysis_folder / "processed_index_cow_index_scores.xlsx"

        if not index_file.exists():
            logger.warning(f"母牛指数文件不存在: {index_file}")
            return _get_empty_data()

        df_index = pd.read_excel(index_file)
        logger.info(f"读取到 {len(df_index)} 条母牛指数数据")

        # 读取母牛基础数据（获取是否在场信息）
        cow_data_file = None
        if project_folder:
            cow_data_file = project_folder / "standardized_data" / "processed_cow_data.xlsx"

        # 检查指数文件中是否已经包含必要字段
        if '是否在场' in df_index.columns and 'sex' in df_index.columns:
            # 文件中已包含必要字段，直接使用
            df_merged = df_index.copy()
            logger.info("指数文件中已包含是否在场和性别信息")
        elif cow_data_file and cow_data_file.exists():
            # 从母牛基础数据文件合并
            df_cow = pd.read_excel(cow_data_file)

            # 合并数据
            df_merged = df_index.merge(
                df_cow[['cow_id', '是否在场', 'sex']],
                on='cow_id',
                how='left'
            )

            # 填充缺失值（对于在指数文件中但不在基础数据中的牛）
            df_merged['是否在场'].fillna('是', inplace=True)
            df_merged['sex'].fillna('母', inplace=True)
            logger.info(f"从母牛基础数据合并了 {len(df_merged)} 条记录")
        else:
            # 都没有，使用默认值
            logger.warning("母牛基础数据文件不存在，默认所有牛只在场")
            df_merged = df_index.copy()
            df_merged['是否在场'] = '是'
            df_merged['sex'] = '母'

        # 自动识别指数列
        # 优先级:
        # 1. 任何以_index结尾的列（如测试_index、NM_index等）
        # 2. Index Score
        # 3. Combine Index Score
        index_columns = [col for col in df_merged.columns if col.endswith('_index')]

        if index_columns:
            # 使用第一个找到的_index列
            index_col = index_columns[0]
            df_merged['index_score'] = df_merged[index_col]
            logger.info(f"使用指数列: {index_col}")

            if len(index_columns) > 1:
                logger.warning(f"发现多个指数列: {index_columns}，使用第一个: {index_col}")
        elif 'Index Score' in df_merged.columns:
            df_merged['index_score'] = df_merged['Index Score']
            logger.info("使用指数列: Index Score")
        elif 'Combine Index Score' in df_merged.columns:
            df_merged['index_score'] = df_merged['Combine Index Score']
            logger.info("使用指数列: Combine Index Score")
        else:
            logger.error("未找到指数得分列（*_index/Index Score/Combine Index Score）")
            return _get_empty_data()

        # 计算分布数据
        distribution_present = _calculate_distribution(
            df_merged[df_merged['是否在场'] == '是'],
            'index_score'
        )

        distribution_all = _calculate_distribution(
            df_merged[df_merged['sex'] == '母'],
            'index_score'
        )

        logger.info("✓ 母牛指数数据收集完成")

        return {
            'distribution_present': distribution_present,
            'distribution_all': distribution_all,
            'detail_df': df_merged
        }

    except Exception as e:
        logger.error(f"收集母牛指数数据失败: {e}", exc_info=True)
        return _get_empty_data()


def _calculate_distribution(df: pd.DataFrame, score_column: str) -> pd.DataFrame:
    """
    计算指数分布统计（固定9组，以0为基准，整数步长）

    Args:
        df: 数据DataFrame
        score_column: 指数列名

    Returns:
        分布统计DataFrame
    """
    if df.empty or score_column not in df.columns:
        return pd.DataFrame()

    # 过滤有效数据
    valid_data = df[df[score_column].notna()][score_column]

    if len(valid_data) == 0:
        return pd.DataFrame()

    # 获取最小值和最大值
    min_score = valid_data.min()
    max_score = valid_data.max()

    # 计算总范围
    range_size = max_score - min_score

    # 计算理想步长（使得9组能覆盖范围）
    ideal_step = range_size / 9

    # 选择合适的整数步长（10, 30, 50, 100, 200, 500, 1000等）
    step_candidates = [10, 30, 50, 100, 200, 300, 500, 1000, 2000, 5000]
    step = 10  # 默认步长

    for candidate in step_candidates:
        if candidate >= ideal_step:
            step = candidate
            break
    else:
        # 如果所有候选步长都不够，使用最大的或计算更大的
        step = ((int(ideal_step) // 1000) + 1) * 1000

    # 确定起始点（以0为基准）
    # 负数方向：找到能覆盖min_score的最小起点
    if min_score < 0:
        start_point = -((-int(min_score) // step) + 1) * step
    else:
        start_point = (int(min_score) // step) * step

    # 生成9个区间
    bins = [start_point + i * step for i in range(10)]

    # 确保bins能覆盖max_score
    while bins[-1] < max_score:
        bins = [b + step for b in bins]

    # 统计各区间头数
    distribution_data = []

    for i in range(9):
        lower = bins[i]
        upper = bins[i + 1]

        # 最后一个区间包含上界
        if i == 8:
            count = len(valid_data[(valid_data >= lower) & (valid_data <= upper)])
        else:
            count = len(valid_data[(valid_data >= lower) & (valid_data < upper)])

        # 格式化区间显示
        distribution_data.append({
            '分布区间': f'{int(lower)}-{int(upper)}',
            '头数': count
        })

    df_dist = pd.DataFrame(distribution_data)

    # 计算占比
    total = df_dist['头数'].sum()
    df_dist['占比(%)'] = (df_dist['头数'] / total * 100).round(2)

    return df_dist


def _get_empty_data() -> dict:
    """返回空数据结构"""
    return {
        'distribution_present': pd.DataFrame(),
        'distribution_all': pd.DataFrame(),
        'detail_df': pd.DataFrame()
    }
