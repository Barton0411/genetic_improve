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

            from utils.file_manager import FileManager
            metadata = FileManager.load_project_metadata(self.project_path)
            if metadata.get("project_type") == "multi_farm_group":
                from core.group_report import GroupExcelReportGenerator

                generator = GroupExcelReportGenerator(
                    self.project_path,
                    service_staff=self.service_staff or "",
                    progress_callback=self.progress_callback,
                )
                success, result = generator.generate()
                self.finished.emit(success, result)
                return

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

            if success:
                try:
                    from core.group_tasks.manual_stage_bridge import (
                        commit_manual_group_excel_if_ready,
                    )

                    commit_manual_group_excel_if_ready(
                        self.project_path,
                        Path(result),
                    )
                except Exception as bridge_error:
                    # 单场报告本身已经成功，不能因为父任务尚不满足完整
                    # 分析口径而把报告改判失败。父任务保持未就绪，用户
                    # 补完缺失分析并重新生成报告后会再次提交。
                    logger.info(
                        "单场Excel已生成，但暂未提交牧场组阶段: %s",
                        bridge_error,
                    )

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
