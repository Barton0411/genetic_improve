# gui/progress.py

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
                             QPushButton, QTextEdit, QApplication, QMessageBox, QWidget,
                             QGridLayout)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QTextCursor, QColor
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
        # 添加最小化按钮，移除强制置顶
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinimizeButtonHint)
        
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
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setMinimumHeight(22)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #e8e8e8;
                text-align: center;
                height: 22px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # 进度百分比和已用时间
        time_layout = QHBoxLayout()
        self.percent_label = QLabel("0%")
        self.elapsed_label = QLabel("已用时间: 0:00")
        self.elapsed_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        time_layout.addWidget(self.percent_label)
        time_layout.addStretch()
        time_layout.addWidget(self.elapsed_label)
        layout.addLayout(time_layout)

        # 记录开始时间
        self._start_time = time.time()

        # 子任务进度条容器（默认隐藏）
        self._sub_tasks_container = QWidget(self)
        self._sub_tasks_layout = QVBoxLayout(self._sub_tasks_container)
        self._sub_tasks_layout.setContentsMargins(0, 0, 0, 0)
        self._sub_tasks_layout.setSpacing(4)
        self._sub_tasks_container.setVisible(False)
        layout.addWidget(self._sub_tasks_container)

        # 子任务跟踪 {task_id: {"icon": QLabel, "bar": QProgressBar, "name": QLabel}}
        self._sub_task_widgets = {}

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
            # 追赶目标进度
            diff = self.target_progress - self.current_progress
            increment = max(0.5, diff * 0.1)
            self.current_progress = min(self.current_progress + increment, self.target_progress)
            self.progress_bar.setValue(int(self.current_progress))
        elif self.current_progress >= self.target_progress and self.current_progress < 95:
            # 空闲爬升：最多超前target 5%，让用户感觉仍在进行
            max_allowed = min(self.target_progress + 5, 95)
            if self.current_progress < max_allowed:
                self.current_progress += 0.15
                self.progress_bar.setValue(int(self.current_progress))
        # 注意：不再强制拉回current_progress，避免进度条回退

        # 更新百分比和已用时间
        pct = int(self.current_progress)
        self.percent_label.setText(f"{pct}%")
        elapsed = time.time() - self._start_time
        em, es = divmod(int(elapsed), 60)
        if pct > 5 and elapsed > 3:
            total_estimated = elapsed / (pct / 100)
            remaining = max(0, total_estimated - elapsed)
            rm, rs = divmod(int(remaining), 60)
            self.elapsed_label.setText(f"已用 {em}:{es:02d} | 预计剩余 {rm}:{rs:02d}")
        else:
            self.elapsed_label.setText(f"已用时间: {em}:{es:02d}")

    def update_progress(self, value):
        """更新进度条目标值（只允许前进，防止并行回调导致回退）"""
        if value < 0 or value > 100:
            return
        if value > self.target_progress:
            self.target_progress = value
        # 不再直接设置进度条，让定时器平滑更新

    def update_info(self, info):
        """更新信息区域"""
        self.info_text.append(info)
        self.info_text.moveCursor(QTextCursor.MoveOperation.End)

    def set_task_info(self, info):
        """设置当前任务信息"""
        self.task_label.setText(info)
        # 同时在详细信息区域记录
        self.info_text.append(info)
        self.info_text.moveCursor(QTextCursor.MoveOperation.End)

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

    # ---- 子任务进度条 ---- #

    def show_sub_tasks(self, task_names: list):
        """创建并显示子任务进度条"""
        # 清除旧的子任务widget
        self._clear_sub_tasks()

        for name in task_names:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(6)

            # 状态图标
            icon_label = QLabel("\u23f3")  # 沙漏
            icon_label.setFixedWidth(16)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row_layout.addWidget(icon_label)

            # 任务名
            name_label = QLabel(name)
            name_label.setFixedWidth(130)
            name_label.setStyleSheet("font-size: 11px;")
            row_layout.addWidget(name_label)

            # 小进度条
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setFixedHeight(14)
            bar.setTextVisible(False)
            bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    background-color: #e8e8e8;
                }
                QProgressBar::chunk {
                    background-color: #3498db;
                    border-radius: 2px;
                }
            """)
            row_layout.addWidget(bar)

            self._sub_tasks_layout.addLayout(row_layout)
            self._sub_task_widgets[name] = {
                "icon": icon_label,
                "bar": bar,
                "name": name_label,
            }

        self._sub_tasks_container.setVisible(True)

    def update_sub_task(self, task_id: str, pct: int):
        """更新子任务进度"""
        w = self._sub_task_widgets.get(task_id)
        if not w:
            return
        pct = max(0, min(100, pct))
        w["bar"].setValue(pct)

    def complete_sub_task(self, task_id: str, success: bool):
        """标记子任务完成"""
        w = self._sub_task_widgets.get(task_id)
        if not w:
            return
        if success:
            w["icon"].setText("\u2713")  # 对勾
            w["icon"].setStyleSheet("color: #27ae60; font-weight: bold;")
            w["bar"].setValue(100)
            w["bar"].setStyleSheet("""
                QProgressBar {
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    background-color: #e8e8e8;
                }
                QProgressBar::chunk {
                    background-color: #27ae60;
                    border-radius: 2px;
                }
            """)
        else:
            w["icon"].setText("\u2717")  # 叉号
            w["icon"].setStyleSheet("color: #e74c3c; font-weight: bold;")
            w["bar"].setStyleSheet("""
                QProgressBar {
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    background-color: #e8e8e8;
                }
                QProgressBar::chunk {
                    background-color: #e74c3c;
                    border-radius: 2px;
                }
            """)

    def hide_sub_tasks(self):
        """隐藏子任务区域"""
        self._sub_tasks_container.setVisible(False)

    def _clear_sub_tasks(self):
        """清除所有子任务widget"""
        self._sub_task_widgets.clear()
        while self._sub_tasks_layout.count():
            item = self._sub_tasks_layout.takeAt(0)
            if item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

    def closeEvent(self, event):
        """点击关闭按钮时的处理"""
        print("[DEBUG-PROGRESS-8] 关闭进度对话框")
        # 停止定时器
        if hasattr(self, 'progress_timer'):
            self.progress_timer.stop()
        # 直接关闭窗口，不再弹出确认对话框
        self.cancelled = True
        event.accept()
