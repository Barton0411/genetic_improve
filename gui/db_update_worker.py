# gui/db_update_worker.py

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.data.update_manager import run_update_process
import traceback

class DBUpdateWorker(QObject):
    progress = pyqtSignal(int)      # 进度百分比
    message = pyqtSignal(str)       # 消息更新
    finished = pyqtSignal()         # 处理完成
    error = pyqtSignal(str)         # 发生错误

    @pyqtSlot()
    def run(self):
        try:
            # 在这里可以添加更多的进度更新逻辑
            run_update_process()
            self.finished.emit()
        except Exception as e:
            # 记录详细错误信息到日志
            error_trace = traceback.format_exc()
            import logging
            logging.error(f"数据库更新失败: {error_trace}")
            
            # 只发送简单的错误信息，不包含堆栈跟踪
            self.error.emit(str(e))
