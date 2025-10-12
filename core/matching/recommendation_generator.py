"""
选配推荐生成器
用于为每头母牛生成推荐公牛列表并计算约束条件
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from sqlalchemy import create_engine, text
from core.data.update_manager import LOCAL_DB_PATH
from core.inbreeding.inbreeding_calculator import InbreedingCalculator

logger = logging.getLogger(__name__)

class RecommendationGenerator:
    """选配推荐生成器"""
    
    def __init__(self):
        self.cow_data = None
        self.bull_data = None
        self.inbreeding_calculator = None  # Will be initialized when data is loaded
        
    def load_data(self, project_path: Path):
        """加载必要的数据文件"""
        try:
            # 加载母牛指数数据
            index_file = project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
            if not index_file.exists():
                raise FileNotFoundError(f"未找到母牛指数文件: {index_file}")
            
            self.cow_data = pd.read_excel(index_file)
            # 只处理在场的母牛
            self.cow_data = self.cow_data[
                (self.cow_data['sex'] == '母') & 
                (self.cow_data['是否在场'] == '是')
            ].copy()
            
            # 加载备选公牛数据
            bull_file = project_path / "standardized_data" / "processed_bull_data.xlsx"
            if not bull_file.exists():
                raise FileNotFoundError(f"未找到备选公牛文件: {bull_file}")
            
            self.bull_data = pd.read_excel(bull_file)
            
            # 尝试加载公牛指数得分
            bull_index_file = project_path / "analysis_results" / "processed_index_bull_scores.xlsx"
            if bull_index_file.exists():
                try:
                    bull_index_data = pd.read_excel(bull_index_file)
                    # 查找指数列（可能是 xxx_index 格式）
                    index_columns = [col for col in bull_index_data.columns if col.endswith('_index')]
                    
                    if 'bull_id' in bull_index_data.columns and index_columns:
                        # 使用第一个找到的指数列
                        index_col = index_columns[0]
                        # 将指数列重命名为 Index Score
                        bull_index_data['Index Score'] = bull_index_data[index_col]
                        
                        self.bull_data = pd.merge(
                            self.bull_data,
                            bull_index_data[['bull_id', 'Index Score']],
                            on='bull_id',
                            how='left'
                        )
                        logger.info(f"成功加载公牛指数得分（使用列: {index_col}）")
                    else:
                        logger.warning("公牛指数文件格式不正确，未找到指数列")
                except Exception as e:
                    logger.warning(f"加载公牛指数得分失败: {e}")
            else:
                logger.warning("未找到公牛指数得分文件，将使用默认值0")
            
            # 初始化近交系数计算器
            cow_data_file = project_path / "standardized_data" / "processed_cow_data.xlsx"
            if cow_data_file.exists():
                self.inbreeding_calculator = InbreedingCalculator(
                    db_path=LOCAL_DB_PATH,
                    cow_data_path=cow_data_file
                )
            else:
                logger.warning("未找到母牛数据文件，近交系数计算将不可用")
                self.inbreeding_calculator = None
            
            logger.info(f"数据加载完成: {len(self.cow_data)}头母牛, {len(self.bull_data)}头公牛")
            return True
            
        except Exception as e:
            logger.error(f"数据加载失败: {e}")
            return False
    
    def _get_bulls_by_type(self, semen_type: str) -> List[str]:
        """获取指定类型的公牛列表"""
        if 'semen_type' not in self.bull_data.columns:
            return []

        bulls = self.bull_data[self.bull_data['semen_type'] == semen_type]['bull_id'].tolist()
        return [str(bull_id) for bull_id in bulls if pd.notna(bull_id)]
    
    def _rank_bulls_for_cow(self, cow_row: pd.Series, bull_ids: List[str]) -> List[Tuple[str, float, float]]:
        """为母牛排序公牛推荐优先级，返回(bull_id, bull_score, offspring_score)列表"""
        try:
            # 获取母牛的综合指数得分
            cow_score = cow_row.get('Combine Index Score', 0)
            
            bull_info_list = []
            
            for bull_id in bull_ids:
                bull_row = self.bull_data[self.bull_data['bull_id'] == bull_id]
                if not bull_row.empty:
                    # 获取公牛的指数得分
                    bull_score = bull_row['Index Score'].iloc[0] if 'Index Score' in bull_row.columns else 0
                    
                    # 计算预期后代得分：母牛得分和公牛得分的平均值
                    offspring_score = 0.5 * (cow_score + bull_score)
                    
                    bull_info_list.append((bull_id, bull_score, offspring_score))
                else:
                    # 如果找不到公牛信息，使用默认值
                    bull_info_list.append((bull_id, 0, cow_score * 0.5))
            
            # 按预期后代得分降序排序
            bull_info_list.sort(key=lambda x: x[2], reverse=True)
            return bull_info_list
            
        except Exception as e:
            logger.warning(f"排序公牛失败: {e}, 使用默认排序")
            # 返回默认排序，包含默认分数
            return [(bull_id, 0, 0) for bull_id in bull_ids]
    
    def _calculate_inbreeding_coefficient(self, cow_id: str, bull_id: str) -> float:
        """计算近交系数
        
        注意：当前实现暂时返回0，因为calculate_inbreeding_coefficient方法
        只能计算单个动物的近交系数，而不是配对的预期近交系数
        """
        try:
            if self.inbreeding_calculator is None:
                return 0.0
            
            # TODO: 实现计算配对后代预期近交系数的逻辑
            # 目前暂时返回0
            return 0.0
            
        except Exception as e:
            logger.warning(f"计算近交系数失败 (母牛{cow_id}, 公牛{bull_id}): {e}")
            return 0.0
    
    def _check_defect_genes(self, cow_id: str, bull_id: str) -> str:
        """检查隐性基因情况"""
        try:
            # 这里应该实现实际的隐性基因检查逻辑
            # 目前返回默认的无风险状态
            return "-"
        except Exception as e:
            logger.warning(f"检查隐性基因失败 (母牛{cow_id}, 公牛{bull_id}): {e}")
            return "-"
    
    def generate_recommendations(self, progress_callback=None) -> pd.DataFrame:
        """生成选配推荐报告"""
        if self.cow_data is None or self.bull_data is None:
            raise ValueError("请先加载数据")
        
        # 获取各类型公牛
        regular_bulls = self._get_bulls_by_type('常规')
        sexed_bulls = self._get_bulls_by_type('性控')
        
        if not regular_bulls and not sexed_bulls:
            raise ValueError("未找到已分类的公牛数据")
        
        logger.info(f"常规公牛: {len(regular_bulls)}头, 性控公牛: {len(sexed_bulls)}头")
        
        results = []
        total_cows = len(self.cow_data)
        
        for idx, (_, cow_row) in enumerate(self.cow_data.iterrows()):
            cow_id = str(cow_row['cow_id'])
            
            if progress_callback:
                progress = int((idx / total_cows) * 100)
                progress_callback(f"正在分析母牛 {cow_id} ({idx+1}/{total_cows})", progress)
            
            result_row = {
                'cow_id': cow_id,
                'breed': cow_row.get('breed', ''),
                'sire': cow_row.get('sire', ''),
                'mgs': cow_row.get('mgs', ''),
                'dam': cow_row.get('dam', ''),
                'mmgs': cow_row.get('mmgs', ''),
                'lac': cow_row.get('lac', ''),
                'calving_date': cow_row.get('calving_date', ''),
                'birth_date': cow_row.get('birth_date', ''),
                'services_time': cow_row.get('services_time', ''),
                'group': cow_row.get('group', ''),
                'Combine Index Score': cow_row.get('Combine Index Score', 0)
            }
            
            # 处理常规冻精推荐
            if regular_bulls:
                ranked_regular_bulls = self._rank_bulls_for_cow(cow_row, regular_bulls)
                for i in range(1, 4):  # 1-3选
                    if i <= len(ranked_regular_bulls):
                        bull_id, bull_score, offspring_score = ranked_regular_bulls[i-1]
                        result_row[f'推荐常规冻精{i}选'] = bull_id
                        
                        # 计算近交系数
                        inbreeding_coeff = self._calculate_inbreeding_coefficient(cow_id, bull_id)
                        result_row[f'常规冻精{i}近交系数'] = f"{inbreeding_coeff:.2%}"
                        
                        # 检查隐性基因
                        gene_status = self._check_defect_genes(cow_id, bull_id)
                        result_row[f'常规冻精{i}隐性基因情况'] = gene_status
                        
                        # 添加得分信息
                        result_row[f'常规冻精{i}得分'] = round(offspring_score, 2)
                    else:
                        result_row[f'推荐常规冻精{i}选'] = ""
                        result_row[f'常规冻精{i}近交系数'] = ""
                        result_row[f'常规冻精{i}隐性基因情况'] = ""
                        result_row[f'常规冻精{i}得分'] = ""
            
            # 处理性控冻精推荐
            if sexed_bulls:
                ranked_sexed_bulls = self._rank_bulls_for_cow(cow_row, sexed_bulls)
                for i in range(1, 4):  # 1-3选
                    if i <= len(ranked_sexed_bulls):
                        bull_id, bull_score, offspring_score = ranked_sexed_bulls[i-1]
                        result_row[f'推荐性控冻精{i}选'] = bull_id
                        
                        # 计算近交系数
                        inbreeding_coeff = self._calculate_inbreeding_coefficient(cow_id, bull_id)
                        result_row[f'性控冻精{i}近交系数'] = f"{inbreeding_coeff:.2%}"
                        
                        # 检查隐性基因
                        gene_status = self._check_defect_genes(cow_id, bull_id)
                        result_row[f'性控冻精{i}隐性基因情况'] = gene_status
                        
                        # 添加得分信息
                        result_row[f'性控冻精{i}得分'] = round(offspring_score, 2)
                    else:
                        result_row[f'推荐性控冻精{i}选'] = ""
                        result_row[f'性控冻精{i}近交系数'] = ""
                        result_row[f'性控冻精{i}隐性基因情况'] = ""
                        result_row[f'性控冻精{i}得分'] = ""
            
            results.append(result_row)
        
        return pd.DataFrame(results)
    
    def save_recommendations(self, recommendations_df: pd.DataFrame, output_path: Path):
        """保存推荐报告"""
        try:
            # 重新排列列的顺序
            ordered_columns = ['cow_id']
            
            # 添加常规冻精相关列
            for i in range(1, 4):
                ordered_columns.extend([
                    f'推荐常规冻精{i}选',
                    f'常规冻精{i}隐性基因情况',
                    f'常规冻精{i}近交系数',
                    f'常规冻精{i}得分'
                ])
            
            # 添加性控冻精相关列
            for i in range(1, 4):
                ordered_columns.extend([
                    f'推荐性控冻精{i}选',
                    f'性控冻精{i}隐性基因情况',
                    f'性控冻精{i}近交系数',
                    f'性控冻精{i}得分'
                ])
            
            # 添加母牛信息列
            ordered_columns.extend([
                'breed', 'sire', 'mgs', 'dam', 'mmgs', 
                'lac', 'calving_date', 'birth_date', 
                'services_time', 'group', 'Combine Index Score'
            ])
            
            # 只保留存在的列
            ordered_columns = [col for col in ordered_columns if col in recommendations_df.columns]
            
            # 重新排列DataFrame
            recommendations_df = recommendations_df[ordered_columns]
            
            # 保存到Excel
            recommendations_df.to_excel(output_path, index=False)
            logger.info(f"选配推荐报告已保存至: {output_path}")
            return True
        except Exception as e:
            logger.error(f"保存推荐报告失败: {e}")
            return False 