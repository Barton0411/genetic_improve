"""
选配推荐生成后台工作者
"""

from PyQt6.QtCore import QThread, pyqtSignal
from pathlib import Path
import logging
from core.matching.simple_recommendation_generator import SimpleRecommendationGenerator
from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator

logger = logging.getLogger(__name__)

class RecommendationWorker(QThread):
    """选配推荐生成后台工作者"""
    
    # 信号定义
    progress_updated = pyqtSignal(str, int)  # 进度信息, 百分比
    recommendation_completed = pyqtSignal(Path)    # 推荐完成，传递报告文件路径
    error_occurred = pyqtSignal(str)         # 错误信息
    prerequisites_needed = pyqtSignal(str)  # 需要前置条件
    
    def __init__(self, project_path: Path):
        super().__init__()
        self.project_path = project_path
        self.matrix_generator = MatrixRecommendationGenerator(project_path)
        self.simple_generator = SimpleRecommendationGenerator()
        
    def run(self):
        """执行推荐生成任务"""
        try:
            # 更新进度
            self.progress_updated.emit("正在加载数据...", 10)
            
            # 使用矩阵生成器
            if not self.matrix_generator.load_data():
                error_msg = (
                    "数据加载失败！\n\n"
                    "可能的原因：\n"
                    "1. 缺少母牛育种指数数据 - 请先进行「母牛育种指数计算」\n"
                    "2. 缺少公牛育种指数数据 - 请先进行「公牛育种指数计算」\n"
                    "3. 缺少近交系数和隐性基因数据 - 请先进行「备选公牛近交和隐性基因分析」\n"
                    "4. 必要的数据文件不存在或格式不正确\n\n"
                    "请按顺序完成以上计算后再试。"
                )
                self.error_occurred.emit(error_msg)
                return
            
            # 生成配对矩阵
            self.progress_updated.emit("正在生成配对矩阵...", 30)
            matrices = self.matrix_generator.generate_matrices()
            
            # 保存矩阵结果
            self.progress_updated.emit("正在保存配对矩阵...", 70)
            output_file = self.project_path / "analysis_results" / "individual_mating_matrices.xlsx"
            if self.matrix_generator.save_matrices(matrices, output_file):
                # 同时保存兼容格式的推荐汇总
                self.progress_updated.emit("正在保存推荐汇总...", 90)
                summary_file = self.project_path / "analysis_results" / "individual_mating_report.xlsx"
                matrices['推荐汇总'].to_excel(summary_file, index=False)
                
                # 推荐完成
                self.progress_updated.emit("选配推荐生成完成！", 100)
                self.recommendation_completed.emit(output_file)
            else:
                self.error_occurred.emit("保存推荐结果失败")
                
        except Exception as e:
            logger.error(f"选配推荐生成失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.error_occurred.emit(f"选配推荐生成失败: {str(e)}") 