"""
分配工具函数
"""

import numpy as np
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


def calculate_proportional_allocation(
    bull_inventories: Dict[str, int], 
    total_cows: int,
    ensure_minimum: bool = True
) -> Dict[str, int]:
    """
    按库存比例计算分配数量，确保每头有库存的公牛至少分配1头母牛
    
    Args:
        bull_inventories: 公牛库存字典 {bull_id: inventory}
        total_cows: 需要分配的母牛总数
        ensure_minimum: 是否确保最小分配（至少1头）
        
    Returns:
        分配字典 {bull_id: allocated_count}
    """
    # 过滤出有库存的公牛
    available_bulls = {bid: inv for bid, inv in bull_inventories.items() if inv > 0}
    
    if not available_bulls:
        return {}
    
    if total_cows == 0:
        return {bid: 0 for bid in available_bulls}
    
    # 如果公牛数量大于母牛数量，特殊处理
    if ensure_minimum and len(available_bulls) > total_cows:
        # 按库存量排序，优先分配给库存多的公牛
        sorted_bulls = sorted(available_bulls.items(), key=lambda x: x[1], reverse=True)
        allocation = {}
        for i in range(total_cows):
            bull_id = sorted_bulls[i][0]
            allocation[bull_id] = 1
        # 其余公牛分配0头
        for bull_id in available_bulls:
            if bull_id not in allocation:
                allocation[bull_id] = 0
        return allocation
    
    # 计算总库存
    total_inventory = sum(available_bulls.values())
    
    # 初始按比例分配
    initial_allocation = {}
    allocated_count = 0
    
    # 先按比例分配整数部分
    for bull_id, inventory in available_bulls.items():
        ratio = inventory / total_inventory
        allocated = int(total_cows * ratio)
        initial_allocation[bull_id] = allocated
        allocated_count += allocated
    
    # 分配剩余的母牛（由于取整产生的）
    remaining = total_cows - allocated_count
    if remaining > 0:
        # 计算每头公牛的小数部分，优先分配给小数部分大的
        fractional_parts = []
        for bull_id, inventory in available_bulls.items():
            ratio = inventory / total_inventory
            fractional = (total_cows * ratio) - initial_allocation[bull_id]
            fractional_parts.append((bull_id, fractional))
        
        # 按小数部分降序排序
        fractional_parts.sort(key=lambda x: x[1], reverse=True)
        
        # 分配剩余
        for i in range(remaining):
            bull_id = fractional_parts[i][0]
            initial_allocation[bull_id] += 1
    
    # 如果需要确保最小分配
    if ensure_minimum:
        # 找出分配为0的公牛
        zero_bulls = [bid for bid, count in initial_allocation.items() if count == 0]
        
        if zero_bulls:
            # 从分配最多的公牛中转移
            while zero_bulls:
                # 找到分配最多的公牛
                max_bull = max(initial_allocation.items(), key=lambda x: x[1])
                if max_bull[1] <= 1:
                    # 所有公牛都只有1头或0头，无法再转移
                    break
                
                # 转移1头给分配为0的公牛
                zero_bull = zero_bulls.pop(0)
                initial_allocation[max_bull[0]] -= 1
                initial_allocation[zero_bull] = 1
    
    return initial_allocation


def calculate_equal_allocation(
    bull_ids: List[str],
    total_cows: int
) -> Dict[str, int]:
    """
    平均分配母牛给公牛列表
    
    Args:
        bull_ids: 公牛ID列表
        total_cows: 需要分配的母牛总数
        
    Returns:
        分配字典 {bull_id: allocated_count}
    """
    if not bull_ids or total_cows == 0:
        return {}
    
    # 基础分配
    base_count = total_cows // len(bull_ids)
    remainder = total_cows % len(bull_ids)
    
    allocation = {}
    for i, bull_id in enumerate(bull_ids):
        # 前remainder头公牛多分配1头
        allocation[bull_id] = base_count + (1 if i < remainder else 0)
    
    return allocation


def adjust_allocation_for_constraints(
    initial_allocation: Dict[str, int],
    available_cows: List[str],
    constraints_checker
) -> Tuple[Dict[str, List[str]], List[str]]:
    """
    根据约束条件调整分配
    
    Args:
        initial_allocation: 初始分配计划 {bull_id: count}
        available_cows: 可用母牛列表
        constraints_checker: 约束检查函数 (cow_id, bull_id) -> bool
        
    Returns:
        (最终分配 {bull_id: [cow_ids]}, 未分配母牛列表)
    """
    final_allocation = {bull_id: [] for bull_id in initial_allocation}
    unallocated_cows = []
    
    # 创建公牛分配队列
    bull_queue = []
    for bull_id, count in initial_allocation.items():
        bull_queue.extend([bull_id] * count)
    
    # 为每头母牛寻找合适的公牛
    for cow_id in available_cows:
        allocated = False
        
        # 尝试按顺序分配
        for i, bull_id in enumerate(bull_queue):
            if bull_id in final_allocation and len(final_allocation[bull_id]) < initial_allocation[bull_id]:
                if constraints_checker(cow_id, bull_id):
                    final_allocation[bull_id].append(cow_id)
                    allocated = True
                    break
        
        if not allocated:
            # 尝试任何有配额的公牛
            for bull_id in initial_allocation:
                if len(final_allocation[bull_id]) < initial_allocation[bull_id]:
                    if constraints_checker(cow_id, bull_id):
                        final_allocation[bull_id].append(cow_id)
                        allocated = True
                        break
        
        if not allocated:
            unallocated_cows.append(cow_id)
    
    return final_allocation, unallocated_cows