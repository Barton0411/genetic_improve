"""
个体选配后台工作者
"""

from PyQt6.QtCore import QThread, pyqtSignal
from pathlib import Path
import logging
from typing import Dict, List, Optional
from core.matching.individual_matcher import IndividualMatcher

logger = logging.getLogger(__name__)

class MatchingWorker(QThread):
    """个体选配后台工作者"""
    
    # 信号定义
    progress_updated = pyqtSignal(str, int)  # 进度信息, 百分比
    matching_completed = pyqtSignal(Path)    # 选配完成，传递结果文件路径
    error_occurred = pyqtSignal(str)         # 错误信息
    
    def __init__(self, project_path: Path, selected_groups: List[str], 
                 semen_counts: Dict[str, int], inbreeding_threshold: float,
                 control_defect_genes: bool):
        super().__init__()
        self.project_path = project_path
        self.selected_groups = selected_groups
        self.semen_counts = semen_counts
        self.inbreeding_threshold = inbreeding_threshold
        self.control_defect_genes = control_defect_genes
        self.matcher = IndividualMatcher()
        
    def run(self):
        """执行个体选配任务"""
        try:
            # 步骤1: 数据加载
            self.progress_updated.emit("正在加载数据文件...", 10)
            if not self.matcher.load_data(self.project_path):
                self.error_occurred.emit("数据加载失败，请检查必要文件是否存在")
                return
            
            # 步骤2: 参数设置
            self.progress_updated.emit("正在设置选配参数...", 20)
            self.matcher.set_parameters(
                self.semen_counts,
                self.inbreeding_threshold,
                self.control_defect_genes
            )
            
            # 步骤3: 执行选配
            self.progress_updated.emit("正在执行个体选配算法...", 30)
            result_df = self.matcher.perform_matching(self.selected_groups)
            
            # 步骤4: 生成选配表
            self.progress_updated.emit("正在生成选配结果表...", 70)
            
            # 加载原始母牛指数数据，添加选配结果列
            index_file = self.project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
            if not index_file.exists():
                self.error_occurred.emit("未找到母牛指数文件")
                return
            
            import pandas as pd
            base_data = pd.read_excel(index_file)
            
            # 只保留在场母牛
            base_data = base_data[
                (base_data['sex'] == '母') & 
                (base_data['是否在场'] == '是')
            ].copy()
            
            # 合并选配结果
            final_result = pd.merge(
                base_data,
                result_df[['cow_id', '性控1选', '性控2选', '性控3选', '常规1选', '常规2选', '常规3选']],
                on='cow_id',
                how='left'
            )
            
            # 步骤5: 保存结果
            self.progress_updated.emit("正在保存选配结果...", 90)
            output_file = self.project_path / "analysis_results" / "individual_matching_results.xlsx"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            final_result.to_excel(output_file, index=False)
            
            self.progress_updated.emit("个体选配完成！", 100)
            self.matching_completed.emit(output_file)
            
        except Exception as e:
            logger.error(f"个体选配失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.error_occurred.emit(f"个体选配失败: {str(e)}") 