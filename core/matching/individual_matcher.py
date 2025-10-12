"""
个体选配核心逻辑模块
实现基于组优先级的双轮分配机制

⚠️ 废弃警告：此模块已被废弃，请使用 CycleBasedMatcher 替代
DEPRECATED: This module is deprecated. Please use CycleBasedMatcher instead.
"""

import pandas as pd
import numpy as np
import re
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict

logger = logging.getLogger(__name__)

class IndividualMatcher:
    """个体选配器，实现智能选配算法"""
    
    def __init__(self):
        self.cow_data = None
        self.bull_data = None
        self.selection_report = None
        self.semen_counts = {}
        self.semen_ratios = {}
        self.inbreeding_threshold = 0.0625  # 默认6.25%
        self.control_defect_genes = True
        
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
            
            # 加载选配报告数据
            report_file = project_path / "analysis_results" / "individual_mating_report.xlsx"
            if not report_file.exists():
                raise FileNotFoundError(f"未找到选配报告文件: {report_file}")
            
            self.selection_report = pd.read_excel(report_file)
            
            logger.info(f"数据加载完成: {len(self.cow_data)}头母牛, {len(self.bull_data)}头公牛")
            return True
            
        except Exception as e:
            logger.error(f"数据加载失败: {e}")
            return False
    
    def set_parameters(self, semen_counts: Dict[str, int], 
                      inbreeding_threshold: float = 0.0625,
                      control_defect_genes: bool = True):
        """设置选配参数"""
        self.semen_counts = semen_counts
        self.inbreeding_threshold = inbreeding_threshold
        self.control_defect_genes = control_defect_genes
        
        # 计算各冻精类型的比例
        self.semen_ratios = self._calculate_semen_ratios(semen_counts)
        
    def _calculate_semen_ratios(self, semen_counts: Dict[str, int]) -> Dict[str, Dict[str, float]]:
        """计算冻精比例"""
        ratios = {'常规': {}, '性控': {}}
        
        # 按类型分组计算比例
        for bull_id, count in semen_counts.items():
            # 从备选公牛数据中获取分类
            bull_row = self.bull_data[self.bull_data['bull_id'] == bull_id]
            if bull_row.empty:
                continue

            # 向后兼容：优先使用semen_type，否则使用classification
            if 'semen_type' in bull_row.columns:
                classification = bull_row['semen_type'].iloc[0]
            else:
                classification = bull_row['classification'].iloc[0]
            if classification in ratios:
                ratios[classification][bull_id] = count
        
        # 转换为百分比
        for semen_type in ratios:
            total = sum(ratios[semen_type].values())
            if total > 0:
                for bull_id in ratios[semen_type]:
                    ratios[semen_type][bull_id] = ratios[semen_type][bull_id] / total * 100
        
        return ratios
    
    def _parse_group_priority(self, group_name: str) -> Tuple[int, int]:
        """解析组名优先级
        返回: (优先级, 周期数字)
        优先级: 0=周期组, 1=难孕牛, 2=已孕牛, 3=默认组
        """
        group_name = str(group_name).lower()
        
        # 检查是否是周期组
        cycle_match = re.search(r'第?(\d+)周期', group_name)
        if cycle_match:
            cycle_num = int(cycle_match.group(1))
            return (0, cycle_num)
        
        # 检查特殊组
        if '难孕牛' in group_name:
            return (1, 0)
        elif '已孕牛' in group_name:
            return (2, 0)
        else:
            # 默认组
            return (3, 0)
    
    def _sort_groups_by_priority(self) -> List[str]:
        """按优先级排序分组"""
        if 'group' not in self.cow_data.columns:
            return []
        
        groups = self.cow_data['group'].unique()
        
        # 为每个组计算优先级
        group_priorities = []
        for group in groups:
            priority, cycle_num = self._parse_group_priority(group)
            group_priorities.append((priority, cycle_num, group))
        
        # 排序：优先级越小越优先，同优先级按周期数字排序
        group_priorities.sort(key=lambda x: (x[0], x[1]))
        
        return [group for _, _, group in group_priorities]
    
    def _get_cow_recommendations(self, cow_id: str, semen_type: str, round_num: int) -> List[str]:
        """获取母牛的推荐冻精列表"""
        cow_report = self.selection_report[self.selection_report['cow_id'] == cow_id]
        if cow_report.empty:
            return []
        
        recommendations = []
        for i in range(1, 4):  # 1-3选
            col_name = f"推荐{semen_type}冻精{i}选"
            if col_name in cow_report.columns:
                bull_id = cow_report[col_name].iloc[0]
                if pd.notna(bull_id) and str(bull_id).strip():
                    recommendations.append(str(bull_id).strip())
        
        return recommendations
    
    def _check_allocation_constraints(self, cow_id: str, bull_id: str, semen_type: str, round_num: int) -> bool:
        """检查分配约束条件"""
        cow_report = self.selection_report[self.selection_report['cow_id'] == cow_id]
        if cow_report.empty:
            return False
        
        # 查找对应的约束信息
        for i in range(1, 4):
            col_bull = f"推荐{semen_type}冻精{i}选"
            col_inbreeding = f"{semen_type}冻精{i}近交系数"
            col_genes = f"{semen_type}冻精{i}隐性基因情况"
            
            if (col_bull in cow_report.columns and 
                cow_report[col_bull].iloc[0] == bull_id):
                
                # 检查近交系数
                if col_inbreeding in cow_report.columns:
                    inbreeding_str = cow_report[col_inbreeding].iloc[0]
                    if pd.notna(inbreeding_str) and inbreeding_str != "N/A":
                        try:
                            inbreeding_coeff = float(str(inbreeding_str).strip('%')) / 100
                            if inbreeding_coeff > self.inbreeding_threshold:
                                return False
                        except (ValueError, TypeError):
                            pass
                
                # 检查隐性基因
                if self.control_defect_genes and col_genes in cow_report.columns:
                    gene_info = cow_report[col_genes].iloc[0]
                    if str(gene_info).strip() == "高风险":
                        return False
                
                return True
        
        return False
    
    def perform_matching(self, selected_groups: List[str] = None) -> pd.DataFrame:
        """执行个体选配"""
        if self.cow_data is None or self.bull_data is None:
            raise ValueError("请先加载数据")
        
        # 如果没有指定分组，使用所有分组
        if selected_groups is None:
            selected_groups = self._sort_groups_by_priority()
        else:
            # 对选定的分组进行排序
            all_sorted_groups = self._sort_groups_by_priority()
            selected_groups = [g for g in all_sorted_groups if g in selected_groups]
        
        logger.info(f"开始选配，处理组顺序: {selected_groups}")
        
        # 初始化结果DataFrame
        result_columns = ['cow_id'] + [f"{semen_type}{i}选" for semen_type in ['性控', '常规'] for i in range(1, 4)]
        result_df = pd.DataFrame(columns=result_columns)
        
        # 初始化使用计数器
        usage_counters = defaultdict(int)
        
        # 按组优先级进行分配
        for group_name in selected_groups:
            logger.info(f"处理分组: {group_name}")
            
            # 获取该组的母牛，按权重名_index降序排序
            group_cows = self.cow_data[self.cow_data['group'] == group_name].copy()
            
            # 查找权重名_index列
            weight_col = None
            for col in group_cows.columns:
                if col.endswith('_index'):
                    weight_col = col
                    break
            
            if weight_col:
                group_cows = group_cows.sort_values(by=weight_col, ascending=False)
            else:
                logger.warning(f"未找到权重指数列，使用默认排序")
            
            # 对该组执行双轮分配
            group_result = self._allocate_group(group_cows, usage_counters)
            result_df = pd.concat([result_df, group_result], ignore_index=True)
        
        # 合并基础数据
        final_result = pd.merge(
            self.cow_data[['cow_id', 'group', 'lac', 'age', 'sire', 'mgs', 'dam', 'mmgs', 
                          'calving_date', 'birth_date', 'breed', 'sex']],
            result_df,
            on='cow_id',
            how='left'
        )
        
        return final_result
    
    def _allocate_group(self, group_cows: pd.DataFrame, usage_counters: Dict[str, int]) -> pd.DataFrame:
        """对单个分组执行双轮分配"""
        group_size = len(group_cows)
        result_rows = []
        
        # 初始化每头母牛的结果记录
        for _, cow in group_cows.iterrows():
            cow_result = {'cow_id': cow['cow_id']}
            for semen_type in ['性控', '常规']:
                for i in range(1, 4):
                    cow_result[f"{semen_type}{i}选"] = None
            result_rows.append(cow_result)
        
        # 分配顺序：性控1选 -> 性控2选 -> 性控3选 -> 常规1选 -> 常规2选 -> 常规3选
        allocation_order = [(semen_type, i) for semen_type in ['性控', '常规'] for i in range(1, 4)]
        
        for semen_type, round_num in allocation_order:
            logger.info(f"  分配 {semen_type}{round_num}选")
            
            # 计算该轮次的配额
            group_ratios = self.semen_ratios.get(semen_type, {})
            target_counts = {}
            for bull_id, ratio in group_ratios.items():
                target_counts[bull_id] = int(group_size * ratio / 100)
            
            # 第一轮：严格按比例分配
            current_usage = defaultdict(int)
            allocated_cows = set()
            
            for i, cow_result in enumerate(result_rows):
                if cow_result[f"{semen_type}{round_num}选"] is not None:
                    continue  # 已分配
                
                cow_id = cow_result['cow_id']
                recommendations = self._get_cow_recommendations(cow_id, semen_type, round_num)
                
                for bull_id in recommendations:
                    if (self._check_allocation_constraints(cow_id, bull_id, semen_type, round_num) and
                        current_usage[bull_id] < target_counts.get(bull_id, 0)):
                        
                        cow_result[f"{semen_type}{round_num}选"] = bull_id
                        current_usage[bull_id] += 1
                        allocated_cows.add(i)
                        break
            
            # 第二轮：不考虑配额限制，确保每头母牛都有分配
            for i, cow_result in enumerate(result_rows):
                if cow_result[f"{semen_type}{round_num}选"] is not None:
                    continue  # 已分配
                
                cow_id = cow_result['cow_id']
                recommendations = self._get_cow_recommendations(cow_id, semen_type, round_num)
                
                for bull_id in recommendations:
                    if self._check_allocation_constraints(cow_id, bull_id, semen_type, round_num):
                        cow_result[f"{semen_type}{round_num}选"] = bull_id
                        current_usage[bull_id] += 1
                        break
        
        return pd.DataFrame(result_rows)
    
    def save_results(self, result_df: pd.DataFrame, output_path: Path):
        """保存选配结果"""
        try:
            result_df.to_excel(output_path, index=False)
            logger.info(f"选配结果已保存至: {output_path}")
            return True
        except Exception as e:
            logger.error(f"保存结果失败: {e}")
            return False 