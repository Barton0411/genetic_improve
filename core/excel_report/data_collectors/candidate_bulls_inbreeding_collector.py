"""
备选公牛近交系数分析数据收集器
收集Sheet 13所需的所有数据：备选公牛-近交系数分析
"""

from pathlib import Path
import logging
import pandas as pd
import glob

logger = logging.getLogger(__name__)


def collect_candidate_bulls_inbreeding_data(analysis_folder: Path, project_folder: Path, cache=None) -> dict:
    """
    收集备选公牛近交系数分析数据 (Sheet 13)

    Args:
        analysis_folder: 分析结果文件夹路径
        project_folder: 项目文件夹路径（用于读取processed_cow_data）
        cache: DataCache实例（可选）

    Returns:
        数据字典:
        {
            'bulls': [  # 按高风险占比从高到低排序的公牛列表
                {
                    'bull_id': '001HO09154',
                    'original_bull_id': '151HO04449',
                    'mature_cow_count': 218,  # 成母牛总数
                    'heifer_count': 65,       # 后备牛总数
                    'total_cow_count': 283,   # 全群总数
                    'distribution': {  # 近交系数分布
                        'intervals': ['< 3.125%', '3.125% - 6.25%', '6.25% - 12.5%', '> 12.5%'],
                        'mature_counts': [180, 30, 8, 0],
                        'mature_ratios': [0.826, 0.138, 0.037, 0.0],
                        'heifer_counts': [55, 8, 2, 0],
                        'heifer_ratios': [0.846, 0.123, 0.031, 0.0],
                        'total_counts': [235, 38, 10, 0],
                        'total_ratios': [0.830, 0.134, 0.035, 0.0],
                        'risk_levels': ['安全🟢', '低风险🟡', '高风险🔴', '极高风险🔴']
                    },
                    'high_risk_summary': {  # 高风险汇总（>6.25%）
                        'mature_count': 8,
                        'mature_ratio': 0.037,
                        'heifer_count': 2,
                        'heifer_ratio': 0.031,
                        'total_count': 10,
                        'total_ratio': 0.035
                    }
                },
                ...
            ]
        }
    """
    try:
        # 1. 查找最新的备选公牛分析结果文件
        pattern = str(analysis_folder / "备选公牛_近交系数及隐性基因分析结果*.xlsx")
        files = glob.glob(pattern)

        if not files:
            logger.warning(f"未找到备选公牛分析结果文件: {pattern}")
            return {}

        latest_file = max(files, key=lambda x: Path(x).stat().st_mtime)
        logger.info(f"读取文件: {latest_file}")

        # 2. 读取数据（使用缓存）
        if cache:
            df = cache.get_excel(latest_file)
        else:
            df = pd.read_excel(latest_file)

        # 确保有必要的列
        if '后代近交系数' not in df.columns:
            logger.warning("文件中缺少'后代近交系数'列")
            return {}

        # 3. 读取processed_cow_data获取胎次和在场信息
        cow_data_file = project_folder / "standardized_data" / "processed_cow_data.xlsx"
        if not cow_data_file.exists():
            logger.warning(f"未找到文件: {cow_data_file}")
            return {}

        if cache:
            cow_data = cache.get_excel(str(cow_data_file))
        else:
            cow_data = pd.read_excel(cow_data_file)

        # 提取需要的列（processed_cow_data使用cow_id作为列名）
        cow_info = cow_data[['cow_id', '是否在场', 'sex', 'lac']].copy()
        cow_info['cow_id'] = cow_info['cow_id'].astype(str)
        # 确保sex列正确填充（处理全NaN的情况，母牛数据默认为'母'）
        if cow_info['sex'].isna().all():
            cow_info['sex'] = '母'
        else:
            cow_info['sex'] = cow_info['sex'].fillna('母')

        # 4. 合并数据（备选公牛文件使用母牛号，processed_cow_data使用cow_id）
        df['母牛号'] = df['母牛号'].astype(str)
        merged = df.merge(cow_info, left_on='母牛号', right_on='cow_id', how='left')

        # 5. 筛选在群母牛
        in_herd = merged[(merged['是否在场'] == '是') & (merged['sex'] == '母')].copy()

        if len(in_herd) == 0:
            logger.warning("没有在群母牛数据")
            return {}

        # 6. 转换后代近交系数为float
        in_herd['后代近交系数_float'] = in_herd['后代近交系数'].apply(_parse_percentage)

        # 7. 获取所有备选公牛
        bulls = in_herd['备选公牛号'].unique()
        logger.info(f"识别到 {len(bulls)} 个备选公牛")

        # 8. 按公牛统计
        bulls_data = []
        for bull_id in bulls:
            bull_data = in_herd[in_herd['备选公牛号'] == bull_id].copy()

            # 获取公牛的原始号
            original_bull_id = bull_data['原始备选公牛号'].iloc[0] if len(bull_data) > 0 else ''

            # 分组统计
            mature_cows = bull_data[bull_data['lac'] > 0]
            heifers = bull_data[bull_data['lac'] == 0]

            mature_count = len(mature_cows)
            heifer_count = len(heifers)
            total_count = len(bull_data)

            # 统计近交系数分布
            distribution = _analyze_inbreeding_distribution_by_group(
                mature_cows, heifers, bull_data
            )

            # 计算高风险汇总（>6.25%）
            mature_high_risk = len(mature_cows[mature_cows['后代近交系数_float'] >= 0.0625])
            heifer_high_risk = len(heifers[heifers['后代近交系数_float'] >= 0.0625])
            total_high_risk = len(bull_data[bull_data['后代近交系数_float'] >= 0.0625])

            bulls_data.append({
                'bull_id': str(bull_id),
                'original_bull_id': str(original_bull_id),
                'mature_cow_count': mature_count,
                'heifer_count': heifer_count,
                'total_cow_count': total_count,
                'distribution': distribution,
                'high_risk_summary': {
                    'mature_count': mature_high_risk,
                    'mature_ratio': mature_high_risk / mature_count if mature_count > 0 else 0,
                    'heifer_count': heifer_high_risk,
                    'heifer_ratio': heifer_high_risk / heifer_count if heifer_count > 0 else 0,
                    'total_count': total_high_risk,
                    'total_ratio': total_high_risk / total_count if total_count > 0 else 0
                }
            })

        # 9. 按高风险占比从高到低排序
        bulls_data.sort(key=lambda x: x['high_risk_summary']['total_ratio'], reverse=True)

        return {'bulls': bulls_data}

    except Exception as e:
        logger.error(f"收集备选公牛近交系数数据时发生错误: {e}", exc_info=True)
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


