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
            run_update_process()

            # 获取云端数据库的版本号和更新时间
            try:
                from api.data_client import get_cloud_db_version_with_time
                cloud_version, cloud_update_time = get_cloud_db_version_with_time()

                if cloud_version and cloud_update_time:
                    version_info = f"{cloud_version}#{cloud_update_time}"  # 用#分隔版本和时间
                    import logging
                    logging.info(f"获取到云端数据库版本: {cloud_version}, 更新时间: {cloud_update_time}")
                else:
                    # 如果云端获取失败，尝试获取本地版本作为备用
                    from core.data.update_manager import get_local_db_version_with_time
                    local_version, local_update_time = get_local_db_version_with_time()
                    if local_version and local_update_time:
                        version_info = f"{local_version}#{local_update_time}"
                        import logging
                        logging.warning(f"无法获取云端版本，使用本地版本: {local_version}")
                    else:
                        version_info = ""
            except Exception as e:
                # 如果获取云端版本失败，使用本地版本
                import logging
                logging.error(f"获取云端数据库版本失败: {e}")
                from core.data.update_manager import get_local_db_version_with_time
                local_version, local_update_time = get_local_db_version_with_time()
                if local_version and local_update_time:
                    version_info = f"{local_version}#{local_update_time}"
                else:
                    version_info = ""

            self.finished.emit(version_info)
        except Exception as e:
            # 记录详细错误信息到日志
            error_trace = traceback.format_exc()
            import logging
            logging.error(f"数据库更新失败: {error_trace}")
            
            # 只发送简单的错误信息，不包含堆栈跟踪
            self.error.emit(str(e))
