# core/inbreeding/pedigree_database.py

import logging
import sqlite3
import pickle
import os
from pathlib import Path
import pandas as pd
import re
from typing import Dict, Set, List, Tuple, Optional
from sqlalchemy import create_engine, text
import time

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PedigreeDatabase:
    """系谱库管理类，负责构建和维护基于本地bull_library的系谱库"""
    
    def __init__(self, db_path: Path, pedigree_cache_path: Optional[Path] = None):
        """
        初始化系谱库管理器
        
        Args:
            db_path: 本地bull_library.db的路径
            pedigree_cache_path: 系谱库缓存文件路径，默认为db_path同目录下的pedigree_cache.pkl
        """
        self.db_path = db_path
        self.pedigree_cache_path = pedigree_cache_path or db_path.parent / 'pedigree_cache.pkl'
        self.engine = create_engine(f'sqlite:///{db_path}')
        
        # 系谱数据结构
        self.pedigree = {}  # 格式: {animal_id: {'sire': sire_id, 'dam': dam_id, 'type': type}}
        self.virtual_nodes = set()  # 跟踪虚拟节点
        
        # NAAB到REG映射缓存
        self.naab_to_reg_map = {}
        
    def build_pedigree(self, progress_callback=None) -> Dict:
        """
        构建系谱库
        
        Args:
            progress_callback: 进度回调函数
            
        Returns:
            Dict: 构建好的系谱库
        """
        try:
            if progress_callback:
                progress_callback(0, "开始构建系谱库...")
                
            # 加载NAAB到REG映射
            if progress_callback:
                progress_callback(20, "加载NAAB到REG映射...")
            self._load_naab_reg_mapping()
            
            # 构建公牛系谱
            if progress_callback:
                progress_callback(30, "构建公牛系谱...")
            self._build_bull_pedigree(progress_callback)
            
            # 保存系谱库
            if progress_callback:
                progress_callback(90, "保存系谱库...")
            self._save_pedigree_to_cache()
            
            if progress_callback:
                progress_callback(100, "系谱库构建完成")
                
            return self.pedigree
        except Exception as e:
            logging.error(f"构建系谱库失败: {e}")
            if progress_callback:
                progress_callback(-1, f"构建系谱库失败: {e}")
            return {}
    
    def load_pedigree(self) -> Dict:
        """
        尝试从缓存加载系谱库
        
        Returns:
            Dict: 加载的系谱库，如果加载失败则返回空字典
        """
        try:
            if not self.pedigree_cache_path.exists():
                logging.info("系谱缓存文件不存在")
                return {}
                
            start_time = time.time()
            with open(self.pedigree_cache_path, 'rb') as f:
                cached_data = pickle.load(f)
                self.pedigree = cached_data.get('pedigree', {})
                self.virtual_nodes = cached_data.get('virtual_nodes', set())
                self.naab_to_reg_map = cached_data.get('naab_to_reg_map', {})
                
            logging.info(f"从缓存加载系谱库完成，包含{len(self.pedigree)}个动物，耗时{time.time()-start_time:.2f}秒")
            return self.pedigree
        except Exception as e:
            logging.error(f"从缓存加载系谱库失败: {e}")
            # 加载失败时初始化空系谱
            self.pedigree = {}
            self.virtual_nodes = set()
            return {}
    
    def _save_pedigree_to_cache(self):
        """将系谱库保存到缓存文件"""
        try:
            # 确保存在父目录
            self.pedigree_cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 准备缓存数据
            cache_data = {
                'pedigree': self.pedigree,
                'virtual_nodes': self.virtual_nodes,
                'naab_to_reg_map': self.naab_to_reg_map,
                'timestamp': time.time()
            }
            
            with open(self.pedigree_cache_path, 'wb') as f:
                pickle.dump(cache_data, f)
                
            logging.info(f"系谱库已保存到缓存文件: {self.pedigree_cache_path}")
        except Exception as e:
            logging.error(f"保存系谱库到缓存失败: {e}")
    
    def _load_naab_reg_mapping(self):
        """加载NAAB号到REG号的映射"""
        try:
            query = "SELECT `BULL NAAB`, `BULL REG` FROM bull_library WHERE `BULL NAAB` IS NOT NULL AND `BULL REG` IS NOT NULL"
            df = pd.read_sql(query, self.engine)
            
            # 构建映射字典
            mapping = {}
            for _, row in df.iterrows():
                naab = row['BULL NAAB']
                reg = row['BULL REG']
                if pd.notna(naab) and pd.notna(reg) and naab and reg:
                    mapping[str(naab).strip()] = str(reg).strip()
            
            self.naab_to_reg_map = mapping
            logging.info(f"已加载{len(mapping)}个NAAB到REG的映射")
        except Exception as e:
            logging.error(f"加载NAAB到REG映射失败: {e}")
    
    def _is_naab_format(self, bull_id: str) -> bool:
        """
        检查是否为NAAB格式的公牛号
        
        Args:
            bull_id: 公牛ID
            
        Returns:
            bool: 如果是NAAB格式，返回True；否则返回False
        """
        if not bull_id or pd.isna(bull_id) or not isinstance(bull_id, str):
            return False
        
        # 正则表达式匹配NAAB格式: 3个数字 + 2个字母 + 5个数字
        return bool(re.match(r'^\d{3}[A-Z]{2}\d{5}$', bull_id))
    
    def convert_naab_to_reg(self, bull_id: str) -> str:
        """
        将NAAB号转换为REG号
        
        Args:
            bull_id: 公牛ID，可能是NAAB号或其他格式
            
        Returns:
            str: 对应的REG号，如果无法转换则返回原ID
        """
        if not bull_id or pd.isna(bull_id) or not isinstance(bull_id, str):
            return ""
            
        bull_id = bull_id.strip()
        
        # 如果不是NAAB格式，直接返回原ID
        if not self._is_naab_format(bull_id):
            return bull_id
            
        # 查找映射
        return self.naab_to_reg_map.get(bull_id, bull_id)
    
    def _build_bull_pedigree(self, progress_callback=None):
        """
        构建公牛系谱
        
        Args:
            progress_callback: 进度回调函数
        """
        try:
            start_time = time.time()
            
            # 清空现有系谱
            self.pedigree = {}
            self.virtual_nodes = set()
            
            # 查询所有公牛记录，增加GIB字段
            query = """
            SELECT `BULL REG`, `SIRE REG`, `MGS REG`, `MMGS REG`, `GIB` 
            FROM bull_library 
            WHERE `BULL REG` IS NOT NULL
            """
            
            df = pd.read_sql(query, self.engine)
            
            total_bulls = len(df)
            logging.info(f"从数据库加载了{total_bulls}头公牛记录")
            
            if progress_callback:
                progress_callback(40, f"处理{total_bulls}头公牛...")
            
            # 处理每个公牛记录
            for idx, row in df.iterrows():
                bull_reg = str(row['BULL REG']).strip() if pd.notna(row['BULL REG']) else None
                sire_reg = str(row['SIRE REG']).strip() if pd.notna(row['SIRE REG']) else None
                mgs_reg = str(row['MGS REG']).strip() if pd.notna(row['MGS REG']) else None
                mmgs_reg = str(row['MMGS REG']).strip() if pd.notna(row['MMGS REG']) else None
                
                # 处理GIB值（百分比格式）
                gib_value = None
                if pd.notna(row['GIB']):
                    try:
                        gib_percentage = float(row['GIB'])
                        # 将百分比转换为小数形式 (70 -> 0.7)
                        gib_value = gib_percentage / 100.0
                        # 验证值是否在合理范围内
                        if gib_value < 0 or gib_value > 1:
                            logging.warning(f"公牛 {bull_reg} 的GIB值 {gib_percentage}% 超出正常范围(0-100)，将不使用此值")
                            gib_value = None
                    except (ValueError, TypeError):
                        logging.warning(f"公牛 {bull_reg} 的GIB值 '{row['GIB']}' 无法转换为数值，将不使用此值")
                        gib_value = None
                
                if not bull_reg:
                    continue
                
                # 创建虚拟母亲和外祖母ID
                virtual_dam_id = f"{bull_reg}_dam"
                virtual_mgd_id = f"{bull_reg}_mgd"
                
                # 添加公牛本身，增加gib字段
                self.pedigree[bull_reg] = {
                    'sire': sire_reg if sire_reg else "",
                    'dam': virtual_dam_id,
                    'type': 'bull',
                    'gib': gib_value  # 添加GIB值
                }
                
                # 添加虚拟母亲
                self.pedigree[virtual_dam_id] = {
                    'sire': mgs_reg if mgs_reg else "",
                    'dam': virtual_mgd_id,
                    'type': 'virtual_cow',
                    'gib': None  # 虚拟节点没有GIB值
                }
                self.virtual_nodes.add(virtual_dam_id)
                
                # 添加虚拟外祖母
                self.pedigree[virtual_mgd_id] = {
                    'sire': mmgs_reg if mmgs_reg else "",
                    'dam': "",
                    'type': 'virtual_cow',
                    'gib': None  # 虚拟节点没有GIB值
                }
                self.virtual_nodes.add(virtual_mgd_id)
                
                # 更新进度
                if progress_callback and idx % 1000 == 0:
                    progress = 40 + int((idx / total_bulls) * 40)
                    progress_callback(progress, f"已处理 {idx}/{total_bulls} 头公牛...")
            
            logging.info(f"系谱库构建完成，包含{len(self.pedigree)}个动物，其中{len(self.virtual_nodes)}个虚拟节点，耗时{time.time()-start_time:.2f}秒")
            
            if progress_callback:
                progress_callback(80, "系谱构建完成，准备保存...")
                
        except Exception as e:
            logging.error(f"构建公牛系谱失败: {e}")
            raise
    
    def export_pedigree_file(self, output_path: Path):
        """
        导出系谱文件，格式为: animal_id sire_id dam_id [gib]
        
        Args:
            output_path: 输出文件路径
        """
        try:
            with open(output_path, 'w') as f:
                # 添加表头
                f.write("animal_id sire_id dam_id gib type\n")
                
                for animal_id, info in self.pedigree.items():
                    sire = info['sire'] if info['sire'] else "0"
                    dam = info['dam'] if info['dam'] else "0"
                    gib = f"{info.get('gib', 'NA')}" if info.get('gib') is not None else "NA"
                    animal_type = info.get('type', 'unknown')
                    
                    f.write(f"{animal_id} {sire} {dam} {gib} {animal_type}\n")
            
            logging.info(f"系谱文件已导出到: {output_path}")
        except Exception as e:
            logging.error(f"导出系谱文件失败: {e}")
    
    def renumber_pedigree(self) -> Tuple[Dict, Dict, Dict]:
        """
        重新编号系谱，确保父母在子代之前
        
        Returns:
            Tuple[Dict, Dict, Dict]: 
                - 重编号后的系谱
                - 原始ID到新ID的映射
                - 新ID到原始ID的映射
        """
        try:
            # 创建ID映射
            old_to_new = {}
            new_to_old = {}
            
            # 拓扑排序
            visited = set()
            temp_mark = set()
            ordered_ids = []
            
            def visit(node_id):
                if node_id in visited:
                    return
                if node_id in temp_mark:
                    # 检测到循环，跳过
                    logging.warning(f"系谱中检测到循环: {node_id}")
                    return
                
                temp_mark.add(node_id)
                
                # 访问父母节点
                if node_id in self.pedigree:
                    sire_id = self.pedigree[node_id]['sire']
                    dam_id = self.pedigree[node_id]['dam']
                    
                    if sire_id and sire_id in self.pedigree:
                        visit(sire_id)
                    if dam_id and dam_id in self.pedigree:
                        visit(dam_id)
                
                temp_mark.remove(node_id)
                visited.add(node_id)
                ordered_ids.append(node_id)
            
            # 对所有节点进行拓扑排序
            for animal_id in self.pedigree:
                if animal_id not in visited:
                    visit(animal_id)
            
            # 创建新的编号
            for i, old_id in enumerate(ordered_ids):
                new_id = str(i + 1)  # 从1开始编号
                old_to_new[old_id] = new_id
                new_to_old[new_id] = old_id
            
            # 创建重新编号后的系谱
            renumbered_pedigree = {}
            for new_id, old_id in new_to_old.items():
                old_info = self.pedigree[old_id]
                
                # 获取父母的新ID
                new_sire = old_to_new.get(old_info['sire'], '0')  # 未知父亲设为0
                new_dam = old_to_new.get(old_info['dam'], '0')    # 未知母亲设为0
                
                renumbered_pedigree[new_id] = {
                    'old_id': old_id,
                    'sire': new_sire,
                    'dam': new_dam,
                    'type': old_info['type']
                }
            
            logging.info(f"系谱重新编号完成，共{len(renumbered_pedigree)}个节点")
            return renumbered_pedigree, old_to_new, new_to_old
            
        except Exception as e:
            logging.error(f"重新编号系谱失败: {e}")
            return {}, {}, {}

    def build_cow_pedigree(self, cow_data_path: Path, progress_callback=None, 
                        export_temp_file: bool = True, export_merged_file: bool = True) -> Dict:
        """
        从母牛数据构建母牛系谱库，并与现有公牛系谱库合并
        
        Args:
            cow_data_path: 母牛数据文件路径（Excel文件）
            progress_callback: 进度回调函数
            export_temp_file: 是否导出临时母牛系谱文件
            export_merged_file: 是否导出合并后的系谱文件
            
        Returns:
            Dict: 构建好的合并系谱库
        """
        try:
            if progress_callback:
                progress_callback(0, "开始构建母牛系谱库...")
                
            # 确保NAAB到REG映射已加载
            if not self.naab_to_reg_map:
                if progress_callback:
                    progress_callback(10, "加载NAAB到REG映射...")
                self._load_naab_reg_mapping()
                
            # 读取母牛数据
            if progress_callback:
                progress_callback(20, "读取母牛数据...")
                
            try:
                cow_df = pd.read_excel(cow_data_path, dtype=str)
                logging.info(f"从{cow_data_path}读取了{len(cow_df)}条母牛数据")
            except Exception as e:
                logging.error(f"读取母牛数据失败: {e}")
                if progress_callback:
                    progress_callback(-1, f"读取母牛数据失败: {e}")
                return self.pedigree
                
            # 处理母牛数据，构建临时系谱
            if progress_callback:
                progress_callback(30, "处理母牛数据，构建临时系谱...")
                
            cow_pedigree = self.process_cow_data(cow_df, progress_callback)
            
            # 导出临时母牛系谱文件（用于检查）
            if export_temp_file:
                if progress_callback:
                    progress_callback(70, "导出临时母牛系谱文件...")
                    
                temp_file_path = cow_data_path.parent / "temp_cow_pedigree.txt"
                self.export_cow_pedigree(cow_pedigree, temp_file_path)
                
            # 合并系谱
            if progress_callback:
                progress_callback(80, "合并母牛系谱和公牛系谱...")
                
            self.merge_pedigrees(cow_pedigree)
            
            # 导出合并后的系谱文件（用于检查）
            if export_merged_file:
                if progress_callback:
                    progress_callback(90, "导出合并后的系谱文件...")
                    
                merged_file_path = cow_data_path.parent / "merged_pedigree.txt"
                self.export_pedigree_file(merged_file_path)
                
            if progress_callback:
                progress_callback(100, "母牛系谱库构建和合并完成")
                
            return self.pedigree
                
        except Exception as e:
            logging.error(f"构建母牛系谱库失败: {e}")
            if progress_callback:
                progress_callback(-1, f"构建母牛系谱库失败: {e}")
            return self.pedigree
            
    def process_cow_data(self, cow_df: pd.DataFrame, progress_callback=None) -> Dict:
        """
        处理母牛数据，标准化ID并构建系谱关系
        
        Args:
            cow_df: 母牛数据DataFrame
            progress_callback: 进度回调函数
            
        Returns:
            Dict: 构建好的母牛系谱（临时）
        """
        cow_pedigree = {}  # 临时母牛系谱
        total_cows = len(cow_df)
        
        try:
            # 检查必要的列是否存在
            required_columns = ['cow_id', 'sire']
            for col in required_columns:
                if col not in cow_df.columns:
                    logging.error(f"母牛数据缺少必要的列: {col}")
                    return {}
                    
            # 清理数据，移除无效行
            cow_df = cow_df.fillna("")
            
            # 处理每行母牛数据
            for idx, row in cow_df.iterrows():
                # 更新进度
                if progress_callback and idx % 100 == 0:
                    progress = 30 + int((idx / total_cows) * 30)
                    progress_callback(progress, f"已处理 {idx}/{total_cows} 头母牛...")
                
                # 提取并标准化ID
                cow_id = self.standardize_animal_id(row['cow_id'], 'cow')
                if not cow_id:  # 跳过无效ID
                    continue
                    
                sire_id = self.standardize_animal_id(row['sire'], 'bull')
                dam_id = self.standardize_animal_id(row.get('dam', ""), 'cow')
                
                # 添加母牛本身到系谱
                cow_pedigree[cow_id] = {
                    'sire': sire_id,
                    'dam': dam_id,
                    'type': 'cow',
                    'gib': None  # 母牛通常没有GIB值
                }
                
                # 处理母牛的母亲（如果母亲不在现有数据中）
                if dam_id and dam_id not in cow_pedigree:
                    mgs_id = self.standardize_animal_id(row.get('mgs', ""), 'bull')
                    mgd_id = self.standardize_animal_id(row.get('mgd', ""), 'cow')
                    
                    cow_pedigree[dam_id] = {
                        'sire': mgs_id,
                        'dam': mgd_id,
                        'type': 'cow',
                        'gib': None  # 母牛通常没有GIB值
                    }
                    
                    # 处理外祖母（如果外祖母不在现有数据中）
                    if mgd_id and mgd_id not in cow_pedigree:
                        mmgs_id = self.standardize_animal_id(row.get('mmgs', ""), 'bull')
                        
                        cow_pedigree[mgd_id] = {
                            'sire': mmgs_id,
                            'dam': "",
                            'type': 'cow',
                            'gib': None  # 母牛通常没有GIB值
                        }
            
            logging.info(f"母牛系谱处理完成，共构建了{len(cow_pedigree)}个节点")
            return cow_pedigree
            
        except Exception as e:
            logging.error(f"处理母牛数据时出错: {e}")
            return {}
    
    def standardize_animal_id(self, animal_id: str, id_type: str = 'unknown') -> str:
        """
        标准化动物ID，处理NAAB和非NAAB格式
        
        Args:
            animal_id: 动物ID
            id_type: ID类型，可以是'cow'、'bull'或'unknown'
            
        Returns:
            str: 标准化后的ID
        """
        if not animal_id or pd.isna(animal_id):
            return ""
            
        animal_id = str(animal_id).strip()
        if not animal_id:
            return ""
            
        # 对于公牛类型的ID，尝试转换NAAB格式
        if id_type == 'bull' and self._is_naab_format(animal_id):
            reg_id = self.convert_naab_to_reg(animal_id)
            if reg_id:
                return reg_id
                
        return animal_id
    
    def merge_pedigrees(self, cow_pedigree: Dict):
        """
        合并母牛系谱和公牛系谱，解决冲突问题
        
        Args:
            cow_pedigree: 母牛系谱
        """
        try:
            # 记录操作统计
            stats = {
                'added': 0,        # 新增的节点
                'replaced_virtual': 0,  # 替换的虚拟节点
                'preserved': 0     # 保留的现有节点
            }
            
            # 遍历母牛系谱的每个动物
            for animal_id, info in cow_pedigree.items():
                # 情况1：ID已存在于公牛系谱且不是虚拟节点
                if animal_id in self.pedigree and animal_id not in self.virtual_nodes:
                    # 公牛数据优先，不修改
                    # 但如果原来没有GIB值而新数据有，则更新GIB
                    if self.pedigree[animal_id].get('gib') is None and info.get('gib') is not None:
                        self.pedigree[animal_id]['gib'] = info['gib']
                    stats['preserved'] += 1
                    continue
                    
                # 情况2：ID是虚拟节点，用实际信息替换
                elif animal_id in self.virtual_nodes:
                    # 更新父母信息和GIB值，但保留虚拟节点标记
                    self.pedigree[animal_id]['sire'] = info['sire']
                    self.pedigree[animal_id]['dam'] = info['dam']
                    if info.get('gib') is not None:
                        self.pedigree[animal_id]['gib'] = info['gib']
                    stats['replaced_virtual'] += 1
                    
                # 情况3：全新的ID，直接添加
                else:
                    self.pedigree[animal_id] = info
                    stats['added'] += 1
            
            logging.info(f"系谱合并完成，新增节点: {stats['added']}，替换虚拟节点: {stats['replaced_virtual']}，"
                        f"保留现有节点: {stats['preserved']}")
                        
        except Exception as e:
            logging.error(f"合并系谱时出错: {e}")
    
    def export_cow_pedigree(self, cow_pedigree: Dict, output_path: Path):
        """
        导出母牛系谱到文件，用于检查
        
        Args:
            cow_pedigree: 母牛系谱
            output_path: 输出文件路径
        """
        try:
            with open(output_path, 'w') as f:
                f.write("animal_id,sire_id,dam_id,type,gib\n")  # 添加表头
                for animal_id, info in cow_pedigree.items():
                    sire = info['sire'] if info['sire'] else "0"
                    dam = info['dam'] if info['dam'] else "0"
                    animal_type = info['type']
                    gib = f"{info.get('gib', 'NA')}" if info.get('gib') is not None else "NA"
                    f.write(f"{animal_id},{sire},{dam},{animal_type},{gib}\n")
            
            logging.info(f"母牛系谱文件已导出到: {output_path}")
        except Exception as e:
            logging.error(f"导出母牛系谱文件失败: {e}")


