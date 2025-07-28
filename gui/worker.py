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
        print(f"[DEBUG-WORKER-INIT] CowDataWorker初始化: input_files={input_files}, project_path={project_path}")

    def progress_callback(self, progress_value, message=None):
        """统一的进度回调函数，同时处理进度值和消息"""
        self.progress.emit(progress_value)
        if message:
            self.message.emit(message)

    @pyqtSlot()
    def run(self):
        import logging
        import traceback
        print("[DEBUG-WORKER-1] CowDataWorker开始运行")
        
        # 配置日志
        try:
            log_file = self.project_path / "worker_cow_data.log"
            logging.basicConfig(
                filename=log_file,
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s'
            )
            print(f"[DEBUG-WORKER-2] 日志文件配置在: {log_file}")
        except Exception as e:
            print(f"[DEBUG-WORKER-ERROR] 配置日志文件时出错: {e}")
        
        try:
            print("[DEBUG-WORKER-3] 开始上传并标准化母牛数据")
            logging.info(f"开始上传并标准化母牛数据，项目路径: {self.project_path}")
            logging.info(f"输入文件: {self.input_files}")
            
            # 检查项目路径是否存在
            if not self.project_path.exists():
                error_msg = f"项目路径不存在: {self.project_path}"
                print(f"[DEBUG-WORKER-ERROR] {error_msg}")
                logging.error(error_msg)
                self.error.emit(error_msg)
                return
                
            # 检查输入文件是否存在
            if not self.input_files or not self.input_files[0].exists():
                error_msg = f"输入文件不存在或无效: {self.input_files}"
                print(f"[DEBUG-WORKER-ERROR] {error_msg}")
                logging.error(error_msg)
                self.error.emit(error_msg)
                return
            
            # 记录文件信息
            print("[DEBUG-WORKER-4] 检查文件信息")
            file_info = f"文件大小: {self.input_files[0].stat().st_size} 字节"
            print(f"[DEBUG-WORKER-5] {file_info}")
            logging.info(file_info)
            self.message.emit(f"处理文件: {self.input_files[0].name}")
            self.message.emit(file_info)
            
            # 导入上传函数
            print("[DEBUG-WORKER-6] 导入upload_and_standardize_cow_data函数")
            from core.data.uploader import upload_and_standardize_cow_data
            
            # 上传并标准化数据，传递进度回调
            print("[DEBUG-WORKER-7] 调用upload_and_standardize_cow_data函数")
            standardized_path = upload_and_standardize_cow_data(
                self.input_files, 
                self.project_path, 
                progress_callback=self.progress_callback  # 使用新的回调函数
            )
            
            print(f"[DEBUG-WORKER-8] 处理完成，标准化文件路径: {standardized_path}")
            logging.info(f"处理完成，标准化文件路径: {standardized_path}")
            self.finished.emit(standardized_path)
            print("[DEBUG-WORKER-9] 发送finished信号，工作线程结束")
            
        except Exception as e:
            error_trace = traceback.format_exc()
            error_msg = f"处理母牛数据时发生错误: {str(e)}"
            print(f"[DEBUG-WORKER-ERROR] {error_msg}")
            print(error_trace)
            logging.error(error_msg)
            logging.error(error_trace)
            self.error.emit(f"{error_msg}\n\n详细错误信息:\n{error_trace}")

