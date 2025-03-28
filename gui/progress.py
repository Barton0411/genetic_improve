# gui/progress.py

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QTextEdit, QApplication
from PyQt6.QtCore import Qt, QObject, pyqtSignal
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("进度")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        
        # 设置合适的窗口大小以显示更多日志
        self.resize(800, 600)  # 稍微增加窗口大小

        # 标题信息
        self.title_label = QLabel("当前任务: 未知 (0/0)")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")

        # 主进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 2px;
                text-align: center;
                height: 12px;
                background-color: #f5f5f5;
                margin-top: 4px;
                margin-bottom: 4px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 1px;
            }
        """)

        # 日志文本框，用于显示计算过程中的print输出
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(400)  # 增加最小高度
        
        # 设置等宽字体和样式
        font = self.log_text.font()
        font.setFamily("Consolas")  # Windows 上更好的等宽字体
        font.setPointSize(10)
        self.log_text.setFont(font)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        
        # 批量更新相关变量
        self.update_counter = 0
        self.update_threshold = 50  # 降低阈值以提高更新频率
        self.last_update_time = time.time()
        self.update_interval = 0.1  # 降低更新间隔以提高响应性
        
        # 设置输出重定向
        self.redirector = OutputRedirector()
        self.redirector.outputWritten.connect(self.append_log)
        sys.stdout = self.redirector
        
        # 可选的取消按钮
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.cancel_button.clicked.connect(self.on_cancel_clicked)

        # 布局
        layout = QVBoxLayout()
        layout.addWidget(self.title_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_text)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.cancelled = False
    
    def append_log(self, text):
        """优化的日志添加方法"""
        # 添加文本到日志框
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text.rstrip('\n') + '\n')
        
        # 增加计数器
        self.update_counter += 1
        current_time = time.time()
        
        # 仅在累积一定数量的消息或经过一定时间后更新UI
        if (self.update_counter >= self.update_threshold or 
            (current_time - self.last_update_time) > self.update_interval):
            
            # 滚动到底部
            self.log_text.setTextCursor(cursor)
            self.log_text.ensureCursorVisible()
            
            # 立即处理事件循环，确保GUI更新
            QApplication.processEvents()
            
            # 重置计数器和更新时间
            self.update_counter = 0
            self.last_update_time = current_time

    def on_cancel_clicked(self):
        self.cancelled = True
        # 修改标题显示取消状态
        self.setWindowTitle("进度 (已取消 - 正在停止计算...)")
        # 更新取消按钮文本
        self.cancel_button.setText("正在取消...")
        self.cancel_button.setEnabled(False)
        # 立即处理事件以更新UI
        QApplication.processEvents()
        # 不立即关闭窗口，显示"正在取消"状态
        
    def closeEvent(self, event):
        # 关闭对话框时设置取消标志，确保不会遗漏取消指令
        self.cancelled = True
        # 关闭对话框时恢复标准输出
        sys.stdout = self.redirector._old_stdout
        super().closeEvent(event)

    def set_task_info(self, task_name: str):
        """
        更新当前任务名称
        
        Args:
            task_name: 当前执行的任务名称
        """
        self.title_label.setText(f"当前任务: {task_name}")
        QApplication.processEvents()

    def update_progress(self, value: int):
        """
        更新进度条的百分比进度（0~100）
        """
        self.progress_bar.setValue(value)
        # 确保进度条更新立即显示
        QApplication.processEvents()
        
    def update_info(self, message: str, *args, **kwargs):
        """
        兼容旧代码的方法，将消息添加到日志
        """
        # 忽略额外参数，只使用消息文本
        if message:
            self.append_log(message)
            # 同时更新任务名称
            self.set_task_info(message)
