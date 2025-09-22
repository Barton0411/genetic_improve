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
            # 定义进度回调函数
            def progress_callback(progress, message):
                self.progress.emit(progress)
                self.message.emit(message)

            # 传递进度回调函数到更新过程
            run_update_process(progress_callback=progress_callback)

            # 获取本地数据库的版本号和更新时间（从OSS下载的版本）
            try:
                from core.data.update_manager import get_local_db_version_with_time
                local_version, local_update_time = get_local_db_version_with_time()

                if local_version and local_update_time:
                    version_info = f"{local_version}#{local_update_time}"  # 用#分隔版本和时间
                    import logging
                    logging.info(f"数据库版本: {local_version}, 更新时间: {local_update_time}")
                else:
                    version_info = ""
                    import logging
                    logging.warning("无法获取数据库版本信息")
            except Exception as e:
                import logging
                logging.error(f"获取数据库版本失败: {e}")
                version_info = ""

            self.finished.emit(version_info)
        except Exception as e:
            # 记录详细错误信息到日志
            error_trace = traceback.format_exc()
            import logging
            logging.error(f"数据库更新失败: {error_trace}")
            
            # 只发送简单的错误信息，不包含堆栈跟踪
            self.error.emit(str(e))
