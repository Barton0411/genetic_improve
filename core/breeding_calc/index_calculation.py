# core/breeding_calc/index_calculation.py

from pathlib import Path
import json
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from sqlalchemy import create_engine, text

from .base_calculation import BaseCowCalculation
from .cow_traits_calc import TRAITS_TRANSLATION
import os
from pathlib import Path

# 标准差数据
TRAIT_SD = {
    'MILK': 567, 'NM$': 100, 'FS': 56, 'FE': 50, 'RFI': 46.2,
    'FAT': 25, 'PROT': 15, 'MAST': 2.6, 'EFC': 2.05, 'PL': 1.7,
    'CCR': 1.6, 'LIV': 1.6, 'DPR': 1.4, 'MET': 1.4, 'HCR': 1.3,
    'TPI': 100, 'CM$': 100, 'FM$': 100, 'ST': 1, 'SG': 1,
    'BD': 1, 'DF': 1, 'RA': 1, 'RW': 1, 'LS': 1,
    'LR': 1, 'FA': 1, 'FLS': 1, 'FU': 1, 'UH': 1,
    'UW': 1, 'UC': 1, 'UD': 1, 'FT': 1, 'RT': 1,
    'TL': 1, 'GM$': 100, 'KET': 1, 'PTAT': 1, 'RP': 0.9,
    'BDC': 0.76, 'DA': 0.7, 'UDC': 0.65, 'FLC': 0.53,
    'HLiv': 0.4, 'MFV': 0.4, 'SCS': 0.14, 'FAT %': 0.1, 'PROT%': 0.04
}

# 系统预设权重
DEFAULT_WEIGHTS = {
    'NM$权重': {'NM$': 100},
    'TPI权重': {'TPI': 100}
}