def _analyze_inbreeding_distribution_by_group(mature_cows: pd.DataFrame,
                                               heifers: pd.DataFrame,
                                               all_cows: pd.DataFrame) -> dict:
    """
    分析成母牛、后备牛、全群的近交系数分布

    Args:
        mature_cows: 成母牛DataFrame
        heifers: 后备牛DataFrame
        all_cows: 全群DataFrame

    Returns:
        分布数据字典
    """
    intervals = ['< 3.125%', '3.125% - 6.25%', '6.25% - 12.5%', '> 12.5%']
    risk_levels = ['安全🟢', '低风险🟡', '高风险🔴', '极高风险🔴']

    # 成母牛统计
    mature_counts, mature_ratios = _calculate_distribution(mature_cows)

    # 后备牛统计
    heifer_counts, heifer_ratios = _calculate_distribution(heifers)

    # 全群统计
    total_counts, total_ratios = _calculate_distribution(all_cows)

    return {
        'intervals': intervals,
        'mature_counts': mature_counts,
        'mature_ratios': mature_ratios,
        'heifer_counts': heifer_counts,
        'heifer_ratios': heifer_ratios,
        'total_counts': total_counts,
        'total_ratios': total_ratios,
        'risk_levels': risk_levels
    }


def _calculate_distribution(df: pd.DataFrame) -> tuple:
    """
    计算单个分组的近交系数分布

    Returns:
        (counts, ratios) 元组
    """
    total = len(df)
    if total == 0:
        return [0, 0, 0, 0], [0.0, 0.0, 0.0, 0.0]

    count_safe = len(df[df['后代近交系数_float'] < 0.03125])
    count_low = len(df[(df['后代近交系数_float'] >= 0.03125) & (df['后代近交系数_float'] < 0.0625)])
    count_high = len(df[(df['后代近交系数_float'] >= 0.0625) & (df['后代近交系数_float'] < 0.125)])
    count_extreme = len(df[df['后代近交系数_float'] >= 0.125])

    counts = [count_safe, count_low, count_high, count_extreme]
    ratios = [c / total for c in counts]

    return counts, ratios
