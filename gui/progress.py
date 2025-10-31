# gui/progress.py

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QTextEdit, QApplication, QMessageBox
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QTextCursor
import sys
import time  # 添加time模块导入

# 创建一个标准输出重定向类
class OutputRedirector(QObject):
    outputWritten = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self._old_stdout = sys.stdout
        
    def write(self, text):
        self._old_stdout.write(text)
        self.outputWritten.emit(text)
        
    def flush(self):
        self._old_stdout.flush()

class ProgressDialog(QDialog):
    """进度对话框，用于显示数据处理进度"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cancelled = False
        self.title_text = "处理进度"
        self.current_progress = 0  # 当前显示的进度值
        self.target_progress = 0   # 目标进度值
        self.initUI()

    def initUI(self):
        self.setWindowTitle(self.title_text)
        self.setMinimumWidth(400)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        # 设置窗口保持在最上层
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # 标题
        self.title_label = QLabel(self.title_text)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self.title_label.font()
        font.setBold(True)
        font.setPointSize(14)
        self.title_label.setFont(font)
        layout.addWidget(self.title_label)
        
        # 任务信息
        self.task_label = QLabel("准备中...")
        layout.addWidget(self.task_label)
        
        # 进度条
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # 详细信息区域
        self.info_text = QTextEdit(self)
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(150)
        layout.addWidget(self.info_text)
        
        # 取消按钮
        self.cancel_button = QPushButton("取消", self)
        self.cancel_button.clicked.connect(self.on_cancel)
        layout.addWidget(self.cancel_button, 0, Qt.AlignmentFlag.AlignRight)

        # 设置布局
        self.setLayout(layout)

        # 创建定时器用于平滑进度条动画
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self._update_smooth_progress)
        self.progress_timer.start(50)  # 每50ms更新一次

    def _update_smooth_progress(self):
        """平滑更新进度条（由定时器调用）"""
        if self.current_progress < self.target_progress:
            # 计算增量，距离越远增长越快
            diff = self.target_progress - self.current_progress
            increment = max(0.5, diff * 0.1)  # 至少增长0.5%，最多增长差值的10%
            self.current_progress = min(self.current_progress + increment, self.target_progress)
            self.progress_bar.setValue(int(self.current_progress))
        elif self.current_progress >= self.target_progress and self.current_progress < 95:
            # 即使已经到达目标值，只要还没到95%，就继续缓慢增长
            # 这样可以避免在长时间任务期间进度条完全停止
            # 但限制在不超过目标值+3%，避免进度条跑得太超前
            max_allowed = min(self.target_progress + 3, 95)
            if self.current_progress < max_allowed:
                self.current_progress += 0.1  # 每50ms增长0.1%，非常缓慢
                self.progress_bar.setValue(int(self.current_progress))
        elif self.current_progress > self.target_progress:
            # 如果目标值降低了（一般不应该发生），直接设置
            self.current_progress = self.target_progress
            self.progress_bar.setValue(int(self.current_progress))

    def update_progress(self, value):
        """更新进度条目标值"""
        if value < 0 or value > 100:
            return
        self.target_progress = value
        # 不再直接设置进度条，让定时器平滑更新

    def update_info(self, info):
        """更新信息区域"""
        self.info_text.append(info)
        self.info_text.moveCursor(QTextCursor.MoveOperation.End)
        QApplication.processEvents()

    def set_task_info(self, info):
        """设置当前任务信息"""
        self.task_label.setText(info)
        # 同时在详细信息区域记录
        self.info_text.append(info)
        self.info_text.moveCursor(QTextCursor.MoveOperation.End)
        QApplication.processEvents()

    def on_cancel(self):
        """取消操作"""
        reply = QMessageBox.question(
            self, 
            "确认取消", 
            "确定要取消当前操作吗?", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            print("[DEBUG-PROGRESS-7] 确认取消，设置cancelled=True")
            self.cancelled = True
            self.close()

    def closeEvent(self, event):
        """点击关闭按钮时的处理"""
        print("[DEBUG-PROGRESS-8] 关闭进度对话框")
        # 停止定时器
        if hasattr(self, 'progress_timer'):
            self.progress_timer.stop()
        # 直接关闭窗口，不再弹出确认对话框
        self.cancelled = True
        event.accept()
