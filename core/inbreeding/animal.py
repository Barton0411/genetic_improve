#!/usr/bin/env python
# -*- coding: utf-8 -*-

class Animal:
    """动物类，用于近交系数计算"""
    
    def __init__(self, id: str, sire_id: str = None, dam_id: str = None):
        """初始化动物对象
        
        Args:
            id: 动物ID
            sire_id: 父亲ID
            dam_id: 母亲ID
        """
        self.id = id
        self.sire_id = sire_id
        self.dam_id = dam_id
        self.inbreeding_coef = 0.0  # 近交系数
        
    def __str__(self):
        """字符串表示"""
        return f"Animal(id={self.id}, sire={self.sire_id}, dam={self.dam_id})"
    
    def __repr__(self):
        """表示形式"""
        return self.__str__()
    
    @property
    def has_parents(self):
        """是否有父母信息"""
        return self.sire_id is not None or self.dam_id is not None
    
    @property
    def has_complete_parents(self):
        """是否有完整的父母信息"""
        return self.sire_id is not None and self.dam_id is not None 