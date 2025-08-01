"""
PPT分析文本自动生成器

负责为PPT各个部分生成分析文本
"""

import logging
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class AnalysisTextGenerator:
    """分析文本生成器类"""
    
    def __init__(self, trait_translations: Dict[str, str]):
        """
        初始化分析文本生成器
        
        Args:
            trait_translations: 性状翻译字典
        """
        self.trait_translations = trait_translations
        
    def generate_pedigree_analysis_text(self, pedigree_data: pd.DataFrame) -> Dict[str, str]:
        """
        生成系谱分析文本
        
        Args:
            pedigree_data: 系谱数据
            
        Returns:
            分析文本字典
        """
        try:
            texts = {}
            
            # 计算统计数据
            total_animals = len(pedigree_data)
            
            # 父系识别率
            if 'sire_identified' in pedigree_data.columns:
                sire_identified = (pedigree_data['sire_identified'] == '已识别').sum()
                sire_rate = sire_identified / total_animals * 100 if total_animals > 0 else 0
            else:
                sire_rate = 0
                
            # 外祖父识别率
            if 'mgs_identified' in pedigree_data.columns:
                mgs_identified = (pedigree_data['mgs_identified'] == '已识别').sum()
                mgs_rate = mgs_identified / total_animals * 100 if total_animals > 0 else 0
            else:
                mgs_rate = 0
                
            # 生成概述文本
            texts['overview'] = (
                f"本牧场共有{total_animals}头牛只的系谱记录。"
                f"其中父系识别率为{sire_rate:.1f}%，"
                f"外祖父识别率为{mgs_rate:.1f}%。"
            )
            
            # 生成详细分析文本
            texts['detailed'] = (
                f"系谱完整性分析显示，本牧场的父系识别工作"
                f"{'表现良好' if sire_rate > 80 else '仍有提升空间'}。"
                f"建议{'继续保持' if sire_rate > 80 else '加强'}系谱记录管理，"
                f"特别是{'外祖父系' if mgs_rate < sire_rate else '整体'}的识别工作。"
            )
            
            # 生成改进建议
            suggestions = []
            if sire_rate < 90:
                suggestions.append("加强配种记录管理，确保所有配种信息准确记录")
            if mgs_rate < 70:
                suggestions.append("完善母牛系谱档案，追溯外祖父信息")
            if not suggestions:
                suggestions.append("继续保持良好的系谱记录管理")
                
            texts['suggestions'] = "改进建议：" + "；".join(suggestions) + "。"
            
            return texts
            
        except Exception as e:
            logger.error(f"生成系谱分析文本失败: {str(e)}")
            return {
                'overview': "系谱数据分析中...",
                'detailed': "详细分析处理中...",
                'suggestions': "建议生成中..."
            }
    
    def generate_genetic_evaluation_text(self, cow_data: pd.DataFrame, 
                                       selected_traits: List[str]) -> Dict[str, str]:
        """
        生成遗传评估分析文本
        
        Args:
            cow_data: 母牛性状数据
            selected_traits: 选中的性状列表
            
        Returns:
            分析文本字典
        """
        try:
            texts = {}
            
            # 过滤在场牛只
            if '是否在场' in cow_data.columns:
                in_herd = cow_data[cow_data['是否在场'] == '是']
            else:
                in_herd = cow_data
                
            total_cows = len(in_herd)
            
            # 计算各性状的平均值和标准差
            trait_stats = {}
            for trait in selected_traits:
                if trait in in_herd.columns:
                    trait_data = in_herd[trait].dropna()
                    if len(trait_data) > 0:
                        trait_stats[trait] = {
                            'mean': trait_data.mean(),
                            'std': trait_data.std(),
                            'count': len(trait_data)
                        }
            
            # 生成概述文本
            texts['overview'] = (
                f"本次遗传评估涵盖{total_cows}头在场母牛，"
                f"评估性状包括{len(trait_stats)}个关键性状。"
            )
            
            # 生成性状分析文本
            trait_analysis = []
            for trait, stats in trait_stats.items():
                trait_name = self.trait_translations.get(trait, trait)
                trait_analysis.append(
                    f"{trait_name}平均值为{stats['mean']:.2f}(±{stats['std']:.2f})"
                )
                
            texts['trait_analysis'] = "各性状表现：" + "；".join(trait_analysis[:3]) + "等。"
            
            # 生成遗传趋势分析
            if 'birth_date' in in_herd.columns:
                in_herd['birth_year'] = pd.to_datetime(in_herd['birth_date']).dt.year
                recent_years = in_herd['birth_year'].max() - 2
                
                # 计算近三年的遗传进展
                recent_cows = in_herd[in_herd['birth_year'] >= recent_years]
                older_cows = in_herd[in_herd['birth_year'] < recent_years]
                
                progress_traits = []
                for trait in selected_traits[:3]:  # 只分析前3个性状
                    if trait in in_herd.columns:
                        recent_mean = recent_cows[trait].mean()
                        older_mean = older_cows[trait].mean()
                        if pd.notna(recent_mean) and pd.notna(older_mean):
                            change = ((recent_mean - older_mean) / older_mean * 100) if older_mean != 0 else 0
                            trait_name = self.trait_translations.get(trait, trait)
                            if abs(change) > 0.1:
                                progress_traits.append(
                                    f"{trait_name}{'提升' if change > 0 else '下降'}{abs(change):.1f}%"
                                )
                                
                texts['genetic_trend'] = (
                    f"遗传进展分析显示，近三年出生的母牛在"
                    f"{', '.join(progress_traits[:2]) if progress_traits else '各性状上保持稳定'}。"
                )
            else:
                texts['genetic_trend'] = "遗传趋势分析需要出生日期数据。"
            
            return texts
            
        except Exception as e:
            logger.error(f"生成遗传评估文本失败: {str(e)}")
            return {
                'overview': "遗传评估数据分析中...",
                'trait_analysis': "性状分析处理中...",
                'genetic_trend': "遗传趋势分析中..."
            }
    
    def generate_breeding_index_text(self, index_data: pd.DataFrame) -> Dict[str, str]:
        """
        生成育种指数分析文本
        
        Args:
            index_data: 育种指数数据
            
        Returns:
            分析文本字典
        """
        try:
            texts = {}
            
            if '育种指数得分' not in index_data.columns:
                return {
                    'overview': "育种指数数据缺失",
                    'distribution': "分布分析不可用",
                    'recommendations': "请确保育种指数计算完成"
                }
                
            # 计算统计数据
            scores = index_data['育种指数得分'].dropna()
            mean_score = scores.mean()
            std_score = scores.std()
            
            # 计算分位数
            q1 = scores.quantile(0.25)
            q2 = scores.quantile(0.50)
            q3 = scores.quantile(0.75)
            
            # 生成概述文本
            texts['overview'] = (
                f"牛群育种指数平均得分为{mean_score:.1f}分，"
                f"标准差为{std_score:.1f}。"
                f"中位数为{q2:.1f}分。"
            )
            
            # 生成分布分析
            texts['distribution'] = (
                f"育种指数分布分析显示，"
                f"25%的牛只得分低于{q1:.1f}分，"
                f"50%的牛只得分在{q1:.1f}-{q3:.1f}分之间，"
                f"25%的牛只得分高于{q3:.1f}分。"
            )
            
            # 生成选配建议
            high_performers = len(scores[scores > q3])
            texts['recommendations'] = (
                f"建议重点关注得分前25%的{high_performers}头高遗传潜力母牛，"
                f"优先安排优质冻精配种。"
                f"对于得分较低的个体，建议考虑淘汰或使用性控冻精。"
            )
            
            return texts
            
        except Exception as e:
            logger.error(f"生成育种指数文本失败: {str(e)}")
            return {
                'overview': "育种指数分析中...",
                'distribution': "分布分析处理中...",
                'recommendations': "建议生成中..."
            }
    
    def generate_bull_usage_text(self, breeding_data: pd.DataFrame, 
                               bull_traits: pd.DataFrame) -> Dict[str, str]:
        """
        生成公牛使用分析文本
        
        Args:
            breeding_data: 配种记录数据
            bull_traits: 公牛性状数据
            
        Returns:
            分析文本字典
        """
        try:
            texts = {}
            
            # 统计公牛使用情况
            if 'BULL NAAB' in breeding_data.columns:
                bull_usage = breeding_data['BULL NAAB'].value_counts()
                total_matings = len(breeding_data)
                unique_bulls = len(bull_usage)
                
                # 计算冻精类型分布
                if '冻精类型' in breeding_data.columns:
                    semen_types = breeding_data['冻精类型'].value_counts()
                    type_text = "、".join([
                        f"{stype}占{count/total_matings*100:.1f}%" 
                        for stype, count in semen_types.items()
                    ])
                else:
                    type_text = "冻精类型数据缺失"
                
                texts['overview'] = (
                    f"共使用{unique_bulls}头公牛的冻精，"
                    f"完成配种{total_matings}次。"
                    f"冻精类型分布：{type_text}。"
                )
                
                # 分析主要使用的公牛
                top_bulls = bull_usage.head(5)
                top_bull_info = []
                for bull_id, count in top_bulls.items():
                    usage_rate = count / total_matings * 100
                    top_bull_info.append(f"{bull_id}({usage_rate:.1f}%)")
                    
                texts['top_bulls'] = (
                    f"使用最多的5头公牛为：{', '.join(top_bull_info)}。"
                    f"前5头公牛的使用占比达{top_bulls.sum()/total_matings*100:.1f}%。"
                )
                
                # 生成公牛选择建议
                if unique_bulls < 10:
                    suggestion = "建议增加公牛多样性，避免近交风险"
                elif unique_bulls > 50:
                    suggestion = "公牛使用较为分散，建议优化公牛选择策略"
                else:
                    suggestion = "公牛使用多样性适中，继续保持"
                    
                texts['suggestions'] = suggestion
                
            else:
                texts['overview'] = "配种记录中缺少公牛信息"
                texts['top_bulls'] = "无法分析公牛使用情况"
                texts['suggestions'] = "请完善配种记录"
                
            return texts
            
        except Exception as e:
            logger.error(f"生成公牛使用分析文本失败: {str(e)}")
            return {
                'overview': "公牛使用分析中...",
                'top_bulls': "主要公牛分析中...",
                'suggestions': "建议生成中..."
            }
    
    def generate_trait_progress_text(self, trait_data: pd.DataFrame, 
                                   trait_name: str) -> str:
        """
        生成单个性状进展分析文本
        
        Args:
            trait_data: 性状数据（包含年份信息）
            trait_name: 性状名称
            
        Returns:
            分析文本
        """
        try:
            if 'birth_year' not in trait_data.columns or trait_name not in trait_data.columns:
                return f"{trait_name}进展数据不完整。"
                
            # 按年份分组计算平均值
            yearly_avg = trait_data.groupby('birth_year')[trait_name].mean()
            
            # 计算趋势
            if len(yearly_avg) >= 3:
                recent_avg = yearly_avg.iloc[-3:].mean()
                older_avg = yearly_avg.iloc[:-3].mean() if len(yearly_avg) > 3 else yearly_avg.iloc[0]
                
                change = ((recent_avg - older_avg) / abs(older_avg) * 100) if older_avg != 0 else 0
                
                trend = "上升" if change > 1 else "下降" if change < -1 else "稳定"
                
                return (
                    f"{self.trait_translations.get(trait_name, trait_name)}"
                    f"近三年呈{trend}趋势"
                    f"{f'，变化幅度为{abs(change):.1f}%' if abs(change) > 1 else ''}。"
                )
            else:
                return f"{self.trait_translations.get(trait_name, trait_name)}数据点不足，无法分析趋势。"
                
        except Exception as e:
            logger.error(f"生成性状进展文本失败: {str(e)}")
            return f"{trait_name}进展分析出错。"