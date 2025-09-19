"""平均分配工具函数"""

import logging
from typing import Dict, List
import math

logger = logging.getLogger(__name__)


def calculate_equal_allocation(
    available_bull_ids: List[str],
    total_cows: int
) -> Dict[str, int]:
    """
    平均分配母牛给所有可用的公牛

    Args:
        available_bull_ids: 可用公牛ID列表
        total_cows: 需要分配的母牛总数

    Returns:
        分配字典 {bull_id: allocated_count}
    """
    if not available_bull_ids or total_cows == 0:
        return {}

    num_bulls = len(available_bull_ids)

    # 计算每头公牛的基础配额
    base_quota = total_cows // num_bulls
    remainder = total_cows % num_bulls

    allocation = {}
    for i, bull_id in enumerate(available_bull_ids):
        # 前remainder头公牛多分配1头
        if i < remainder:
            allocation[bull_id] = base_quota + 1
        else:
            allocation[bull_id] = base_quota

    logger.info(f"平均分配: {total_cows}头母牛 -> {num_bulls}头公牛，每头约{base_quota}头")

    return allocation


def calculate_ratio_based_allocation(
    available_bull_ids: List[str],
    total_cows: int,
    target_ratio: float
) -> Dict[str, int]:
    """
    按固定比例分配母牛（用于1选）
    比例指的是该类型冻精占总配种的比例

    Args:
        available_bull_ids: 可用公牛ID列表
        total_cows: 总母牛数
        target_ratio: 目标比例 (0-1之间)

    Returns:
        分配字典 {bull_id: allocated_count}
    """
    if not available_bull_ids or total_cows == 0:
        return {}

    # 计算该类型应分配的母牛数
    target_count = int(total_cows * target_ratio)

    # 使用平均分配
    return calculate_equal_allocation(available_bull_ids, target_count)