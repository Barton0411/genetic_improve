"""
配种记录明细数据收集器
收集Sheet 7所需数据：直接读取已配公牛分析结果文件
"""

from pathlib import Path
import logging
import pandas as pd
import glob

logger = logging.getLogger(__name__)


def collect_breeding_detail_data(analysis_folder: Path, cache=None) -> dict:
    """
    收集配种记录明细数据 (Sheet 7)

    直接读取"已配公牛_近交系数及隐性基因分析结果_*.xlsx"文件

    Args:
        analysis_folder: 分析结果文件夹路径
        cache: DataCache实例（可选），用于缓存已读取的Excel文件

    Returns:
        数据字典:
        {
            'file_path': 文件路径,
            'data': DataFrame数据
        }
    """
    try:
        # 1. 查找最新的已配公牛分析结果文件
        pattern = str(analysis_folder / "已配公牛_近交系数及隐性基因分析结果_*.xlsx")
        files = glob.glob(pattern)

        if not files:
            logger.warning(f"未找到已配公牛分析结果文件: {pattern}")
            return {}

        # 按文件名时间戳排序，获取最新文件
        latest_file = max(files, key=lambda x: Path(x).name)
        logger.info(f"读取文件: {latest_file}")

        # 2. 读取Excel文件（使用缓存）
        if cache:
            df = cache.get_excel(latest_file)
        else:
            df = pd.read_excel(latest_file)

        logger.info(f"成功读取配种记录明细数据: {len(df)}行, {len(df.columns)}列")

        return {
            'file_path': latest_file,
            'data': df
        }

    except Exception as e:
        logger.error(f"收集配种记录明细数据时发生错误: {e}", exc_info=True)
        return {}
