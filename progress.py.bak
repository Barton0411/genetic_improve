# gui/progress.py

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton
from PyQt6.QtCore import Qt

class ProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("进度")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)

        # 标题信息
        self.title_label = QLabel("当前任务: 未知 (0/0)")
        self.title_label.setStyleSheet("font-weight: bold;")

        # 主进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        # 状态信息
        self.info_label = QLabel("剩余时间: 未知 | 处理速度: 未知")
        
        # 可选的取消按钮（如有需要）
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.on_cancel_clicked)

        # 布局
        layout = QVBoxLayout()
        layout.addWidget(self.title_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.info_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        self.cancelled = False

    def on_cancel_clicked(self):
        self.cancelled = True
        self.close()

    def set_task_info(self, task_name: str, current_step: int, total_steps: int):
        """
        更新任务名称与进度，如:
        task_name: "计算牛群近交系数"
        current_step: 2
        total_steps: 5
        显示: "当前任务: 计算牛群近交系数 (2/5)"
        """
        self.title_label.setText(f"当前任务: {task_name} ({current_step}/{total_steps})")

    def update_progress(self, value: int):
        """
        更新进度条的百分比进度（0~100）
        """
        self.progress_bar.setValue(value)

    def update_info(self, remaining_time: str, speed: str):
        """
        更新剩余时间和处理速度信息，例如:
        remaining_time: "5分30秒"
        speed: "10个记录/秒"
        """
        self.info_label.setText(f"剩余时间: {remaining_time} | 处理速度: {speed}")
