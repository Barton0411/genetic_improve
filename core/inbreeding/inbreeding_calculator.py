from unittest import result
import pandas as pd
import numpy as np
from pathlib import Path
from sqlalchemy import create_engine, text
import logging
from typing import Dict, List, Tuple, Set, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class Animal:
    """动物节点类"""
    def __init__(self, id: str, is_bull: bool = False):
        self.id = id
        self.is_bull = is_bull
        self.sire = None  # 父亲
        self.dam = None   # 母亲
        self.gib = None   # GIB值
        self.generation = 0  # 代数

class InbreedingCalculator:
    def __init__(self, db_path: Path, cow_data_path: Path):
        """初始化近交系数计算器"""
        self.db_path = db_path
        self.cow_data_path = cow_data_path
        self._bull_cache = {}  # 缓存公牛信息
        self._calculation_cache = {}  # 缓存计算结果
        self.engine = create_engine(f'sqlite:///{db_path}')
        self.cow_data = None  # 将在load_data中加载
        self.MAX_GENERATIONS = 6  # 最大追溯代数
        self.common_ancestors = set()  # 存储找到的共同祖先
        self.ancestor_paths = {}  # 存储到每个共同祖先的路径
        
        # 加载数据
        self.load_data()

    def load_data(self):
        """加载母牛数据"""
        try:
            logging.info(f"正在从{self.cow_data_path}加载母牛数据...")
            self.cow_data = pd.read_excel(
                self.cow_data_path,
                dtype={
                    'cow_id': str,
                    'sire': str,
                    'dam': str
                }
            )
            # 清理牛号中的空格
            for col in ['cow_id', 'sire', 'dam']:
                if col in self.cow_data.columns:
                    self.cow_data[col] = self.cow_data[col].str.strip()
            
            logging.info(f"成功加载{len(self.cow_data)}条母牛记录")
        except Exception as e:
            logging.error(f"加载母牛数据时出错: {str(e)}")
            raise

    def get_bull_info(self, bull_id: str) -> Optional[Dict]:
        """获取公牛信息，使用缓存"""
        if not bull_id or pd.isna(bull_id):
            return None
            
        bull_id = str(bull_id).strip()
        if bull_id in self._bull_cache:
            return self._bull_cache[bull_id]
            
        try:
            with self.engine.connect() as conn:
                # 先通过 prepare_bull_id 获取 REG 号
                bull_info = self.prepare_bull_id(bull_id)
                if not bull_info or not bull_info.get('reg'):
                    return None
                
                # 使用 REG 号查询完整系谱信息
                result = conn.execute(
                    text("SELECT * FROM bull_library WHERE `BULL REG`=:reg_no"),
                    {"reg_no": bull_info['reg']}
                ).fetchone()
                
                if result:
                    info = dict(result._mapping)
                    # 存储更完整的系谱信息，使用 REG 号作为键
                    bull_data = {
                        'bull_id': bull_info['reg'],  # 使用 REG 号作为 ID
                        'bull_reg': info.get('BULL REG'),
                        'sire': info.get('SIRE REG'),     # 父亲的 REG 号
                        'mgs': info.get('MGS REG'),       # 母亲的父亲的 REG 号
                        'mmgs': info.get('MMGS REG'),     # 母亲的母亲的父亲的 REG 号
                        'GIB': info.get('GIB', 0)
                    }
                    self._bull_cache[bull_info['reg']] = bull_data
                    return bull_data
                    
                return None
                    
        except Exception as e:
            logging.error(f"查询公牛{bull_id}信息时出错: {str(e)}")
            return None

    def get_cow_info(self, cow_id: str) -> Optional[pd.Series]:
        """获取母牛信息"""
        if not cow_id or pd.isna(cow_id):
            return None
            
        cow_id = str(cow_id).strip()
        cow_info = self.cow_data[self.cow_data['cow_id'] == cow_id]
        if len(cow_info) > 0:
            return cow_info.iloc[0]
        return None

    def build_complete_pedigree(self, animal_id: str, generation: int = 0, max_gen: int = 6) -> Dict:
        """构建完整的系谱树，包含所有可用的祖先信息"""
        if generation >= max_gen or pd.isna(animal_id):
            return None

        animal_id = str(animal_id).strip()
        result = {
            'id': animal_id,
            'generation': generation,
            'gib': None,
            'sire': None,
            'dam': None,
            'type': None
        }
        
        # 1. 首先从牛群信息获取完整系谱
        cow_info = self.get_cow_info(animal_id)
        if cow_info is not None:  # 是母牛
            result['type'] = 'cow'
            
            # 1.1 添加父亲信息
            if not pd.isna(cow_info['sire']):
                # 使用父亲的 NAAB 号查找对应的 REG 号和系谱信息
                sire_info = self.prepare_bull_id(cow_info['sire'])
                if sire_info and sire_info.get('reg'):
                    # 使用 REG 号获取完整系谱
                    bull_info = self.get_bull_info(sire_info['reg'])
                    if bull_info:
                        result['sire'] = {
                            'id': sire_info['reg'],
                            'type': 'bull',
                            'generation': generation + 1,
                            'gib': bull_info.get('GIB')
                        }
                        # 递归构建父亲的系谱
                        if bull_info.get('sire'):
                            result['sire']['sire'] = self.build_complete_pedigree(
                                bull_info['sire'],
                                generation + 2,
                                max_gen
                            )
                        # 构建父亲的母系系谱
                        if bull_info.get('mgs'):
                            result['sire']['dam'] = {
                                'id': 'unknown_dam',
                                'type': 'cow',
                                'generation': generation + 2,
                                'sire': self.build_complete_pedigree(
                                    bull_info['mgs'],
                                    generation + 3,
                                    max_gen
                                )
                            }
                            # 添加母亲的母系信息
                            if bull_info.get('mmgs'):
                                result['sire']['dam']['dam'] = {
                                    'id': 'unknown_mgd',
                                    'type': 'cow',
                                    'generation': generation + 3,
                                    'sire': self.build_complete_pedigree(
                                        bull_info['mmgs'],
                                        generation + 4,
                                        max_gen
                                    )
                                }
            
            # 1.2 添加母亲信息
            if not pd.isna(cow_info['dam']):
                dam_info = self.get_cow_info(cow_info['dam'])
                if dam_info is not None:
                    result['dam'] = {
                        'id': cow_info['dam'],
                        'type': 'cow',
                        'generation': generation + 1
                    }
                    
                    # 1.2.1 添加外祖父(mgs)
                    if not pd.isna(dam_info['sire']):
                        mgs_info = self.prepare_bull_id(dam_info['sire'])
                        if mgs_info and mgs_info.get('reg'):
                            bull_info = self.get_bull_info(mgs_info['reg'])
                            if bull_info:
                                result['dam']['sire'] = {
                                    'id': mgs_info['reg'],
                                    'type': 'bull',
                                    'generation': generation + 2,
                                    'gib': bull_info.get('GIB')
                                }
                                # 递归构建外祖父的系谱
                                if bull_info.get('sire'):
                                    result['dam']['sire']['sire'] = self.build_complete_pedigree(
                                        bull_info['sire'],
                                        generation + 3,
                                        max_gen
                                    )
                                if bull_info.get('mgs'):
                                    result['dam']['sire']['dam'] = {
                                        'id': 'unknown_dam',
                                        'type': 'cow',
                                        'generation': generation + 3,
                                        'sire': self.build_complete_pedigree(
                                            bull_info['mgs'],
                                            generation + 4,
                                            max_gen
                                        )
                                    }
        
        # 2. 如果是公牛ID，直接从公牛数据库查询系谱
        else:
            bull_info = self.prepare_bull_id(animal_id)
            if bull_info and bull_info.get('reg'):
                complete_info = self.get_bull_info(bull_info['reg'])
                if complete_info:
                    result['type'] = 'bull'
                    result['id'] = bull_info['reg']
                    result['gib'] = complete_info.get('GIB')
                    
                    # 添加父亲系谱
                    if complete_info.get('sire'):
                        result['sire'] = self.build_complete_pedigree(
                            complete_info['sire'],
                            generation + 1,
                            max_gen
                        )
                    
                    # 添加母系系谱
                    if complete_info.get('mgs'):
                        result['dam'] = {
                            'id': 'unknown_dam',
                            'type': 'cow',
                            'generation': generation + 1,
                            'sire': self.build_complete_pedigree(
                                complete_info['mgs'],
                                generation + 2,
                                max_gen
                            )
                        }
                        # 添加母亲的母系信息
                        if complete_info.get('mmgs'):
                            result['dam']['dam'] = {
                                'id': 'unknown_mgd',
                                'type': 'cow',
                                'generation': generation + 2,
                                'sire': self.build_complete_pedigree(
                                    complete_info['mmgs'],
                                    generation + 3,
                                    max_gen
                                )
                            }
        
        return result

    def prepare_bull_id(self, bull_id: str) -> Dict:
        """准备公牛的 NAAB 和 REG 号"""
        if not bull_id or pd.isna(bull_id):
            return None
            
        bull_id = str(bull_id).strip()
        try:
            with self.engine.connect() as conn:
                # 1. 先尝试作为 NAAB 号查询
                if len(bull_id) < 11:
                    result = conn.execute(
                        text("SELECT * FROM bull_library WHERE `BULL NAAB`=:bull_id"),
                        {"bull_id": bull_id}
                    ).fetchone()
                    if result:
                        bull_info = dict(result._mapping)
                        return {
                            'naab': bull_id,
                            'reg': bull_info.get('BULL REG'),
                            'gib': bull_info.get('GIB', 0)
                        }
                
                # 2. 再尝试作为 REG 号查询
                result = conn.execute(
                    text("SELECT * FROM bull_library WHERE `BULL REG`=:bull_id"),
                    {"bull_id": bull_id}
                ).fetchone()
                if result:
                    bull_info = dict(result._mapping)
                    return {
                        'naab': bull_info.get('BULL NAAB'),
                        'reg': bull_id,
                        'gib': bull_info.get('GIB', 0)
                    }
                
                return None
                
        except Exception as e:
            logging.error(f"准备公牛ID时出错: {str(e)}")
            return None

    def find_common_ancestors_in_pedigrees(self, pedigree1: Dict, pedigree2: Dict) -> List[Dict]:
        """在两个系谱树中查找共同祖先及其路径"""
        def collect_ancestors(pedigree: Dict, current_path: List[str] = None) -> Dict[str, Dict]:
            if not pedigree:
                return {}
            
            if current_path is None:
                current_path = []
            
            ancestors = {}
            current_path = current_path + [pedigree['id']]
            
            # 记录当前节点（无论是公牛还是母牛，都直接添加到祖先集合中）
            # 使用ID作为键
            ancestors[pedigree['id']] = {
                'path': current_path,
                'gib': pedigree.get('gib', 0),
                'generation': pedigree['generation'],
                'naab': '',
                'reg': pedigree['id']  # 使用ID作为REG
            }
            
            # 如果是公牛，尝试查找REG号
            if pedigree.get('type') == 'bull':
                bull_info = self.prepare_bull_id(pedigree['id'])
                if bull_info and bull_info.get('reg'):
                    reg_no = bull_info['reg']
                    # 如果能找到REG号，使用REG号作为键
                    ancestors[reg_no] = {
                        'path': current_path,
                        'gib': bull_info.get('gib'),
                        'generation': pedigree['generation'],
                        'naab': bull_info.get('naab'),
                        'reg': reg_no
                    }
            
            # 递归查找父系和母系
            if pedigree.get('sire'):
                ancestors.update(collect_ancestors(pedigree['sire'], current_path))
            if pedigree.get('dam'):
                ancestors.update(collect_ancestors(pedigree['dam'], current_path))
            
            return ancestors
        
        # 收集两个系谱中的所有祖先
        ancestors1 = collect_ancestors(pedigree1)
        ancestors2 = collect_ancestors(pedigree2)
        
        # 调试信息
        print(f"系谱1祖先数量: {len(ancestors1)}")
        print(f"系谱2祖先数量: {len(ancestors2)}")
        
        # 计算并显示前几代祖先
        for i in range(1, 4):  # 显示前3代
            gen1_ancestors = [a['reg'] for a in ancestors1.values() if a['generation'] == i]
            gen2_ancestors = [a['reg'] for a in ancestors2.values() if a['generation'] == i]
            print(f"第{i}代: 系谱1有{len(gen1_ancestors)}个祖先, 系谱2有{len(gen2_ancestors)}个祖先")
            if i <= 2:  # 只显示前两代的祖先详情
                print(f"  系谱1第{i}代祖先: {', '.join(gen1_ancestors)}")
                print(f"  系谱2第{i}代祖先: {', '.join(gen2_ancestors)}")
        
        # 使用ID作为键查找共同祖先
        common_ids = set(ancestors1.keys()) & set(ancestors2.keys())
        print(f"找到{len(common_ids)}个共同祖先ID")
        if common_ids:
            # 显示前10个共同祖先
            print(f"共同祖先ID: {', '.join(list(common_ids)[:10])}{'...' if len(common_ids) > 10 else ''}")
        
        # 整理共同祖先信息
        common_ancestors = []
        for reg_no in common_ids:
            info1 = ancestors1[reg_no]
            info2 = ancestors2[reg_no]
            common_ancestors.append({
                'reg': reg_no,
                'naab': info1['naab'],
                'gib': info1['gib'],
                'path1': info1['path'],
                'path2': info2['path'],
                'total_generations': info1['generation'] + info2['generation']
            })
        
        # 按总代数排序（代数越小表示祖先越近）
        sorted_ancestors = sorted(common_ancestors, key=lambda x: x['total_generations'])
        
        # 显示排序后的共同祖先信息
        print(f"按总代数排序后的共同祖先:")
        for i, ancestor in enumerate(sorted_ancestors[:5]):  # 只显示前5个
            print(f"  {i+1}. {ancestor['reg']}, 总代数: {ancestor['total_generations']}")
        
        return sorted_ancestors

    def calculate_inbreeding_coefficient(self, animal_id: str) -> Tuple[float, str, str]:
        """计算近交系数
        
        使用Wright方法计算近交系数：F = Σ(0.5)^(n+n'+1) * (1+F_A)
        其中n和n'是从父母到共同祖先的代数，F_A是共同祖先的近交系数
        
        Args:
            animal_id: 动物ID
            
        Returns:
            Tuple[float, str, str]: (近交系数, 状态信息, 计算方法)
        """
        # 检查缓存
        if animal_id in self._calculation_cache:
            return self._calculation_cache[animal_id]
            
        # 获取动物信息
        animal = self.get_cow_info(animal_id)
        if animal is None:
            return 0.0, "NOT_FOUND", "ERROR"
        
        try:
            # 构建父母双方的完整系谱
            if not pd.isna(animal['sire']) and not pd.isna(animal['dam']):
                sire_pedigree = self.build_complete_pedigree(animal['sire'])
                dam_pedigree = self.build_complete_pedigree(animal['dam'])
                
                # 查找共同祖先
                common_ancestors = self.find_common_ancestors_in_pedigrees(
                    sire_pedigree,
                    dam_pedigree
                )
                
                if common_ancestors:
                    # 使用共同祖先计算近交系数
                    F_total = 0.0
                    self.common_ancestors = {a['reg'] for a in common_ancestors}  # 使用 REG 号存储
                    self.ancestor_paths = {}
                    
                    # 按世代数排序，优先处理较近的共同祖先
                    for ancestor in common_ancestors:
                        # 记录路径
                        self.ancestor_paths[ancestor['reg']] = {
                            'path1': ancestor['path1'],
                            'path2': ancestor['path2'],
                            'naab': ancestor['naab'],
                            'gib': ancestor['gib']
                        }
                        
                        # 计算贡献 - 按照Wright公式
                        path1_len = len(ancestor['path1']) - 1  # 父系路径长度
                        path2_len = len(ancestor['path2']) - 1  # 母系路径长度
                        
                        # Wright公式: (0.5)^(n+n'+1)
                        base_contribution = (0.5) ** (path1_len + path2_len + 1)
                        
                        # 考虑共同祖先自身的近交系数
                        ancestor_f = 0.0
                        # 如果有GIB值，使用GIB估计
                        if ancestor['gib'] and ancestor['gib'] > 0:
                            # GIB值通常是百分比，需要转为小数
                            ancestor_f = ancestor['gib'] / 100
                        
                        # Wright公式包含祖先自身的近交系数：(0.5)^(n+n'+1) * (1+F_A)
                        final_contribution = base_contribution * (1 + ancestor_f)
                        F_total += final_contribution
                    
                    # 将结果存入缓存
                    result = (F_total, "COMPLETE", "PEDIGREE")
                    self._calculation_cache[animal_id] = result
                    return result
                    
                # 如果没有找到共同祖先，尝试使用父系GIB值估算
                sire_info = self.prepare_bull_id(animal['sire'])
                if sire_info and sire_info.get('gib') is not None:
                    # 父系GIB值的一半作为近交系数估计
                    F = sire_info['gib'] / 200  
                    result = (F, "Using GIB value", "GIB")
                    self._calculation_cache[animal_id] = result
                    return result
                
                # 无共同祖先且无父系GIB值
                result = (0.0, "NO_COMMON_ANCESTOR", "NONE")
                self._calculation_cache[animal_id] = result
                return result
            
            # 父母信息不完整
            result = (0.0, "INCOMPLETE_PEDIGREE", "ERROR")
            self._calculation_cache[animal_id] = result
            return result
            
        except Exception as e:
            logging.error(f"计算近交系数时出错: {str(e)}")
            return 0.0, "ERROR", "ERROR"
    
    def get_bull_by_naab(self, naab_no: str) -> Optional[Dict]:
        """通过 NAAB 号查找公牛信息"""
        if not naab_no or pd.isna(naab_no):
            return None
            
        naab_no = str(naab_no).strip()
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("SELECT * FROM bull_library WHERE `BULL NAAB`=:naab_no"),
                    {"naab_no": naab_no}
                ).fetchone()
                
                if result:
                    bull_info = dict(result._mapping)
                    return {
                        'bull_id': naab_no,
                        'REG': bull_info.get('BULL REG'),
                        'NAAB': bull_info.get('BULL NAAB'),
                        'GIB': bull_info.get('GIB', 0)
                    }
                return None
                
        except Exception as e:
            logging.error(f"查询公牛NAAB号{naab_no}时出错: {str(e)}")
            return None

    def get_bull_by_reg(self, reg_no: str) -> Optional[Dict]:
        """通过 REG 号查找公牛信息"""
        if not reg_no or pd.isna(reg_no):
            return None
            
        reg_no = str(reg_no).strip()
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("SELECT * FROM bull_library WHERE `BULL REG`=:reg_no"),
                    {"reg_no": reg_no}
                ).fetchone()
                
                if result:
                    bull_info = dict(result._mapping)
                    return {
                        'bull_id': reg_no,
                        'REG': bull_info.get('BULL REG'),
                        'NAAB': bull_info.get('BULL NAAB'),
                        'GIB': bull_info.get('GIB', 0)
                    }
                return None
                
        except Exception as e:
            logging.error(f"查询公牛REG号{reg_no}时出错: {str(e)}")
            return None