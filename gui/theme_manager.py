"""
主题管理器 - 用于处理深色/浅色模式自适应
"""
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor
import sys


class ThemeManager:
    """主题管理器，处理深色/浅色模式"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialized = True

    @property
    def is_dark_mode(self) -> bool:
        """实时检测系统是否使用深色模式"""
        return self._detect_dark_mode()

    def _detect_dark_mode(self) -> bool:
        """检测系统是否使用深色模式"""
        app = QApplication.instance()
        if app:
            palette = app.palette()
            # 通过比较窗口背景色的亮度来判断是否为深色模式
            bg_color = palette.color(QPalette.ColorRole.Window)
            # 计算亮度 (0-255)
            brightness = (bg_color.red() * 299 + bg_color.green() * 587 + bg_color.blue() * 114) / 1000
            return brightness < 128
        return False

    def get_table_style(self) -> str:
        """获取表格的样式表"""
        if self.is_dark_mode:
            return """
            QTableWidget {
                background-color: #3a3a3a;
                color: #e0e0e0;
                gridline-color: #555;
                border: 1px solid #555;
            }
            QTableWidget::item {
                color: #e0e0e0;
                background-color: #3a3a3a;
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #3a7fc5;
                color: white;
            }
            QHeaderView::section {
                background-color: #4a4a4a;
                color: #e0e0e0;
                padding: 5px;
                border: 1px solid #555;
            }
            QTableWidget::item:hover {
                background-color: #4a4a4a;
            }
            """
        else:
            return """
            QTableWidget {
                background-color: white;
                color: #2c3e50;
                gridline-color: #ddd;
                border: 1px solid #ddd;
            }
            QTableWidget::item {
                color: #2c3e50;
                background-color: white;
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                color: #2c3e50;
                padding: 5px;
                border: 1px solid #ddd;
            }
            QTableWidget::item:hover {
                background-color: #f5f5f5;
            }
            """

    def get_preview_table_style(self) -> str:
        """获取预览表格的样式表 - 仅在深色模式下应用样式"""
        if self.is_dark_mode:
            return """
            QTableWidget {
                background-color: #3a3a3a;
                color: #e0e0e0;
                gridline-color: #555;
                border: 1px solid #555;
            }
            QTableWidget::item {
                color: #e0e0e0;
                background-color: #3a3a3a;
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #3a7fc5;
                color: white;
            }
            QHeaderView::section {
                background-color: #4a4a4a;
                color: #e0e0e0;
                padding: 5px;
                border: 1px solid #555;
            }
            QTableWidget::item:hover {
                background-color: #4a4a4a;
            }
            """
        else:
            # 浅色模式下不应用任何样式，保持默认
            return ""

    def get_dialog_style(self) -> str:
        """获取对话框的样式表"""
        if self.is_dark_mode:
            return """
            QDialog {
                background-color: #3a3a3a;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
            QLineEdit, QSpinBox, QComboBox {
                background-color: #4a4a4a;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 5px;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid #3a7fc5;
            }
            QPushButton {
                background-color: #4a4a4a;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QGroupBox {
                color: #e0e0e0;
                border: 1px solid #555;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #e0e0e0;
            }
            QTextEdit, QTextBrowser {
                background-color: #4a4a4a;
                color: #e0e0e0;
                border: 1px solid #555;
            }
            QCheckBox {
                color: #e0e0e0;
            }
            QRadioButton {
                color: #e0e0e0;
            }
            """
        else:
            return """
            QDialog {
                background-color: white;
                color: #2c3e50;
            }
            QLabel {
                color: #2c3e50;
            }
            QLineEdit, QSpinBox, QComboBox {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #ddd;
                padding: 5px;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid #3498db;
            }
            QPushButton {
                background-color: #f0f0f0;
                color: #2c3e50;
                border: 1px solid #ddd;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            QGroupBox {
                color: #2c3e50;
                border: 1px solid #ddd;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #2c3e50;
            }
            QTextEdit, QTextBrowser {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #ddd;
            }
            QCheckBox {
                color: #2c3e50;
            }
            QRadioButton {
                color: #2c3e50;
            }
            """

    def get_main_window_style(self) -> str:
        """获取主窗口的样式表"""
        if self.is_dark_mode:
            return """
            QMainWindow {
                background-color: #3a3a3a;
            }
            QWidget {
                color: #e0e0e0;
            }
            QTreeView {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                selection-background-color: #3a7fc5;
            }
            QTreeView::item:hover {
                background-color: #4a4a4a;
            }
            QTreeView::item:selected {
                background-color: #3a7fc5;
            }
            QListWidget {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
            }
            QListWidget::item:hover {
                background-color: #4a4a4a;
            }
            QListWidget::item:selected {
                background-color: #3a7fc5;
                color: white;
            }
            QTabWidget::pane {
                background-color: #3a3a3a;
                border: 1px solid #555;
            }
            QTabBar::tab {
                background-color: #4a4a4a;
                color: #e0e0e0;
                padding: 8px 12px;
            }
            QTabBar::tab:selected {
                background-color: #3a3a3a;
                color: white;
            }
            QTabBar::tab:hover {
                background-color: #5a5a5a;
            }
            QProgressBar {
                border: 1px solid #555;
                background-color: #4a4a4a;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3a7fc5;
            }
            """
        else:
            return """
            QMainWindow {
                background-color: #f5f5f5;
            }
            QWidget {
                color: #2c3e50;
            }
            QTreeView {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #ddd;
                selection-background-color: #3498db;
            }
            QTreeView::item:hover {
                background-color: #f0f0f0;
            }
            QTreeView::item:selected {
                background-color: #3498db;
                color: white;
            }
            QListWidget {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #ddd;
            }
            QListWidget::item:hover {
                background-color: #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QTabWidget::pane {
                background-color: white;
                border: 1px solid #ddd;
            }
            QTabBar::tab {
                background-color: #f0f0f0;
                color: #2c3e50;
                padding: 8px 12px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #2c3e50;
            }
            QTabBar::tab:hover {
                background-color: #e0e0e0;
            }
            QProgressBar {
                border: 1px solid #ddd;
                background-color: #f0f0f0;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3498db;
            }
            """

    def get_frame_style(self) -> str:
        """获取框架的样式表"""
        if self.is_dark_mode:
            return """
            QFrame {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 5px;
            }
            """
        else:
            return """
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 5px;
            }
            """

    def get_text_color(self) -> str:
        """获取文本颜色"""
        return "#e0e0e0" if self.is_dark_mode else "#2c3e50"

    def get_background_color(self) -> str:
        """获取背景颜色"""
        return "#3a3a3a" if self.is_dark_mode else "white"

    def get_border_color(self) -> str:
        """获取边框颜色"""
        return "#555" if self.is_dark_mode else "#ddd"

    def get_hover_color(self) -> str:
        """获取悬停颜色"""
        return "#4a4a4a" if self.is_dark_mode else "#f0f0f0"

    def get_selection_color(self) -> str:
        """获取选中颜色"""
        return "#3a7fc5" if self.is_dark_mode else "#3498db"

    def get_button_style_for_index_calc(self) -> str:
        """获取牛只指数计算页面按钮的样式"""
        if self.is_dark_mode:
            # 深色模式下，可用时蓝色，不可用时深灰色
            return """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover:!disabled {
                background-color: #2980b9;
            }
            QPushButton:pressed:!disabled {
                background-color: #21618c;
            }
            QPushButton:disabled {
                background-color: #5a5a5a;
                color: #999999;
            }
            """
        else:
            # 浅色模式，可用时蓝色，不可用时浅灰色
            return """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover:!disabled {
                background-color: #2980b9;
            }
            QPushButton:pressed:!disabled {
                background-color: #21618c;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
            """

    def get_auto_grouping_style(self) -> str:
        """获取自动分组对话框的专用样式"""
        # 实时检测深色模式
        if self.is_dark_mode:
            return """
            QDialog {
                background-color: #3a3a3a;
                color: white;
            }
            QLabel {
                color: white;
            }
            QGroupBox {
                color: white;
                border: 1px solid #555;
            }
            QGroupBox::title {
                color: white;
            }
            QPushButton {
                background-color: #5a5a5a;
                color: black;
                border: 1px solid #666;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #6a6a6a;
            }
            QTableWidget {
                background-color: #3a3a3a;
                color: white;
            }
            QTableWidget::item {
                background-color: #3a3a3a;
                color: white;
            }
            QSpinBox {
                background-color: #4a4a4a;
                color: white;
                border: 1px solid #555;
            }
            QComboBox {
                background-color: #4a4a4a;
                color: white;
                border: 1px solid #555;
            }
            """
        else:
            # 浅色模式保持原样
            return ""

    def apply_theme_to_widget(self, widget):
        """将主题应用到特定控件"""
        widget_type = type(widget).__name__

        if widget_type == "QTableWidget":
            widget.setStyleSheet(self.get_table_style())
        elif widget_type == "QDialog":
            widget.setStyleSheet(self.get_dialog_style())
        elif widget_type == "QMainWindow":
            widget.setStyleSheet(self.get_main_window_style())
        elif widget_type == "QFrame":
            widget.setStyleSheet(self.get_frame_style())


# 全局主题管理器实例
theme_manager = ThemeManager()