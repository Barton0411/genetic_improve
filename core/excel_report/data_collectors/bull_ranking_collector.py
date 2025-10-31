"""
备选公牛排名数据收集器
收集Sheet 10所需的所有数据
"""

from pathlib import Path
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def collect_bull_ranking_data(analysis_folder) -> dict:
    """
    收集备选公牛排名数据

    Args:
        analysis_folder: 分析结果文件夹路径（字符串或Path对象）

    Returns:
        数据字典，包含:
        - bull_rankings: 公牛排名DataFrame（按ranking排序）
        - total_bulls: 公牛总数
        - sexed_bulls: 性控公牛数
        - regular_bulls: 常规公牛数
    """
    # 确保是Path对象
    analysis_path = Path(analysis_folder) if isinstance(analysis_folder, str) else analysis_folder

    # 查找备选公牛排名文件
    ranking_file = analysis_path / "processed_index_bull_scores.xlsx"

    if not ranking_file.exists():
        logger.warning("备选公牛排名文件不存在，跳过Sheet 10")
        return {}

    try:
        logger.info("开始收集备选公牛排名数据...")

        # 读取排名数据
        df = pd.read_excel(ranking_file, sheet_name="Sheet1")
        logger.info(f"读取到 {len(df)} 条公牛排名记录")

        # 按ranking排序
        df = df.sort_values('ranking').reset_index(drop=True)

        # 统计
        sexed_count = (df['semen_type'] == '性控').sum()
        regular_count = (df['semen_type'] == '常规').sum()

        result = {
            'bull_rankings': df,
            'total_bulls': len(df),
            'sexed_bulls': sexed_count,
            'regular_bulls': regular_count
        }

        logger.info(f"✓ 备选公牛排名数据收集完成: {len(df)}头公牛 (性控: {sexed_count}, 常规: {regular_count})")
        return result

    except Exception as e:
        logger.error(f"收集备选公牛排名数据失败: {e}", exc_info=True)
        return {}
