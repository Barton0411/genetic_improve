"""
选配推荐生成后台工作者
"""

from PyQt6.QtCore import QThread, pyqtSignal
from pathlib import Path
import logging
from core.matching.recommendation_generator import RecommendationGenerator

logger = logging.getLogger(__name__)

class RecommendationWorker(QThread):
    """选配推荐生成后台工作者"""
    
    # 信号定义
    progress_updated = pyqtSignal(str, int)  # 进度信息, 百分比
    recommendation_completed = pyqtSignal(Path)    # 推荐完成，传递报告文件路径
    error_occurred = pyqtSignal(str)         # 错误信息
    
    def __init__(self, project_path: Path):
        super().__init__()
        self.project_path = project_path
        self.generator = RecommendationGenerator()
        
    def run(self):
        """执行推荐生成任务"""
        try:
            # 步骤1: 数据加载
            self.progress_updated.emit("正在加载数据文件...", 10)
            if not self.generator.load_data(self.project_path):
                self.error_occurred.emit("数据加载失败，请检查必要文件是否存在")
                return
            
            # 步骤2: 生成推荐
            self.progress_updated.emit("正在生成选配推荐...", 20)
            
            def progress_callback(message, progress):
                # 将20-90的进度范围映射给推荐生成过程
                actual_progress = 20 + int(progress * 0.7)
                self.progress_updated.emit(message, actual_progress)
            
            recommendations_df = self.generator.generate_recommendations(progress_callback)
            
            # 步骤3: 保存结果
            self.progress_updated.emit("正在保存推荐报告...", 95)
            output_file = self.project_path / "analysis_results" / "individual_mating_report.xlsx"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            if self.generator.save_recommendations(recommendations_df, output_file):
                self.progress_updated.emit("选配推荐生成完成！", 100)
                self.recommendation_completed.emit(output_file)
            else:
                self.error_occurred.emit("保存推荐报告失败")
            
        except Exception as e:
            logger.error(f"选配推荐生成失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.error_occurred.emit(f"选配推荐生成失败: {str(e)}") 