class GenomicDataWorker(QObject):
    progress = pyqtSignal(int)      # 进度百分比
    message = pyqtSignal(str)       # 消息更新
    finished = pyqtSignal(Path)     # 处理完成，返回文件路径
    error = pyqtSignal(str)         # 发生错误

    def __init__(self, input_files, project_path):
        super().__init__()
        self.input_files = input_files
        self.project_path = project_path

    def progress_callback(self, progress_value, message=None):
        """进度回调函数，发送进度值和对应的消息"""
        # 发送进度值
        if progress_value is not None:
            self.progress.emit(progress_value)
        
        # 处理消息
        if message is not None:
            self.message.emit(message)
        else:
            # 如果没有提供消息，根据进度值生成默认消息
            if progress_value is not None:
                if progress_value == 5:
                    self.message.emit("开始处理基因组检测数据...")
                elif progress_value >= 10 and progress_value < 70:
                    self.message.emit(f"正在处理数据文件... ({progress_value}%)")
                elif progress_value == 75:
                    self.message.emit("正在合并处理结果...")
                elif progress_value == 100:
                    self.message.emit("基因组数据处理完成！")

    @pyqtSlot()
    def run(self):
        try:
            # 上传并标准化基因组检测数据，传递进度回调
            standardized_path = upload_and_standardize_genomic_data(
                self.input_files, 
                self.project_path, 
                progress_callback=self.progress_callback  # 使用回调方法
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

    def __init__(self, cow_key_traits_page, detail_path, yearly_path, pedigree_path, genomic_path=None):
        super().__init__()
        self.cow_key_traits_page = cow_key_traits_page
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

    def traits_progress_callback(self, progress_value, message=None):
        """用于 TraitsCalculation 的进度回调函数"""
        if progress_value is not None:
            self.progress.emit(progress_value)
        if message is not None:
            self.message.emit(message)

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
            parent = self.cow_key_traits_page.parent()
            while parent and not isinstance(parent, QMainWindow):
                parent = parent.parent()
            
            if not parent:
                self.error.emit("无法获取主窗口")
                return
            
            # 核心计算逻辑
            success, message = self.cow_key_traits_page.perform_cow_traits_calculation(
                parent,  # 传递找到的主窗口
                progress_callback=self.traits_progress_callback,  # 使用新的回调函数
                task_info_callback=self.task_info.emit
            )
            
            if success:
                self.finished.emit()
            else:
                self.error.emit(message)

        except Exception as e:
            error_trace = traceback.format_exc()
            self.error.emit(str(e) + "\n" + error_trace)

class BreedingDataWorker(QObject):
    progress = pyqtSignal(int)      # 进度百分比
    message = pyqtSignal(str)       # 消息更新
    finished = pyqtSignal(Path)     # 处理完成，返回文件路径
    error = pyqtSignal(str)         # 发生错误

    def __init__(self, input_files, project_path):
        super().__init__()
        self.input_files = input_files
        self.project_path = project_path
        print(f"[DEBUG-BREEDING-WORKER-INIT] BreedingDataWorker初始化: input_files={input_files}, project_path={project_path}")

    def progress_callback(self, progress_value, message=None):
        """统一的进度回调函数，同时处理进度值和消息"""
        print(f"[DEBUG-BREEDING-WORKER-PROGRESS] 进度: {progress_value}%, 消息: {message}")
        self.progress.emit(progress_value)
        if message:
            self.message.emit(message)

    @pyqtSlot()
    def run(self):
        import logging
        import traceback
        print("[DEBUG-BREEDING-WORKER-1] BreedingDataWorker开始运行")
        
        # 配置日志
        try:
            log_file = self.project_path / "breeding_worker.log"
            logging.basicConfig(
                filename=log_file,
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                force=True
            )
            print(f"[DEBUG-BREEDING-WORKER-2] 日志文件配置在: {log_file}")
        except Exception as e:
            print(f"[DEBUG-BREEDING-WORKER-ERROR] 配置日志文件时出错: {e}")
        
        try:
            print("[DEBUG-BREEDING-WORKER-3] 开始上传并标准化配种记录")
            logging.info(f"开始上传并标准化配种记录，项目路径: {self.project_path}")
            logging.info(f"输入文件: {self.input_files}")
            
            # 检查项目路径是否存在
            if not self.project_path.exists():
                error_msg = f"项目路径不存在: {self.project_path}"
                print(f"[DEBUG-BREEDING-WORKER-ERROR] {error_msg}")
                logging.error(error_msg)
                self.error.emit(error_msg)
                return
                
            # 检查输入文件是否存在
            if not self.input_files or not self.input_files[0].exists():
                error_msg = f"输入文件不存在或无效: {self.input_files}"
                print(f"[DEBUG-BREEDING-WORKER-ERROR] {error_msg}")
                logging.error(error_msg)
                self.error.emit(error_msg)
                return
            
            # 检查母牛数据文件是否存在
            cow_data_file = self.project_path / "standardized_data" / "processed_cow_data.xlsx"
            if not cow_data_file.exists():
                error_msg = "请先上传并处理母牛数据，再上传配种记录"
                print(f"[DEBUG-BREEDING-WORKER-ERROR] {error_msg}")
                logging.error(error_msg)
                self.error.emit(error_msg)
                return
            
            # 记录文件信息
            print("[DEBUG-BREEDING-WORKER-4] 检查文件信息")
            file_info = f"文件大小: {self.input_files[0].stat().st_size} 字节"
            print(f"[DEBUG-BREEDING-WORKER-5] {file_info}")
            logging.info(file_info)
            self.message.emit(f"处理文件: {self.input_files[0].name}")
            self.message.emit(file_info)
            
            # 导入上传函数
            print("[DEBUG-BREEDING-WORKER-6] 导入upload_and_standardize_breeding_data函数")
            from core.data.uploader import upload_and_standardize_breeding_data
            
            # 上传并标准化数据，传递进度回调
            print("[DEBUG-BREEDING-WORKER-7] 调用upload_and_standardize_breeding_data函数")
            standardized_path = upload_and_standardize_breeding_data(
                self.input_files, 
                self.project_path, 
                progress_callback=self.progress_callback  # 使用回调函数
            )
            
            print(f"[DEBUG-BREEDING-WORKER-8] 处理完成，标准化文件路径: {standardized_path}")
            logging.info(f"处理完成，标准化文件路径: {standardized_path}")
            self.finished.emit(standardized_path)
            print("[DEBUG-BREEDING-WORKER-9] 发送finished信号，工作线程结束")
            
        except Exception as e:
            error_trace = traceback.format_exc()
            error_msg = f"处理配种记录时发生错误: {str(e)}"
            print(f"[DEBUG-BREEDING-WORKER-ERROR] {error_msg}")
            print(error_trace)
            logging.error(error_msg)
            logging.error(error_trace)
            self.error.emit(f"{error_msg}\n\n详细错误信息:\n{error_trace}")

