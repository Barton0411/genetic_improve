# gui/worker.py

from PyQt6.QtCore import QThread, QObject, pyqtSignal, pyqtSlot
from pathlib import Path
import traceback
import time
import datetime
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from PyQt6.QtWidgets import QMainWindow

from core.data.update_manager import (
    LOCAL_DB_PATH,
    CLOUD_DB_USER,
    CLOUD_DB_PASSWORD,
    CLOUD_DB_HOST,
    CLOUD_DB_PORT,
    CLOUD_DB_NAME
)
from core.data.uploader import (
    upload_and_standardize_cow_data,
    upload_and_standardize_genomic_data
)
from gui.progress import ProgressDialog

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

# gui/worker.py
class TraitsCalculationWorker(QObject):
    progress = pyqtSignal(int)       # 总体进度百分比
    step_progress = pyqtSignal(int)  # 当前步骤进度百分比
    message = pyqtSignal(str)        # 消息更新
    task_info = pyqtSignal(str, int, int)  # 任务信息更新
    speed_info = pyqtSignal(str, str)  # 速度信息更新
    finished = pyqtSignal()          # 处理完成
    error = pyqtSignal(str)          # 发生错误

    def __init__(self, key_traits_page, detail_path, yearly_path, pedigree_path, genomic_path=None):
        super().__init__()
        self.key_traits_page = key_traits_page
        self.detail_path = detail_path
        self.yearly_path = yearly_path
        self.pedigree_path = pedigree_path
        self.genomic_path = genomic_path
        self.total_steps = 4 if genomic_path else 3
        self.start_time = time.time()
        self.last_progress = 0
        self.processed_items = 0
        self.cancelled = False

    def update_progress(self, step, step_progress):
        # 计算总体进度
        total_progress = ((step - 1) * 100 + step_progress) // self.total_steps
        self.progress.emit(total_progress)
        self.step_progress.emit(step_progress)
        
        # 更新处理项数和速度信息
        self.processed_items += 1
        self.last_progress = total_progress
        self.update_speed_info()

    def update_speed_info(self):
        current_time = time.time()
        elapsed_time = current_time - self.start_time
        
        if elapsed_time > 0:
            # 计算每个进度点的平均耗时
            avg_time_per_progress = elapsed_time / max(self.last_progress, 1)
            
            # 计算剩余进度点
            remaining_progress = 100 - self.last_progress
            
            # 估算剩余时间
            estimated_remaining_time = avg_time_per_progress * remaining_progress
            
            # 计算处理速度
            items_per_second = self.processed_items / elapsed_time
            
            # 格式化剩余时间
            if estimated_remaining_time < 60:
                remaining_time = f"{int(estimated_remaining_time)}秒"
            else:
                minutes = int(estimated_remaining_time // 60)
                seconds = int(estimated_remaining_time % 60)
                remaining_time = f"{minutes}分{seconds}秒"
            
            speed = f"{items_per_second:.1f}项/秒"
            self.speed_info.emit(remaining_time, speed)
        else:
            self.speed_info.emit("计算中...", "计算中...")
   
    @pyqtSlot()
    def run(self):
        try:
            self.start_time = time.time()
            
            # 获取主窗口实例
            parent = self.key_traits_page.parent()
            while parent and not isinstance(parent, QMainWindow):
                parent = parent.parent()
            
            if not parent:
                self.error.emit("无法获取主窗口")
                return
            
            # 核心计算逻辑
            success, message = self.key_traits_page.perform_traits_calculation(
                parent,  # 传递找到的主窗口
                progress_callback=lambda p: self.update_progress(1, p),
                task_info_callback=self.task_info.emit
            )
            
            if success:
                self.finished.emit()
            else:
                self.error.emit(message)

        except Exception as e:
            error_trace = traceback.format_exc()
            self.error.emit(str(e) + "\n" + error_trace)

