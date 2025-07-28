#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Wright近交系数计算器
基于Wright方法计算个体的近交系数和个体间的近亲系数
"""

import logging
from typing import Dict, List, Tuple, Set, Optional

from core.inbreeding.pedigree_manager import PedigreeManager, Animal

class WrightInbreedingCalculator:
    """Wright近交系数计算器类"""
    
    def __init__(self, pedigree_manager: PedigreeManager):
        """
        初始化Wright近交系数计算器
        
        Args:
            pedigree_manager: 系谱管理器实例
        """
        self.pedigree_manager = pedigree_manager
        self.inbreeding_cache = {}  # 缓存已计算的近交系数
        self.relationship_cache = {}  # 缓存已计算的近亲系数
        
    def calculate_inbreeding(self, animal_id: str) -> float:
        """
        计算个体的近交系数
        
        Args:
            animal_id: 个体ID（可以是NAAB号或REG号）
            
        Returns:
            近交系数，范围[0, 1]
        """
        # 检查是否为NAAB格式，如果是则尝试转换为REG号
        original_id = animal_id
        if self.pedigree_manager.is_naab_format(animal_id):
            reg_id = self.pedigree_manager.naab_to_reg(animal_id)
            if reg_id:
                animal_id = reg_id
        
        # 检查缓存
        cache_key = original_id
        if cache_key in self.inbreeding_cache:
            return self.inbreeding_cache[cache_key]
        
        # 构建系谱
        animal = self.pedigree_manager.build_pedigree(animal_id)
        if not animal:
            raise ValueError(f"无法找到ID为 {original_id} 的个体")
        
        # 如果没有父母信息，则近交系数为0
        if not animal.get('sire') and not animal.get('dam'):
            self.inbreeding_cache[cache_key] = 0.0
            return 0.0
        
        # 计算近交系数
        inbreeding_coef = self._calculate_inbreeding_recursive(animal)
        
        # 缓存结果
        self.inbreeding_cache[cache_key] = inbreeding_coef
        
        return inbreeding_coef
    
    def _calculate_inbreeding_recursive(self, animal: Animal) -> float:
        """
        递归计算个体的近交系数
        
        Args:
            animal: 个体对象
            
        Returns:
            近交系数，范围[0, 1]
        """
        # 如果没有父母，则近交系数为0
        if not animal.get('sire') or not animal.get('dam'):
            return 0.0
        
        # 找出所有共同祖先
        common_ancestors = self.pedigree_manager.find_common_ancestors(
            animal['sire']['id'], animal['dam']['id']
        )
        
        if not common_ancestors:
            return 0.0
        
        # 计算每个共同祖先的贡献
        inbreeding_coef = 0.0
        for ancestor_info in common_ancestors:
            ancestor_id = ancestor_info['id']
            path1 = ancestor_info['path1']
            path2 = ancestor_info['path2']
            
            # 计算路径长度（代数）
            n1 = len(path1)
            n2 = len(path2)
            
            # 获取祖先的近交系数
            ancestor_inbreeding = 0.0
            try:
                ancestor_inbreeding = self.calculate_inbreeding(ancestor_id)
            except ValueError:
                # 如果无法计算祖先的近交系数，则使用0
                pass
            
            # 计算该祖先对近交系数的贡献
            # F = Σ (0.5)^(n1+n2+1) * (1 + Fa)
            contribution = (0.5) ** (n1 + n2 + 1) * (1 + ancestor_inbreeding)
            inbreeding_coef += contribution
        
        return inbreeding_coef
    
    def calculate_relationship(self, animal_id1: str, animal_id2: str) -> float:
        """
        计算两个个体之间的近亲系数
        
        Args:
            animal_id1: 第一个个体ID（可以是NAAB号或REG号）
            animal_id2: 第二个个体ID（可以是NAAB号或REG号）
            
        Returns:
            近亲系数，范围[0, 1]
        """
        # 检查是否为同一个体
        if animal_id1 == animal_id2:
            return 1.0
        
        # 处理NAAB号转换
        original_id1 = animal_id1
        original_id2 = animal_id2
        
        if self.pedigree_manager.is_naab_format(animal_id1):
            reg_id = self.pedigree_manager.naab_to_reg(animal_id1)
            if reg_id:
                animal_id1 = reg_id
        
        if self.pedigree_manager.is_naab_format(animal_id2):
            reg_id = self.pedigree_manager.naab_to_reg(animal_id2)
            if reg_id:
                animal_id2 = reg_id
        
        # 创建缓存键（按字母顺序排序以确保一致性）
        cache_key = tuple(sorted([original_id1, original_id2]))
        
        # 检查缓存
        if cache_key in self.relationship_cache:
            return self.relationship_cache[cache_key]
        
        # 构建系谱
        animal1 = self.pedigree_manager.build_pedigree(animal_id1)
        animal2 = self.pedigree_manager.build_pedigree(animal_id2)
        
        if not animal1 or not animal2:
            missing_id = original_id1 if not animal1 else original_id2
            raise ValueError(f"无法找到ID为 {missing_id} 的个体")
        
        # 找出所有共同祖先
        common_ancestors = self.pedigree_manager.find_common_ancestors(animal_id1, animal_id2)
        
        if not common_ancestors:
            self.relationship_cache[cache_key] = 0.0
            return 0.0
        
        # 计算每个共同祖先的贡献
        relationship_coef = 0.0
        for ancestor_info in common_ancestors:
            ancestor_id = ancestor_info['id']
            path1 = ancestor_info['path1']
            path2 = ancestor_info['path2']
            
            # 计算路径长度（代数）
            n1 = len(path1)
            n2 = len(path2)
            
            # 获取祖先的近交系数
            ancestor_inbreeding = 0.0
            try:
                ancestor_inbreeding = self.calculate_inbreeding(ancestor_id)
            except ValueError:
                # 如果无法计算祖先的近交系数，则使用0
                pass
            
            # 计算该祖先对近亲系数的贡献
            # R = Σ (0.5)^(n1+n2) * (1 + Fa)
            contribution = (0.5) ** (n1 + n2) * (1 + ancestor_inbreeding)
            relationship_coef += contribution
        
        # 缓存结果
        self.relationship_cache[cache_key] = relationship_coef
        
        return relationship_coef
    
    def get_animal_display_id(self, animal_id: str) -> str:
        """
        获取动物的显示ID，优先使用NAAB号，如果没有则使用REG号
        
        Args:
            animal_id: 动物ID
            
        Returns:
            用于显示的ID
        """
        # 如果已经是NAAB格式，直接返回
        if self.pedigree_manager.is_naab_format(animal_id):
            return animal_id
        
        # 尝试获取对应的NAAB号
        naab_id = self.pedigree_manager.reg_to_naab(animal_id)
        if naab_id:
            return f"{animal_id} (NAAB: {naab_id})"
        
        return animal_id 