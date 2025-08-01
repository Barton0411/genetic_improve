"""
简化版选配推荐生成工作线程
"""

from PyQt6.QtCore import QThread, pyqtSignal
from pathlib import Path
import logging
from core.matching.simple_recommendation_generator import SimpleRecommendationGenerator

logger = logging.getLogger(__name__)

class SimpleRecommendationWorker(QThread):
    """简化版推荐生成工作线程"""
    
    # 信号定义
    progress_updated = pyqtSignal(str, int)  # 进度信息, 百分比
    recommendation_completed = pyqtSignal(Path)    # 推荐完成，传递报告文件路径
    error_occurred = pyqtSignal(str)         # 错误信息
    
    def __init__(self, project_path: Path):
        super().__init__()
        self.project_path = project_path
        self.generator = SimpleRecommendationGenerator()
        
    def run(self):
        """执行推荐生成任务"""
        try:
            # 更新进度
            self.progress_updated.emit("正在加载数据...", 10)
            
            # 生成推荐
            self.progress_updated.emit("正在生成选配推荐...", 50)
            
            success = self.generator.generate_recommendations(self.project_path)
            
            if success:
                # 推荐完成
                self.progress_updated.emit("推荐生成完成！", 100)
                output_file = self.project_path / "analysis_results" / "individual_mating_report.xlsx"
                self.recommendation_completed.emit(output_file)
            else:
                self.error_occurred.emit("生成推荐失败，请检查日志")
                
        except Exception as e:
            logger.error(f"推荐生成异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.error_occurred.emit(f"生成推荐时发生错误: {str(e)}")