"""
简化版个体选配推荐生成器
重新设计，更加健壮和易于维护
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json

logger = logging.getLogger(__name__)

class SimpleRecommendationGenerator:
    """简化版推荐生成器"""
    
    def __init__(self):
        self.project_path = None
        self.cow_data = None
        self.bull_data = None
        self.inbreeding_data = None
        self.genetic_defect_data = None
        
    def generate_recommendations(self, project_path: Path) -> bool:
        """
        生成选配推荐的主函数
        
        Args:
            project_path: 项目路径
            
        Returns:
            是否成功生成
        """
        try:
            self.project_path = project_path
            
            # 1. 加载基础数据
            logger.info("开始生成个体选配推荐...")
            if not self._load_basic_data():
                return False
                
            # 2. 加载近交系数和隐性基因数据（如果有）
            self._load_genetic_analysis_data()
            
            # 3. 生成推荐
            recommendations = self._generate_all_recommendations()
            
            # 4. 保存结果
            output_file = self.project_path / "analysis_results" / "individual_mating_report.xlsx"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            self._save_recommendations(recommendations, output_file)
            logger.info(f"推荐报告已保存至: {output_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"生成推荐失败: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    def _load_basic_data(self) -> bool:
        """加载基础数据"""
        try:
            # 1. 加载母牛数据
            cow_file = self.project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
            if not cow_file.exists():
                logger.error(f"未找到母牛指数文件: {cow_file}")
                return False
                
            self.cow_data = pd.read_excel(cow_file)
            # 筛选在场母牛
            self.cow_data = self.cow_data[
                (self.cow_data['sex'] == '母') & 
                (self.cow_data['是否在场'] == '是')
            ].copy()
            
            logger.info(f"加载了 {len(self.cow_data)} 头在场母牛")
            
            # 2. 加载公牛数据
            bull_file = self.project_path / "standardized_data" / "processed_bull_data.xlsx"
            if not bull_file.exists():
                logger.error(f"未找到公牛数据文件: {bull_file}")
                return False
                
            self.bull_data = pd.read_excel(bull_file)
            
            # 确保有必要的列
            if 'bull_id' not in self.bull_data.columns:
                logger.error("公牛数据缺少 bull_id 列")
                return False
                
            # 确保有semen_type列（向后兼容）
            if 'semen_type' not in self.bull_data.columns:
                if 'classification' in self.bull_data.columns:
                    self.bull_data['semen_type'] = self.bull_data['classification']
                else:
                    # 默认都是常规
                    self.bull_data['semen_type'] = '常规'
                    
            # 添加支数列（如果没有）
            if 'semen_count' not in self.bull_data.columns:
                if '支数' in self.bull_data.columns:
                    self.bull_data['semen_count'] = self.bull_data['支数']
                else:
                    # 默认都有库存
                    self.bull_data['semen_count'] = 100
                    
            logger.info(f"加载了 {len(self.bull_data)} 头公牛")
            
            # 3. 加载公牛指数（如果有）
            bull_index_file = self.project_path / "analysis_results" / "processed_index_bull_scores.xlsx"
            if bull_index_file.exists():
                bull_index_data = pd.read_excel(bull_index_file)
                if 'bull_id' in bull_index_data.columns:
                    # 找到指数列
                    index_cols = [col for col in bull_index_data.columns if col.endswith('_index')]
                    if index_cols:
                        # 合并指数数据
                        self.bull_data = pd.merge(
                            self.bull_data,
                            bull_index_data[['bull_id'] + index_cols],
                            on='bull_id',
                            how='left'
                        )
                        # 使用第一个指数列作为Index Score
                        self.bull_data['Index Score'] = self.bull_data[index_cols[0]]
                        
            # 如果还没有Index Score，使用默认值
            if 'Index Score' not in self.bull_data.columns:
                self.bull_data['Index Score'] = 2500  # 默认值
                
            return True
            
        except Exception as e:
            logger.error(f"加载基础数据失败: {e}")
            return False
            
    def _load_genetic_analysis_data(self):
        """加载近交系数和隐性基因分析数据"""
        try:
            analysis_dir = self.project_path / "analysis_results"
            
            # 查找近交系数和隐性基因分析文件
            patterns = [
                "备选公牛_近交系数及隐性基因分析结果_*.xlsx",
                "*近交系数*隐性基因*.xlsx",
                "candidate_inbreeding_coefficients.xlsx"
            ]
            
            analysis_file = None
            for pattern in patterns:
                files = list(analysis_dir.glob(pattern))
                if files:
                    # 选择最新的文件
                    analysis_file = max(files, key=lambda x: x.stat().st_mtime)
                    break
                    
            if analysis_file:
                logger.info(f"找到分析文件: {analysis_file.name}")
                analysis_data = pd.read_excel(analysis_file)
                
                # 保存原始数据用于查找
                self.inbreeding_data = analysis_data
                self.genetic_defect_data = analysis_data
            else:
                logger.warning("未找到近交系数和隐性基因分析文件，将使用默认值")
                self.inbreeding_data = None
                self.genetic_defect_data = None
                
        except Exception as e:
            logger.warning(f"加载遗传分析数据失败: {e}")
            self.inbreeding_data = None
            self.genetic_defect_data = None
            
    def _get_inbreeding_coefficient(self, cow_id: str, bull_id: str) -> float:
        """获取近交系数"""
        if self.inbreeding_data is None:
            return 0.0
            
        try:
            # 尝试不同的列名组合
            cow_cols = ['母牛号', 'dam_id', 'cow_id']
            bull_cols = ['备选公牛号', '公牛号', 'sire_id', 'bull_id']
            coeff_cols = ['近交系数', '后代近交系数', 'inbreeding_coefficient']
            
            # 找到实际的列名
            cow_col = next((col for col in cow_cols if col in self.inbreeding_data.columns), None)
            bull_col = next((col for col in bull_cols if col in self.inbreeding_data.columns), None)
            coeff_col = next((col for col in coeff_cols if col in self.inbreeding_data.columns), None)
            
            if not all([cow_col, bull_col, coeff_col]):
                return 0.0
                
            # 查找数据
            mask = (self.inbreeding_data[cow_col].astype(str) == str(cow_id)) & \
                   (self.inbreeding_data[bull_col].astype(str) == str(bull_id))
                   
            if mask.any():
                coeff = self.inbreeding_data.loc[mask, coeff_col].iloc[0]
                # 处理百分比格式
                if isinstance(coeff, str) and '%' in coeff:
                    return float(coeff.strip('%')) / 100
                return float(coeff) if pd.notna(coeff) else 0.0
                
        except Exception as e:
            logger.debug(f"获取近交系数失败 ({cow_id}, {bull_id}): {e}")
            
        return 0.0
        
    def _check_genetic_defects(self, cow_id: str, bull_id: str) -> str:
        """检查隐性基因状态"""
        if self.genetic_defect_data is None:
            return "Safe"  # 默认安全
            
        try:
            # 尝试不同的列名组合
            cow_cols = ['母牛号', 'dam_id', 'cow_id']
            bull_cols = ['备选公牛号', '公牛号', 'sire_id', 'bull_id']
            
            # 找到实际的列名
            cow_col = next((col for col in cow_cols if col in self.genetic_defect_data.columns), None)
            bull_col = next((col for col in bull_cols if col in self.genetic_defect_data.columns), None)
            
            if not all([cow_col, bull_col]):
                return "Safe"
                
            # 查找数据
            mask = (self.genetic_defect_data[cow_col].astype(str) == str(cow_id)) & \
                   (self.genetic_defect_data[bull_col].astype(str) == str(bull_id))
                   
            if mask.any():
                row = self.genetic_defect_data.loc[mask].iloc[0]
                
                # 检查各种隐性基因
                defect_genes = ['HH1', 'HH2', 'HH3', 'HH4', 'HH5', 'HH6', 
                               'MW', 'BLAD', 'CVM', 'DUMPS', 'Citrullinemia',
                               'Brachyspina', 'Factor XI', 'Mulefoot', 
                               'Cholesterol deficiency', 'Chondrodysplasia']
                
                for gene in defect_genes:
                    if gene in row.index:
                        status = str(row[gene]).strip()
                        if status == '高风险':
                            return "高风险"
                            
        except Exception as e:
            logger.debug(f"检查隐性基因失败 ({cow_id}, {bull_id}): {e}")
            
        return "-"
        
    def _generate_all_recommendations(self) -> pd.DataFrame:
        """生成所有推荐"""
        recommendations = []
        
        total_cows = len(self.cow_data)
        
        for idx, cow in self.cow_data.iterrows():
            if idx % 10 == 0:
                logger.info(f"正在生成推荐 {idx+1}/{total_cows}")
                
            cow_id = str(cow['cow_id'])
            cow_score = cow.get('Combine Index Score', cow.get('Index Score', 2500))
            
            # 复制母牛基本信息
            rec = cow.to_dict()
            
            # 为每种冻精类型生成推荐
            for semen_type in ['常规', '性控']:
                # 获取该类型的公牛
                type_bulls = self.bull_data[
                    self.bull_data['semen_type'] == semen_type
                ].copy()
                
                if type_bulls.empty:
                    continue
                    
                # 计算每个公牛的得分和约束
                bull_scores = []
                
                for _, bull in type_bulls.iterrows():
                    bull_id = str(bull['bull_id'])
                    bull_score = bull.get('Index Score', 2500)
                    
                    # 计算后代得分
                    offspring_score = 0.5 * (cow_score + bull_score)
                    
                    # 获取近交系数
                    inbreeding_coeff = self._get_inbreeding_coefficient(cow_id, bull_id)
                    
                    # 检查隐性基因
                    gene_status = self._check_genetic_defects(cow_id, bull_id)
                    
                    # 判断是否满足约束（避开高风险）
                    meets_constraints = (inbreeding_coeff <= 0.03125 and gene_status != '高风险')
                    
                    bull_scores.append({
                        'bull_id': bull_id,
                        'bull_score': bull_score,
                        'offspring_score': offspring_score,
                        'inbreeding_coeff': inbreeding_coeff,
                        'gene_status': gene_status,
                        'meets_constraints': meets_constraints,
                        'semen_count': bull.get('semen_count', bull.get('支数', 0))
                    })
                
                # 按后代得分排序
                bull_scores.sort(key=lambda x: x['offspring_score'], reverse=True)
                
                # 保存完整的推荐列表
                rec[f'{semen_type}_valid_bulls'] = bull_scores
                
                # 填充前3个推荐位置
                valid_bulls = [b for b in bull_scores if b['meets_constraints']]
                all_bulls = bull_scores
                
                for i in range(1, 4):
                    if i <= len(valid_bulls):
                        # 优先使用满足约束的公牛
                        bull_info = valid_bulls[i-1]
                    elif i <= len(all_bulls):
                        # 如果不够，使用其他公牛
                        bull_info = all_bulls[i-1]
                    else:
                        # 没有公牛了
                        continue
                        
                    rec[f'推荐{semen_type}冻精{i}选'] = bull_info['bull_id']
                    rec[f'{semen_type}冻精{i}近交系数'] = f"{bull_info['inbreeding_coeff']*100:.2f}%"
                    rec[f'{semen_type}冻精{i}隐性基因情况'] = bull_info['gene_status']
                    rec[f'{semen_type}冻精{i}得分'] = bull_info['offspring_score']
                    
            recommendations.append(rec)
            
        return pd.DataFrame(recommendations)
        
    def _save_recommendations(self, recommendations: pd.DataFrame, output_file: Path):
        """保存推荐结果"""
        # 选择要保存的列
        base_cols = ['cow_id', 'breed', 'group', 'birth_date', 'Combine Index Score']
        
        # 添加推荐列
        rec_cols = []
        for i in range(1, 4):
            for semen_type in ['常规', '性控']:
                prefix = f'{semen_type}冻精{i}'
                rec_cols.extend([
                    f'推荐{prefix}选',
                    f'{prefix}近交系数',
                    f'{prefix}隐性基因情况',
                    f'{prefix}得分'
                ])
                
        # 保留valid_bulls列
        valid_bulls_cols = ['常规_valid_bulls', '性控_valid_bulls']
        
        # 合并所有列
        all_cols = base_cols + rec_cols + valid_bulls_cols
        
        # 只保留存在的列
        save_cols = [col for col in all_cols if col in recommendations.columns]
        
        # 保存到Excel
        recommendations[save_cols].to_excel(output_file, index=False)
        
        logger.info(f"推荐报告已保存，包含 {len(recommendations)} 条记录")