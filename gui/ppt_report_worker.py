"""
PPT报告生成Worker线程
用于在后台生成PPT报告，避免UI阻塞
"""

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class PPTReportWorker(QObject):
    """PPT报告生成Worker"""

    # 信号定义
    progress = pyqtSignal(int, str)  # 进度百分比，消息
    finished = pyqtSignal(bool, str)  # 成功标志，文件路径或错误消息

    def __init__(self, project_path: str, farm_name: str = None, reporter_name: str = None):
        """
        初始化Worker

        Args:
            project_path: 项目路径
            farm_name: 牧场名称
            reporter_name: 汇报人
        """
        super().__init__()
        self.project_path = Path(project_path)
        self.farm_name = farm_name
        self.reporter_name = reporter_name
        self._is_cancelled = False

    def cancel(self):
        """标记取消"""
        self._is_cancelled = True

    def progress_callback(self, message: str, progress_value: int):
        """
        进度回调函数

        Args:
            message: 进度消息
            progress_value: 进度值 0-100
        """
        if not self._is_cancelled:
            self.progress.emit(progress_value, message)

    @pyqtSlot()
    def run(self):
        """执行PPT报告生成任务"""
        try:
            if self._is_cancelled:
                return

            logger.info(f"开始生成PPT报告: {self.project_path}")

            # 导入生成器
            from core.ppt_report import ExcelBasedPPTGenerator

            # 创建生成器
            generator = ExcelBasedPPTGenerator(
                project_path=self.project_path,
                farm_name=self.farm_name,
                reporter_name=self.reporter_name
            )

            if self._is_cancelled:
                return

            # 执行生成
            success = generator.generate_ppt(self.progress_callback)

            if self._is_cancelled:
                return

            # 发送完成信号
            if success:
                output_path = str(generator.last_output_path) if generator.last_output_path else ""
                self.finished.emit(True, output_path)
                logger.info(f"PPT报告生成成功: {output_path}")
            else:
                self.finished.emit(False, "PPT生成失败")
                logger.error("PPT报告生成失败")

        except Exception as e:
            if not self._is_cancelled:
                error_msg = f"生成PPT报告时发生异常: {str(e)}"
                logger.error(error_msg, exc_info=True)
                self.finished.emit(False, error_msg)
