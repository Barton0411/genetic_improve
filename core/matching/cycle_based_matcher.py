"""
基于周期的选配分配器
严格按照周期顺序和冻精比例进行分配
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import math

from .allocation_utils import calculate_proportional_allocation, calculate_equal_allocation

logger = logging.getLogger(__name__)

class CycleBasedMatcher:
    """基于周期的选配分配器"""
    
    def __init__(self):
        self.recommendations_df = None
        self.bull_data = None
        self.bull_inventory = {}  # 公牛库存 {(bull_id, semen_type): remaining_count}
        self.bull_scores = {}  # 公牛得分 {bull_id: score}
        self.allocation_results = []  # 分配结果
        self.inbreeding_threshold = 6.25  # 默认近交系数阈值
        self.control_defect_genes = True  # 默认控制隐性基因
        
    def load_data(self, recommendations_df: pd.DataFrame, bull_data_path: Path) -> bool:
        """加载数据"""
        try:
            self.recommendations_df = recommendations_df
            
            # 尝试加载母牛指数数据
            project_path = bull_data_path.parent.parent
            index_file = project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
            if index_file.exists():
                try:
                    index_df = pd.read_excel(index_file)
                    # 合并指数得分
                    if 'cow_id' in index_df.columns and 'Combine Index Score' in index_df.columns:
                        # 确保cow_id是字符串类型
                        index_df['cow_id'] = index_df['cow_id'].astype(str)
                        self.recommendations_df['cow_id'] = self.recommendations_df['cow_id'].astype(str)
                        # 合并得分
                        self.recommendations_df = self.recommendations_df.merge(
                            index_df[['cow_id', 'Combine Index Score']], 
                            on='cow_id', 
                            how='left'
                        )
                        logger.info("成功加载母牛指数得分")
                except Exception as e:
                    logger.warning(f"加载母牛指数得分失败: {e}")
            
            # 加载公牛数据
            if bull_data_path.exists():
                self.bull_data = pd.read_excel(bull_data_path)
                
                # 加载公牛指数得分
                bull_index_file = project_path / "analysis_results" / "processed_index_bull_scores.xlsx"
                if bull_index_file.exists():
                    try:
                        bull_index_df = pd.read_excel(bull_index_file)
                        # 查找指数列（可能是 xxx_index 格式）
                        index_columns = [col for col in bull_index_df.columns if col.endswith('_index')]
                        
                        if 'bull_id' in bull_index_df.columns and index_columns:
                            # 使用第一个找到的指数列
                            index_col = index_columns[0]
                            # 将指数列重命名为Bull Index Score
                            bull_index_df['Bull Index Score'] = bull_index_df[index_col]
                            
                            # 确保bull_id是字符串类型
                            bull_index_df['bull_id'] = bull_index_df['bull_id'].astype(str)
                            self.bull_data['bull_id'] = self.bull_data['bull_id'].astype(str)
                            
                            # 合并公牛指数得分
                            self.bull_data = self.bull_data.merge(
                                bull_index_df[['bull_id', 'Bull Index Score']],
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
                
                # 初始化库存和得分（使用复合键）
                for _, bull in self.bull_data.iterrows():
                    bull_id = str(bull['bull_id'])

                    # 获取semen_type
                    if 'semen_type' in bull:
                        semen_type = str(bull['semen_type'])
                    elif 'classification' in bull:
                        semen_type = str(bull['classification'])
                    else:
                        semen_type = '常规'  # 默认为常规

                    # 支持多种列名，bull 是一个 Series
                    if 'semen_count' in bull:
                        count = bull['semen_count']
                    elif '支数' in bull:
                        count = bull['支数']
                    else:
                        count = 0

                    # 使用(bull_id, semen_type)作为复合键
                    self.bull_inventory[(bull_id, semen_type)] = int(count)

                    # 保存公牛得分（按bull_id，不区分类型）
                    self.bull_scores[bull_id] = bull.get('Bull Index Score', 0)
                    
                # 检查是否所有支数都是0
                if all(count == 0 for count in self.bull_inventory.values()):
                    logger.warning("所有公牛的冻精支数都为0，请先设置冻精库存")
                    return False
                    
                logger.info(f"加载了 {len(self.bull_data)} 头公牛的库存信息")
                return True
            else:
                logger.error(f"未找到公牛数据文件: {bull_data_path}")
                return False
                
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            return False
            
    def set_inventory(self, inventory_dict: Dict):
        """设置公牛库存，支持复合键{(bull_id, semen_type): count}"""
        for key, count in inventory_dict.items():
            if key in self.bull_inventory:
                self.bull_inventory[key] = count
        logger.info(f"更新了 {len(inventory_dict)} 条库存记录")
        
    def check_zero_inventory(self) -> bool:
        """检查是否所有公牛库存都是0"""
        return all(count == 0 for count in self.bull_inventory.values())
        
    def get_inventory_summary(self) -> pd.DataFrame:
        """获取库存汇总（使用复合键）"""
        summary = []
        for (bull_id, semen_type), count in self.bull_inventory.items():
            summary.append({
                '公牛号': bull_id,
                '冻精类型': semen_type,
                '当前库存': count
            })
        return pd.DataFrame(summary)
        
    def perform_allocation(self, selected_groups: List[str], progress_callback=None) -> pd.DataFrame:
        """
        执行基于周期的分配

        Args:
            selected_groups: 选中的分组列表
            progress_callback: 进度回调函数

        Returns:
            分配结果DataFrame
        """
        # 重置结果
        self.allocation_results = []

        # 保存原始库存，不在分配过程中修改
        self.original_inventory = self.bull_inventory.copy()

        # 检查推荐数据
        if self.recommendations_df is None:
            logger.error("recommendations_df 为 None")
            return pd.DataFrame()

        logger.info(f"recommendations_df 类型: {type(self.recommendations_df)}")
        logger.info(f"recommendations_df 列: {list(self.recommendations_df.columns) if hasattr(self.recommendations_df, 'columns') else 'No columns'}")

        if 'group' not in self.recommendations_df.columns:
            logger.error("recommendations_df 缺少 'group' 列")
            logger.error(f"可用列: {list(self.recommendations_df.columns)}")
            return pd.DataFrame()

        # 筛选选中分组的母牛，同时处理 nan 值
        # 首先过滤掉 group 列中的 nan 值
        valid_recommendations = self.recommendations_df[self.recommendations_df['group'].notna()].copy()

        # 将group列和selected_groups都转换为字符串进行比较
        valid_recommendations['group_str'] = valid_recommendations['group'].astype(str)
        selected_groups_str = [str(g) for g in selected_groups]

        selected_cows = valid_recommendations[
            valid_recommendations['group_str'].isin(selected_groups_str)
        ].copy()

        # 恢复原始的group列
        selected_cows = selected_cows.drop('group_str', axis=1)

        logger.info(f"选中的分组: {selected_groups}")
        logger.info(f"筛选后的母牛数量: {len(selected_cows)}")

        if selected_cows.empty:
            logger.warning("未找到选中分组的母牛")
            return pd.DataFrame()
            
        # 按周期分组并排序
        cycle_groups = self._group_by_cycles(selected_cows, selected_groups)
        
        total_cycles = len(cycle_groups)
        
        # 按周期顺序处理
        total_cows_all_cycles = sum(len(cows) for _, cows in cycle_groups)
        processed_cows = 0

        for cycle_idx, (cycle_name, cycle_cows) in enumerate(cycle_groups):
            cycle_cow_count = len(cycle_cows)

            if progress_callback:
                progress = int((cycle_idx / total_cycles) * 100)
                progress_callback(f"正在分配 {cycle_name} ({cycle_cow_count}头母牛)", progress)

            logger.info(f"开始分配 {cycle_name}，包含 {cycle_cow_count} 头母牛")

            # 为这个周期的所有母牛分配
            self._allocate_cycle(cycle_name, cycle_cows)

            processed_cows += cycle_cow_count
            logger.info(f"累计已处理: ({processed_cows}/{total_cows_all_cycles}头)")
            
        # 转换结果为DataFrame
        result_df = self._convert_results_to_dataframe()
        
        if progress_callback:
            progress_callback("分配完成", 100)
            
        return result_df
        
    def _group_by_cycles(self, cows_df: pd.DataFrame, selected_groups: List[str]) -> List[Tuple[str, pd.DataFrame]]:
        """按分组处理母牛（支持手动分组和自动分组）"""
        cycle_groups = []

        # 处理所有选中的分组（不区分是否包含"周期"等关键字）
        for group in selected_groups:
            # 跳过 nan
            if pd.isna(group):
                logger.warning(f"跳过无效分组: {group}")
                continue

            # 转换为字符串进行比较
            group_str = str(group)

            # 获取该分组的母牛（比较时将两边都转为字符串）
            group_cows = cows_df[cows_df['group'].astype(str) == group_str].copy()

            if not group_cows.empty:
                # 按指数得分排序（高分优先）
                # 尝试多个可能的得分列名
                score_cols = ['index_score', 'Combine Index Score', 'NM$权重_index']
                score_col = None
                for col in score_cols:
                    if col in group_cows.columns:
                        score_col = col
                        break

                if score_col:
                    group_cows = group_cows.sort_values(score_col, ascending=False)

                cycle_groups.append((group_str, group_cows))
                logger.info(f"处理分组 '{group_str}'，包含 {len(group_cows)} 头母牛")
            else:
                logger.warning(f"分组 '{group_str}' 没有找到母牛")

        # 对分组进行排序（如果是自动分组的周期组，按周期数字排序；否则保持原顺序）
        def sort_key(x):
            group_name = x[0]
            # 尝试提取周期数字（仅用于自动分组的排序）
            import re
            match = re.search(r'第(\d+)周期', group_name)
            if match:
                return (0, int(match.group(1)))  # 周期组优先，按数字排序
            else:
                # 非周期组，保持原始顺序
                try:
                    return (1, selected_groups.index(group_name))
                except ValueError:
                    return (2, 0)  # 如果找不到，放在最后

        cycle_groups.sort(key=sort_key)

        return cycle_groups
        
    def _extract_cycle_number(self, cycle_name: str) -> int:
        """提取周期数字"""
        import re
        match = re.search(r'第(\d+)周期', cycle_name)
        if match:
            return int(match.group(1))
        return 999  # 非周期组排在最后
        
    def _allocate_cycle(self, cycle_name: str, cycle_cows: pd.DataFrame):
        """为一个周期分配选配"""
        try:
            logger.info(f"开始为 {cycle_name} 分配选配，包含 {len(cycle_cows)} 头母牛")
            
            # 检查是否是非性控组（包括肉牛组）
            if '+非性控' in cycle_name:
                # 非性控组只分配常规冻精
                logger.info(f"{cycle_name} 是非性控组，只分配常规冻精")
                semen_type = '常规'
                # 使用新的统一分配方法
                self._allocate_all_choices_with_progression(cycle_name, cycle_cows, semen_type)
            else:
                # 性控组分别处理常规和性控
                for semen_type in ['常规', '性控']:
                    logger.info(f"处理 {semen_type} 冻精分配")
                    # 使用新的统一分配方法
                    self._allocate_all_choices_with_progression(cycle_name, cycle_cows, semen_type)
        except Exception as e:
            logger.error(f"分配周期 {cycle_name} 时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _allocate_all_choices_with_progression(self, cycle_name: str, cycle_cows: pd.DataFrame, semen_type: str):
        """使用递进机制一次性为所有母牛分配1、2、3选"""
        logger.info(f"开始为 {cycle_name} 分配 {semen_type} 冻精（使用完整递进机制）")

        total_cows = len(cycle_cows)

        # 第一步：按比例分配1选
        self._allocate_first_choice_proportional(cycle_name, cycle_cows, semen_type)

        # 第二步：为每头母牛处理递进分配
        for idx, (_, cow) in enumerate(cycle_cows.iterrows()):
            cow_id = str(cow['cow_id'])
            current_cow = idx + 1

            # 记录进度
            if current_cow % 50 == 0 or current_cow == total_cows:
                logger.info(f"{cycle_name} {semen_type}递进分配进度: ({current_cow}/{total_cows}头)")
            valid_bulls_key = f'{semen_type}_valid_bulls'
            
            # 获取有效公牛列表
            valid_bulls_str = cow.get(valid_bulls_key, None)
            if valid_bulls_str is None:
                logger.debug(f"母牛 {cow_id} 没有 {semen_type} 有效公牛列表")
                continue
                
            # 解析字符串形式的列表
            valid_bulls = []
            if isinstance(valid_bulls_str, str):
                try:
                    import ast
                    valid_bulls = ast.literal_eval(valid_bulls_str)
                except:
                    valid_bulls = []
            else:
                valid_bulls = valid_bulls_str
            
            if not valid_bulls:
                continue
            
            # 计算每个公牛的后代得分并排序
            cow_score = cow.get('Combine Index Score', 0)
            for bull in valid_bulls:
                bull_id = bull['bull_id']
                bull_score = self.bull_scores.get(bull_id, 0)
                # 后代得分 = 母牛得分和公牛得分的平均值
                bull['offspring_score'] = 0.5 * (cow_score + bull_score)
                bull['bull_score'] = bull_score
            
            # 按后代得分排序（高分优先）
            valid_bulls.sort(key=lambda x: x.get('offspring_score', 0), reverse=True)
            
            # 获取已分配的公牛
            already_allocated = self._get_cow_allocations(cow_id, semen_type)
            
            # 过滤出可用的公牛（有库存、满足约束、未分配）
            # 使用(bull_id, semen_type)复合键查询库存
            available_bulls = [
                bull for bull in valid_bulls
                if self.bull_inventory.get((bull['bull_id'], semen_type), 0) > 0 and
                   self._meets_constraints(bull) and
                   bull['bull_id'] not in already_allocated
            ]
            
            # 递进分配机制
            choice_num = len(already_allocated) + 1  # 下一个要分配的选择号
            
            # 最多分配3个选择
            while choice_num <= 3 and available_bulls:
                # 取第一个可用的公牛（得分最高的）
                bull_info = available_bulls[0]
                bull_id = bull_info['bull_id']
                
                # 分配
                self._record_allocation(cow_id, bull_id, semen_type, choice_num, bull_info)
                # 不再减库存，1/2/3选是独立的推荐方案
                # self.bull_inventory[bull_id] -= 1

                # 从可用列表中移除已分配的公牛
                available_bulls = available_bulls[1:]

                # 不再需要检查库存用尽，因为不扣库存
                # if self.bull_inventory[bull_id] == 0:
                #     available_bulls = [
                #         b for b in available_bulls
                #         if b['bull_id'] != bull_id
                #     ]
                
                choice_num += 1
            
            if choice_num == 1:
                logger.debug(f"母牛 {cow_id} 没有任何 {semen_type} 冻精分配")
            
    def _allocate_first_choice_proportional(self, cycle_name: str, cycle_cows: pd.DataFrame, semen_type: str):
        """分配1选（严格按库存比例）"""
        try:
            # 获取该类型有库存的公牛（使用复合键）
            bull_inventories = {}
            for (bull_id, bull_semen_type), count in self.bull_inventory.items():
                if count > 0 and bull_semen_type == semen_type:
                    bull_inventories[bull_id] = count
        except Exception as e:
            logger.error(f"获取公牛库存时出错: {e}")
            return

        if not bull_inventories:
            logger.warning(f"{cycle_name} 没有可用的{semen_type}公牛")
            return

        total_cows = len(cycle_cows)
        logger.info(f"{cycle_name} {semen_type}1选：需要分配 {total_cows} 头母牛")

        # 使用按库存比例分配函数，确保小库存公牛至少分配1头
        from core.matching.allocation_utils import calculate_proportional_allocation
        bull_quotas = calculate_proportional_allocation(
            bull_inventories,
            total_cows,
            ensure_minimum=True
        )
            
        logger.info(f"配额分配: {bull_quotas}")
        
        # 创建候选列表（每头母牛的有效公牛列表）
        candidates = []
        skipped_cows = []

        for idx, (_, cow) in enumerate(cycle_cows.iterrows()):
            cow_id = str(cow['cow_id'])
            current_cow = idx + 1

            # 记录进度
            if current_cow % 100 == 0 or current_cow == total_cows:
                logger.info(f"{cycle_name} {semen_type}第1选准备: ({current_cow}/{total_cows}头)")
            valid_bulls_key = f'{semen_type}_valid_bulls'
            
            valid_bulls = cow.get(valid_bulls_key, None)
            if valid_bulls is not None:
                # 如果是字符串，尝试解析
                if isinstance(valid_bulls, str):
                    try:
                        import ast
                        valid_bulls = ast.literal_eval(valid_bulls)
                    except:
                        valid_bulls = []
                # 只保留有库存和配额的公牛（使用复合键查询库存）
                valid_bulls = [
                    b for b in valid_bulls
                    if b['bull_id'] in bull_quotas and
                    bull_quotas[b['bull_id']] > 0 and
                    self.bull_inventory.get((b['bull_id'], semen_type), 0) > 0 and
                    self._meets_constraints(b)  # 满足约束
                ]
                
                # 无论是否有满足配额的公牛，都保存所有有效公牛供后续递进使用
                if valid_bulls:
                    # 计算每个公牛的后代得分
                    cow_score = cow.get('Combine Index Score', 0)
                    for bull in valid_bulls:
                        bull_id = bull['bull_id']
                        bull_score = self.bull_scores.get(bull_id, 0)
                        # 后代得分 = 母牛得分和公牛得分的平均值
                        bull['offspring_score'] = 0.5 * (cow_score + bull_score)
                        bull['bull_score'] = bull_score
                    
                    # 按后代得分排序（高分优先）
                    valid_bulls.sort(key=lambda x: x.get('offspring_score', 0), reverse=True)
                    
                # 获取原始的所有有效公牛（不过滤配额）
                all_valid_bulls_raw = cow.get(valid_bulls_key, None)
                all_valid_bulls = []
                if all_valid_bulls_raw is not None:
                    if isinstance(all_valid_bulls_raw, str):
                        try:
                            import ast
                            all_valid_bulls = ast.literal_eval(all_valid_bulls_raw)
                        except:
                            all_valid_bulls = []
                    else:
                        all_valid_bulls = all_valid_bulls_raw
                    
                if all_valid_bulls:
                    candidates.append({
                        'cow_id': cow_id,
                        'cow_score': cow.get('Combine Index Score', 0),
                        'valid_bulls': valid_bulls,  # 满足配额的公牛
                        'all_valid_bulls': all_valid_bulls  # 所有有效公牛（用于递进）
                    })
                else:
                    skipped_cows.append(cow_id)
            else:
                skipped_cows.append(cow_id)
                    
        # 按母牛得分排序（高分优先）
        candidates.sort(key=lambda x: x['cow_score'], reverse=True)
        
        if skipped_cows:
            logger.warning(f"{cycle_name} {semen_type}1选: {len(skipped_cows)}头母牛没有可用公牛而被跳过")
        
        # 分配
        used_quotas = defaultdict(int)
        total_candidates = len(candidates)

        for idx, candidate in enumerate(candidates):
            cow_id = candidate['cow_id']
            current_candidate = idx + 1

            # 记录分配进度
            if current_candidate % 100 == 0 or current_candidate == total_candidates:
                logger.info(f"{cycle_name} {semen_type}第1选分配: ({current_candidate}/{total_candidates}头)")
            allocated = False
            
            # 尝试分配给得分最高且有配额的公牛
            for bull_info in candidate['valid_bulls']:
                bull_id = bull_info['bull_id']

                if (bull_id in bull_quotas and
                    used_quotas[bull_id] < bull_quotas[bull_id] and
                    self.bull_inventory.get((bull_id, semen_type), 0) > 0):

                    # 分配成功
                    self._record_allocation(cow_id, bull_id, semen_type, 1, bull_info)
                    used_quotas[bull_id] += 1
                    # 不再减库存，1/2/3选是独立的推荐方案
                    # self.bull_inventory[bull_id] -= 1
                    allocated = True
                    break
                    
            if not allocated:
                logger.warning(f"母牛 {cow_id} 无法分配{semen_type}1选（没有符合条件的公牛或库存不足）")
                
        # 记录实际分配情况
        actual_allocation = dict(used_quotas)
        logger.info(f"实际分配: {actual_allocation}")
        
    def _allocate_second_third_choice(self, cycle_name: str, cycle_cows: pd.DataFrame,
                                     semen_type: str, choice_num: int):
        """分配2选或3选（平均分配给库存>0的公牛）"""
        # 获取有库存的公牛列表（使用复合键）
        available_bulls = [
            bull_id for (bull_id, bull_semen_type), count in self.bull_inventory.items()
            if count > 0 and bull_semen_type == semen_type
        ]

        if not available_bulls:
            logger.warning(f"{cycle_name} 没有可用的{semen_type}公牛用于{choice_num}选")
            return

        # 计算平均分配配额
        total_cows = len(cycle_cows)
        from core.matching.equal_allocation_utils import calculate_equal_allocation
        bull_quotas = calculate_equal_allocation(available_bulls, total_cows)

        logger.info(f"{cycle_name} {semen_type}{choice_num}选: {total_cows}头母牛平均分配给{len(available_bulls)}头公牛")
        logger.info(f"平均配额: {bull_quotas}")

        # 记录已使用的配额
        used_quotas = {bull_id: 0 for bull_id in available_bulls}
        skipped_count = 0
        total_cows_for_choice = len(cycle_cows)

        for idx, (_, cow) in enumerate(cycle_cows.iterrows()):
            cow_id = str(cow['cow_id'])
            current_cow = idx + 1

            # 记录进度
            if current_cow % 100 == 0 or current_cow == total_cows_for_choice:
                logger.info(f"{cycle_name} {semen_type}{choice_num}选分配: ({current_cow}/{total_cows_for_choice}头)")
            
            # 获取已分配的公牛
            already_allocated = self._get_cow_allocations(cow_id, semen_type)
            
            # 获取该母牛的有效公牛列表
            valid_bulls_key = f'{semen_type}_valid_bulls'
            valid_bulls = cow.get(valid_bulls_key, None)
            if valid_bulls is not None:
                # 如果是字符串，尝试解析
                if isinstance(valid_bulls, str):
                    try:
                        import ast
                        valid_bulls = ast.literal_eval(valid_bulls)
                    except:
                        valid_bulls = []
                
                # 计算每个公牛的后代得分
                cow_score = cow.get('Combine Index Score', 0)
                for bull in valid_bulls:
                    bull_id = bull['bull_id']
                    bull_score = self.bull_scores.get(bull_id, 0)
                    # 后代得分 = 母牛得分和公牛得分的平均值
                    bull['offspring_score'] = 0.5 * (cow_score + bull_score)
                    bull['bull_score'] = bull_score
                
                # 按后代得分排序（高分优先）
                valid_bulls.sort(key=lambda x: x.get('offspring_score', 0), reverse=True)
                
                # 找一个未分配、有库存、未超配额的公牛
                allocated = False
                for bull_info in valid_bulls:
                    bull_id = bull_info['bull_id']

                    if (bull_id not in already_allocated and
                        bull_id in bull_quotas and
                        used_quotas[bull_id] < bull_quotas[bull_id] and
                        self.bull_inventory.get((bull_id, semen_type), 0) > 0):

                        # 分配成功
                        self._record_allocation(cow_id, bull_id, semen_type, choice_num, bull_info)
                        used_quotas[bull_id] += 1
                        # 不再减库存，1/2/3选是独立的推荐方案
                        # self.bull_inventory[bull_id] -= 1

                        allocated = True
                        break
                        
                if not allocated:
                    logger.debug(f"母牛 {cow_id} 无法分配{semen_type}{choice_num}选")
                    skipped_count += 1
            else:
                # 没有有效公牛列表
                skipped_count += 1
        
        if skipped_count > 0:
            logger.warning(f"{cycle_name} {semen_type}{choice_num}选: {skipped_count}头母牛无法分配")

        # 记录实际分配情况
        actual_allocation = dict(used_quotas)
        logger.info(f"{choice_num}选实际分配: {actual_allocation}")
                    
    def _get_available_bulls_with_ratio(self, semen_type: str) -> Dict[str, float]:
        """获取有库存的公牛及其比例（使用复合键）"""
        bulls_with_stock = {}
        total_stock = 0

        # 直接从复合键库存中筛选
        for (bull_id, bull_semen_type), stock in self.bull_inventory.items():
            if bull_semen_type == semen_type and stock > 0:
                bulls_with_stock[bull_id] = stock
                total_stock += stock

        # 计算比例
        if total_stock > 0:
            return {bull_id: stock / total_stock for bull_id, stock in bulls_with_stock.items()}
        else:
            return {}
            
    def _get_bull_type(self, bull_id: str) -> str:
        """获取公牛类型"""
        bull_row = self.bull_data[self.bull_data['bull_id'] == bull_id]
        if not bull_row.empty:
            bull_series = bull_row.iloc[0]
            # 先尝试 classification，再尝试 semen_type
            if 'classification' in bull_series:
                return bull_series['classification']
            elif 'semen_type' in bull_series:
                return bull_series['semen_type']
        return ''
        
    def _get_cow_allocations(self, cow_id: str, semen_type: str) -> set:
        """获取母牛已分配的公牛"""
        allocated = set()
        for result in self.allocation_results:
            if result['cow_id'] == cow_id and result['semen_type'] == semen_type:
                allocated.add(result['bull_id'])
        return allocated
        
    def _record_allocation(self, cow_id: str, bull_id: str, semen_type: str, 
                          choice_num: int, bull_info: dict):
        """记录分配结果"""
        self.allocation_results.append({
            'cow_id': cow_id,
            'bull_id': bull_id,
            'semen_type': semen_type,
            'choice_num': choice_num,
            'offspring_score': bull_info.get('offspring_score', 0),
            'inbreeding_coeff': bull_info.get('inbreeding_coeff', 0),
            'gene_status': bull_info.get('gene_status', 'Unknown')
        })
        
    def _convert_results_to_dataframe(self) -> pd.DataFrame:
        """将分配结果转换为DataFrame"""
        if not self.allocation_results:
            return pd.DataFrame()
            
        logger.info(f"开始转换分配结果，共 {len(self.allocation_results)} 条分配记录")
            
        # 获取所有母牛的基本信息
        cow_info = {}
        for _, cow in self.recommendations_df.iterrows():
            cow_id = str(cow['cow_id'])
            cow_info[cow_id] = {
                'cow_id': cow_id,
                'group': cow.get('group', ''),
                'Combine Index Score': cow.get('Combine Index Score', 0)
            }
            
        # 按母牛整理分配结果
        allocated_cow_ids = set()  # 记录有分配的母牛ID
        for result in self.allocation_results:
            cow_id = result['cow_id']
            allocated_cow_ids.add(cow_id)
            if cow_id in cow_info:
                key = f"{result['choice_num']}选{result['semen_type']}"
                cow_info[cow_id][key] = result['bull_id']
                # 使用复合键获取剩余库存
                bull_key = (result['bull_id'], result['semen_type'])
                cow_info[cow_id][f"{key}_剩余"] = self.bull_inventory.get(bull_key, 0)
        
        logger.info(f"有分配记录的母牛数量: {len(allocated_cow_ids)}")
        logger.info(f"推荐列表中的母牛总数: {len(cow_info)}")
        
        # 列出没有分配的母牛
        unallocated_cows = set(cow_info.keys()) - allocated_cow_ids
        if unallocated_cows:
            logger.warning(f"以下 {len(unallocated_cows)} 头母牛没有任何分配:")
            for group in self.recommendations_df['group'].unique():
                group_unallocated = [cow_id for cow_id in unallocated_cows 
                                   if cow_info[cow_id]['group'] == group]
                if group_unallocated:
                    logger.warning(f"  {group}: {len(group_unallocated)}头")
                
        # 转换为DataFrame（包含所有母牛）
        result_df = pd.DataFrame(list(cow_info.values()))
        
        logger.info(f"转换完成，结果包含 {len(result_df)} 头母牛")
        
        # 重新排列列
        ordered_columns = ['cow_id', 'group', 'Combine Index Score']
        for i in range(1, 4):
            for semen_type in ['性控', '常规']:
                col = f"{i}选{semen_type}"
                if col in result_df.columns:
                    ordered_columns.append(col)
                    remaining_col = f"{col}_剩余"
                    if remaining_col in result_df.columns:
                        ordered_columns.append(remaining_col)
                        
        # 只保留存在的列
        ordered_columns = [col for col in ordered_columns if col in result_df.columns]
        
        return result_df[ordered_columns]
        
    def save_allocation_result(self, result_df: pd.DataFrame, output_path: Path):
        """保存分配结果"""
        try:
            result_df.to_excel(output_path, index=False)
            logger.info(f"分配结果已保存至: {output_path}")
            return True
        except Exception as e:
            logger.error(f"保存分配结果失败: {e}")
            return False
            
    def get_allocation_summary(self) -> pd.DataFrame:
        """获取分配汇总（使用复合键）"""
        summary = []

        # 重新统计，分别计算每个选择的分配
        # allocation_results 的结构是: {'cow_id', 'bull_id', 'semen_type', 'choice_num', ...}
        # 使用复合键 (bull_id, semen_type) 进行统计
        choice_counts = {}
        for result in self.allocation_results:
            bull_id = result['bull_id']
            semen_type = result['semen_type']  # '常规' 或 '性控'
            choice_num = result['choice_num']  # 1, 2, 或 3

            # 使用复合键
            composite_key = (bull_id, semen_type)

            # 初始化公牛的计数器
            if composite_key not in choice_counts:
                choice_counts[composite_key] = {'1选': 0, '2选': 0, '3选': 0}

            # 增加对应选择的计数
            choice_key = f'{choice_num}选'
            choice_counts[composite_key][choice_key] += 1

        # 从复合键库存中获取每个公牛的信息
        for (bull_id, semen_type), original_count in self.bull_inventory.items():
            # 获取该公牛的分配统计
            composite_key = (bull_id, semen_type)
            bull_counts = choice_counts.get(composite_key, {'1选': 0, '2选': 0, '3选': 0})
            first_choice = bull_counts['1选']
            second_choice = bull_counts['2选']
            third_choice = bull_counts['3选']

            summary.append({
                '公牛号': bull_id,
                '冻精类型': semen_type,
                '原始库存': original_count,
                '1选推荐': first_choice,
                '2选推荐': second_choice,
                '3选推荐': third_choice,
                '剩余库存': original_count,  # 库存不变，因为1/2/3选是独立推荐
                '1选推荐率': f"{(first_choice/original_count*100):.1f}%" if original_count > 0 else "0%"
            })

        return pd.DataFrame(summary)
    
    def _meets_constraints(self, bull_info: dict) -> bool:
        """检查公牛是否满足约束条件"""
        # 检查近交系数
        inbreeding_coeff = bull_info.get('inbreeding_coeff', 0)
        if inbreeding_coeff > self.inbreeding_threshold:
            return False
        
        # 检查隐性基因
        if self.control_defect_genes:
            gene_status = bull_info.get('gene_status', 'Unknown')
            if gene_status == '高风险':
                return False
        
        return True