"""
Excel报告生成Worker线程
用于在后台生成Excel报告，避免UI阻塞
"""

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ExcelReportWorker(QObject):
    """Excel报告生成Worker"""

    # 信号定义
    progress = pyqtSignal(int, str)  # 进度百分比，消息
    finished = pyqtSignal(bool, str)  # 成功标志，结果路径或错误消息

    def __init__(self, project_path: str, service_staff: str = None):
        """
        初始化Worker

        Args:
            project_path: 项目路径
            service_staff: 牧场服务人员
        """
        super().__init__()
        self.project_path = Path(project_path)
        self.service_staff = service_staff

    def progress_callback(self, progress_value: int, message: str):
        """
        进度回调函数

        Args:
            progress_value: 进度值 0-100
            message: 进度消息
        """
        self.progress.emit(progress_value, message)

    @pyqtSlot()
    def run(self):
        """执行报告生成任务"""
        try:
            logger.info(f"开始生成Excel报告: {self.project_path}")

            # 导入生成器
            from core.excel_report import ExcelReportGenerator

            # 创建生成器，传入进度回调
            generator = ExcelReportGenerator(
                self.project_path,
                self.service_staff,
                progress_callback=self.progress_callback
            )

            # 执行生成
            success, result = generator.generate()

            # 发送完成信号
            self.finished.emit(success, result)

            if success:
                logger.info(f"Excel报告生成成功: {result}")
            else:
                logger.error(f"Excel报告生成失败: {result}")

        except Exception as e:
            error_msg = f"生成Excel报告时发生异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.finished.emit(False, error_msg)
