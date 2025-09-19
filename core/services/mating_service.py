"""
统一的选配服务接口
整合推荐生成、分组管理、分配等功能
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import logging
from datetime import datetime

from ..data import DataLoader
from ..grouping.group_manager import GroupManager
from ..matching.matrix_recommendation_generator import MatrixRecommendationGenerator
from ..matching.cycle_based_matcher import CycleBasedMatcher
from api.data_client import DataAPIClient

logger = logging.getLogger(__name__)


class MatingService:
    """统一的选配服务"""
    
    def __init__(self, base_path: Path, project_name: Optional[str] = None, farm_id: Optional[str] = None):
        """
        初始化选配服务

        Args:
            base_path: 项目基础路径
            project_name: 项目名称
            farm_id: 牧场站号
        """
        self.base_path = Path(base_path)
        self.project_name = project_name
        self.farm_id = farm_id

        # 初始化各个组件
        self.data_loader = DataLoader(base_path, project_name)

        # 设置项目路径
        if project_name:
            project_path = base_path / "genetic_projects" / project_name
        else:
            project_path = base_path

        self.group_manager = GroupManager(project_path)
        self.recommendation_generator = MatrixRecommendationGenerator(project_path)
        self.matcher = CycleBasedMatcher()

        # 数据缓存
        self.data_cache = {}

        # 初始化API客户端
        self.api_client = None
        
    def load_data(self) -> bool:
        """
        加载所有必要的数据
        
        Returns:
            是否成功加载
        """
        try:
            logger.info("开始加载数据...")
            self.data_cache = self.data_loader.load_all_data()
            
            # 验证数据
            issues = self.data_loader.validate_data(self.data_cache)
            if issues:
                logger.warning(f"数据验证发现问题: {issues}")
                
            return True
            
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            return False
    
    def generate_recommendations(self, 
                               inbreeding_threshold: float = 6.25,
                               control_defect_genes: bool = True,
                               progress_callback: Optional[callable] = None) -> pd.DataFrame:
        """
        生成推荐矩阵
        
        Args:
            inbreeding_threshold: 近交系数阈值
            control_defect_genes: 是否控制隐性基因
            progress_callback: 进度回调函数
            
        Returns:
            推荐结果DataFrame
        """
        if not self.data_cache:
            logger.error("数据未加载")
            return pd.DataFrame()
            
        try:
            # 获取在场母牛
            cow_df = self.data_cache.get('cow_complete', pd.DataFrame())
            if cow_df.empty:
                logger.error("没有母牛数据")
                return pd.DataFrame()
                
            available_cows = cow_df[
                (cow_df['是否在场'] == '是') & 
                (cow_df['sex'] == '母')
            ].copy()
            
            if available_cows.empty:
                logger.error("没有在场的母牛")
                return pd.DataFrame()
                
            # 加载其他必要数据
            bull_df = self.data_cache.get('bull_complete', pd.DataFrame())
            inbreeding_df = self.data_cache.get('inbreeding', pd.DataFrame())
            defect_genes_df = self.data_cache.get('defect_genes', pd.DataFrame())
            
            # 设置推荐生成器的参数
            self.recommendation_generator.cow_df = available_cows
            self.recommendation_generator.bull_df = bull_df
            self.recommendation_generator.inbreeding_df = inbreeding_df
            self.recommendation_generator.defect_genes_df = defect_genes_df
            self.recommendation_generator.inbreeding_threshold = inbreeding_threshold
            self.recommendation_generator.control_defect_genes = control_defect_genes
            
            # 生成推荐矩阵
            matrices = self.recommendation_generator.generate_matrices()
            
            # 获取推荐汇总
            recommendations = matrices.get('summary', pd.DataFrame())
            
            return recommendations
            
        except Exception as e:
            logger.error(f"生成推荐失败: {e}")
            return pd.DataFrame()
    
    def perform_grouping(self, 
                        cow_df: pd.DataFrame,
                        strategy_table: Optional[pd.DataFrame] = None,
                        heifer_age_days: int = 420,
                        cycle_days: int = 21) -> pd.DataFrame:
        """
        执行母牛分组
        
        Args:
            cow_df: 母牛数据
            strategy_table: 策略表
            heifer_age_days: 后备牛开配日龄
            cycle_days: 周期天数
            
        Returns:
            包含分组信息的DataFrame
        """
        try:
            # 如果没有提供策略表，尝试从缓存加载
            if strategy_table is None:
                strategy_table = self.data_cache.get('strategy', pd.DataFrame())
                
            # 执行分组
            grouped_df = self.group_manager.group_cows(
                cow_df=cow_df,
                strategy_table=strategy_table,
                heifer_age_days=heifer_age_days,
                cycle_days=cycle_days
            )
            
            return grouped_df
            
        except Exception as e:
            logger.error(f"分组失败: {e}")
            return cow_df
    
    def perform_allocation(self,
                          recommendations_df: pd.DataFrame,
                          selected_groups: List[str],
                          bull_inventory: Dict[str, int],
                          progress_callback: Optional[callable] = None) -> pd.DataFrame:
        """
        执行选配分配
        
        Args:
            recommendations_df: 推荐结果（包含分组信息）
            selected_groups: 选中的分组
            bull_inventory: 公牛库存
            progress_callback: 进度回调
            
        Returns:
            分配结果DataFrame
        """
        try:
            # 设置匹配器数据
            self.matcher.recommendations_df = recommendations_df
            self.matcher.bull_inventory = bull_inventory.copy()
            
            # 执行分配
            allocation_result = self.matcher.perform_allocation(
                selected_groups=selected_groups,
                progress_callback=progress_callback
            )
            
            return allocation_result
            
        except Exception as e:
            logger.error(f"分配失败: {e}")
            return pd.DataFrame()
    
    def execute_complete_mating(self,
                              inbreeding_threshold: float = 6.25,
                              control_defect_genes: bool = True,
                              heifer_age_days: int = 420,
                              cycle_days: int = 21,
                              selected_groups: Optional[List[str]] = None,
                              progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        执行完整的选配流程
        
        Args:
            inbreeding_threshold: 近交系数阈值
            control_defect_genes: 是否控制隐性基因
            heifer_age_days: 后备牛开配日龄
            cycle_days: 周期天数
            selected_groups: 选中的分组（如果为None，选择所有分组）
            progress_callback: 进度回调
            
        Returns:
            包含各阶段结果的字典
        """
        results = {
            'success': False,
            'recommendations': pd.DataFrame(),
            'grouping': pd.DataFrame(),
            'allocation': pd.DataFrame(),
            'errors': []
        }
        
        try:
            # 1. 加载数据
            if not self.data_cache:
                if not self.load_data():
                    results['errors'].append("数据加载失败")
                    return results
            
            # 2. 生成推荐
            if progress_callback:
                progress_callback("正在生成推荐矩阵...", 20)
                
            recommendations = self.generate_recommendations(
                inbreeding_threshold=inbreeding_threshold,
                control_defect_genes=control_defect_genes
            )
            
            if recommendations.empty:
                results['errors'].append("推荐生成失败")
                return results
                
            results['recommendations'] = recommendations
            
            # 3. 执行分组
            if progress_callback:
                progress_callback("正在进行母牛分组...", 40)
                
            grouped_recommendations = self.perform_grouping(
                cow_df=recommendations,
                heifer_age_days=heifer_age_days,
                cycle_days=cycle_days
            )
            
            results['grouping'] = grouped_recommendations
            
            # 4. 确定要分配的分组
            if selected_groups is None:
                # 选择所有分组
                selected_groups = grouped_recommendations['group'].unique().tolist()
            
            # 5. 准备公牛库存
            bull_inventory = self._prepare_bull_inventory()
            
            # 6. 执行分配
            if progress_callback:
                progress_callback("正在执行选配分配...", 60)
                
            allocation_result = self.perform_allocation(
                recommendations_df=grouped_recommendations,
                selected_groups=selected_groups,
                bull_inventory=bull_inventory,
                progress_callback=lambda msg, pct: progress_callback(msg, 60 + int(pct * 0.4))
            )
            
            if allocation_result.empty:
                results['errors'].append("分配失败")
                return results
                
            results['allocation'] = allocation_result
            results['success'] = True
            
            if progress_callback:
                progress_callback("选配完成", 100)
            
            return results
            
        except Exception as e:
            logger.error(f"执行选配流程失败: {e}")
            results['errors'].append(str(e))
            return results
    
    def _prepare_bull_inventory(self) -> Dict[str, int]:
        """
        准备公牛库存信息
        
        Returns:
            公牛库存字典
        """
        bull_df = self.data_cache.get('bull_complete', pd.DataFrame())
        
        if bull_df.empty:
            return {}
        
        inventory = {}
        
        # 检查可能的库存字段名
        inventory_fields = ['支数', 'inventory', '库存', 'stock']
        
        for field in inventory_fields:
            if field in bull_df.columns:
                for _, bull in bull_df.iterrows():
                    bull_id = str(bull['bull_id'])
                    count = int(bull[field]) if pd.notna(bull[field]) else 0
                    inventory[bull_id] = count
                break
        else:
            # 如果没有库存字段，默认每头公牛100支
            logger.warning("未找到库存字段，使用默认库存100")
            for _, bull in bull_df.iterrows():
                bull_id = str(bull['bull_id'])
                inventory[bull_id] = 100
        
        return inventory
    
    def save_results(self, results: Dict[str, Any], output_dir: Path) -> bool:
        """
        保存选配结果
        
        Args:
            results: 选配结果字典
            output_dir: 输出目录
            
        Returns:
            是否成功保存
        """
        try:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存时间戳
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 保存各个结果
            if 'recommendations' in results and not results['recommendations'].empty:
                rec_file = output_dir / f"recommendations_{timestamp}.xlsx"
                results['recommendations'].to_excel(rec_file, index=False)
                logger.info(f"推荐结果已保存: {rec_file}")
            
            if 'allocation' in results and not results['allocation'].empty:
                alloc_file = output_dir / f"allocation_{timestamp}.xlsx"
                results['allocation'].to_excel(alloc_file, index=False)
                logger.info(f"分配结果已保存: {alloc_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"保存结果失败: {e}")
            return False

    def upload_results_to_api(self, results: Dict[str, Any], constraints: Dict[str, Any] = None, notes: str = None) -> Tuple[bool, str]:
        """
        上传选配结果到API服务器

        Args:
            results: 选配结果字典
            constraints: 选配约束条件
            notes: 备注

        Returns:
            Tuple[bool, str]: (成功标志, 消息)
        """
        try:
            # 检查必要参数
            if not self.farm_id:
                return False, "未设置牧场站号"

            if not self.project_name:
                return False, "未设置项目名称"

            # 初始化API客户端
            if not self.api_client:
                self.api_client = DataAPIClient()

            # 准备数据
            allocations = []
            group_summaries = []
            bull_summaries = []
            unallocated_cows = []

            # 处理分配结果
            if 'allocation' in results and not results['allocation'].empty:
                allocation_df = results['allocation']
                for _, row in allocation_df.iterrows():
                    allocations.append({
                        'cow_id': str(row.get('cow_id', '')),
                        'bull_id': str(row.get('bull_id', '')),
                        'choice_num': int(row.get('choice_num', 1)) if pd.notna(row.get('choice_num')) else 1,
                        'semen_type': str(row.get('semen_type', '常规')),
                        'offspring_score': float(row.get('offspring_score', 0)) if pd.notna(row.get('offspring_score')) else 0,
                        'inbreeding_coeff': float(row.get('inbreeding_coeff', 0)) if pd.notna(row.get('inbreeding_coeff')) else 0,
                        'gene_status': str(row.get('gene_status', 'Unknown'))
                    })

            # 处理分组汇总
            if 'grouping' in results and not results['grouping'].empty:
                grouping_df = results['grouping']
                groups = grouping_df['group'].unique()
                for group in groups:
                    group_data = grouping_df[grouping_df['group'] == group]
                    group_summaries.append({
                        'group_name': str(group),
                        'total_cows': len(group_data),
                        'allocated_cows': len(group_data[group_data['bull_id'].notna()]) if 'bull_id' in group_data.columns else 0,
                        'unallocated_cows': len(group_data[group_data['bull_id'].isna()]) if 'bull_id' in group_data.columns else len(group_data)
                    })

            # 准备约束条件
            if not constraints:
                constraints = {
                    'inbreeding_threshold': 6.25,
                    'control_defect_genes': True
                }

            # 上传到API
            success, result_id, message = self.api_client.upload_mating_result(
                farm_id=self.farm_id,
                project_name=self.project_name,
                allocations=allocations,
                group_summaries=group_summaries,
                bull_summaries=bull_summaries,
                unallocated_cows=unallocated_cows,
                constraints=constraints,
                notes=notes
            )

            if success:
                logger.info(f"成功上传选配结果到API, ID: {result_id}")
                return True, f"结果已上传，ID: {result_id}"
            else:
                logger.error(f"上传选配结果失败: {message}")
                return False, message

        except Exception as e:
            logger.error(f"上传选配结果到API失败: {e}")
            return False, str(e)