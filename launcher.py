#!/usr/bin/env python3
"""
快速启动加载器
显示加载界面，同时在后台启动主程序
"""
import sys
import os
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout, QProgressBar
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QProcess
from PyQt6.QtGui import QPixmap, QFont, QPalette, QColor
import subprocess
from pathlib import Path

class LoadingWindow(QWidget):
    """加载窗口"""
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        """初始化UI"""
        # 设置窗口属性
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(400, 250)
        
        # 居中显示
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
        
        # 创建布局
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 创建背景widget
        bg_widget = QWidget()
        bg_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 240);
                border-radius: 10px;
                border: 1px solid #ddd;
            }
        """)
        
        bg_layout = QVBoxLayout(bg_widget)
        bg_layout.setSpacing(20)
        
        # Logo或标题
        title_label = QLabel("遗传改良系统")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        title_label.setFont(font)
        title_label.setStyleSheet("color: #2c3e50;")
        bg_layout.addWidget(title_label)
        
        # 状态标签
        self.status_label = QLabel("正在启动程序...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #7f8c8d;")
        bg_layout.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 无限循环模式
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 5px;
                background-color: #f0f0f0;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 4px;
            }
        """)
        bg_layout.addWidget(self.progress_bar)
        
        # 版本信息
        version_label = QLabel("v1.0.0")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #bdc3c7; font-size: 10px;")
        bg_layout.addWidget(version_label)
        
        bg_layout.addStretch()
        
        layout.addWidget(bg_widget)
        self.setLayout(layout)

class MainProgramLoader(QThread):
    """主程序加载线程"""
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def run(self):
        """运行主程序"""
        try:
            # 导入主程序模块
            import main
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

def main():
    """启动器主函数"""
    app = QApplication(sys.argv)
    
    # 显示加载窗口
    loading_window = LoadingWindow()
    loading_window.show()
    
    # 启动主程序
    def start_main_program():
        loading_window.status_label.setText("正在加载模块...")
        
        # 延迟导入主程序
        QTimer.singleShot(100, lambda: __import__('main').main())
        
        # 关闭加载窗口
        QTimer.singleShot(500, loading_window.close)
    
    # 显示加载界面一小段时间后启动主程序
    QTimer.singleShot(100, start_main_program)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()