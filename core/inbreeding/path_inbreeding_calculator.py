# core/inbreeding/path_inbreeding_calculator.py

import os
import sys
import json
import time
import logging
import pickle
import math
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional
from pathlib import Path
import pandas as pd
import csv

from core.inbreeding.inbreeding_calculator import InbreedingCalculator
from core.data.update_manager import get_pedigree_db

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PathInbreedingCalculator:
    """使用通径法(Path Method)计算近交系数的计算器"""
    
    def __init__(self, max_generations: int = 6):
        """
        初始化计算器
        
        Args:
            max_generations: 追溯的最大代数
        """
        self.pedigree_db = get_pedigree_db()
        self.max_generations = max_generations
        self._inbreeding_cache = {}  # 缓存计算结果
        self._path_cache = {}  # 缓存路径结果
        self._ancestors_cache = {}  # 祖先路径缓存: (animal_id, max_gen) -> {ancestor_id: [paths]}

    def clear_cache(self):
        """
        清除所有缓存

        使用场景：
        1. 系谱数据更新后
        2. 计算逻辑修改后
        3. 需要重新计算时
        """
        cache_count = len(self._inbreeding_cache) + len(self._path_cache) + len(self._ancestors_cache)
        self._inbreeding_cache.clear()
        self._path_cache.clear()
        self._ancestors_cache.clear()
        logger.info(f"清除了 {cache_count} 个缓存条目")

    def calculate_inbreeding_coefficient(self, animal_id: str) -> Tuple[float, Dict, Dict]:
        """
        计算指定动物的近交系数
        
        Args:
            animal_id: 动物ID
            
        Returns:
            Tuple[float, Dict, Dict]: 
                - 近交系数
                - 共同祖先及其贡献
                - 计算路径
        """
        # 标准化ID（可能是NAAB格式）
        animal_id = self.pedigree_db.standardize_animal_id(animal_id, 'bull')
        
        logger.debug(f"开始计算动物 {animal_id} 的近交系数")

        # 如果已经计算过，直接返回缓存结果
        if animal_id in self._inbreeding_cache:
            inbreeding_coef, contributions, paths = self._inbreeding_cache[animal_id]
            logger.debug(f"发现缓存结果: 近交系数 = {inbreeding_coef:.6f} ({inbreeding_coef*100:.4f}%)")
            return self._inbreeding_cache[animal_id]

        # 检查动物是否在系谱中
        if animal_id not in self.pedigree_db.pedigree:
            logger.warning(f"动物 {animal_id} 不在系谱中")
            return 0.0, {}, {}
        
        # 检查是否有GIB值
        animal_info = self.pedigree_db.pedigree[animal_id]
        if animal_info.get('gib') is not None:
            gib_value = animal_info['gib']
            # 确保GIB值是小数（有些系统可能存储为百分比）
            if gib_value > 1.0:
                logger.debug(f"GIB值为百分比格式，转换为小数: {gib_value} -> {gib_value/100.0}")
                gib_value = gib_value / 100.0
            logger.debug(f"动物 {animal_id} 有GIB值: {gib_value:.6f} ({gib_value*100:.4f}%), 直接使用")
            # 因为没有路径信息，返回空字典
            self._inbreeding_cache[animal_id] = (gib_value, {"GIB值": gib_value}, {})
            return gib_value, {"GIB值": gib_value}, {}
        
        start_time = time.time()
        logger.debug(f"动物 {animal_id} 无GIB值，使用通径法(Wright's Formula)计算近交系数")
        
        # 获取动物的父母
        info = self.pedigree_db.pedigree[animal_id]
        sire_id = info.get('sire', '')
        dam_id = info.get('dam', '')
        
        logger.debug(f"动物 {animal_id} 的父亲: {sire_id}, 母亲: {dam_id}")

        # 如果父母信息不全，无法计算近交系数
        if not sire_id or not dam_id:
            logger.debug(f"动物 {animal_id} 的父母信息不全，无法使用通径法计算近交系数")
            return 0.0, {"父母信息不全": 0.0}, {}
        
        # 使用通径法计算近交系数
        inbreeding_coef, contributions, paths = self._calculate_using_path_method(sire_id, dam_id)
        
        elapsed_time = time.time() - start_time
        logger.debug(f"动物 {animal_id} 的近交系数计算完成: {inbreeding_coef:.6f} ({inbreeding_coef*100:.4f}%), 耗时: {elapsed_time:.2f}秒")
        
        # 缓存结果
        self._inbreeding_cache[animal_id] = (inbreeding_coef, contributions, paths)
        
        return inbreeding_coef, contributions, paths
    
    def _filter_redundant_common_ancestors(self, common_ancestors: Set[str],
                                          sire_ancestors: Dict[str, List[List[str]]],
                                          dam_ancestors: Dict[str, List[List[str]]]) -> Set[str]:
        """
        过滤掉冗余的共同祖先（即那些是其他共同祖先的祖先的个体）

        原理：如果祖先A是祖先B的祖先，且B已经是共同祖先，
             则A的贡献已经通过B计算过了，不应该再单独计算A

        Args:
            common_ancestors: 所有共同祖先的集合
            sire_ancestors: 父系祖先路径字典 {祖先ID: [路径列表]}
            dam_ancestors: 母系祖先路径字典 {祖先ID: [路径列表]}

        Returns:
            过滤后的共同祖先集合
        """
        if not common_ancestors:
            return common_ancestors

        logger.debug(f"开始过滤冗余共同祖先，初始数量: {len(common_ancestors)}")

        filtered_ancestors = set()
        redundant_details = []

        # 注意：不在这里过滤共同祖先，因为可能会过滤过度
        # 而是在后续的路径验证中过滤无效通径

        # 对每个共同祖先，标记为保留（后续通过路径验证来过滤）
        for ancestor_id in common_ancestors:
            is_redundant = False
            redundant_reason = None

            # 如果不是冗余的，加入过滤后的集合
            if not is_redundant:
                filtered_ancestors.add(ancestor_id)
            else:
                redundant_details.append((ancestor_id, redundant_reason))

        # 输出过滤结果
        removed_count = len(common_ancestors) - len(filtered_ancestors)
        logger.debug(f"过滤结果: {len(common_ancestors)} → {len(filtered_ancestors)} 个有效共同祖先")

        return filtered_ancestors

    def _calculate_using_path_method(self, sire_id: str, dam_id: str) -> Tuple[float, Dict, Dict]:
        """
        使用通径法(Wright's Formula)计算近交系数
        
        Args:
            sire_id: 父亲ID
            dam_id: 母亲ID
            
        Returns:
            Tuple[float, Dict, Dict]: 
                - 近交系数
                - 共同祖先及其贡献
                - 计算路径
        """
        # 标准化ID
        sire_id = self.pedigree_db.standardize_animal_id(sire_id, 'bull')
        dam_id = self.pedigree_db.standardize_animal_id(dam_id, 'cow')
        
        logger.debug(f"计算 {sire_id} 和 {dam_id} 的共同祖先")

        # 检查是否有缓存
        cache_key = (sire_id, dam_id)
        if cache_key in self._path_cache:
            inbreeding_coef, contributions, paths = self._path_cache[cache_key]
            logger.debug(f"发现缓存结果: 总共 {len(contributions)} 个共同祖先, 近交系数 = {inbreeding_coef:.6f}")
            return self._path_cache[cache_key]
        
        # 获取父系和母系祖先
        logger.debug(f"收集 {sire_id} 的祖先...")
        sire_ancestors = self._get_ancestors_with_paths(sire_id, self.max_generations)
        logger.debug(f"找到 {len(sire_ancestors)} 个父系祖先")

        logger.debug(f"收集 {dam_id} 的祖先...")
        dam_ancestors = self._get_ancestors_with_paths(dam_id, self.max_generations)
        logger.debug(f"找到 {len(dam_ancestors)} 个母系祖先")
        
        # 找出共同祖先
        common_ancestors = set(sire_ancestors.keys()) & set(dam_ancestors.keys())

        # 如果父亲本身是母亲的祖先，也应该计入共同祖先
        if sire_id in dam_ancestors:
            common_ancestors.add(sire_id)
            if sire_id not in sire_ancestors:
                sire_ancestors[sire_id] = [[]]  # 空路径，父亲到父亲自己，路径长度=0
            logger.debug(f"父亲 {sire_id} 是母亲的祖先，计入共同祖先")

        # 如果母亲本身是父亲的祖先，也应该计入共同祖先
        if dam_id in sire_ancestors:
            common_ancestors.add(dam_id)
            if dam_id not in dam_ancestors:
                dam_ancestors[dam_id] = [[]]  # 空路径，母亲到母亲自己，路径长度=0
            logger.debug(f"母亲 {dam_id} 是父亲的祖先，计入共同祖先")

        logger.debug(f"找到 {len(common_ancestors)} 个初始共同祖先: {', '.join(list(common_ancestors)[:5])}{'...' if len(common_ancestors) > 5 else ''}")

        # 过滤冗余的共同祖先（即那些是其他共同祖先的祖先的个体）
        common_ancestors = self._filter_redundant_common_ancestors(
            common_ancestors, sire_ancestors, dam_ancestors
        )

        logger.debug(f"过滤后剩余 {len(common_ancestors)} 个有效共同祖先")

        # 计算各个共同祖先的贡献
        inbreeding_coef = 0.0
        contributions = {}
        paths = {}
        
        # 在通径法中，如果同一条通径上有多代祖先，应该优先保留离后代最近的那个作为共同祖先。
        # 这里不在集合层面提前“合并”父辈与祖辈，而是让每个共同祖先根据自身路径独立计算贡献，
        # 由路径过滤规则负责避免同一条通径被多次计数。
        for ancestor_id in common_ancestors:
            # 获取所有从父亲到祖先的路径
            sire_paths = sire_ancestors[ancestor_id]
            # 获取所有从母亲到祖先的路径
            dam_paths = dam_ancestors[ancestor_id]
            
            logger.debug(f"计算祖先 {ancestor_id} 的贡献: 父系路径={len(sire_paths)}, 母系路径={len(dam_paths)}")
            
            # 计算该祖先的贡献
            ancestor_contribution = 0.0
            ancestor_paths = []
            valid_path_count = 0
            
            # 根据Wright's Formula计算
            for sire_path in sire_paths:
                for dam_path in dam_paths:
                    # 路径长度（代数）
                    sire_length = len(sire_path)
                    dam_length = len(dam_path)

                    # Wright通径规则验证：通径中不应有重复节点
                    # 检查1：父系路径和母系路径之间的交叉（除了共同祖先）
                    sire_nodes = set(sire_path)
                    dam_nodes = set(dam_path)
                    common_nodes = sire_nodes & dam_nodes
                    if len(common_nodes) > 1 or (len(common_nodes) == 1 and ancestor_id not in common_nodes):
                        # print(f"    跳过无效路径：父系和母系路径有交叉节点 {common_nodes}")
                        continue

                    # 检查2：父系路径（除了终点祖先）不应包含母系起点（dam_id）
                    # 路径格式：[中间节点..., 共同祖先]，所以除去最后一个元素
                    sire_path_without_ancestor = sire_path[:-1] if sire_length > 1 else []
                    if dam_id in sire_path_without_ancestor:
                        # print(f"    跳过无效路径：父系路径中间包含母系起点 {dam_id}")
                        continue

                    # 检查3：母系路径（除了终点祖先）不应包含父系起点（sire_id）
                    # 路径格式：[中间节点..., 共同祖先]，所以除去最后一个元素
                    dam_path_without_ancestor = dam_path[:-1] if dam_length > 1 else []
                    if sire_id in dam_path_without_ancestor:
                        # print(f"    跳过无效路径：母系路径中间包含父系起点 {sire_id}")
                        continue

                    # 检查4：单条路径内部不应有重复节点
                    if len(sire_path) != len(sire_nodes):
                        # print(f"    跳过无效路径：父系路径有重复节点")
                        continue
                    if len(dam_path) != len(dam_nodes):
                        # print(f"    跳过无效路径：母系路径有重复节点")
                        continue

                    valid_path_count += 1
                    
                    # 使用Wright's公式: F = Σ(0.5)^(n₁+n₂) * (1+F_A)
                    # 先计算路径贡献: (0.5)^(n₁+n₂)
                    path_contribution = 0.5 ** (sire_length + dam_length)
                    
                    # 检查共同祖先是否有自身的近交系数
                    ancestor_f = 0.0
                    if ancestor_id in self._inbreeding_cache:
                        ancestor_f, _, _ = self._inbreeding_cache[ancestor_id]
                    elif ancestor_id in self.pedigree_db.pedigree:
                        # 检查是否有GIB值
                        ancestor_info = self.pedigree_db.pedigree[ancestor_id]
                        if ancestor_info.get('gib') is not None:
                            ancestor_f = ancestor_info['gib']
                            # 确保GIB值是小数（有些系统可能存储为百分比）
                            if ancestor_f > 1.0:
                                ancestor_f = ancestor_f / 100.0
                    
                    # Wright's公式中的(1+F_A)部分
                    path_contribution *= (1 + ancestor_f)
                    
                    # 打印路径详情
                    if valid_path_count <= 5:
                        sire_path_str = " -> ".join([str(x) for x in sire_path])
                        dam_path_str = " -> ".join([str(x) for x in dam_path])
                        logger.debug(f"  路径 {valid_path_count}: {sire_id} -> {sire_path_str} <- {dam_path_str} <- {dam_id}, 贡献={path_contribution:.8f}")
                    
                    # 记录路径和贡献（包含路径长度和祖先近交系数，用于显示）
                    sire_path_str = " -> ".join([str(x) for x in sire_path])
                    dam_path_str = " -> ".join([str(x) for x in dam_path])
                    path_str = f"{sire_id} -> {sire_path_str} <- {dam_path_str} <- {dam_id}"
                    # 保存为元组: (路径字符串, 贡献值, n1, n2, F_CA)
                    ancestor_paths.append((path_str, path_contribution, sire_length, dam_length, ancestor_f))
                    
                    # 累加贡献
                    ancestor_contribution += path_contribution
            
            # 记录该祖先的总贡献
            if ancestor_contribution > 0:
                contributions[ancestor_id] = ancestor_contribution
                paths[ancestor_id] = ancestor_paths
                
                # 累加到总近交系数
                inbreeding_coef += ancestor_contribution
                logger.debug(f"  祖先 {ancestor_id}: {valid_path_count} 条有效路径, 贡献={ancestor_contribution:.8f}, 累计={inbreeding_coef:.8f}")
            else:
                logger.debug(f"  祖先 {ancestor_id} 没有有效路径或贡献为零")

        logger.debug(f"最终近交系数: {inbreeding_coef:.8f} ({inbreeding_coef*100:.6f}%)")
        
        # 缓存结果
        self._path_cache[cache_key] = (inbreeding_coef, contributions, paths)
        
        return inbreeding_coef, contributions, paths
    
    def _get_ancestors_with_paths(self, animal_id: str, max_generations: int) -> Dict[str, List[List[str]]]:
        """
        获取动物的所有祖先以及到达这些祖先的路径
        
        Args:
            animal_id: 动物ID
            max_generations: 最大代数
            
        Returns:
            Dict[str, List[List[str]]]: 祖先ID -> 路径列表的映射
        """
        # 缓存检查
        cache_key = (animal_id, max_generations)
        if cache_key in self._ancestors_cache:
            return self._ancestors_cache[cache_key]

        result = {}  # 祖先ID -> 路径列表

        # 若animal_id不在系谱中，直接返回
        if animal_id not in self.pedigree_db.pedigree:
            logger.debug(f"动物 {animal_id} 不在系谱中，无法获取祖先")
            return result

        # 初始化队列，每个元素是(当前ID, 当前路径, 当前代数)
        queue = [(animal_id, [], 0)]

        logger.debug(f"开始搜索 {animal_id} 的祖先，最大追溯 {max_generations} 代")

        parent_count = 0
        while queue:
            current_id, current_path, current_gen = queue.pop(0)

            # 检查是否超过最大代数
            if current_gen > max_generations:
                continue

            # 检查当前路径中是否已经包含此节点（避免环路）
            if current_id in current_path:
                continue

            # 将当前ID加入路径
            new_path = current_path + [current_id]

            # 如果当前ID不是起始ID，将其添加到结果中
            if current_id != animal_id:
                if current_id not in result:
                    result[current_id] = []
                # 存储从动物到祖先的完整路径
                result[current_id].append(new_path[1:])

            # 如果已经达到最大代数，不再继续
            if current_gen == max_generations:
                continue

            # 获取父母并添加到队列中
            if current_id in self.pedigree_db.pedigree:
                info = self.pedigree_db.pedigree[current_id]
                sire_id = info.get('sire', '')
                dam_id = info.get('dam', '')

                parent_count += 1
                if parent_count <= 10 or parent_count % 100 == 0:
                    gen_str = '代数' + str(current_gen)
                    logger.debug(f"  {gen_str:<6} 处理 {current_id:<15} 父: {sire_id:<15} 母: {dam_id:<15}")

                # 只要父母不在当前路径中（无环路），就添加到队列
                if sire_id and sire_id not in new_path:
                    queue.append((sire_id, new_path, current_gen + 1))
                if dam_id and dam_id not in new_path:
                    queue.append((dam_id, new_path, current_gen + 1))

        # 结果统计
        total_paths = sum(len(paths) for paths in result.values())
        logger.debug(f"完成搜索，找到 {len(result)} 个祖先，共 {total_paths} 条路径")

        # 缓存结果
        self._ancestors_cache[cache_key] = result
        return result
    
    def print_inbreeding_details(self, animal_id: str, min_contribution: float = 0.001):
        """
        打印动物的近交系数详情
        
        Args:
            animal_id: 动物ID
            min_contribution: 最小贡献阈值，低于此值的祖先将不显示
        """
        # 计算近交系数
        inbreeding_coef, contributions, paths = self.calculate_inbreeding_coefficient(animal_id)
        
        print(f"\n===== 动物 {animal_id} 的近交系数详情 =====")
        print(f"总近交系数: {inbreeding_coef:.6f} ({inbreeding_coef*100:.4f}%)")
        
        # 如果没有近交
        if not contributions or inbreeding_coef <= 0:
            print("该动物没有检测到近交")
            return
        
        # 检查是否是GIB值
        if "GIB值" in contributions:
            print(f"该动物使用GIB值: {contributions['GIB值']:.6f}")
            return
            
        # 检查是否是父母信息不全
        if "父母信息不全" in contributions:
            print("无法计算近交系数，因为父母信息不全")
            return
        
        # 标准化ID，以便在输出时显示
        std_animal_id = self.pedigree_db.standardize_animal_id(animal_id, 'bull')
        print(f"标准化ID: {std_animal_id}")
        
        # 获取父母信息
        if std_animal_id in self.pedigree_db.pedigree:
            info = self.pedigree_db.pedigree[std_animal_id]
            sire_id = info.get('sire', '')
            dam_id = info.get('dam', '')
            print(f"父号: {sire_id}")
            print(f"母号: {dam_id}")
        
        # 按贡献排序共同祖先
        sorted_ancestors = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
        
        print(f"\n共找到 {len(sorted_ancestors)} 个共同祖先:")
        
        # 打印各祖先贡献
        for ancestor_id, contribution in sorted_ancestors:
            # 如果贡献低于阈值，跳过
            if contribution < min_contribution:
                continue
                
            contribution_percent = contribution * 100
            total_percent = (contribution / inbreeding_coef) * 100
            
            print(f"\n祖先 {ancestor_id} - 贡献: {contribution:.6f} ({contribution_percent:.4f}%) - 占总近交系数的 {total_percent:.2f}%")
            
            # 打印路径
            ancestor_paths = paths.get(ancestor_id, [])
            if ancestor_paths:
                print(f"  发现 {len(ancestor_paths)} 条路径:")
                for i, (path_str, path_contrib) in enumerate(ancestor_paths[:5]):  # 只显示前5条路径
                    path_percent = path_contrib * 100
                    print(f"  {i+1}. 贡献: {path_contrib:.6f} ({path_percent:.4f}%)")
                    print(f"     {path_str}")
                
                if len(ancestor_paths) > 5:
                    print(f"  ...还有 {len(ancestor_paths) - 5} 条路径未显示...")
    
    def export_inbreeding_report(self, animal_id: str, output_file: Path, min_contribution: float = 0.001):
        """
        导出动物的近交系数详情到CSV文件
        
        Args:
            animal_id: 动物ID
            output_file: 输出文件路径
            min_contribution: 最小贡献阈值，低于此值的祖先将不导出
        """
        # 计算近交系数
        inbreeding_coef, contributions, paths = self.calculate_inbreeding_coefficient(animal_id)
        
        # 创建输出目录(如果不存在)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 准备CSV文件
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # 写入标题行和基本信息
            writer.writerow(['动物ID', '标准化ID', '总近交系数', '百分比'])
            std_animal_id = self.pedigree_db.standardize_animal_id(animal_id, 'bull')
            writer.writerow([animal_id, std_animal_id, f"{inbreeding_coef:.6f}", f"{inbreeding_coef*100:.4f}%"])
            writer.writerow([])  # 空行
            
            # 父母信息
            writer.writerow(['父号', '母号'])
            if std_animal_id in self.pedigree_db.pedigree:
                info = self.pedigree_db.pedigree[std_animal_id]
                sire_id = info.get('sire', '')
                dam_id = info.get('dam', '')
                writer.writerow([sire_id, dam_id])
            else:
                writer.writerow(['未知', '未知'])
            writer.writerow([])  # 空行
            
            # 如果没有近交或使用的是GIB值
            if not contributions or inbreeding_coef <= 0:
                writer.writerow(['没有检测到近交'])
                return
            
            if "GIB值" in contributions:
                writer.writerow(['使用GIB值', f"{contributions['GIB值']:.6f}"])
                return
                
            if "父母信息不全" in contributions:
                writer.writerow(['无法计算近交系数', '父母信息不全'])
                return
            
            # 按贡献排序共同祖先
            sorted_ancestors = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
            
            # 写入共同祖先表头
            writer.writerow(['共同祖先', '贡献值', '贡献百分比', '占总近交比例'])
            
            # 写入各祖先贡献
            for ancestor_id, contribution in sorted_ancestors:
                if contribution < min_contribution:
                    continue
                    
                contribution_percent = contribution * 100
                total_percent = (contribution / inbreeding_coef) * 100
                
                writer.writerow([
                    ancestor_id, 
                    f"{contribution:.6f}", 
                    f"{contribution_percent:.4f}%", 
                    f"{total_percent:.2f}%"
                ])
            
            writer.writerow([])  # 空行
            
            # 写入路径详情
            writer.writerow(['共同祖先', '路径', '贡献值', '贡献百分比'])
            
            for ancestor_id, contribution in sorted_ancestors:
                if contribution < min_contribution:
                    continue
                    
                ancestor_paths = paths.get(ancestor_id, [])
                if not ancestor_paths:
                    continue
                    
                # 对于每个祖先最多写入10条路径
                for i, (path_str, path_contrib) in enumerate(ancestor_paths[:10]):
                    path_percent = path_contrib * 100
                    writer.writerow([
                        ancestor_id,
                        path_str,
                        f"{path_contrib:.6f}", 
                        f"{path_percent:.4f}%"
                    ])
                
                # 如果有更多路径，写入说明
                if len(ancestor_paths) > 10:
                    writer.writerow([
                        ancestor_id,
                        f"...还有{len(ancestor_paths) - 10}条路径未显示...",
                        "", ""
                    ])
                    
                writer.writerow([])  # 在不同祖先之间添加空行
        
        logging.info(f"近交系数报告已导出到: {output_file}")
    
    def calculate_potential_offspring_inbreeding(self, bull_id: str, cow_id: str) -> Tuple[float, Dict[str, float], Dict[str, List[Tuple[str, float]]]]:
        """计算潜在后代的近交系数
        
        计算bull_id配给cow_id所产生的潜在后代的近交系数
        
        Args:
            bull_id: 公牛ID
            cow_id: 母牛ID
            
        Returns:
            Tuple[float, Dict[str, float], Dict[str, List[Tuple[str, float]]]]: 
                - 近交系数
                - 每个共同祖先的贡献字典 {祖先ID: 贡献值}
                - 每个共同祖先的所有路径 {祖先ID: [(路径字符串, 贡献值), ...]}
        """
        # 记录输入参数
        logger.debug(f"计算后代近交系数: bull_id={bull_id}, cow_id={cow_id}")

        # 检查输入
        if not bull_id or not cow_id:
            logger.debug(f"无效输入: bull_id={bull_id}, cow_id={cow_id}")
            return 0.0, {}, {}
            
        # 对ID进行标准化处理
        bull_id = bull_id.strip() if isinstance(bull_id, str) else str(bull_id)
        cow_id = cow_id.strip() if isinstance(cow_id, str) else str(cow_id)
        
        # 特殊情况1: 如果公牛是母牛的父亲 - 优先单独处理
        cow_father = self._get_direct_father(cow_id)
        if cow_father and cow_father == bull_id:
            logger.debug(f"直系血亲关系: 公牛 {bull_id} 是母牛 {cow_id} 的父亲")
            logger.debug(f"使用直接公式计算直系血亲关系的近交系数")

            # 计算公牛(父亲)自身的近交系数
            bull_inbreeding, _, _ = self.calculate_inbreeding_coefficient(bull_id)

            # 后代近交系数 = 0.25 * (1 + 父亲近交系数)
            inbreeding_coef = 0.25 * (1 + bull_inbreeding)

            # 创建返回结果
            common_ancestors = {bull_id: inbreeding_coef}
            paths = {bull_id: [(f"子代 <- {cow_id} <- {bull_id} -> {bull_id} -> 子代", inbreeding_coef)]}

            logger.debug(f"直系血亲关系后代近交系数: {inbreeding_coef:.6f} ({inbreeding_coef*100:.2f}%)")
            return inbreeding_coef, common_ancestors, paths

        # 构建牛只系谱 - 使用_get_ancestors_with_paths方法而不是不存在的_build_animal_pedigree
        logger.debug(f"构建公牛 {bull_id} 系谱...")
        bull_pedigree = {}
        bull_ancestors = self._get_ancestors_with_paths(bull_id, self.max_generations)
        for ancestor_id, paths in bull_ancestors.items():
            bull_pedigree[ancestor_id] = ancestor_id
            
        logger.debug(f"构建母牛 {cow_id} 系谱...")
        cow_pedigree = {}
        cow_ancestors = self._get_ancestors_with_paths(cow_id, self.max_generations)
        for ancestor_id, paths in cow_ancestors.items():
            cow_pedigree[ancestor_id] = ancestor_id
        
        # 记录系谱构建结果
        bull_pedigree_size = len(bull_pedigree) if bull_pedigree else 0
        cow_pedigree_size = len(cow_pedigree) if cow_pedigree else 0
        logger.debug(f"系谱构建结果: bull_pedigree_size={bull_pedigree_size}, cow_pedigree_size={cow_pedigree_size}")
        
        if not bull_pedigree or not cow_pedigree:
            logger.debug(f"系谱构建失败: bull_pedigree={bool(bull_pedigree)}, cow_pedigree={bool(cow_pedigree)}")
            # 即使系谱不完整，也返回0而不是nan
            return 0.0, {}, {}
        
        # 计算每个祖先的代数（到牛只的距离）
        def calculate_generation(ancestors_paths):
            """计算每个祖先距离牛只的代数"""
            generations = {}
            for ancestor, paths in ancestors_paths.items():
                # 取最短路径作为代数（距离）
                min_gen = min(len(path) for path in paths) if paths else float('inf')
                generations[ancestor] = min_gen
            return generations
            
        # 计算公牛和母牛祖先的代数
        bull_generations = calculate_generation(bull_ancestors)
        cow_generations = calculate_generation(cow_ancestors)
            
        # 识别共同祖先：直接使用交集，不在集合层面做"远祖合并近祖"的压缩，
        # 让每个祖先在后续通径计算中独立贡献，这样像 509HO11351 这种更近的祖先可以单独展示。
        common_ancestors = set(bull_ancestors.keys()) & set(cow_ancestors.keys())

        # 如果公牛本身是母牛的祖先，也应该计入共同祖先（计算预测后代的近交系数）
        if bull_id in cow_ancestors:
            common_ancestors.add(bull_id)
            # 为公牛添加空路径（公牛到公牛自己，路径长度=0）
            if bull_id not in bull_ancestors:
                bull_ancestors[bull_id] = [[]]
            logger.debug(f"公牛 {bull_id} 是母牛的祖先，计入共同祖先")

        logger.debug(f"找到共同祖先: {len(common_ancestors)}个")

        if not common_ancestors:
            logger.debug("没有找到共同祖先，后代近交系数为0")
            return 0.0, {}, {}
            
        # 计算每个共同祖先的贡献
        inbreeding_contributions = {}
        ancestor_paths = {}
        
        for ancestor in common_ancestors:
            # 计算从公牛和母牛到该祖先的所有路径
            bull_paths = bull_ancestors.get(ancestor, [])
            cow_paths = cow_ancestors.get(ancestor, [])
            
            # 如果任一方没有路径，跳过该祖先
            if not bull_paths or not cow_paths:
                logger.debug(f"祖先 {ancestor} 缺少路径: bull_paths={bool(bull_paths)}, cow_paths={bool(cow_paths)}")
                continue
                
            # 计算该祖先的所有可能路径
            ancestor_contribution = 0.0
            all_path_details = []
            valid_path_count = 0
            invalid_path_count = 0

            for bull_path in bull_paths:
                for cow_path in cow_paths:
                    # Wright通径规则验证：通径中不应有重复节点
                    bull_nodes = set(bull_path)
                    cow_nodes = set(cow_path)
                    common_nodes = bull_nodes & cow_nodes

                    # 检查1：除了共同祖先外，路径不应有其他交叉点
                    if len(common_nodes) > 1 or (len(common_nodes) == 1 and ancestor not in common_nodes):
                        invalid_path_count += 1
                        if invalid_path_count <= 3:
                            logger.debug(f"跳过无效通径（两条路径有交叉）: 父系={' → '.join(bull_path)}, 母系={' → '.join(cow_path)}, 交叉={common_nodes}")
                        continue

                    # 检查2：父系路径（除了终点祖先）不应包含母系起点（cow_id）
                    # 路径格式：[中间节点..., 共同祖先]，所以除去最后一个元素
                    bull_path_without_ancestor = bull_path[:-1] if len(bull_path) > 1 else []
                    if cow_id in bull_path_without_ancestor:
                        invalid_path_count += 1
                        if invalid_path_count <= 3:
                            logger.debug(f"跳过无效通径（父系路径中间包含母系起点）: {bull_id} ← {' ← '.join(bull_path)}")
                        continue

                    # 检查3：母系路径（除了终点祖先）不应包含父系起点（bull_id）
                    # 路径格式：[中间节点..., 共同祖先]，所以除去最后一个元素
                    cow_path_without_ancestor = cow_path[:-1] if len(cow_path) > 1 else []
                    if bull_id in cow_path_without_ancestor:
                        invalid_path_count += 1
                        if invalid_path_count <= 3:
                            logger.debug(f"跳过无效通径（母系路径中间包含父系起点）: {cow_id} ← {' ← '.join(cow_path)}")
                        continue

                    # 检查4：单条路径内部不应有重复节点
                    if len(bull_path) != len(bull_nodes):
                        invalid_path_count += 1
                        if invalid_path_count <= 3:
                            logger.debug(f"跳过无效通径（父系路径内部有重复）: {' ← '.join(bull_path)}")
                        continue

                    if len(cow_path) != len(cow_nodes):
                        invalid_path_count += 1
                        if invalid_path_count <= 3:
                            logger.debug(f"跳过无效通径（母系路径内部有重复）: {' ← '.join(cow_path)}")
                        continue

                    valid_path_count += 1

                    # 计算路径系数: (1/2)^(n1+n2+1) * (1 + F_ancestor)
                    sire_length = len(bull_path)
                    dam_length = len(cow_path)
                    path_length = sire_length + dam_length
                    ancestor_inbreeding, _, _ = self.calculate_inbreeding_coefficient(ancestor)
                    path_coef = (0.5) ** (path_length + 1) * (1 + ancestor_inbreeding)

                    # 构建路径字符串（格式：公牛 ← 父系路径 ← 共同祖先 → 母系路径 → 母牛）
                    # 例如：47 ← 13 ← 29 → 14 → 36
                    # 注意：bull_path和cow_path都包含ancestor作为最后一个元素

                    path_str = f"{bull_id}"

                    # 父系路径：从公牛到共同祖先（bull_path已包含ancestor）
                    if bull_path:
                        path_str += " ← " + " ← ".join([str(p) for p in bull_path])

                    # 母系路径：从共同祖先到母牛
                    # cow_path是从母牛到祖先，格式为[母系节点1, ..., ancestor]
                    # 需要去掉ancestor，反转，然后添加
                    if cow_path:
                        # 去掉最后一个元素（ancestor），然后反转
                        cow_path_without_ancestor = cow_path[:-1] if len(cow_path) > 1 else []
                        if cow_path_without_ancestor:
                            path_str += " → " + " → ".join([str(p) for p in reversed(cow_path_without_ancestor)])

                    path_str += f" → {cow_id}"

                    if valid_path_count <= 5:
                        logger.debug(f"有效通径 {valid_path_count}: {path_str}, n1={sire_length}, n2={dam_length}, 贡献={(path_coef*100):.4f}%")

                    ancestor_contribution += path_coef
                    # 保存为元组: (路径字符串, 贡献值, n1, n2, F_CA)
                    all_path_details.append((path_str, path_coef, sire_length, dam_length, ancestor_inbreeding))

            if invalid_path_count > 0:
                logger.debug(f"祖先 {ancestor}: 过滤掉 {invalid_path_count} 条无效通径，保留 {valid_path_count} 条有效通径")
            
            # 保存这个祖先的总贡献和所有路径(如果贡献大于0)
            if ancestor_contribution > 0:
                inbreeding_contributions[ancestor] = ancestor_contribution
                ancestor_paths[ancestor] = all_path_details
                logger.debug(f"祖先 {ancestor} 对近交系数的贡献: {ancestor_contribution:.6f}")
            else:
                logger.debug(f"祖先 {ancestor} 贡献为零")
        
        # 计算总的近交系数
        total_inbreeding = sum(inbreeding_contributions.values())
        logger.debug(f"后代近交系数计算结果: {total_inbreeding:.6f}, 共同祖先数量: {len(inbreeding_contributions)}")

        # 确保返回值有效
        if math.isnan(total_inbreeding):
            logger.warning(f"计算结果为NaN，返回0.0代替")
            return 0.0, {}, {}
            
        return total_inbreeding, inbreeding_contributions, ancestor_paths
        
    def _get_direct_father(self, animal_id: str) -> Optional[str]:
        """获取动物的直接父亲ID"""
        # 使用系谱库直接查找
        if not animal_id:
            return None
            
        # 从系谱库查找父亲信息
        animal_info = self.pedigree_db.pedigree.get(animal_id, {})
        father_id = animal_info.get('sire')
        
        return father_id
    
    def clear_cache(self):
        """清除计算缓存"""
        self._inbreeding_cache.clear()
        self._path_cache.clear()
        self._ancestors_cache.clear()
        logger.info("计算缓存已清除")
    
    def calculate_relationship_coefficient(self, animal1_id: str, animal2_id: str) -> float:
        """
        计算两个动物之间的亲缘关系系数
        
        Args:
            animal1_id: 第一个动物ID
            animal2_id: 第二个动物ID
            
        Returns:
            float: 亲缘关系系数
        """
        try:
            # 如果是同一个动物，返回1.0
            if animal1_id == animal2_id:
                return 1.0
                
            # 标准化ID
            animal1_id = self.pedigree_db.standardize_animal_id(animal1_id, 'bull')
            animal2_id = self.pedigree_db.standardize_animal_id(animal2_id, 'bull')
            
            # 计算两个动物与其潜在后代的亲缘关系，都是0.5
            # 也就是说，animal1_id和animal2_id的亲缘关系系数 = 2 * 它们潜在后代的近交系数
            offspring_inbreeding, _, _ = self.calculate_potential_offspring_inbreeding(animal1_id, animal2_id)
            relationship_coef = 2 * offspring_inbreeding
            
            return relationship_coef
            
        except Exception as e:
            logging.error(f"计算亲缘关系系数时出错: {e}")
            return 0.0 
