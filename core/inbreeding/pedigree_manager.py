"""
系谱管理模块 - 负责整合所有数据源并提供高效的系谱查询功能
"""

import pandas as pd
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Optional, List, Set, Tuple, Any
import numpy as np
from functools import lru_cache
import re

# 定义Animal类型，用于类型提示
class Animal(Dict[str, Any]):
    """表示一个动物的系谱信息"""
    pass

class PedigreeManager:
    """
    系谱管理器 - 负责整合所有数据源并提供高效的系谱查询功能
    
    主要功能:
    1. 从多个数据源加载动物系谱信息
    2. 提供高效的系谱查询接口
    3. 支持系谱缓存，避免重复查询
    4. 处理循环引用和深度限制
    """
    
    def __init__(self, project_path: Path = None, db_path: str = None, max_depth: int = 5):
        """
        初始化系谱管理器
        
        参数:
            project_path: 项目路径，用于加载标准化的数据文件
            db_path: 本地数据库路径，默认为None，将自动查找
            max_depth: 系谱查询的最大深度，默认为5
        """
        self.project_path = project_path if project_path else Path(".")
        self.db_path = db_path
        self.max_depth = max_depth
        
        # 数据缓存
        self.cow_data = None
        self.breeding_data = None
        self.bull_data = None
        
        # 系谱缓存
        self._animal_cache = {}
        
        # NAAB号和REG号的映射缓存
        self._naab_to_reg_cache = {}
        self._reg_to_naab_cache = {}
        
        # 用于检测循环引用
        self.processed_ids = set()
        
        # 初始化日志
        self.logger = logging.getLogger(__name__)
        
        # 加载数据
        self._load_data()
        
    def _load_data(self):
        """加载所有数据源"""
        self.logger.info("开始加载系谱数据...")
        
        # 加载母牛数据
        if self.project_path:
            cow_data_path = self.project_path / "standardized_data" / "processed_cow_data.xlsx"
            if cow_data_path.exists():
                try:
                    self.cow_data = pd.read_excel(cow_data_path)
                    self.logger.info(f"成功加载母牛数据，共{len(self.cow_data)}行")
                except Exception as e:
                    self.logger.error(f"加载母牛数据失败: {e}")
            
            # 加载配种记录
            breeding_data_path = self.project_path / "standardized_data" / "processed_breeding_data.xlsx"
            if breeding_data_path.exists():
                try:
                    self.breeding_data = pd.read_excel(breeding_data_path)
                    self.logger.info(f"成功加载配种记录，共{len(self.breeding_data)}行")
                except Exception as e:
                    self.logger.error(f"加载配种记录失败: {e}")
            
            # 加载备选公牛数据
            bull_data_path = self.project_path / "standardized_data" / "processed_bull_data.xlsx"
            if bull_data_path.exists():
                try:
                    self.bull_data = pd.read_excel(bull_data_path)
                    self.logger.info(f"成功加载备选公牛数据，共{len(self.bull_data)}行")
                except Exception as e:
                    self.logger.error(f"加载备选公牛数据失败: {e}")
        
        # 确保数据库路径存在
        if self.db_path is None:
            # 尝试在项目根目录查找
            if self.project_path:
                root_db_path = self.project_path / "local_bull_library.db"
                if root_db_path.exists():
                    self.db_path = str(root_db_path)
                    self.logger.info(f"找到数据库: {self.db_path}")
            
            # 如果还是没找到，尝试在当前目录查找
            if self.db_path is None:
                current_db_path = Path("local_bull_library.db")
                if current_db_path.exists():
                    self.db_path = str(current_db_path)
                    self.logger.info(f"找到数据库: {self.db_path}")
                else:
                    self.logger.warning("未找到数据库，部分系谱信息可能不可用")
    
    def is_naab_format(self, bull_id: str) -> bool:
        """
        判断公牛ID是否为NAAB格式（如001HO09162，3个数字+2个字母+5个数字）
        
        参数:
            bull_id: 公牛ID
            
        返回:
            是否为NAAB格式
        """
        if not bull_id or not isinstance(bull_id, str):
            return False
        
        # NAAB格式正则表达式：3个数字 + 2个字母 + 5个数字
        naab_pattern = r'^\d{3}[A-Z]{2}\d{5}$'
        return bool(re.match(naab_pattern, bull_id))
    
    def naab_to_reg(self, naab: str) -> Optional[str]:
        """
        将NAAB号转换为REG号
        
        参数:
            naab: NAAB号
            
        返回:
            对应的REG号，如果未找到则返回None
        """
        if not naab or not self.is_naab_format(naab):
            return None
        
        # 检查缓存
        if naab in self._naab_to_reg_cache:
            return self._naab_to_reg_cache[naab]
        
        # 从数据库查询
        if self.db_path:
            try:
                conn = sqlite3.connect(self.db_path)
                query = """
                    SELECT `BULL REG` as reg
                    FROM bull_library 
                    WHERE `BULL NAAB` = ?
                """
                
                cursor = conn.cursor()
                cursor.execute(query, (naab,))
                result = cursor.fetchone()
                conn.close()
                
                if result and result[0]:
                    reg = result[0]
                    # 缓存结果
                    self._naab_to_reg_cache[naab] = reg
                    self._reg_to_naab_cache[reg] = naab
                    return reg
            except Exception as e:
                self.logger.error(f"NAAB转REG查询出错: {e}")
        
        return None
    
    def reg_to_naab(self, reg: str) -> Optional[str]:
        """
        将REG号转换为NAAB号
        
        参数:
            reg: REG号
            
        返回:
            对应的NAAB号，如果未找到则返回None
        """
        if not reg:
            return None
        
        # 检查缓存
        if reg in self._reg_to_naab_cache:
            return self._reg_to_naab_cache[reg]
        
        # 从数据库查询
        if self.db_path:
            try:
                conn = sqlite3.connect(self.db_path)
                query = """
                    SELECT `BULL NAAB` as naab
                    FROM bull_library 
                    WHERE `BULL REG` = ?
                """
                
                cursor = conn.cursor()
                cursor.execute(query, (reg,))
                result = cursor.fetchone()
                conn.close()
                
                if result and result[0]:
                    naab = result[0]
                    # 缓存结果
                    self._reg_to_naab_cache[reg] = naab
                    self._naab_to_reg_cache[naab] = reg
                    return naab
            except Exception as e:
                self.logger.error(f"REG转NAAB查询出错: {e}")
        
        return None
    
    @lru_cache(maxsize=1024)
    def get_animal_info(self, animal_id: str) -> Optional[Dict[str, Any]]:
        """
        获取动物信息，优先从缓存获取，缓存未命中则从数据源查询
        
        参数:
            animal_id: 动物ID
            
        返回:
            包含动物信息的字典，如果未找到则返回None
        """
        if not animal_id or pd.isna(animal_id) or animal_id == '':
            return None
            
        # 标准化ID
        animal_id = str(animal_id).strip()
        
        # 检查缓存
        if animal_id in self._animal_cache:
            return self._animal_cache[animal_id]
        
        # 如果是NAAB格式，尝试转换为REG格式
        original_id = animal_id
        reg_id = None
        
        if self.is_naab_format(animal_id):
            reg_id = self.naab_to_reg(animal_id)
            if reg_id:
                # 如果转换成功，使用REG号查询，但保留原始NAAB号
                animal_id = reg_id
        
        # 依次从各数据源查询
        animal_info = self._get_bull_info_from_db(animal_id)
        if animal_info:
            # 保存原始NAAB号
            if original_id != animal_id:
                animal_info['naab'] = original_id
            self._animal_cache[original_id] = animal_info
            return animal_info
            
        animal_info = self._get_bull_info_from_file(animal_id)
        if animal_info:
            # 保存原始NAAB号
            if original_id != animal_id:
                animal_info['naab'] = original_id
            self._animal_cache[original_id] = animal_info
            return animal_info
            
        animal_info = self._get_cow_info(animal_id)
        if animal_info:
            self._animal_cache[original_id] = animal_info
            return animal_info
            
        # 未找到信息
        self._animal_cache[original_id] = {'id': original_id, 'not_found': True}
        return self._animal_cache[original_id]
    
    def _get_bull_info_from_db(self, bull_id: str) -> Optional[Dict[str, Any]]:
        """从数据库获取公牛信息"""
        if not self.db_path or not bull_id:
            return None
            
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
                SELECT `BULL NAAB` as naab, `BULL REG` as reg, 
                       `SIRE REG` as sire_reg, `MGS REG` as mgs_reg,
                       `MMGS REG` as mmgs_reg, GIB as gib
                FROM bull_library 
                WHERE `BULL NAAB` = ? OR `BULL REG` = ?
            """
            
            result = pd.read_sql_query(query, conn, params=[bull_id, bull_id])
            conn.close()
            
            if len(result) > 0:
                info = result.iloc[0].to_dict()
                return {
                    'id': bull_id,
                    'type': 'bull',
                    'reg': info.get('reg'),
                    'naab': info.get('naab'),
                    'sire_reg': info.get('sire_reg'),
                    'mgs_reg': info.get('mgs_reg'),
                    'mmgs_reg': info.get('mmgs_reg'),
                    'gib': info.get('gib')
                }
            return None
        except Exception as e:
            self.logger.error(f"查询公牛信息时出错: {e}")
            return None
    
    def _get_bull_info_from_file(self, bull_id: str) -> Optional[Dict[str, Any]]:
        """从备选公牛文件获取公牛信息"""
        if self.bull_data is None or not bull_id:
            return None
            
        # 查找bull_id列
        bull_id_col = None
        for col in ['bull_id', 'naab', 'reg']:
            if col in self.bull_data.columns:
                bull_id_col = col
                break
                
        if bull_id_col is None:
            self.logger.warning("无法找到公牛ID列")
            return None
            
        # 查找匹配的行
        matches = self.bull_data[self.bull_data[bull_id_col] == bull_id]
        if len(matches) == 0:
            return None
            
        # 查找sire列
        sire_col = None
        for col in ['sire', 'sire_reg', '父号']:
            if col in self.bull_data.columns:
                sire_col = col
                break
                
        # 查找mgs列
        mgs_col = None
        for col in ['mgs', 'mgs_reg', '外祖父']:
            if col in self.bull_data.columns:
                mgs_col = col
                break
                
        row = matches.iloc[0]
        result = {
            'id': bull_id,
            'type': 'bull',
        }
        
        if sire_col and pd.notna(row[sire_col]):
            result['sire_reg'] = str(row[sire_col])
            
        if mgs_col and pd.notna(row[mgs_col]):
            result['mgs_reg'] = str(row[mgs_col])
            
        return result
    
    def _get_cow_info(self, cow_id: str) -> Optional[Dict[str, Any]]:
        """从母牛数据获取母牛信息"""
        if self.cow_data is None or not cow_id:
            return None
            
        # 查找cow_id列
        cow_id_col = None
        for col in ['cow_id', '母牛号', '耳号']:
            if col in self.cow_data.columns:
                cow_id_col = col
                break
                
        if cow_id_col is None:
            self.logger.warning("无法找到母牛ID列")
            return None
            
        # 查找匹配的行
        matches = self.cow_data[self.cow_data[cow_id_col] == cow_id]
        if len(matches) == 0:
            return None
            
        # 查找sire列
        sire_col = None
        for col in ['sire', '父号']:
            if col in self.cow_data.columns:
                sire_col = col
                break
                
        # 查找dam列
        dam_col = None
        for col in ['dam', '母号']:
            if col in self.cow_data.columns:
                dam_col = col
                break
                
        # 查找mgs列
        mgs_col = None
        for col in ['mgs', '外祖父']:
            if col in self.cow_data.columns:
                mgs_col = col
                break
                
        row = matches.iloc[0]
        result = {
            'id': cow_id,
            'type': 'cow',
        }
        
        if sire_col and pd.notna(row[sire_col]):
            result['sire'] = str(row[sire_col])
            
        if dam_col and pd.notna(row[dam_col]):
            result['dam'] = str(row[dam_col])
            
        if mgs_col and pd.notna(row[mgs_col]):
            result['mgs'] = str(row[mgs_col])
            
        return result
    
    def build_pedigree(self, animal_id: str, depth: int = 0) -> Animal:
        """
        构建动物的系谱树
        
        参数:
            animal_id: 动物ID
            depth: 当前递归深度
            
        返回:
            系谱树字典
        """
        # 检查循环引用
        if animal_id in self.processed_ids:
            return {'id': animal_id, 'cycle_detected': True}
            
        # 检查深度限制
        if depth >= self.max_depth:
            return {'id': animal_id, 'max_depth_reached': True}
            
        # 标记为已处理
        self.processed_ids.add(animal_id)
        
        # 获取动物信息
        animal_info = self.get_animal_info(animal_id)
        
        if not animal_info or animal_info.get('not_found'):
            self.processed_ids.remove(animal_id)
            return {'id': animal_id, 'not_found': True}
        
        # 构建结果
        result = {'id': animal_id, 'type': animal_info.get('type', 'unknown')}
        
        # 保存REG号和NAAB号
        if animal_info.get('reg'):
            result['reg'] = animal_info['reg']
        
        if animal_info.get('naab'):
            result['naab'] = animal_info['naab']
        elif self.is_naab_format(animal_id):
            result['naab'] = animal_id
        elif animal_info.get('reg'):
            # 尝试查找对应的NAAB号
            naab = self.reg_to_naab(animal_info['reg'])
            if naab:
                result['naab'] = naab
        
        # 递归获取父系信息
        sire_id = animal_info.get('sire') or animal_info.get('sire_reg')
        if sire_id:
            result['sire'] = self.build_pedigree(sire_id, depth + 1)
        
        # 递归获取母系信息
        dam_id = animal_info.get('dam')
        if dam_id:
            result['dam'] = self.build_pedigree(dam_id, depth + 1)
        
        # 获取外祖父信息
        mgs_id = animal_info.get('mgs') or animal_info.get('mgs_reg')
        if mgs_id and not dam_id:  # 如果有母亲信息，则通过母亲获取外祖父
            result['mgs'] = self.build_pedigree(mgs_id, depth + 1)
        
        # 获取外祖母的父亲信息
        mmgs_id = animal_info.get('mmgs_reg')
        if mmgs_id and not dam_id:  # 如果有母亲信息，则通过母亲获取
            result['mmgs'] = self.build_pedigree(mmgs_id, depth + 1)
        
        # 处理完成，从已处理集合中移除
        self.processed_ids.remove(animal_id)
        
        return result
    
    def find_common_ancestors(self, animal1_id: str, animal2_id: str) -> List[Dict[str, Any]]:
        """
        查找两个动物的共同祖先
        
        参数:
            animal1_id: 第一个动物ID
            animal2_id: 第二个动物ID
            
        返回:
            共同祖先列表，每个元素包含祖先ID和到两个动物的路径
        """
        # 重置处理集合
        self.processed_ids = set()
        
        # 构建两个动物的系谱
        pedigree1 = self.build_pedigree(animal1_id)
        
        # 重置处理集合
        self.processed_ids = set()
        
        pedigree2 = self.build_pedigree(animal2_id)
        
        # 获取第一个动物的所有祖先
        ancestors1 = self._extract_ancestors(pedigree1)
        
        # 获取第二个动物的所有祖先
        ancestors2 = self._extract_ancestors(pedigree2)
        
        # 查找共同祖先
        common_ancestors = []
        for ancestor_id in ancestors1.keys():
            if ancestor_id in ancestors2:
                common_ancestors.append({
                    'id': ancestor_id,
                    'path1': ancestors1[ancestor_id],
                    'path2': ancestors2[ancestor_id]
                })
        
        return common_ancestors
    
    def _extract_ancestors(self, pedigree: Dict[str, Any], path: List[str] = None) -> Dict[str, List[str]]:
        """
        从系谱树中提取所有祖先及其路径
        
        参数:
            pedigree: 系谱树
            path: 当前路径
            
        返回:
            祖先ID到路径的映射
        """
        if path is None:
            path = []
        
        result = {}
        
        # 如果检测到循环或达到最大深度，则跳过
        if pedigree.get('cycle_detected') or pedigree.get('max_depth_reached') or pedigree.get('not_found'):
            return result
        
        # 当前动物ID
        animal_id = pedigree['id']
        current_path = path + [animal_id]
        
        # 将当前动物添加到结果中（无论是否是祖先）
        result[animal_id] = current_path[:-1]  # 不包括当前动物自身
        
        # 递归处理父亲
        if 'sire' in pedigree:
            sire_ancestors = self._extract_ancestors(pedigree['sire'], current_path)
            result.update(sire_ancestors)
        
        # 递归处理母亲
        if 'dam' in pedigree:
            dam_ancestors = self._extract_ancestors(pedigree['dam'], current_path)
            result.update(dam_ancestors)
        
        # 递归处理外祖父（如果直接提供）
        if 'mgs' in pedigree:
            mgs_ancestors = self._extract_ancestors(pedigree['mgs'], current_path)
            result.update(mgs_ancestors)
        
        # 递归处理外祖母的父亲（如果直接提供）
        if 'mmgs' in pedigree:
            mmgs_ancestors = self._extract_ancestors(pedigree['mmgs'], current_path)
            result.update(mmgs_ancestors)
        
        return result
    
    def clear_cache(self):
        """清除所有缓存"""
        self._animal_cache.clear()
        self.get_animal_info.cache_clear()
        self.processed_ids.clear() 