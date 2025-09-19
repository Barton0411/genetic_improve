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
            from core.data.update_manager import get_local_db_version
            from datetime import datetime

            run_update_process()

            # 获取更新后的版本号
            current_version = get_local_db_version()
            update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            version_info = f"{current_version}#{update_time}"  # 用#分隔版本和时间

            self.finished.emit(version_info)
        except Exception as e:
            # 记录详细错误信息到日志
            error_trace = traceback.format_exc()
            import logging
            logging.error(f"数据库更新失败: {error_trace}")
            
            # 只发送简单的错误信息，不包含堆栈跟踪
            self.error.emit(str(e))