class IndexCalculation(BaseCowCalculation):
    def __init__(self):
        super().__init__()
        self.output_prefix = "processed_index"
        self.required_columns = ['cow_id']  # 基本必需列


    @staticmethod
    def get_global_weights_path() -> Path:
        """获取全局权重配置文件路径"""
        # 找到genetic_projects目录
        current_dir = Path(__file__).resolve().parent  # core/breeding_calc
        while current_dir.name != 'genetic_improve':
            current_dir = current_dir.parent
        
        # genetic_projects是genetic_improve的同级目录
        weights_path = current_dir.parent / "genetic_projects" / "index_weights"
        weights_path.mkdir(parents=True, exist_ok=True)
        return weights_path
        
    def load_weights(self) -> Dict[str, Dict[str, float]]:
        """加载所有权重配置（包括系统预设和用户自定义）"""
        weights = DEFAULT_WEIGHTS.copy()
        
        try:
            # 使用全局路径
            weights_file = self.get_global_weights_path() / "custom_weights.json"
            if weights_file.exists():
                with open(weights_file, 'r', encoding='utf-8') as f:
                    custom_weights = json.load(f)
                weights.update(custom_weights)
        except Exception as e:
            print(f"加载用户自定义权重失败: {e}")
                
        return weights
        
    def save_custom_weight(self, weight_name: str, weight_values: Dict[str, float]) -> bool:
        """保存用户自定义权重"""
        try:
            # 使用全局路径
            weights_file = self.get_global_weights_path() / "custom_weights.json"
            
            # 读取现有权重
            existing_weights = {}
            if weights_file.exists():
                with open(weights_file, 'r', encoding='utf-8') as f:
                    existing_weights = json.load(f)
            
            # 更新权重
            existing_weights[weight_name] = weight_values
            
            # 保存
            with open(weights_file, 'w', encoding='utf-8') as f:
                json.dump(existing_weights, f, ensure_ascii=False, indent=4)
                
            return True
            
        except Exception as e:
            print(f"保存自定义权重失败: {e}")
            return False
            
    def delete_custom_weight(self, weight_name: str) -> bool:
        """删除用户自定义权重"""
        try:
            weights_file = self.get_global_weights_path() / "custom_weights.json"
            
            if not weights_file.exists():
                return False
                
            with open(weights_file, 'r', encoding='utf-8') as f:
                weights = json.load(f)
                
            if weight_name in weights:
                del weights[weight_name]
                
                with open(weights_file, 'w', encoding='utf-8') as f:
                    json.dump(weights, f, ensure_ascii=False, indent=4)
                    
                return True
            return False
            
        except Exception as e:
            print(f"删除自定义权重失败: {e}")
            return False
            
    def validate_weight_values(self, weight_values: Dict[str, float]) -> bool:
        """验证权重值是否有效"""
        total = sum(abs(v) for v in weight_values.values())
        return abs(total - 100) < 0.0001  # 允许一点点浮点数误差
        
    def calculate_index_score(self, trait_values: dict, weight_values: dict) -> float:
        """计算指数得分"""
        score = 0
        for trait, weight in weight_values.items():
            if trait in trait_values and trait in TRAIT_SD:
                # 每个性状的得分 = 性状值/性状标准差 × 权重值
                score += (trait_values[trait] / TRAIT_SD[trait]) * weight
        return score
        
    def process_cow_index(self, main_window, weight_name: str) -> Tuple[bool, str]:
        """处理母牛群指数计算"""
        try:
            project_path = main_window.selected_project_path
            
            # 1. 首先检查是否有processed_cow_data.xlsx
            cow_data_path = project_path / "standardized_data" / "processed_cow_data.xlsx"
            if not cow_data_path.exists():
                return False, "请先上传母牛数据"
                
            # 2. 加载权重配置并获取性状列表
            weights = self.load_weights() 
            if weight_name not in weights:
                return False, f"未找到权重配置：{weight_name}"
                
            weight_values = weights[weight_name]
            selected_traits = list(weight_values.keys())
            
            # 3. 计算关键性状
            success, cow_df = self.calculate_cow_traits(project_path, selected_traits)
            if not success:
                return False, "计算母牛关键性状失败"
            
            # 4. 检查基因组数据并更新
            genomic_path = project_path / "standardized_data" / "processed_genomic_data.xlsx"
            if genomic_path.exists():
                try:
                    genomic_df = pd.read_excel(genomic_path)
                    for trait in selected_traits:
                        # 为每个性状创建source列
                        cow_df[f'{trait}_source'] = 'P'  # 默认为系谱计算
                        
                        # 遍历每头母牛
                        for idx, row in cow_df.iterrows():
                            genomic_row = genomic_df[genomic_df['cow_id'] == row['cow_id']]
                            if not genomic_row.empty and trait in genomic_row.columns:
                                if pd.notna(genomic_row[trait].iloc[0]):
                                    cow_df.at[idx, trait] = genomic_row[trait].iloc[0]
                                    cow_df.at[idx, f'{trait}_source'] = 'G'
                except Exception as e:
                    print(f"处理基因组数据时发生错误: {e}")
            
            # 5. 计算指数得分
            trait_columns = [col for col in cow_df.columns if col in selected_traits]
            cow_df[f'{weight_name}_index'] = cow_df.apply(
                lambda row: self.calculate_index_score(
                    {trait: row[trait] for trait in trait_columns}, 
                    weight_values
                ),
                axis=1
            )
            
            # 6. 排序并添加排名
            cow_df = cow_df.sort_values(f'{weight_name}_index', ascending=False)
            cow_df['ranking'] = range(1, len(cow_df) + 1)
            
            # 7. 保存结果
            output_path = project_path / "analysis_results" / f"{self.output_prefix}_cow_scores.xlsx"
            return self.save_results_with_retry(cow_df, output_path), "计算完成"
            
        except Exception as e:
            return False, str(e)
            
    def process_bull_index(self, main_window, weight_name: str) -> Tuple[bool, str]:
        """处理公牛指数计算"""
        try:
            project_path = main_window.selected_project_path
            
            # 1. 首先检查是否有processed_bull_data.xlsx
            bull_data_path = project_path / "standardized_data" / "processed_bull_data.xlsx"
            if not bull_data_path.exists():
                return False, "请先上传备选公牛数据"
                
            # 2. 加载权重配置
            weights = self.load_weights()
            if weight_name not in weights:
                return False, f"未找到权重配置：{weight_name}"
                
            weight_values = weights[weight_name]
            selected_traits = list(weight_values.keys())
            
            # 3. 从数据库查询公牛性状数据
            bull_df = pd.read_excel(bull_data_path)
            if not self.init_db_connection():
                return False, "连接数据库失败"
                
            # 为每个公牛查询性状数据
            for idx, row in bull_df.iterrows():
                bull_id = str(row['bull_id'])
                trait_data, found = self.query_bull_traits(bull_id, selected_traits)
                if found:
                    for trait, value in trait_data.items():
                        bull_df.at[idx, trait] = value
                else:
                    # 如果找不到公牛数据，所有性状值设为None
                    for trait in selected_traits:
                        bull_df.at[idx, trait] = None
            
            # 4. 计算指数得分
            bull_df[f'{weight_name}_index'] = bull_df.apply(
                lambda row: self.calculate_index_score(
                    {trait: row[trait] for trait in selected_traits}, 
                    weight_values
                ),
                axis=1
            )
            
            # 5. 排序并添加排名
            bull_df = bull_df.sort_values(f'{weight_name}_index', ascending=False)
            bull_df['ranking'] = range(1, len(bull_df) + 1)
            
            # 6. 保存结果
            output_path = project_path / "analysis_results" / f"{self.output_prefix}_bull_scores.xlsx"
            return self.save_results_with_retry(bull_df, output_path), "计算完成"
            
        except Exception as e:
            return False, str(e)
            
    def calculate_cow_traits(self, project_path: Path, selected_traits: List[str]) -> Tuple[bool, Optional[pd.DataFrame]]:
        """计算母牛关键性状"""
        try:
            cow_data_path = project_path / "standardized_data" / "processed_cow_data.xlsx"
            if not self.init_db_connection():
                return False, None
                
            cow_df = pd.read_excel(cow_data_path)
            
            # 对每个母牛计算选中的性状
            for trait in selected_traits:
                trait_col = f'sire_{trait}'
                
                # 从数据库查询公牛数据
                bull_ids = cow_df['sire'].dropna().unique()
                bull_traits = {}
                
                for bull_id in bull_ids:
                    if pd.isna(bull_id):
                        continue
                    traits_data, found = self.query_bull_traits(str(bull_id), [trait])
                    if found:
                        bull_traits[str(bull_id)] = traits_data[trait]
                
                # 设置性状值
                cow_df[trait] = cow_df['sire'].apply(
                    lambda x: bull_traits.get(str(x)) if pd.notna(x) else None
                )
            
            return True, cow_df
            
        except Exception as e:
            print(f"计算母牛性状失败: {e}")
            return False, None