# 集成到update_manager.py的函数
def load_or_build_pedigree(db_path: Path, pedigree_cache_path: Optional[Path] = None, progress_callback=None):
    """
    加载或构建系谱库，加载失败时自动构建
    
    Args:
        db_path: 本地bull_library.db的路径
        pedigree_cache_path: 系谱库缓存文件路径
        progress_callback: 进度回调函数
    
    Returns:
        PedigreeDatabase: 系谱库管理器实例
    """
    try:
        if progress_callback:
            progress_callback(0, "初始化系谱库管理器...")
            
        # 创建系谱库管理器
        pedigree_db = PedigreeDatabase(db_path, pedigree_cache_path)
        
        # 尝试加载系谱库
        if progress_callback:
            progress_callback(10, "尝试从缓存加载系谱库...")
            
        pedigree = pedigree_db.load_pedigree()
        
        # 如果加载失败（返回空字典），则构建系谱库
        if not pedigree:
            if progress_callback:
                progress_callback(20, "缓存不存在或加载失败，开始构建系谱库...")
            pedigree_db.build_pedigree(progress_callback)
        else:
            if progress_callback:
                progress_callback(100, "系谱库加载完成")
                
        return pedigree_db
    
    except Exception as e:
        logging.error(f"加载或构建系谱库失败: {e}")
        if progress_callback:
            progress_callback(-1, f"加载或构建系谱库失败: {e}")
        raise
        
def update_pedigree(db_path: Path, pedigree_cache_path: Optional[Path] = None, progress_callback=None):
    """
    强制更新系谱库
    
    Args:
        db_path: 本地bull_library.db的路径
        pedigree_cache_path: 系谱库缓存文件路径
        progress_callback: 进度回调函数
    
    Returns:
        PedigreeDatabase: 系谱库管理器实例
    """
    try:
        if progress_callback:
            progress_callback(0, "初始化系谱库管理器...")
            
        # 创建系谱库管理器
        pedigree_db = PedigreeDatabase(db_path, pedigree_cache_path)
        
        # 构建系谱库
        if progress_callback:
            progress_callback(10, "开始更新系谱库...")
            
        pedigree_db.build_pedigree(progress_callback)
        
        return pedigree_db
    
    except Exception as e:
        logging.error(f"更新系谱库失败: {e}")
        if progress_callback:
            progress_callback(-1, f"更新系谱库失败: {e}")
        raise 