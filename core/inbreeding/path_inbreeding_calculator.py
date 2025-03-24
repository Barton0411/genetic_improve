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
        
        print(f"\n========== 开始计算动物 {animal_id} 的近交系数 ==========")
        
        # 如果已经计算过，直接返回缓存结果
        if animal_id in self._inbreeding_cache:
            inbreeding_coef, contributions, paths = self._inbreeding_cache[animal_id]
            print(f"发现缓存结果: 近交系数 = {inbreeding_coef:.6f} ({inbreeding_coef*100:.4f}%)")
            return self._inbreeding_cache[animal_id]
        
        # 检查动物是否在系谱中
        if animal_id not in self.pedigree_db.pedigree:
            print(f"警告: 动物 {animal_id} 不在系谱中")
            logging.warning(f"动物 {animal_id} 不在系谱中")
            return 0.0, {}, {}
        
        # 检查是否有GIB值
        animal_info = self.pedigree_db.pedigree[animal_id]
        if animal_info.get('gib') is not None:
            gib_value = animal_info['gib']
            # 确保GIB值是小数（有些系统可能存储为百分比）
            if gib_value > 1.0:
                print(f"GIB值为百分比格式，转换为小数: {gib_value} -> {gib_value/100.0}")
                gib_value = gib_value / 100.0
            print(f"动物 {animal_id} 有GIB值: {gib_value:.6f} ({gib_value*100:.4f}%), 直接使用")
            logging.info(f"动物 {animal_id} 有GIB值: {gib_value:.4f}, 直接使用")
            # 因为没有路径信息，返回空字典
            self._inbreeding_cache[animal_id] = (gib_value, {"GIB值": gib_value}, {})
            return gib_value, {"GIB值": gib_value}, {}
        
        start_time = time.time()
        print(f"动物 {animal_id} 无GIB值，使用通径法(Wright's Formula)计算近交系数")
        logging.info(f"开始计算动物 {animal_id} 的近交系数 (通径法)")
        
        # 获取动物的父母
        info = self.pedigree_db.pedigree[animal_id]
        sire_id = info.get('sire', '')
        dam_id = info.get('dam', '')
        
        print(f"动物 {animal_id} 的父亲: {sire_id}, 母亲: {dam_id}")
        
        # 如果父母信息不全，无法计算近交系数
        if not sire_id or not dam_id:
            print(f"警告: 动物 {animal_id} 的父母信息不全，无法使用通径法计算近交系数")
            logging.warning(f"动物 {animal_id} 的父母信息不全，无法使用通径法计算近交系数")
            return 0.0, {"父母信息不全": 0.0}, {}
        
        # 使用通径法计算近交系数
        inbreeding_coef, contributions, paths = self._calculate_using_path_method(sire_id, dam_id)
        
        elapsed_time = time.time() - start_time
        print(f"动物 {animal_id} 的近交系数计算完成: {inbreeding_coef:.6f} ({inbreeding_coef*100:.4f}%), 耗时: {elapsed_time:.2f}秒")
        print(f"找到 {len(contributions)} 个共同祖先")
        if contributions:
            max_contributor = max(contributions.items(), key=lambda x: x[1])
            print(f"贡献最大的祖先: {max_contributor[0]}, 贡献值: {max_contributor[1]:.6f} ({max_contributor[1]*100:.4f}%)")
        print(f"========== 计算结束 ==========\n")
        
        logging.info(f"动物 {animal_id} 的近交系数计算完成: {inbreeding_coef:.4f}, 耗时: {elapsed_time:.2f}秒")
        
        # 缓存结果
        self._inbreeding_cache[animal_id] = (inbreeding_coef, contributions, paths)
        
        return inbreeding_coef, contributions, paths
    
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
        
        print(f"计算 {sire_id} 和 {dam_id} 的共同祖先")
        
        # 检查是否有缓存
        cache_key = (sire_id, dam_id)
        if cache_key in self._path_cache:
            inbreeding_coef, contributions, paths = self._path_cache[cache_key]
            print(f"发现缓存结果: 总共 {len(contributions)} 个共同祖先, 近交系数 = {inbreeding_coef:.6f}")
            return self._path_cache[cache_key]
        
        # 获取父系和母系祖先
        print(f"收集 {sire_id} 的祖先...")
        sire_ancestors = self._get_ancestors_with_paths(sire_id, self.max_generations)
        print(f"找到 {len(sire_ancestors)} 个父系祖先")
        
        print(f"收集 {dam_id} 的祖先...")
        dam_ancestors = self._get_ancestors_with_paths(dam_id, self.max_generations)
        print(f"找到 {len(dam_ancestors)} 个母系祖先")
        
        # 找出共同祖先
        common_ancestors = set(sire_ancestors.keys()) & set(dam_ancestors.keys())
        
        print(f"找到 {len(common_ancestors)} 个共同祖先: {', '.join(list(common_ancestors)[:5])}{'...' if len(common_ancestors) > 5 else ''}")
        
        # 计算各个共同祖先的贡献
        inbreeding_coef = 0.0
        contributions = {}
        paths = {}
        
        for ancestor_id in common_ancestors:
            # 获取所有从父亲到祖先的路径
            sire_paths = sire_ancestors[ancestor_id]
            # 获取所有从母亲到祖先的路径
            dam_paths = dam_ancestors[ancestor_id]
            
            print(f"\n-- 计算祖先 {ancestor_id} 的贡献 --")
            print(f"  从父亲到祖先的路径数: {len(sire_paths)}")
            print(f"  从母亲到祖先的路径数: {len(dam_paths)}")
            
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
                    
                    # 检查是否是有效路径（不包含重复节点）
                    sire_nodes = set(sire_path)
                    dam_nodes = set(dam_path)
                    # 除了共同祖先外，路径不应有其他交叉点
                    common_nodes = sire_nodes & dam_nodes
                    if len(common_nodes) > 1 or (len(common_nodes) == 1 and ancestor_id not in common_nodes):
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
                    if valid_path_count <= 5:  # 只打印前5条路径
                        sire_path_str = " -> ".join([str(x) for x in sire_path])
                        dam_path_str = " -> ".join([str(x) for x in dam_path])
                        print(f"  路径 {valid_path_count}: {sire_id} -> {sire_path_str} <- {dam_path_str} <- {dam_id}")
                        print(f"    路径长度: 父系={sire_length}, 母系={dam_length}, 总长度={sire_length+dam_length}")
                        print(f"    基础贡献: 0.5^{sire_length+dam_length} = {0.5**(sire_length+dam_length):.8f}")
                        if ancestor_f > 0:
                            print(f"    祖先 {ancestor_id} 自身的近交系数: {ancestor_f:.6f}")
                            print(f"    调整后贡献: {0.5**(sire_length+dam_length):.8f} * (1 + {ancestor_f:.6f}) = {path_contribution:.8f}")
                        else:
                            print(f"    最终贡献: {path_contribution:.8f}")
                    
                    # 记录路径和贡献
                    sire_path_str = " -> ".join([str(x) for x in sire_path])
                    dam_path_str = " -> ".join([str(x) for x in dam_path])
                    path_str = f"{sire_id} -> {sire_path_str} <- {dam_path_str} <- {dam_id}"
                    ancestor_paths.append((path_str, path_contribution))
                    
                    # 累加贡献
                    ancestor_contribution += path_contribution
            
            # 记录该祖先的总贡献
            if ancestor_contribution > 0:
                contributions[ancestor_id] = ancestor_contribution
                paths[ancestor_id] = ancestor_paths
                
                # 累加到总近交系数
                inbreeding_coef += ancestor_contribution
                print(f"  祖先 {ancestor_id} 共有 {valid_path_count} 条有效路径, 总贡献值: {ancestor_contribution:.8f}")
                print(f"  当前累计近交系数: {inbreeding_coef:.8f}")
            else:
                print(f"  祖先 {ancestor_id} 没有有效路径或贡献为零")
        
        print(f"\n最终近交系数: {inbreeding_coef:.8f} ({inbreeding_coef*100:.6f}%)")
        
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
        result = {}  # 祖先ID -> 路径列表
        
        # 若animal_id不在系谱中，直接返回
        if animal_id not in self.pedigree_db.pedigree:
            print(f"动物 {animal_id} 不在系谱中，无法获取祖先")
            return result
            
        # 初始化队列，每个元素是(当前ID, 当前路径, 当前代数)
        queue = [(animal_id, [], 0)]
        visited = set()  # 记录已经访问过的节点，避免环路
        
        print(f"开始搜索 {animal_id} 的祖先，最大追溯 {max_generations} 代")
        
        parent_count = 0
        while queue:
            current_id, current_path, current_gen = queue.pop(0)
            
            # 如果已经处理过这个节点，或者超过最大代数，跳过
            if current_id in visited or current_gen > max_generations:
                continue
                
            # 标记为已访问
            visited.add(current_id)
            
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
                
                # 打印进度（每100个父母打印一次）
                parent_count += 1
                if parent_count <= 10 or parent_count % 100 == 0:
                    gen_str = '代数' + str(current_gen)
                    print(f"  {gen_str:<6} 处理 {current_id:<15} 父: {sire_id:<15} 母: {dam_id:<15}")
                
                if sire_id and sire_id not in visited:
                    queue.append((sire_id, new_path, current_gen + 1))
                if dam_id and dam_id not in visited:
                    queue.append((dam_id, new_path, current_gen + 1))
        
        # 打印结果统计
        total_paths = sum(len(paths) for paths in result.values())
        print(f"完成搜索，找到 {len(result)} 个祖先，共 {total_paths} 条路径")
        
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
        print(f"计算后代近交系数: bull_id={bull_id}, cow_id={cow_id}")
        
        # 检查输入
        if not bull_id or not cow_id:
            print(f"[DEBUG] 无效输入: bull_id={bull_id}, cow_id={cow_id}")
            return 0.0, {}, {}
            
        # 对ID进行标准化处理
        bull_id = bull_id.strip() if isinstance(bull_id, str) else str(bull_id)
        cow_id = cow_id.strip() if isinstance(cow_id, str) else str(cow_id)
        
        # 特殊情况: 如果公牛是母牛的父亲 - 优先单独处理
        cow_father = self._get_direct_father(cow_id)
        if cow_father and cow_father == bull_id:
            print(f"[INFO] 直系血亲关系: 公牛 {bull_id} 是母牛 {cow_id} 的父亲")
            print(f"[INFO] 使用直接公式计算直系血亲关系的近交系数")
            
            # 计算公牛(父亲)自身的近交系数
            bull_inbreeding, _, _ = self.calculate_inbreeding_coefficient(bull_id)
            
            # 后代近交系数 = 0.25 * (1 + 父亲近交系数)
            inbreeding_coef = 0.25 * (1 + bull_inbreeding)
            
            # 创建返回结果
            common_ancestors = {bull_id: inbreeding_coef}
            paths = {bull_id: [(f"子代 <- {cow_id} <- {bull_id} -> {bull_id} -> 子代", inbreeding_coef)]}
            
            print(f"[RESULT] 直系血亲关系后代近交系数: {inbreeding_coef:.6f} ({inbreeding_coef*100:.2f}%)")
            return inbreeding_coef, common_ancestors, paths
        
        # 构建牛只系谱 - 使用_get_ancestors_with_paths方法而不是不存在的_build_animal_pedigree
        print(f"构建公牛 {bull_id} 系谱...")
        bull_pedigree = {}
        bull_ancestors = self._get_ancestors_with_paths(bull_id, self.max_generations)
        for ancestor_id, paths in bull_ancestors.items():
            bull_pedigree[ancestor_id] = ancestor_id
            
        print(f"构建母牛 {cow_id} 系谱...")
        cow_pedigree = {}
        cow_ancestors = self._get_ancestors_with_paths(cow_id, self.max_generations)
        for ancestor_id, paths in cow_ancestors.items():
            cow_pedigree[ancestor_id] = ancestor_id
        
        # 记录系谱构建结果
        bull_pedigree_size = len(bull_pedigree) if bull_pedigree else 0
        cow_pedigree_size = len(cow_pedigree) if cow_pedigree else 0
        print(f"系谱构建结果: bull_pedigree_size={bull_pedigree_size}, cow_pedigree_size={cow_pedigree_size}")
        
        if not bull_pedigree or not cow_pedigree:
            print(f"[ERROR] 系谱构建失败: bull_pedigree={bool(bull_pedigree)}, cow_pedigree={bool(cow_pedigree)}")
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
            
        # 识别共同祖先
        all_common_ancestors = set(bull_ancestors.keys()) & set(cow_ancestors.keys())
        print(f"找到所有共同祖先: {len(all_common_ancestors)}个")
        
        # 特殊情况: 如果公牛或母牛是对方的祖先，将其添加到共同祖先集合
        if bull_id in cow_ancestors and bull_id not in all_common_ancestors:
            all_common_ancestors.add(bull_id)
            print(f"[INFO] 添加公牛 {bull_id} 作为母牛祖先到共同祖先集合")
            
        if cow_id in bull_ancestors and cow_id not in all_common_ancestors:
            all_common_ancestors.add(cow_id)
            print(f"[INFO] 添加母牛 {cow_id} 作为公牛祖先到共同祖先集合")
        
        # 按代数对共同祖先排序 (代数越小表示越接近牛只)
        sorted_common_ancestors = sorted(
            all_common_ancestors,
            key=lambda x: min(bull_generations.get(x, float('inf')), cow_generations.get(x, float('inf')))
        )
        
        # 过滤掉在同一血缘线上已有更近共同祖先的远祖先
        filtered_common_ancestors = set()
        # 记录每条路径上是否已有共同祖先
        bull_path_has_ca = {}  # 键: 路径标识符，值: 已存在的最近共同祖先
        cow_path_has_ca = {}   # 键: 路径标识符，值: 已存在的最近共同祖先
        
        for ancestor in sorted_common_ancestors:
            # 获取所有从公牛和母牛到该祖先的路径
            bull_paths = bull_ancestors.get(ancestor, [])
            cow_paths = cow_ancestors.get(ancestor, [])
            
            # 如果任一方没有路径，跳过该祖先
            if not bull_paths or not cow_paths:
                print(f"[WARNING] 祖先 {ancestor} 缺少路径，跳过")
                continue
                
            # 检查是否是需要标记的共同祖先
            should_mark = False
            
            # 特殊情况：祖先就是公牛或母牛本身，必须标记
            if ancestor == bull_id or ancestor == cow_id:
                should_mark = True
                filtered_common_ancestors.add(ancestor)
                print(f"[INFO] 标记特殊祖先: {ancestor} (是公牛或母牛本身)")
                continue
                
            # 检查公牛侧的路径
            for path_idx, path in enumerate(bull_paths):
                path_key = f"bull_path_{path_idx}"
                # 如果这条路径上还没有标记过共同祖先
                if path_key not in bull_path_has_ca:
                    bull_path_has_ca[path_key] = ancestor
                    should_mark = True
            
            # 检查母牛侧的路径
            for path_idx, path in enumerate(cow_paths):
                path_key = f"cow_path_{path_idx}"
                # 如果这条路径上还没有标记过共同祖先
                if path_key not in cow_path_has_ca:
                    cow_path_has_ca[path_key] = ancestor
                    should_mark = True
            
            # 如果需要标记，加入过滤后的共同祖先集合
            if should_mark:
                filtered_common_ancestors.add(ancestor)
                print(f"[INFO] 标记祖先: {ancestor}")
                
        # 使用过滤后的共同祖先进行计算
        common_ancestors = filtered_common_ancestors
        
        # 记录共同祖先数量
        print(f"过滤后的共同祖先数量: {len(common_ancestors)}")
        
        # 如果没有共同祖先，近交系数为0
        if not common_ancestors:
            print(f"[INFO] 没有找到共同祖先，后代近交系数为0")
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
                print(f"[WARNING] 祖先 {ancestor} 缺少路径: bull_paths={bool(bull_paths)}, cow_paths={bool(cow_paths)}")
                continue
                
            # 计算该祖先的所有可能路径
            ancestor_contribution = 0.0
            all_path_details = []
            
            # 特殊情况处理：如果祖先就是公牛自己
            if ancestor == bull_id:
                print(f"[INFO] 特殊情况: 公牛 {bull_id} 自身是共同祖先")
                # 公牛直接是母牛的某个祖先
                for cow_path in cow_paths:
                    # 计算路径系数: (1/2)^(n+1) * (1 + F_ancestor)
                    # 这里n是路径长度，+1是因为还要从公牛到后代
                    path_length = len(cow_path)
                    ancestor_inbreeding, _, _ = self.calculate_inbreeding_coefficient(ancestor)
                    path_coef = (0.5) ** (path_length + 1) * (1 + ancestor_inbreeding)
                    
                    # 构建路径字符串
                    path_str = f"子代 <- {cow_id} <- "
                    path_str += " <- ".join([str(p) for p in reversed(cow_path)])
                    path_str += f" -> {bull_id} -> 子代"
                    
                    print(f"[DEBUG] 路径: {path_str}, 长度: {path_length}, 系数: {path_coef:.6f}")
                    
                    ancestor_contribution += path_coef
                    all_path_details.append((path_str, path_coef))
                    
            # 特殊情况处理：如果祖先就是母牛自己
            elif ancestor == cow_id:
                print(f"[INFO] 特殊情况: 母牛 {cow_id} 自身是共同祖先")
                # 母牛直接是公牛的某个祖先（非常罕见）
                for bull_path in bull_paths:
                    # 计算路径系数: (1/2)^(n+1) * (1 + F_ancestor)
                    path_length = len(bull_path)
                    ancestor_inbreeding, _, _ = self.calculate_inbreeding_coefficient(ancestor)
                    path_coef = (0.5) ** (path_length + 1) * (1 + ancestor_inbreeding)
                    
                    # 构建路径字符串
                    path_str = f"子代 <- {bull_id} <- "
                    path_str += " <- ".join([str(p) for p in reversed(bull_path)])
                    path_str += f" -> {cow_id} -> 子代"
                    
                    print(f"[DEBUG] 路径: {path_str}, 长度: {path_length}, 系数: {path_coef:.6f}")
                    
                    ancestor_contribution += path_coef
                    all_path_details.append((path_str, path_coef))
            
            # 正常情况：祖先既不是公牛也不是母牛
            else:
                # 计算所有可能的路径组合
                for bull_path in bull_paths:
                    for cow_path in cow_paths:
                        # 计算路径系数: (1/2)^(n1+n2+1) * (1 + F_ancestor)
                        path_length = len(bull_path) + len(cow_path)
                        ancestor_inbreeding, _, _ = self.calculate_inbreeding_coefficient(ancestor)
                        path_coef = (0.5) ** (path_length + 1) * (1 + ancestor_inbreeding)
                        
                        # 构建路径字符串
                        path_str = f"子代 <- {cow_id} <- "
                        path_str += " <- ".join([str(p) for p in reversed(cow_path)])
                        path_str += f" -> {ancestor} -> "
                        path_str += " -> ".join([str(p) for p in bull_path])
                        path_str += f" -> {bull_id} -> 子代"
                        
                        ancestor_contribution += path_coef
                        all_path_details.append((path_str, path_coef))
            
            # 保存这个祖先的总贡献和所有路径(如果贡献大于0)
            if ancestor_contribution > 0:
                inbreeding_contributions[ancestor] = ancestor_contribution
                ancestor_paths[ancestor] = all_path_details
                print(f"[INFO] 祖先 {ancestor} 对近交系数的贡献: {ancestor_contribution:.6f}")
            else:
                print(f"[WARNING] 祖先 {ancestor} 贡献为零")
        
        # 计算总的近交系数
        total_inbreeding = sum(inbreeding_contributions.values())
        print(f"[RESULT] 后代近交系数计算结果: {total_inbreeding:.6f}, 共同祖先数量: {len(inbreeding_contributions)}")
        
        # 确保返回值有效
        if math.isnan(total_inbreeding):
            print(f"[ERROR] 计算结果为NaN，返回0.0代替")
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
        logging.info("计算缓存已清除")
    
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