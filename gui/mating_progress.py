"""
选配进度对话框
显示选配进度并防止UI冻结
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QPushButton, QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from pathlib import Path
import logging

from core.matching.mating_worker import MatingWorker

logger = logging.getLogger(__name__)


class MatingProgressDialog(QDialog):
    """选配进度对话框"""
    
    completed = pyqtSignal(dict)  # 完成信号
    
    def __init__(self, project_path: Path, params: dict, parent=None):
        super().__init__(parent)
        self.project_path = project_path
        self.params = params
        self.worker = None
        self.result = None
        
        self.setup_ui()
        self.start_mating()
        
    def setup_ui(self):
        """设置界面"""
        self.setWindowTitle("个体选配进度")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setFixedHeight(200)
        # 添加最小化按钮
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinimizeButtonHint)
        
        layout = QVBoxLayout(self)
        
        # 标题
        self.title_label = QLabel("正在执行个体选配...")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.title_label.setFont(font)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        
        # 进度信息
        self.info_label = QLabel("正在初始化...")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.cancel_mating)
        button_layout.addWidget(self.cancel_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        layout.addStretch()
        
    def start_mating(self):
        """开始选配"""
        # 创建工作线程
        self.worker = MatingWorker(self.project_path, self.params)
        
        # 连接信号
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error_occurred.connect(self.on_error)
        
        # 启动线程
        self.worker.start()
        
    def update_progress(self, message: str, progress: int):
        """更新进度"""
        self.info_label.setText(message)
        self.progress_bar.setValue(progress)
        
    def on_finished(self, result: dict):
        """完成处理 - 自动关闭进度窗口，由 on_mating_completed 显示结果"""
        self.result = result
        self.progress_bar.setValue(100)

        # 先关闭进度窗口，再发送完成信号（避免两个窗口同时显示）
        self.accept()
        self.completed.emit(result)
        
    def on_error(self, error_msg: str):
        """错误处理"""
        self.title_label.setText("选配失败")
        self.info_label.setText(f"错误: {error_msg}")
        self.progress_bar.setValue(0)
        
        # 改变按钮
        self.cancel_btn.setText("关闭")
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.reject)
        
    def cancel_mating(self):
        """取消选配"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.quit()
            self.worker.wait()
        self.reject()
        
    def closeEvent(self, event):
        """关闭事件"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.quit()
            self.worker.wait()
        event.accept()
