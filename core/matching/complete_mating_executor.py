"""
完整的个体选配执行器
整合推荐生成、分组、分配全流程
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import logging
from datetime import datetime

from ..grouping.group_manager import GroupManager
from .matrix_recommendation_generator import MatrixRecommendationGenerator
from .cycle_based_matcher import CycleBasedMatcher

logger = logging.getLogger(__name__)


class CompleteMatingExecutor:
    """完整的个体选配执行器"""
    
    def __init__(self, project_path: Path):
        """
        初始化执行器
        
        Args:
            project_path: 项目路径
        """
        self.project_path = Path(project_path)
        
        # 缓存约束数据，避免重复I/O
        self.cached_inbreeding_df = None
        self.cached_bull_data = None
        self.cached_sexed_bulls = None
        self.cached_regular_bulls = None
        self.group_manager = GroupManager(project_path)
        self.recommendation_generator = MatrixRecommendationGenerator(project_path)
        self.matcher = CycleBasedMatcher()
        
    def execute(self,
                bull_inventory: Dict[str, int],
                inbreeding_threshold: float = 6.25,
                control_defect_genes: bool = True,
                heifer_age_days: int = 420,
                cycle_days: int = 21,
                skip_missing_bulls: bool = False,
                progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        执行完整的个体选配流程

        Args:
            bull_inventory: 公牛库存字典
            inbreeding_threshold: 近交系数阈值
            control_defect_genes: 是否控制隐性基因
            heifer_age_days: 后备牛开配日龄
            cycle_days: 周期天数
            skip_missing_bulls: 是否跳过缺失数据的公牛
            progress_callback: 进度回调函数
            
        Returns:
            结果字典，包含成功标志和最终报告路径
        """
        result = {
            'success': False,
            'report_path': None,
            'error': None
        }
        
        try:
            # 步骤1: 加载数据 (10%)
            if progress_callback:
                progress_callback("正在加载数据...", 10)
            
            load_success = self.recommendation_generator.load_data(skip_missing_bulls=skip_missing_bulls)
            error_msg = getattr(self.recommendation_generator, 'last_error', None)
            skipped_bulls = getattr(self.recommendation_generator, 'skipped_bulls', [])

            # 如果有警告信息但加载成功，记录警告
            if load_success and error_msg and error_msg.startswith("警告:"):
                logger.warning(error_msg)
                # 将警告信息添加到结果中
                result['warnings'] = error_msg
                if skipped_bulls:
                    result['skipped_bulls'] = skipped_bulls
                    logger.info(f"跳过 {len(skipped_bulls)} 头缺少数据的公牛")

            # 如果加载失败，抛出异常
            elif not load_success:
                if error_msg:
                    raise Exception(f"加载数据失败:\n{error_msg}")
                else:
                    raise Exception("加载数据失败，请检查必要的文件是否存在")
            
            # 步骤2: 执行分组 (20%)
            if progress_callback:
                progress_callback("正在进行母牛分组...", 20)
            
            # 加载策略表 - 尝试多个可能的位置
            strategy_df = None
            possible_paths = [
                self.project_path / "standardized_data" / "策略表导入模板.xlsx",
                self.project_path / "data" / "策略表导入模板.xlsx",
                self.project_path / "策略表导入模板.xlsx"
            ]
            
            for strategy_file in possible_paths:
                if strategy_file.exists():
                    try:
                        strategy_df = pd.read_excel(strategy_file)
                        logger.info(f"从 {strategy_file} 加载策略表成功")
                        break
                    except Exception as e:
                        logger.warning(f"加载策略表失败 {strategy_file}: {e}")
            
            if strategy_df is None:
                logger.warning("未找到策略表，将使用默认分组策略")
            
            # 创建策略配置
            strategy_config = {
                'params': {
                    'reserve_age': heifer_age_days,
                    'cycle_days': cycle_days,
                    'cycle_months': 1  # 默认值
                },
                'strategy_table': []
            }
            
            # 如果有策略表，解析并添加到配置中
            if strategy_df is not None:
                logger.info(f"策略表列: {list(strategy_df.columns)}")
                for _, row in strategy_df.iterrows():
                    # 使用更安全的方式访问列
                    group_name = None
                    ratio = None
                    
                    # 尝试不同的列名变体
                    for col_name in ['分组', 'group', 'Group']:
                        if col_name in row.index and pd.notna(row[col_name]):
                            group_name = row[col_name]
                            break
                    
                    for col_name in ['分配比例(%)', '分配比例', 'ratio']:
                        if col_name in row.index and pd.notna(row[col_name]):
                            ratio = float(str(row[col_name]).replace('%', ''))
                            break
                    
                    if group_name and ratio:
                        breeding_methods = []
                        for col in ['第1次配种', '第2次配种', '第3次配种', '第4次+配种']:
                            if col in row.index and pd.notna(row[col]):
                                breeding_methods.append(row[col])
                        
                        strategy_config['strategy_table'].append({
                            'group': group_name,
                            'ratio': ratio,
                            'breeding_methods': breeding_methods
                        })
            else:
                # 使用默认策略
                default_methods = ['普通性控', '普通性控', '常规冻精', '常规冻精']
                for group in ['后备牛A', '后备牛B', '后备牛C', '成母牛A', '成母牛B', '成母牛C']:
                    strategy_config['strategy_table'].append({
                        'group': group,
                        'ratio': 33.33,
                        'breeding_methods': default_methods
                    })
            
            # 创建简单的进度回调包装器
            class SimpleProgressWrapper:
                def set_task_info(self, info):
                    logger.info(f"分组任务: {info}")
                def update_info(self, info):
                    logger.info(f"分组信息: {info}")
                def update_progress(self, progress):
                    logger.debug(f"分组进度: {progress}%")
            
            # 对母牛进行分组
            grouped_cows = self.group_manager.apply_temp_strategy(
                strategy=strategy_config,
                progress_callback=SimpleProgressWrapper()
            )
            
            # 更新推荐生成器的母牛数据
            self.recommendation_generator.cow_data = grouped_cows
            
            # 检查分组后的数据
            if 'group' not in grouped_cows.columns:
                raise Exception("分组后的数据缺少 'group' 列")
            
            logger.info(f"分组后母牛数据列: {list(grouped_cows.columns)}")
            logger.info(f"分组后母牛数量: {len(grouped_cows)}")
            logger.info(f"分组统计: {grouped_cows['group'].value_counts().to_dict()}")
            
            # 详细记录每个分组的母牛数量
            logger.info("===== 步骤2完成：分组统计详情 =====")
            for group_name, count in grouped_cows['group'].value_counts().items():
                logger.info(f"  {group_name}: {count}头")
            
            # 保存更新后的分组数据到原文件，以便分组预览能正确显示
            index_file = self.project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
            if index_file.exists():
                try:
                    # 读取原文件
                    original_df = pd.read_excel(index_file)
                    # 更新group列
                    original_df = original_df.drop('group', axis=1, errors='ignore')
                    # 合并新的分组信息
                    original_df = original_df.merge(
                        grouped_cows[['cow_id', 'group']], 
                        on='cow_id', 
                        how='left'
                    )
                    # 保存回文件
                    original_df.to_excel(index_file, index=False)
                    logger.info(f"已更新分组信息到: {index_file}")
                except Exception as e:
                    logger.warning(f"更新分组文件失败: {e}")
            
            # 步骤3: 生成推荐矩阵 (40%)
            if progress_callback:
                progress_callback("正在生成推荐矩阵...", 40)
            
            # 设置参数
            self.recommendation_generator.inbreeding_threshold = inbreeding_threshold / 100.0  # 转换为小数
            self.recommendation_generator.control_defect_genes = control_defect_genes
            
            # 生成矩阵
            matrices = self.recommendation_generator.generate_matrices()
            
            if matrices is None:
                raise Exception("生成推荐矩阵返回 None")
                
            logger.info(f"生成的矩阵类型: {type(matrices)}")
            logger.info(f"矩阵包含的键: {list(matrices.keys()) if isinstance(matrices, dict) else 'Not a dict'}")
            
            # 获取推荐汇总（包含分组信息）
            recommendations_df = matrices.get('推荐汇总', pd.DataFrame())
            
            if recommendations_df.empty:
                raise Exception("生成推荐矩阵失败")
            
            logger.info("===== 步骤3完成：推荐矩阵统计 =====")
            logger.info(f"推荐矩阵母牛数量: {len(recommendations_df)}")
            if 'group' in recommendations_df.columns:
                for group_name, count in recommendations_df['group'].value_counts().items():
                    logger.info(f"  {group_name}: {count}头")
            
            # 保存推荐矩阵
            matrix_path = self.project_path / "analysis_results" / "个体选配推荐矩阵.xlsx"
            self.recommendation_generator.save_matrices(matrices, matrix_path)
            logger.info(f"推荐矩阵已保存至: {matrix_path}")
            
            # 步骤4: 执行分配 (60%)
            if progress_callback:
                progress_callback("正在执行选配分配...", 60)
            
            # 设置匹配器参数
            # 首先加载公牛数据
            bull_data_path = self.project_path / "standardized_data" / "processed_bull_data.xlsx"
            if not self.matcher.load_data(recommendations_df, bull_data_path):
                logger.warning("使用备用方法设置匹配器数据")
                self.matcher.recommendations_df = recommendations_df
                self.matcher.bull_data = self.recommendation_generator.bull_data  # 使用推荐生成器的公牛数据
                
            # 设置其他参数
            self.matcher.bull_inventory = bull_inventory.copy()
            self.matcher.inbreeding_threshold = inbreeding_threshold
            self.matcher.control_defect_genes = control_defect_genes
            
            # 获取所有分组并过滤掉 nan 值
            all_groups = recommendations_df['group'].unique().tolist()
            # 过滤掉 nan 和非字符串类型的分组
            all_groups = [g for g in all_groups if pd.notna(g) and isinstance(g, str)]
            
            logger.info(f"有效分组列表: {all_groups}")
            
            # 执行分配
            allocation_df = self.matcher.perform_allocation(
                selected_groups=all_groups,
                progress_callback=lambda msg, pct: progress_callback(msg, 60 + int(pct * 0.2)) if progress_callback else None
            )
            
            logger.info("===== 步骤4完成：分配结果统计 =====")
            logger.info(f"分配结果母牛数量: {len(allocation_df)}")
            if 'group' in allocation_df.columns:
                for group_name, count in allocation_df['group'].value_counts().items():
                    logger.info(f"  {group_name}: {count}头")
            
            # 步骤5: 生成最终报告 (80%)
            if progress_callback:
                progress_callback("正在生成最终报告...", 80)
            
            # 生成符合要求的个体选配报告
            final_report = self._generate_final_report(
                allocation_df, 
                recommendations_df,
                grouped_cows
            )
            
            logger.info("===== 步骤5完成：最终报告统计 =====")
            logger.info(f"最终报告母牛数量: {len(final_report)}")
            if '分组' in final_report.columns:
                for group_name, count in final_report['分组'].value_counts().items():
                    logger.info(f"  {group_name}: {count}头")
            
            # 步骤6: 保存报告 (90%)
            if progress_callback:
                progress_callback("正在保存报告...", 90)
            
            # 保存最终报告
            report_path = self.project_path / "analysis_results" / "个体选配报告.xlsx"
            report_path.parent.mkdir(exist_ok=True, parents=True)
            
            with pd.ExcelWriter(report_path, engine='openpyxl') as writer:
                final_report.to_excel(writer, sheet_name='选配结果', index=False)
                
            # 同时保存为兼容格式
            compat_path = self.project_path / "analysis_results" / "individual_mating_report.xlsx"
            final_report.to_excel(compat_path, index=False)
            
            if progress_callback:
                progress_callback("选配完成！", 100)
            
            result['success'] = True
            result['report_path'] = report_path
            
        except Exception as e:
            logger.error(f"执行个体选配失败: {e}")
            import traceback
            logger.error(f"错误堆栈:\n{traceback.format_exc()}")
            result['error'] = str(e)
            
        return result
    
    def _preload_constraint_data(self):
        """预加载约束数据，避免重复I/O操作"""
        try:
            # 1. 加载近交系数及隐性基因分析结果
            possible_files = list(self.project_path.glob("**/备选公牛_近交系数及隐性基因分析结果_*.xlsx"))
            if possible_files:
                latest_file = max(possible_files, key=lambda x: x.stat().st_mtime)
                self.cached_inbreeding_df = pd.read_excel(latest_file)
                logger.info(f"已缓存约束数据文件: {latest_file.name}")
            else:
                logger.warning("未找到约束数据文件")
                self.cached_inbreeding_df = pd.DataFrame()
            
            # 2. 加载公牛数据
            bull_file = self.project_path / "standardized_data" / "processed_bull_data.xlsx"
            if bull_file.exists():
                self.cached_bull_data = pd.read_excel(bull_file)
                # 分别缓存性控和常规公牛
                self.cached_sexed_bulls = self.cached_bull_data[self.cached_bull_data['classification'] == '性控'].copy()
                self.cached_regular_bulls = self.cached_bull_data[self.cached_bull_data['classification'] == '常规'].copy()
                logger.info(f"已缓存公牛数据: 性控{len(self.cached_sexed_bulls)}头，常规{len(self.cached_regular_bulls)}头")
            else:
                logger.warning("未找到公牛数据文件")
                self.cached_bull_data = pd.DataFrame()
                self.cached_sexed_bulls = pd.DataFrame()
                self.cached_regular_bulls = pd.DataFrame()
                
        except Exception as e:
            logger.error(f"预加载约束数据失败: {e}")
            # 初始化空的DataFrame防止后续报错
            self.cached_inbreeding_df = pd.DataFrame()
            self.cached_bull_data = pd.DataFrame()
            self.cached_sexed_bulls = pd.DataFrame()
            self.cached_regular_bulls = pd.DataFrame()

    def _generate_breeding_notes(self, cow_id: str, rec_info: pd.Series, semen_type: str, alloc_row: pd.Series = None) -> str:
        """
        生成选配备注信息
        
        Args:
            cow_id: 母牛号
            rec_info: 推荐信息行
            semen_type: 冻精类型 ('性控' 或 '常规')
            alloc_row: 分配结果行（可选）
        
        Returns:
            备注字符串
        """
        # 检查推荐矩阵中的推荐情况
        rec_missing_positions = []
        for i in range(1, 4):
            rec_col = f'推荐{semen_type}冻精{i}选'
            if rec_col in rec_info.index:
                if pd.isna(rec_info[rec_col]) or not str(rec_info[rec_col]).strip():
                    rec_missing_positions.append(i)
        
        # 分析约束过滤情况
        return self._analyze_constraint_filtering(cow_id, semen_type, rec_missing_positions)
    
    def _analyze_constraint_filtering(self, cow_id: str, semen_type: str, rec_missing_positions: List[int]) -> str:
        """
        分析约束过滤情况，生成相应备注
        
        Args:
            cow_id: 母牛号
            semen_type: 冻精类型
            rec_missing_positions: 推荐中缺失的位置
            
        Returns:
            备注字符串
        """
        try:
            # 使用缓存的约束数据
            if self.cached_inbreeding_df is None or self.cached_inbreeding_df.empty:
                if len(rec_missing_positions) == 3:
                    return f"无{semen_type}推荐（缺少约束数据）"
                elif len(rec_missing_positions) > 0:
                    return f"缺少{semen_type}推荐（缺少约束数据）"
                return ""
            
            # 获取该母牛的约束数据
            cow_data = self.cached_inbreeding_df[self.cached_inbreeding_df['母牛号'] == cow_id]
            if cow_data.empty:
                if len(rec_missing_positions) == 3:
                    return f"无{semen_type}推荐（未找到约束数据）"
                elif len(rec_missing_positions) > 0:
                    return f"缺少{semen_type}推荐（未找到约束数据）"
                return ""
            
            # 获取对应类型的公牛（使用缓存数据）
            if semen_type == '性控':
                type_bulls = self.cached_sexed_bulls
            else:
                type_bulls = self.cached_regular_bulls
                
            if type_bulls.empty:
                if len(rec_missing_positions) == 3:
                    return f"无{semen_type}推荐（无对应公牛）"
                elif len(rec_missing_positions) > 0:
                    return f"缺少{semen_type}推荐（无对应公牛）"
                return ""
            
            # 分析每头公牛的约束情况
            constraint_analysis = self._analyze_bull_constraints(cow_data, type_bulls)
            
            # 根据推荐缺失情况生成备注
            if len(rec_missing_positions) == 3:
                # 完全没有推荐
                return self._generate_no_recommendation_note(semen_type, constraint_analysis)
            elif len(rec_missing_positions) > 0:
                # 部分推荐缺失
                return self._generate_partial_recommendation_note(semen_type, rec_missing_positions, constraint_analysis)
            else:
                # 有完整推荐，但可能跳过了更优公牛
                return self._generate_skipped_better_bulls_note(semen_type, constraint_analysis)
                
        except Exception as e:
            logger.warning(f"分析约束过滤时出错: {e}")
            if len(rec_missing_positions) == 3:
                return f"无{semen_type}推荐（分析失败）"
            elif len(rec_missing_positions) > 0:
                return f"缺少{semen_type}推荐（分析失败）"
            return ""
    
    def _analyze_bull_constraints(self, cow_data: pd.DataFrame, type_bulls: pd.DataFrame) -> Dict[str, Dict]:
        """
        分析每头公牛与母牛的约束情况
        
        Returns:
            {bull_id: {'score': float, 'inbreeding': float, 'genes': [list], 'blocked': bool}}
        """
        analysis = {}
        
        for _, bull in type_bulls.iterrows():
            bull_id = str(bull['bull_id'])
            bull_cow_data = cow_data[cow_data['原始备选公牛号'] == bull_id]
            
            if not bull_cow_data.empty:
                row = bull_cow_data.iloc[0]
                
                # 获取公牛得分
                bull_score = bull.get('Index Score', 0) if 'Index Score' in bull else 0
                
                # 检查近交系数
                inbreeding_blocked = False
                inbreeding_value = 0
                inbreeding_str = row.get('后代近交系数', '')
                if pd.notna(inbreeding_str) and str(inbreeding_str).strip():
                    try:
                        inbreeding_value = float(str(inbreeding_str).strip('%')) / 100
                        if inbreeding_value > 0.03125:  # 3.125%
                            inbreeding_blocked = True
                    except (ValueError, TypeError):
                        pass
                
                # 检查隐性基因
                gene_cols = ['HH1', 'HH2', 'HH3', 'HH4', 'HH5', 'HH6', 'BLAD', 'Chondrodysplasia', 
                            'Citrullinemia', 'DUMPS', 'Factor XI', 'CVM', 'Brachyspina', 'Mulefoot', 
                            'Cholesterol deficiency', 'MW']
                
                high_risk_genes = []
                gene_blocked = False
                for gene in gene_cols:
                    if gene in row.index and pd.notna(row[gene]):
                        value = str(row[gene]).strip()
                        if value == '高风险':
                            high_risk_genes.append(gene)
                            gene_blocked = True
                
                analysis[bull_id] = {
                    'score': bull_score,
                    'inbreeding_value': inbreeding_value,
                    'inbreeding_blocked': inbreeding_blocked,
                    'high_risk_genes': high_risk_genes,
                    'gene_blocked': gene_blocked,
                    'blocked': inbreeding_blocked or gene_blocked
                }
        
        return analysis
    
    def _generate_no_recommendation_note(self, semen_type: str, constraint_analysis: Dict) -> str:
        """生成完全没有推荐的备注"""
        blocked_details = []
        
        for bull_id, data in constraint_analysis.items():
            if data['blocked']:
                details = []
                if data['inbreeding_blocked']:
                    details.append(f"与{bull_id}公牛近交系数为{data['inbreeding_value']*100:.2f}%，大于3.125%阈值")
                if data['gene_blocked']:
                    for gene in data['high_risk_genes']:
                        details.append(f"与{bull_id}公牛存在{gene}基因纯合高风险")
                blocked_details.extend(details)
        
        if blocked_details:
            return f"无{semen_type}推荐：{';'.join(blocked_details)}"
        else:
            return f"无{semen_type}推荐（其他约束）"
    
    def _generate_partial_recommendation_note(self, semen_type: str, missing_positions: List[int], constraint_analysis: Dict) -> str:
        """生成部分推荐缺失的备注"""
        if len(missing_positions) == 2:
            prefix = f"缺少{semen_type}{missing_positions[0]}选、{missing_positions[1]}选"
        else:
            prefix = f"缺少{semen_type}{missing_positions[0]}选"
        
        # 找出被阻挡的公牛的具体约束信息
        blocked_details = []
        for bull_id, data in constraint_analysis.items():
            if data['blocked']:
                if data['inbreeding_blocked']:
                    blocked_details.append(f"与{bull_id}公牛近交系数为{data['inbreeding_value']*100:.2f}%，大于3.125%阈值")
                if data['gene_blocked']:
                    for gene in data['high_risk_genes']:
                        blocked_details.append(f"与{bull_id}公牛存在{gene}基因纯合高风险")
        
        if blocked_details:
            return f"{prefix}：{';'.join(blocked_details)}"
        else:
            return f"{prefix}（其他约束）"
    
    def _generate_skipped_better_bulls_note(self, semen_type: str, constraint_analysis: Dict) -> str:
        """生成跳过更优公牛的备注"""
        # 按得分排序，找出被阻挡的高分公牛
        all_bulls = [(bull_id, data) for bull_id, data in constraint_analysis.items()]
        all_bulls.sort(key=lambda x: x[1]['score'], reverse=True)
        
        # 找出前5名中被阻挡的公牛（这些是被跳过的优质公牛）
        skipped_details = []
        for i, (bull_id, data) in enumerate(all_bulls[:5]):  # 检查前5名
            if data['blocked']:
                if data['inbreeding_blocked']:
                    skipped_details.append(f"与{bull_id}公牛近交系数为{data['inbreeding_value']*100:.2f}%，大于3.125%阈值")
                if data['gene_blocked']:
                    for gene in data['high_risk_genes']:
                        skipped_details.append(f"与{bull_id}公牛存在{gene}基因纯合高风险")
        
        if skipped_details:
            return ';'.join(skipped_details)
        
        return ""  # 没有发现被跳过的优质公牛
    
    def _generate_final_report(self, 
                              allocation_df: pd.DataFrame,
                              recommendations_df: pd.DataFrame,
                              grouped_cows: pd.DataFrame) -> pd.DataFrame:
        """
        生成最终的个体选配报告
        
        按照指定的表头格式生成报告
        """
        logger.info(f"开始生成最终报告...")
        logger.info(f"  allocation_df 行数: {len(allocation_df)}")
        logger.info(f"  recommendations_df 行数: {len(recommendations_df)}")
        logger.info(f"  grouped_cows 行数: {len(grouped_cows)}")
        
        # 预加载约束数据，避免重复I/O
        self._preload_constraint_data()
        
        # 创建报告DataFrame
        report_rows = []
        missing_in_grouped = 0
        missing_in_recommendations = 0
        processed_cow_ids = set()
        
        # 首先处理有分配的母牛
        for _, alloc_row in allocation_df.iterrows():
            cow_id = alloc_row['cow_id']
            processed_cow_ids.add(cow_id)
            
            # 获取母牛基础信息
            cow_matches = grouped_cows[grouped_cows['cow_id'] == cow_id]
            if cow_matches.empty:
                logger.warning(f"未找到母牛 {cow_id} 的基础信息")
                missing_in_grouped += 1
                continue
            cow_info = cow_matches.iloc[0]
            
            rec_matches = recommendations_df[recommendations_df['cow_id'] == cow_id]
            if rec_matches.empty:
                logger.warning(f"未找到母牛 {cow_id} 的推荐信息")
                missing_in_recommendations += 1
                continue
            rec_info = rec_matches.iloc[0]
            
            # 构建报告行
            # 安全获取分组值，处理 nan 情况
            group_value = cow_info.get('group', '')
            if pd.isna(group_value) or not isinstance(group_value, str):
                group_value = '未分组'
                
            # 生成备注信息
            sexed_note = self._generate_breeding_notes(cow_id, rec_info, '性控', alloc_row)
            regular_note = self._generate_breeding_notes(cow_id, rec_info, '常规', alloc_row)
            
            report_row = {
                '母牛号': cow_id,
                '分组': group_value,
                '1选性控': alloc_row.get('1选性控', ''),
                '2选性控': alloc_row.get('2选性控', ''),
                '3选性控': alloc_row.get('3选性控', ''),
                '性控备注': sexed_note,
                '1选常规': alloc_row.get('1选常规', ''),
                '2选常规': alloc_row.get('2选常规', ''),
                '3选常规': alloc_row.get('3选常规', ''),
                '常规备注': regular_note,
                '胎次': cow_info.get('lac', ''),
                '本胎次奶厅高峰产量': cow_info.get('peak_milk', ''),
                '305奶量': cow_info.get('milk_305', ''),
                '泌乳天数': cow_info.get('DIM', ''),
                '繁育状态': cow_info.get('repro_status', ''),
                '母牛指数得分': rec_info.get('index_score', ''),
                '品种': cow_info.get('breed', ''),
                '父亲': cow_info.get('sire', ''),
                '外祖父': cow_info.get('mgs', ''),
                '母亲': cow_info.get('dam', ''),
                '外曾外祖父': cow_info.get('mmgs', ''),
                '产犊日期': cow_info.get('calving_date', ''),
                '出生日期': cow_info.get('birth_date', ''),
                '数据提取日期': datetime.now().strftime('%Y-%m-%d'),
                '月龄': self._calculate_age_months(cow_info.get('birth_date')),
                '配次': cow_info.get('services_time', 0)
            }
            
            report_rows.append(report_row)
        
        # 创建DataFrame并按分组排序
        if not report_rows:
            logger.warning("没有生成任何报告行")
            return pd.DataFrame()
            
        logger.info(f"最终报告汇总:")
        logger.info(f"  成功生成的行数: {len(report_rows)}")
        logger.info(f"  在 grouped_cows 中找不到的母牛数: {missing_in_grouped}")
        logger.info(f"  在 recommendations_df 中找不到的母牛数: {missing_in_recommendations}")
        
        # 统计肉牛标记数量
        if len(report_rows) > 0:
            # 安全检查分组值，处理 nan 和非字符串类型
            beef_count = len([r for r in report_rows 
                            if isinstance(r.get('分组'), str) and '（肉牛）' in r.get('分组', '')])
            if beef_count > 0:
                logger.info(f"  带肉牛标记的母牛数: {beef_count}")
            
        report_df = pd.DataFrame(report_rows)
        
        # 检查是否有分组列
        if '分组' not in report_df.columns:
            logger.error(f"报告缺少'分组'列，可用列: {list(report_df.columns)}")
            return report_df
        
        # 定义分组排序顺序
        group_order = [
            '后备牛第1周期+性控', '后备牛第1周期+性控（肉牛）', '后备牛第1周期+非性控', '后备牛第1周期+非性控（肉牛）',
            '后备牛第2周期+性控', '后备牛第2周期+性控（肉牛）', '后备牛第2周期+非性控', '后备牛第2周期+非性控（肉牛）',
            '后备牛第3周期+性控', '后备牛第3周期+性控（肉牛）', '后备牛第3周期+非性控', '后备牛第3周期+非性控（肉牛）',
            '后备牛第4周期+性控', '后备牛第4周期+性控（肉牛）', '后备牛第4周期+非性控', '后备牛第4周期+非性控（肉牛）',
            '成母牛未孕牛+性控', '成母牛未孕牛+性控（肉牛）', '成母牛未孕牛+非性控', '成母牛未孕牛+非性控（肉牛）',
            '后备牛难孕牛+非性控', '后备牛难孕牛+非性控（肉牛）', '成母牛难孕牛+非性控', '成母牛难孕牛+非性控（肉牛）',
            '后备牛已孕牛+非性控', '后备牛已孕牛+非性控（肉牛）', '成母牛已孕牛+非性控', '成母牛已孕牛+非性控（肉牛）',
            '未分组'  # 添加未分组到最后
        ]
        
        # 创建分组排序映射
        group_sort_map = {group: i for i, group in enumerate(group_order)}
        report_df['group_sort'] = report_df['分组'].map(group_sort_map).fillna(999)
        
        # 排序并删除辅助列
        report_df = report_df.sort_values(['group_sort', '母牛号'])
        report_df = report_df.drop('group_sort', axis=1)
        
        return report_df
    
    def _calculate_age_months(self, birth_date):
        """计算月龄"""
        if pd.isna(birth_date):
            return None
        try:
            birth = pd.to_datetime(birth_date)
            today = datetime.now()
            months = (today.year - birth.year) * 12 + (today.month - birth.month)
            return months
        except:
            return None