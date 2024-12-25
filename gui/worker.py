# gui/worker.py

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from pathlib import Path
from core.data.uploader import upload_and_standardize_cow_data
from core.data.uploader import upload_and_standardize_genomic_data
import traceback

class CowDataWorker(QObject):
    progress = pyqtSignal(int)      # 进度百分比
    message = pyqtSignal(str)       # 消息更新
    finished = pyqtSignal(Path)     # 处理完成，返回文件路径
    error = pyqtSignal(str)         # 发生错误

    def __init__(self, input_files, project_path):
        super().__init__()
        self.input_files = input_files
        self.project_path = project_path

    @pyqtSlot()
    def run(self):
        try:
            # 上传并标准化数据，传递进度回调
            standardized_path = upload_and_standardize_cow_data(
                self.input_files, 
                self.project_path, 
                progress_callback=self.progress.emit  # 传递 emit 方法
            )
            self.finished.emit(standardized_path)
        except Exception as e:
            error_trace = traceback.format_exc()
            self.error.emit(str(e) + "\n" + error_trace)

class GenomicDataWorker(QObject):
    progress = pyqtSignal(int)      # 进度百分比
    message = pyqtSignal(str)       # 消息更新
    finished = pyqtSignal(Path)     # 处理完成，返回文件路径
    error = pyqtSignal(str)         # 发生错误

    def __init__(self, input_files, project_path):
        super().__init__()
        self.input_files = input_files
        self.project_path = project_path

    @pyqtSlot()
    def run(self):
        try:
            # 上传并标准化基因组检测数据，传递进度回调
            standardized_path = upload_and_standardize_genomic_data(
                self.input_files, 
                self.project_path, 
                progress_callback=self.progress.emit  # 传递 emit 方法
            )
            self.finished.emit(standardized_path)
        except Exception as e:
            error_trace = traceback.format_exc()
            self.error.emit(str(e) + "\n" + error_trace)