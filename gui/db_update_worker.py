# gui/db_update_worker.py

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.data.update_manager import run_update_process
import traceback

class DBUpdateWorker(QObject):
    progress = pyqtSignal(int)      # 进度百分比
    message = pyqtSignal(str)       # 消息更新
    finished = pyqtSignal(str)      # 处理完成，返回版本信息
    error = pyqtSignal(str)         # 发生错误

    @pyqtSlot()
    def run(self):
        try:
            # 在这里可以添加更多的进度更新逻辑
            from core.data.update_manager import get_local_db_version_with_time

            run_update_process()

            # 获取更新后的版本号和数据库中的更新时间
            current_version, update_time = get_local_db_version_with_time()

            if current_version and update_time:
                version_info = f"{current_version}#{update_time}"  # 用#分隔版本和时间
            else:
                # 如果获取失败，返回空字符串
                version_info = ""

            self.finished.emit(version_info)
        except Exception as e:
            # 记录详细错误信息到日志
            error_trace = traceback.format_exc()
            import logging
            logging.error(f"数据库更新失败: {error_trace}")
            
            # 只发送简单的错误信息，不包含堆栈跟踪
            self.error.emit(str(e))
