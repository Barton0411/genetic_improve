import sys
import os
import shutil
from pathlib import Path
import json
import logging
import re

from PyQt6.QtCore import (
    Qt, QDir, QUrl, pyqtSignal, QThread, QTimer, QEvent
)
from PyQt6.QtGui import (
    QFileSystemModel, QDesktopServices, QBrush, QPalette, QPixmap, QColor, QFont, QIcon,
    QLinearGradient
)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QFileDialog, QMessageBox, QLabel, 
    QListWidget, QListWidgetItem, QStackedWidget, QInputDialog, 
    QFrame, QTreeView, QGridLayout, QAbstractItemView, QMenu, QGraphicsOpacityEffect,
    QStackedLayout, QGroupBox, QComboBox, QCheckBox, QTableWidget, QTableWidgetItem, 
    QHeaderView, QLineEdit, QTabWidget, QFormLayout, QSpinBox, QDialogButtonBox, 
    QDialog, QProgressDialog, QApplication, QTextBrowser, QSizePolicy, QStyle
)
import warnings
import pandas as pd
import numpy as np

from core.inbreeding.inbreeding_page import InbreedingPage
from gui.farm_selection_page import FarmSelectionPage
warnings.filterwarnings("ignore", category=UserWarning)
from config.settings import Settings
from core.breeding_calc.cow_traits_calc import CowKeyTraitsPage
from utils.file_manager import FileManager
from core.data.uploader import (
    upload_and_standardize_bull_data,
    upload_and_standardize_breeding_data,
    upload_and_standardize_body_data,
    upload_and_standardize_cow_data
)
from gui.worker import CowDataWorker, GenomicDataWorker, BreedingDataWorker
from gui.progress import ProgressDialog
from gui.db_update_worker import DBUpdateWorker
from core.breeding_calc.bull_traits_calc import BullKeyTraitsPage
from core.breeding_calc.index_page import IndexCalculationPage
from core.breeding_calc.mated_bull_traits_calc import MatedBullKeyTraitsPage
from core.api.mating_result_pusher import MatingResultPusher  
# from gui.matching_worker import MatchingWorker  # DEPRECATED - 使用 CycleBasedMatcher 替代
from gui.recommendation_worker import RecommendationWorker
from gui.theme_manager import theme_manager

# 策略表格管理器，用于处理表格创建和数据逻辑
class StrategyTableManager:
    """策略表格管理器，用于处理策略表格的创建和数据操作"""
    
    @staticmethod
    def create_strategy_table(parent):
        """创建策略表格并初始化"""
        strategy_table = QTableWidget(parent)
        strategy_table.setColumnCount(6)
        strategy_table.setRowCount(7)  # 包含一行分隔行
        
        # 隐藏垂直表头（行号）
        strategy_table.verticalHeader().setVisible(False)
        
        headers = ["分组", "分配比例(%)", "第1次配种", "第2次配种", "第3次配种", "第4次+配种"]
        strategy_table.setHorizontalHeaderLabels(headers)
        
        # 设置固定的分组名称
        groups = [
            ("成母牛A", "成母牛"), ("成母牛B", "成母牛"), ("成母牛C", "成母牛"),
            (None, None),  # 空行，用于分隔
            ("后备牛A", "后备牛"), ("后备牛B", "后备牛"), ("后备牛C", "后备牛")
        ]
        
        for i, (group, group_type) in enumerate(groups):
            # 设置分隔行
            if group is None:
                for col in range(6):
                    item = QTableWidgetItem("")
                    item.setFlags(Qt.ItemFlag.NoItemFlags)
                    strategy_table.setItem(i, col, item)
                strategy_table.setRowHeight(i, 10)  # 设置分隔行高度为10像素
                continue
            
            # 分组名称
            name_item = QTableWidgetItem(group)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            name_item.setData(Qt.ItemDataRole.UserRole, group_type)
            name_item.setForeground(QBrush(QColor("#2c3e50")))  # 设置文本颜色
            font = name_item.font()
            font.setPointSize(13)
            name_item.setFont(font)
            strategy_table.setItem(i, 0, name_item)
            
            # 添加分配比例输入
            ratio_item = QTableWidgetItem("0")
            ratio_item.setForeground(QBrush(QColor("#2c3e50")))  # 设置文本颜色
            font = ratio_item.font()
            font.setPointSize(13)
            ratio_item.setFont(font)
            strategy_table.setItem(i, 1, ratio_item)
            
            # 添加配种方式选择下拉框
            for j in range(2, 6):
                combo = QComboBox()
                combo.addItems(["常规冻精", "普通性控", "超级性控", "肉牛冻精", "胚胎"])
                combo.setCurrentIndex(0)  # 设置默认值
                strategy_table.setCellWidget(i, j, combo)
        
        # 设置行高
        for row in range(strategy_table.rowCount()):
            if row != 3:  # 不是分隔行
                strategy_table.setRowHeight(row, 45)  # 增加行高为45像素，使配种方式名称完整显示
        
        # 调整表格列宽，确保文字完整显示
        strategy_table.setColumnWidth(0, 100)  # 分组列
        strategy_table.setColumnWidth(1, 100)  # 分配比例列
        strategy_table.setColumnWidth(2, 130)  # 第1次配种列
        strategy_table.setColumnWidth(3, 130)  # 第2次配种列
        strategy_table.setColumnWidth(4, 130)  # 第3次配种列
        strategy_table.setColumnWidth(5, 130)  # 第4次+配种列
        
        # 设置下拉框样式
        StrategyTableManager.setup_combobox_style(strategy_table)
        
        # 设置表格其他属性
        strategy_table.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        strategy_table.setMinimumWidth(750)  # 设置最小宽度确保完整显示
        strategy_table.setFixedHeight(340)   # 添加这行来设置固定高度
        strategy_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # 禁用水平滚动条
        
        # 表格整体设置
        strategy_table.setFrameShape(QFrame.Shape.StyledPanel)
        strategy_table.setShowGrid(True)
        strategy_table.setGridStyle(Qt.PenStyle.SolidLine)
        strategy_table.horizontalHeader().setStretchLastSection(True)  # 最后一列拉伸填充
        strategy_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        
        # 设置表格样式，提高字体对比度
        strategy_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                gridline-color: #ddd;
                font-size: 13px;
                color: #2c3e50;
            }
            QTableWidget::item {
                color: #2c3e50;  /* 深灰色文字 */
                background-color: white;
                padding: 5px;
                font-weight: normal;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                color: #2c3e50;
                font-weight: bold;
                padding: 5px;
                border: 1px solid #ddd;
            }
        """)
        
        # 设置所有已创建的单元格的字体颜色
        for row in range(strategy_table.rowCount()):
            for col in range(strategy_table.columnCount()):
                item = strategy_table.item(row, col)
                if item:
                    item.setForeground(QBrush(QColor("#2c3e50")))  # 深灰色
                    font = item.font()
                    font.setPointSize(13)
                    item.setFont(font)
        
        return strategy_table
    
    @staticmethod
    def setup_combobox_style(strategy_table):
        """设置所有下拉框的样式"""
        for row in range(strategy_table.rowCount()):
            if row != 3:  # 不是分隔行
                for col in range(2, 6):
                    combo = strategy_table.cellWidget(row, col)
                    if combo:
                        # 设置下拉框样式，确保文本完整显示，极简风格
                        combo.setStyleSheet("""
                            QComboBox { 
                                min-width: 120px; 
                                min-height: 30px; 
                                padding: 2px; 
                                margin: 1px;
                                border: 1px solid #ddd;
                                border-radius: 2px;
                                background-color: white;
                                color: #2c3e50;  /* 深灰色文字 */
                                font-size: 13px;
                                font-weight: normal;
                            }
                            QComboBox:hover {
                                border: 1px solid #3498db;
                            }
                            QComboBox::drop-down {
                                subcontrol-origin: padding;
                                subcontrol-position: right center;
                                width: 15px;
                                border-left: none;
                            }
                            QComboBox::down-arrow {
                                image: none;
                                border-left: 4px solid transparent;
                                border-right: 4px solid transparent;
                                border-top: 5px solid #2c3e50;
                            }
                            QComboBox QAbstractItemView {
                                background-color: white;
                                color: #2c3e50;
                                selection-background-color: #3498db;
                                selection-color: white;
                                border: 1px solid #ddd;
                                font-size: 13px;
                            }
                            QComboBox QAbstractItemView::item {
                                min-height: 25px;
                                padding: 3px;
                            }
                        """)
    
    @staticmethod
    def get_strategy_table_data(strategy_table):
        """获取策略表格中的数据"""
        data = []
        for row in range(strategy_table.rowCount()):
            # 跳过分隔行（第4行，索引为3）
            if row == 3:
                continue
                
            # 检查是否有有效的分组名称单元格
            name_item = strategy_table.item(row, 0)
            if name_item is None:
                continue
                
            # 获取比例，如果为空或无效则设为0
            ratio_item = strategy_table.item(row, 1)
            ratio_text = ratio_item.text() if ratio_item is not None else "0"
            try:
                ratio = float(ratio_text or "0")
            except ValueError:
                ratio = 0
                
            # 安全地获取配种方法
            breeding_methods = []
            for col in range(2, 6):
                combo = strategy_table.cellWidget(row, col)
                if combo is not None:
                    breeding_methods.append(combo.currentText())
                else:
                    # 如果下拉框不存在，添加默认值
                    breeding_methods.append("常规冻精")
            
            row_data = {
                "group": name_item.text(),
                "ratio": ratio,
                "breeding_methods": breeding_methods
            }
            data.append(row_data)
        return data
        
    @staticmethod
    def load_strategy_to_table(strategy_table, strategy_data):
        """将策略数据加载到表格中"""
        if 'strategy_table' not in strategy_data:
            raise ValueError("策略数据缺少strategy_table字段")
            
        # 策略中应该有6行（3行成母牛+3行后备牛）
        strategy_rows = strategy_data['strategy_table']
        if len(strategy_rows) != 6:
            raise ValueError(f"策略数据格式不正确，期望6行，实际{len(strategy_rows)}行")
        
        # 前3项为成母牛A/B/C，后3项为后备牛A/B/C
        # 界面表格有7行，第4行为分隔行
        table_indices = [0, 1, 2, 4, 5, 6]  # 映射策略索引到表格行索引
        
        for strategy_idx, table_idx in enumerate(table_indices):
            if strategy_idx < len(strategy_rows):
                strategy_row = strategy_rows[strategy_idx]
                
                # 设置分配比例 - 先检查单元格是否存在
                ratio_item = strategy_table.item(table_idx, 1)
                if ratio_item:
                    ratio_item.setText(str(strategy_row['ratio']))
                
                # 设置配种方法 - 先检查下拉框是否存在
                for j, method in enumerate(strategy_row['breeding_methods']):
                    combo = strategy_table.cellWidget(table_idx, j + 2)
                    if combo:
                        index = combo.findText(method)
                        if index >= 0:
                            combo.setCurrentIndex(index)

# 修改 sys.path（如果必要，确保只做一次）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class DragDropArea(QFrame):
    dropped = pyqtSignal(Path)  # 发射文件路径时使用Path对象

    """自定义拖拽区域组件，带有虚线边框和加号图示"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #aaa;
                border-radius: 10px;
                background-color: #f9f9f9;
            }
        """)
        self.setMinimumSize(400, 200)
        self.label = QLabel("+", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("font-size: 40px; color: #ccc;")
        layout = QVBoxLayout(self)
        layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignCenter)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            files = [Path(u.toLocalFile()) for u in urls if u.isLocalFile()]
            # 在这里可调用上传逻辑（参考后面上传按钮的逻辑）
            if files:
                file_path = files[0]
                self.dropped.emit(file_path)  # 发射信号，并传递文件路径
            QMessageBox.information(self, "文件拖拽", f"已拖入文件: {', '.join([f.name for f in files])}")
            # 如果要真正实现拖拽上传，需要访问主窗口的selected_project_path进行上传。
            # 可使用信号槽或提供回调函数。



class MainWindow(QMainWindow):
    def __init__(self, username=None):
        try:
            logging.info(f"MainWindow.__init__ started with username: {username}")
            super().__init__()
            logging.info("QMainWindow initialized")
            
            # 设置窗口图标
            icon_path = Path(__file__).parent.parent / "icon.ico"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
            
            self.settings = Settings()
            self.username = username
            self.content_stack = QStackedWidget()
            self.selected_project_path = None
            self.templates_path = Path(__file__).parent.parent / "templates"

            # 分组模式状态：'manual' 或 'auto'，None表示未选择
            self.grouping_mode = None

            # 添加标志防止重复触发
            self._db_update_triggered = False
            self._event_filter_installed = False

            # 保存按钮引用，用于更新状态
            self.manual_group_btn = None
            self.auto_group_btn = None
            
            # 导入版本信息
            from version import get_version
            self.version = get_version()
            logging.info(f"Version: {self.version}")
            
            # 创建所有页面实例
            logging.info("Creating page instances...")
            try:
                self.cow_key_traits_page = CowKeyTraitsPage(parent=self)
                logging.info("CowKeyTraitsPage created")
            except Exception as e:
                logging.exception(f"Failed to create CowKeyTraitsPage: {e}")
                raise
                
            try:
                self.bull_key_traits_page = BullKeyTraitsPage(parent=self)
                logging.info("BullKeyTraitsPage created")
            except Exception as e:
                logging.exception(f"Failed to create BullKeyTraitsPage: {e}")
                raise
                
            try:
                logging.info("Creating IndexCalculationPage...")
                self.index_calculation_page = IndexCalculationPage(parent=self)
                logging.info("IndexCalculationPage created")
            except Exception as e:
                logging.exception(f"Failed to create IndexCalculationPage: {e}")
                # 创建一个空的占位页面避免崩溃
                self.index_calculation_page = QWidget()
                logging.warning("Using placeholder for IndexCalculationPage")
                
            try:
                self.mated_bull_key_traits_page = MatedBullKeyTraitsPage(parent=self)
                logging.info("MatedBullKeyTraitsPage created")
            except Exception as e:
                logging.exception(f"Failed to create MatedBullKeyTraitsPage: {e}")
                self.mated_bull_key_traits_page = QWidget()
                logging.warning("Using placeholder for MatedBullKeyTraitsPage")
                
            # 添加新的近交分析页面实例
            try:
                self.inbreeding_page = InbreedingPage(parent=self)  # 新增
                logging.info("InbreedingPage created")
            except Exception as e:
                logging.exception(f"Failed to create InbreedingPage: {e}")
                self.inbreeding_page = QWidget()
                logging.warning("Using placeholder for InbreedingPage")
            
            logging.info("Setting up UI...")
            self.setup_ui()
            logging.info("UI setup completed")
            # Delay database update until after window is shown
            # self.check_and_update_database_on_startup()
            # Note: _db_update_triggered is already initialized above
            
            logging.info("MainWindow.__init__ completed successfully")

            # 初始化表格引用
            self.semen_tables = {}

            # 初始化对比牧场管理器
            from core.benchmark import BenchmarkManager
            self.benchmark_manager = BenchmarkManager()
            self.selected_comparisons = []  # 已选择的对比牧场列表 [{farm_id, color}, ...]

            # 预定义的对比颜色列表
            self.comparison_colors = [
                '#FF6B6B',  # 红色
                '#4ECDC4',  # 青色
                '#45B7D1',  # 蓝色
                '#FFA07A',  # 橙色
                '#98D8C8',  # 绿色
                '#F7B731',  # 黄色
                '#5F27CD',  # 紫色
                '#00D2D3',  # 青绿
            ]

        except Exception as e:
            logging.exception(f"Error in MainWindow.__init__: {e}")
            raise

    # 暂时禁用eventFilter以避免卡死问题
    # def eventFilter(self, source, event):
    #     """事件过滤器，监听系统主题变化"""
    #     try:
    #         # 只处理应用程序级别的事件，避免过度处理
    #         if source == QApplication.instance():
    #             if event.type() == QEvent.Type.PaletteChange:
    #                 # 系统主题发生变化，更新表格样式
    #                 # 使用定时器稍微延迟执行，确保主题已经完全切换
    #                 if hasattr(self, 'update_preview_tables_style'):
    #                     QTimer.singleShot(100, self.update_preview_tables_style)
    #     except Exception as e:
    #         logging.error(f"eventFilter 处理错误: {e}")
    #     return super().eventFilter(source, event)

    def update_preview_tables_style(self):
        """更新所有预览表格的样式"""
        # 重新获取当前主题样式
        style = theme_manager.get_preview_table_style()

        # 更新分组预览表格
        if hasattr(self, 'group_preview_table') and self.group_preview_table:
            self.group_preview_table.setStyleSheet(style)
            # 强制刷新表格显示
            self.group_preview_table.viewport().update()

        # 更新冻精预览表格 - 通过标签页遍历所有表格
        if hasattr(self, 'semen_tab_widget') and self.semen_tab_widget:
            for i in range(self.semen_tab_widget.count()):
                widget = self.semen_tab_widget.widget(i)
                if widget:
                    # 查找该widget中的所有QTableWidget
                    tables = widget.findChildren(QTableWidget)
                    for table in tables:
                        table.setStyleSheet(style)
                        # 强制刷新表格显示
                        table.viewport().update()

    def showEvent(self, event):
        """Override showEvent to trigger database update after window is shown"""
        super().showEvent(event)
        # 暂时禁用事件过滤器，避免导致卡死
        # if not hasattr(self, '_event_filter_installed') or not self._event_filter_installed:
        #     try:
        #         QApplication.instance().installEventFilter(self)
        #         self._event_filter_installed = True
        #     except Exception as e:
        #         logging.error(f"安装事件过滤器时出错: {e}")
        
        # Only trigger database update once, after the window is first shown
        if not self._db_update_triggered:
            self._db_update_triggered = True
            # Use QTimer to delay the database update more on Windows
            # Windows needs more time to fully render the window
            delay = 1000 if sys.platform == 'win32' else 100
            QTimer.singleShot(delay, self.check_and_update_database_on_startup)

    def setup_ui(self):
        self.setWindowTitle(f"伊利奶牛选配 v{self.version}")
        self.setGeometry(100, 100, 1600, 900)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # 创建左侧导航栏
        self.create_nav_panel(main_layout)
        
        # 创建右侧内容区
        self.create_content_area(main_layout)

        main_layout.setStretch(0, 1)
        main_layout.setStretch(1, 4)

        # 导航栏默认选择第一个页面
        self.nav_list.setCurrentRow(0)

    def create_nav_panel(self, layout):
        nav_frame = QFrame()
        # 设置渐变背景（使用QPalette更可靠）
        nav_frame.setAutoFillBackground(True)
        palette = nav_frame.palette()
        gradient = QLinearGradient(0, 0, 0, 1)
        gradient.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
        gradient.setColorAt(0, QColor("#456ba0"))
        gradient.setColorAt(1, QColor("#2c5282"))
        palette.setBrush(QPalette.ColorRole.Window, QBrush(gradient))
        nav_frame.setPalette(palette)

        # 设置边框
        nav_frame.setStyleSheet("""
            QFrame {
                border-right: 2px solid rgba(0, 0, 0, 0.15);
            }
        """)
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)
        
        # 修改导航项结构，使用嵌套列表表示父子关系
        nav_items = [
            ("伊起牛牧场数据选择", "platform", []),  # 新增：数据平台对接
            ("育种项目管理", "folder", []),
            ("数据上传", "upload", []),
            ("关键育种性状分析", "chart", []),
            ("牛只指数计算排名", "chart", []),
            ("近交系数及隐性基因分析", "analysis", []),
            ("体型外貌评定", "body", []),
            ("个体选配", "match", []),
            ("自动化生成", "report", [])
        ]

        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                font-size: 14px;
                outline: none;
            }
            QListWidget::item {
                color: rgba(255, 255, 255, 0.85);
                padding: 12px 20px;
                margin: 3px 10px;
                border: none;
                font-weight: 500;
                background-color: transparent;
                border-radius: 8px;
            }
            QListWidget::item:selected {
                background-color: #f5f7fa;
                color: #456ba0;
            }
            QListWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.2);
                color: white;
            }
            QListWidget::item:selected:hover {
                background-color: #f5f7fa;
                color: #456ba0;
            }
        """)
        # 设置尺寸策略，让列表可以扩展填充空间
        self.nav_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        # 修改添加导航项的逻辑
        for text, icon, subitems in nav_items:
            # 添加主导航项
            item = QListWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft)
            # 设置主导航项的缩进级别为0
            item.setData(Qt.ItemDataRole.UserRole + 1, 0)
            self.nav_list.addItem(item)
            
            # 如果有子项，添加子导航项
            for subitem in subitems:
                sub_item = QListWidgetItem("    " + subitem)  # 使用空格进行视觉上的缩进
                sub_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft)
                # 设置子导航项的缩进级别为1
                sub_item.setData(Qt.ItemDataRole.UserRole + 1, 1)
                self.nav_list.addItem(sub_item)

        nav_layout.addWidget(self.nav_list)

        # 添加弹性空间，将版本信息推到底部
        nav_layout.addStretch()

        # 在侧边栏最底部添加版本信息
        version_label = QLabel(f"版本: v{self.version}")
        version_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.6);
                font-size: 12px;
                padding: 10px;
                background: transparent;
                border-top: 1px solid rgba(255, 255, 255, 0.15);
            }
        """)
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 添加数据库版本信息
        self.db_version_label = QLabel("数据库版本: 检查中...")
        self.db_version_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.6);
                font-size: 11px;
                padding: 5px 10px;
                background: transparent;
            }
        """)
        self.db_version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.db_version_label.setWordWrap(True)

        # 添加关于按钮
        about_btn = QPushButton("关于")
        about_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.2);
                color: rgba(255, 255, 255, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.3);
                padding: 6px 12px;
                margin: 5px 10px 10px 10px;
                font-size: 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.3);
                color: white;
            }
        """)
        about_btn.clicked.connect(self.show_about_dialog)

        nav_layout.addWidget(version_label)
        nav_layout.addWidget(self.db_version_label)
        nav_layout.addWidget(about_btn)

        layout.addWidget(nav_frame)

        # 连接导航信号
        self.nav_list.currentRowChanged.connect(self.on_nav_item_changed)

    def create_genetic_analysis_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建顶部按钮容器
        button_container = QWidget()
        button_container.setFixedHeight(50)  # 控制按钮高度
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(10, 5, 10, 5)
        button_layout.setSpacing(5)  # 按钮之间添加5像素间距
        
        # 创建按钮样式
        normal_style = """
            QPushButton {
                background-color: #ecf0f1;  /* 更明显的浅灰色背景 */
                color: #2c3e50;            /* 更深的文字颜色 */
                border: 1px solid #bdc3c7; /* 添加边框 */
                border-radius: 4px;        /* 圆角 */
                font-size: 14px;
                font-weight: bold;         /* 加粗字体 */
                padding: 10px 30px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #d5dbdb; /* 悬停时更深的背景色 */
                border-color: #95a5a6;     /* 悬停时更深的边框 */
            }
        """

        selected_style = """
            QPushButton {
                background-color: #3498db;  /* 蓝色背景 */
                color: white;              /* 白色文字 */
                border: 1px solid #2980b9; /* 蓝色边框 */
                border-radius: 4px;        /* 圆角 */
                font-size: 14px;
                font-weight: bold;         /* 加粗字体 */
                padding: 10px 30px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #2980b9; /* 悬停时更深的蓝色 */
            }
        """
        
        # 创建按钮
        self.cow_btn = QPushButton("在群母牛")
        self.bull_btn = QPushButton("备选公牛")
        self.mated_bull_btn = QPushButton("已配公牛")
        
        # 设置默认样式
        for btn in [self.cow_btn, self.bull_btn, self.mated_bull_btn]:
            btn.setStyleSheet(normal_style)
        
        # 创建内容区域
        content_area = QWidget()
        content_layout = QStackedLayout(content_area)
        
        # 将三个页面添加到内容区域
        content_layout.addWidget(self.cow_key_traits_page)
        content_layout.addWidget(self.bull_key_traits_page)
            # 将已配公牛页面添加到内容区域
        content_layout.addWidget(self.mated_bull_key_traits_page)

        
        # 按钮点击事件
        def on_cow_btn_clicked():
            self.cow_btn.setStyleSheet(selected_style)
            self.bull_btn.setStyleSheet(normal_style)
            self.mated_bull_btn.setStyleSheet(normal_style)
            content_layout.setCurrentIndex(0)
        
        def on_bull_btn_clicked():
            self.cow_btn.setStyleSheet(normal_style)
            self.bull_btn.setStyleSheet(selected_style)
            self.mated_bull_btn.setStyleSheet(normal_style)
            content_layout.setCurrentIndex(1)
        
        def on_mated_bull_btn_clicked():
            self.cow_btn.setStyleSheet(normal_style)
            self.bull_btn.setStyleSheet(normal_style)
            self.mated_bull_btn.setStyleSheet(selected_style)
            content_layout.setCurrentIndex(2)
        
        # 连接按钮信号
        self.cow_btn.clicked.connect(on_cow_btn_clicked)
        self.bull_btn.clicked.connect(on_bull_btn_clicked)
        self.mated_bull_btn.clicked.connect(on_mated_bull_btn_clicked)
        
        # 添加按钮到布局
        button_layout.addWidget(self.cow_btn)
        button_layout.addWidget(self.bull_btn)
        button_layout.addWidget(self.mated_bull_btn)
        button_layout.addStretch()
        
        # 添加到主布局
        layout.addWidget(button_container)
        layout.addWidget(content_area)
        
        # 默认选中第一个按钮
        on_cow_btn_clicked()
        
        return page

    def create_content_area(self, layout):
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # 创建背景标签
        background_label = QLabel(container)
        image_path = Path(__file__).parent.parent / "homepage.jpg"
        if image_path.exists():
            pixmap = QPixmap(str(image_path))
            background_label.setPixmap(pixmap)
            background_label.setScaledContents(True)
        
        # 创建半透明遮罩层
        overlay = QWidget(container)
        overlay.setStyleSheet("background-color: rgba(255, 255, 255, 0.6);")
        
        # 创建内容栈
        self.content_stack = QStackedWidget(container)

        # 按顺序添加页面，每个页面只添加一次
        self.content_stack.addWidget(FarmSelectionPage())  # 第0页：伊起牛牧场数据选择
        self.create_project_page()         # 第1页：项目管理
        self.create_upload_page()          # 第2页：数据上传
        genetic_analysis_page = self.create_genetic_analysis_page()  # 第3页：关键育种性状分析
        self.content_stack.addWidget(genetic_analysis_page)
        self.content_stack.addWidget(self.index_calculation_page)    # 第4页：指数计算排名
        self.content_stack.addWidget(self.inbreeding_page)          # 第5页：近交分析页面
        self.content_stack.addWidget(self.create_mating_page())     # 第6页：个体选配页面（原第5页）
        self.content_stack.addWidget(self.create_report_generation_page())  # 第7页：自动化生成页面（原第6页）

        # 设置所有页面的背景为透明
        for i in range(self.content_stack.count()):
            page = self.content_stack.widget(i)
            page.setAutoFillBackground(False)
            page.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 设置组件的位置和大小
        def update_geometry():
            size = container.size()
            background_label.setGeometry(0, 0, size.width(), size.height())
            overlay.setGeometry(0, 0, size.width(), size.height())
            self.content_stack.setGeometry(0, 0, size.width(), size.height())

        container.resizeEvent = lambda e: update_geometry()
        container.setMinimumSize(800, 600)
        update_geometry()
        
        layout.addWidget(container)
        return self.content_stack  
    
    def create_project_page(self):
            """创建育种项目管理页面"""
            # 创建一个自定义的Page类
            class ProjectPage(QWidget):
                def __init__(self, parent=None):
                    super().__init__(parent)
                    self.main_window = parent  # 保存对主窗口的引用
                    self.init_ui()
                    
                def init_ui(self):
                    # 创建内容布局
                    self.main_layout = QVBoxLayout(self)
                    self.main_layout.setContentsMargins(10, 10, 10, 10)
                    
                    # 初始化UI组件
                    self.setup_ui_components()
                    
                def setup_ui_components(self):
                    # 路径显示和修改区域
                    path_layout = QHBoxLayout()
                    path_label = QLabel("当前路径:")
                    path_label.setStyleSheet("color: black;")  # 确保文字清晰可见
                    self.path_button = QPushButton(self.main_window.settings.get_default_storage())
                    self.path_button.clicked.connect(lambda: self.main_window.change_storage_location())
                    path_layout.addWidget(path_label)
                    path_layout.addWidget(self.path_button)
                    
                    # 文件系统模型
                    self.file_system_model = QFileSystemModel()
                    self.file_system_model.setRootPath(self.main_window.settings.get_default_storage())
                    self.file_system_model.setFilter(QDir.Filter.NoDotAndDotDot | QDir.Filter.AllEntries)
                    
                    # 创建树形视图
                    self.file_tree = QTreeView()
                    self.file_tree.setModel(self.file_system_model)
                    self.file_tree.setRootIndex(self.file_system_model.index(self.main_window.settings.get_default_storage()))
                    self.file_tree.setAnimated(False)
                    self.file_tree.setIndentation(20)
                    self.file_tree.setSortingEnabled(True)
                    self.file_tree.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
                    
                    # 连接双击事件
                    self.file_tree.doubleClicked.connect(self.on_file_double_clicked)
                    
                    # 设置右键菜单
                    self.file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                    self.file_tree.customContextMenuRequested.connect(self.show_context_menu)
                    
                    # 设置树形视图的样式
                    self.file_tree.setStyleSheet("""
                        QTreeView {
                            background-color: rgba(255, 255, 255, 0.7);
                            border: 1px solid #ccc;
                            border-radius: 5px;
                        }
                        QTreeView::item:hover {
                            background-color: rgba(200, 200, 200, 0.7);
                        }
                        QTreeView::item:selected {
                            background-color: rgba(51, 153, 255, 0.7);
                        }
                        QTreeView::item {
                            color: black;  /* 确保文字为黑色 */
                        }
                    """)
                    
                    # 调整列宽和表头
                    self.file_tree.setColumnWidth(0, 300)
                    self.file_tree.setHeaderHidden(False)
                    headers = ['名称', '修改日期', '类型', '大小']
                    for i, header in enumerate(headers):
                        if i < self.file_system_model.columnCount():
                            self.file_system_model.setHeaderData(i, Qt.Orientation.Horizontal, header)
                    
                    # 底部按钮区域
                    button_layout = QHBoxLayout()
                    button_style = """
                        QPushButton {
                            background-color: rgba(52, 152, 219, 0.8);
                            color: white;
                            border: none;
                            padding: 8px 20px;
                            border-radius: 4px;
                            min-width: 100px;
                        }
                        QPushButton:hover {
                            background-color: rgba(41, 128, 185, 0.8);
                        }
                    """
                    
                    # 创建按钮
                    create_btn = QPushButton("新建")
                    confirm_btn = QPushButton("确定")
                    delete_btn = QPushButton("删除")
                    
                    # 连接按钮信号
                    create_btn.clicked.connect(lambda: self.main_window.create_new_project())
                    confirm_btn.clicked.connect(lambda: self.main_window.select_project())
                    delete_btn.clicked.connect(lambda: self.main_window.delete_project())
                    
                    # 设置按钮样式
                    for btn in [create_btn, confirm_btn, delete_btn]:
                        btn.setStyleSheet(button_style)
                        button_layout.addWidget(btn)
                    
                    # 将所有组件添加到主布局
                    self.main_layout.addLayout(path_layout)
                    self.main_layout.addWidget(self.file_tree)
                    self.main_layout.addLayout(button_layout)
                    
                def on_file_double_clicked(self, index):
                    """双击文件时打开文件"""
                    if not index.isValid():
                        return
                    file_path = self.file_system_model.filePath(index)
                    path_obj = Path(file_path)
                    
                    if path_obj.is_file():
                        # 根据操作系统打开文件
                        import os
                        import platform
                        
                        if platform.system() == 'Windows':
                            os.startfile(str(path_obj))
                        elif platform.system() == 'Darwin':  # macOS
                            os.system(f'open "{str(path_obj)}"')
                        else:  # Linux
                            os.system(f'xdg-open "{str(path_obj)}"')
                    
                def show_context_menu(self, position):
                    """显示右键菜单"""
                    index = self.file_tree.indexAt(position)
                    if not index.isValid():
                        return
                        
                    file_path = self.file_system_model.filePath(index)
                    path_obj = Path(file_path)
                    
                    # 创建右键菜单
                    context_menu = QMenu(self)
                    
                    # 打开文件/文件夹
                    open_action = context_menu.addAction("打开")
                    open_action.triggered.connect(lambda: self.open_file_or_folder(path_obj))
                    
                    # 如果是文件，添加特定操作
                    if path_obj.is_file():
                        # 用Excel打开（如果是Excel文件）
                        if path_obj.suffix.lower() in ['.xlsx', '.xls']:
                            excel_action = context_menu.addAction("用Excel打开")
                            excel_action.triggered.connect(lambda: self.open_with_excel(path_obj))
                        
                        # 复制文件路径
                        copy_path_action = context_menu.addAction("复制文件路径")
                        copy_path_action.triggered.connect(lambda: self.copy_to_clipboard(str(path_obj)))
                    
                    # 如果是文件夹，添加文件夹特定操作
                    if path_obj.is_dir():
                        # 在文件管理器中显示
                        explorer_action = context_menu.addAction("在文件管理器中显示")
                        explorer_action.triggered.connect(lambda: self.show_in_explorer(path_obj))
                        
                        # 复制文件夹路径
                        copy_path_action = context_menu.addAction("复制文件夹路径")
                        copy_path_action.triggered.connect(lambda: self.copy_to_clipboard(str(path_obj)))
                    
                    context_menu.addSeparator()
                    
                    # 刷新
                    refresh_action = context_menu.addAction("刷新")
                    refresh_action.triggered.connect(self.refresh_file_tree)
                    
                    # 显示菜单
                    context_menu.exec(self.file_tree.mapToGlobal(position))
                    
                def open_file_or_folder(self, path_obj):
                    """打开文件或文件夹"""
                    import os
                    import platform
                    
                    if platform.system() == 'Windows':
                        os.startfile(str(path_obj))
                    elif platform.system() == 'Darwin':  # macOS
                        os.system(f'open "{str(path_obj)}"')
                    else:  # Linux
                        os.system(f'xdg-open "{str(path_obj)}"')
                        
                def open_with_excel(self, path_obj):
                    """用Excel打开文件"""
                    import os
                    import platform
                    
                    if platform.system() == 'Windows':
                        # Windows下尝试用Excel打开
                        os.system(f'start excel "{str(path_obj)}"')
                    elif platform.system() == 'Darwin':  # macOS
                        # macOS下尝试用Excel打开
                        os.system(f'open -a "Microsoft Excel" "{str(path_obj)}"')
                        
                def show_in_explorer(self, path_obj):
                    """在文件管理器中显示"""
                    import os
                    import platform
                    
                    if platform.system() == 'Windows':
                        os.startfile(str(path_obj))
                    elif platform.system() == 'Darwin':  # macOS
                        os.system(f'open "{str(path_obj)}"')
                    else:  # Linux
                        os.system(f'xdg-open "{str(path_obj)}"')
                        
                def copy_to_clipboard(self, text):
                    """复制文本到剪贴板"""
                    clipboard = QApplication.clipboard()
                    clipboard.setText(text)
                    
                def refresh_file_tree(self):
                    """刷新文件树"""
                    # 触发文件系统模型的刷新
                    root_path = self.file_system_model.rootPath()
                    self.file_system_model.setRootPath("")
                    self.file_system_model.setRootPath(root_path)
                    self.file_tree.setRootIndex(self.file_system_model.index(root_path))
            
            # 创建页面实例
            page = ProjectPage(self)
            self.content_stack.addWidget(page)
            
            # 保存必要的引用
            self.file_tree = page.file_tree
            self.file_system_model = page.file_system_model
            self.path_button = page.path_button
            
            return page


    def update_background_image(self):
        """更新背景图大小"""
        if hasattr(self, 'file_tree'):
            size = self.size()
            background_widget = self.file_tree.parent()
            if background_widget:
                image_path = Path(__file__).parent.parent / "homepage.jpg"
                if image_path.exists():
                    pixmap = QPixmap(str(image_path))
                    scaled_pixmap = pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio)
                    palette = background_widget.palette()
                    brush = QBrush(scaled_pixmap)
                    palette.setBrush(QPalette.ColorRole.Window, brush)
                    background_widget.setPalette(palette)

    def get_selected_project_path(self):
        """获取用户在树中选择的项目路径"""
        index = self.file_tree.currentIndex()
        if not index.isValid():
            return None
        file_path = self.file_system_model.filePath(index)
        return Path(file_path)


    def create_new_project(self):
        """创建新项目"""
        farm_name, ok = QInputDialog.getText(self, "新建项目", "请输入牧场名称:")
        if ok and farm_name:
            try:
                project_path = FileManager.create_project(Path(self.settings.get_default_storage()), farm_name)
                QMessageBox.information(self, "成功", f"已创建项目：{project_path.name}")
                
                # 刷新视图: QTreeView基于文件系统自动更新，如果未更新可重设 root index
                self.file_tree.setRootIndex(self.file_system_model.index(self.settings.get_default_storage()))
                
                # 自动选择新创建的项目
                self.select_project_by_path(project_path)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建项目失败：{str(e)}")

    def select_project_by_path(self, project_path: Path):
        """根据项目路径自动选择项目"""
        index = self.file_system_model.index(str(project_path))
        if index.isValid():
            self.file_tree.setCurrentIndex(index)
            self.file_tree.scrollTo(index, QAbstractItemView.ScrollHint.EnsureVisible)  # 确保视图滚动到选中的项目
            self.select_project()
            # 强制刷新模型（通过重新设置根路径）
            self.file_system_model.setRootPath(str(project_path.parent))
        else:
            QMessageBox.warning(self, "警告", f"无法找到项目路径: {project_path}")

    def select_project(self):
        """选择项目，并检查项目结构"""
        project_path = self.get_selected_project_path()
        if project_path is None:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return

        if not project_path.is_dir():
            QMessageBox.warning(self, "警告", "请选择一个项目文件夹")
            return

        if self.check_project_structure(project_path):
            QMessageBox.information(self, "成功", f"已选择项目：{project_path.name}")
            self.selected_project_path = project_path

            # TODO: 在这里添加选择项目后的逻辑
        else:
            QMessageBox.warning(self, "警告", "所选文件夹不是有效的项目文件夹")

    def update_nav_selected_style(self):
        """
        用户确认选择后更改选中项的样式表，以使选中项颜色更显眼（渐变蓝配色）
        """
        self.nav_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
                font-size: 14px;
            }

            QListWidget:focus {
                outline: none;
                border: none;
            }

            QListWidget::item {
                color: rgba(255, 255, 255, 0.85);
                padding: 12px 20px;
                margin: 3px 10px;
                border: none;
                font-weight: 500;
                background-color: transparent;
                border-radius: 8px;
            }
            QListWidget::item:selected {
                background-color: #f5f7fa;
                color: #456ba0;
                outline: none;
            }
            QListWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.2);
                color: white;
            }
            QListWidget::item:selected:hover {
                background-color: #f5f7fa;
                color: #456ba0;
            }

            QListWidget::item:focus {
                outline: none;
            }
        """)

    def check_project_structure(self, project_path: Path) -> bool:
        """检查项目文件夹结构是否完整"""
        required_dirs = {'raw_data', 'standardized_data', 'analysis_results', 'reports'}
        existing_dirs = {item.name for item in project_path.iterdir() if item.is_dir()}
        return required_dirs.issubset(existing_dirs)

    def delete_project(self):
        """删除选中的项目"""
        project_path = self.get_selected_project_path()
        if project_path is None:
            QMessageBox.warning(self, "警告", "请先选择要删除的项目")
            return

        if not project_path.is_dir():
            QMessageBox.warning(self, "警告", "请选择一个项目文件夹")
            return

        reply = QMessageBox.question(self, "确认删除", f"确定要删除项目 {project_path.name} 吗？此操作不可恢复！",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                FileManager.delete_project(project_path)
                QMessageBox.information(self, "成功", "项目已删除")
                # 刷新视图
                self.file_tree.setRootIndex(self.file_system_model.index(self.settings.get_default_storage()))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除失败：{str(e)}")

    def change_storage_location(self):
        """更改存储位置"""
        folder = QFileDialog.getExistingDirectory(self, "选择存储位置", self.settings.get_default_storage())
        if folder:
            self.settings.set_default_storage(folder)
            self.path_button.setText(folder)
            # 重设QFileSystemModel的根目录
            self.file_system_model.setRootPath(folder)
            self.file_tree.setRootIndex(self.file_system_model.index(folder))

    def on_nav_item_changed(self, index):
        current_item = self.nav_list.item(index)
        if current_item:
            text = current_item.text().strip()
            
            # 根据导航文本切换页面
            if text == "育种项目管理":
                self.content_stack.setCurrentIndex(0)  
            elif text == "数据上传":
                self.content_stack.setCurrentIndex(1)  
            elif text == "关键育种性状分析":
                self.content_stack.setCurrentIndex(2)
            elif text == "牛只指数计算排名":
                self.content_stack.setCurrentIndex(3)
            elif text == "近交系数及隐性基因分析":
                self.content_stack.setCurrentIndex(4)
            elif text == "个体选配":
                self.content_stack.setCurrentIndex(5)  # 添加个体选配页面的索引
            elif text == "自动化生成":
                self.content_stack.setCurrentIndex(6)  # 自动化生成页面

            # 切换到个体选配页面时刷新冻精预览
            if text == "个体选配" and hasattr(self, 'load_semen_preview'):
                print("[DEBUG-NAV] 切换到个体选配页面，刷新冻精预览...")
                self.load_semen_preview()
                # 同时刷新分组预览
                self.load_group_preview()
                # 更新表格样式以适应当前主题
                self.update_preview_tables_style()

            # 切换到自动化生成页面时刷新对比牧场选择列表
            if text == "自动化生成" and hasattr(self, 'load_benchmark_farms'):
                print("[DEBUG-NAV] 切换到自动化生成页面，刷新对比牧场选择列表...")
                self.load_benchmark_farms()
            
            self.update_nav_selected_style()

    # 新增"数据上传"页面函数
    def create_upload_page(self):
        page = QWidget()
        layout = QGridLayout(page)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        upload_items = [
            ("母牛数据", "cow_template.xlsx"),
            ("配种记录", "breeding_record_template.xlsx"),
            ("体型外貌数据", "body_conformation_template.xlsx"),
            ("备选公牛数据", "candidate_bull_template.xlsx"),
            ("基因组检测数据", "genomic_data_template.xlsx") 
        ]

        positions = [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0)]
        for (row, col), (display_name, template_file) in zip(positions, upload_items):
            cell_widget = self.create_upload_cell(display_name, template_file)
            cell_widget.setProperty("display_name", display_name)  # 设置 display_name 属性
            layout.addWidget(cell_widget, row, col)

        self.content_stack.addWidget(page)
    
    def create_report_generation_page(self):
        """创建自动化生成页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)

        # 标题
        title_label = QLabel("自动化报告生成")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 32px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 20px;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # 说明文字
        info_label = QLabel(
            "根据您已完成的分析数据，自动生成综合报告。\n"
            "报告将包含系谱分析、关键性状评估、育种指数分布和选配推荐等内容。"
        )
        info_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #7f8c8d;
                margin-bottom: 30px;
            }
        """)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 按钮容器
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(20)

        # PPT报告按钮
        ppt_button = QPushButton("生成PPT报告")
        ppt_button.setMinimumSize(200, 60)
        ppt_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
                padding: 15px 30px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        ppt_button.clicked.connect(self.on_generate_ppt)

        # Excel报告按钮
        excel_button = QPushButton("生成Excel报告")
        excel_button.setMinimumSize(200, 60)
        excel_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
                padding: 15px 30px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        excel_button.clicked.connect(self.on_generate_excel_report)
        excel_button.setToolTip("生成Excel综合报告（包含9个分析sheet）")

        button_layout.addStretch()
        button_layout.addWidget(ppt_button)
        button_layout.addWidget(excel_button)
        button_layout.addStretch()

        layout.addWidget(button_container)

        # 提示信息
        tip_label = QLabel(
            "提示：生成PPT报告前，请确保已完成以下分析：\n"
            "• 系谱识别情况分析\n"
            "• 母牛关键性状指数计算\n"
            "• 母牛育种指数计算"
        )
        tip_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #95a5a6;
                background-color: #ecf0f1;
                padding: 20px;
                border-radius: 5px;
                margin-top: 30px;
            }
        """)
        tip_label.setWordWrap(True)
        layout.addWidget(tip_label)

        # === 对比牧场选择区域 ===
        benchmark_group = QGroupBox("对比牧场选择")
        benchmark_group.setStyleSheet("""
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 20px;
                padding-top: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
        """)
        benchmark_layout = QVBoxLayout()

        # 顶部管理按钮
        top_layout = QHBoxLayout()

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新列表")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        refresh_btn.clicked.connect(self.load_benchmark_farms)
        top_layout.addWidget(refresh_btn)

        top_layout.addStretch()

        # 管理按钮
        manage_btn = QPushButton("管理对比牧场")
        manage_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        manage_btn.clicked.connect(self.open_benchmark_manager)
        top_layout.addWidget(manage_btn)

        benchmark_layout.addLayout(top_layout)

        # 对比数据选择表格（多选，包含对比牧场和外部参考数据）
        table_label = QLabel("选择对比数据（勾选用于报告生成）:")
        table_label.setStyleSheet("font-size: 14px; font-weight: normal; margin-top: 10px;")
        benchmark_layout.addWidget(table_label)

        from PyQt6.QtWidgets import QTableWidget
        self.comparison_sources_table = QTableWidget()
        self.comparison_sources_table.setMaximumHeight(200)
        self.comparison_sources_table.setColumnCount(5)
        self.comparison_sources_table.setHorizontalHeaderLabels(["选择", "类型", "名称", "摘要", "颜色"])
        self.comparison_sources_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.comparison_sources_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.comparison_sources_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.comparison_sources_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.comparison_sources_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.comparison_sources_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 5px;
            }
        """)
        self.comparison_sources_table.verticalHeader().setVisible(False)
        self.comparison_sources_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        # 添加双击事件，预览数据
        self.comparison_sources_table.cellDoubleClicked.connect(self.preview_comparison_data)

        benchmark_layout.addWidget(self.comparison_sources_table)

        # 说明文字
        help_label = QLabel(
            "提示：勾选对比数据后，将在报告中显示对比图表。"
            "对比牧场用于表格和折线图，外部参考数据仅用于折线图。"
            "双击可预览数据详情，点击颜色可修改对比线的显示颜色。"
        )
        help_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #95a5a6;
                padding: 10px;
                background-color: #ecf0f1;
                border-radius: 4px;
                margin-top: 10px;
            }
        """)
        help_label.setWordWrap(True)
        benchmark_layout.addWidget(help_label)

        benchmark_group.setLayout(benchmark_layout)
        layout.addWidget(benchmark_group)

        # 加载对比牧场列表
        self.load_benchmark_farms()

        layout.addStretch()

        return page
    
    # 在 handle_file_upload 方法中添加对基因组检测数据的处理逻辑
    def handle_file_upload(self, file_paths: list[Path], display_name: str):
        """根据上传类型选择不同的处理方法"""
        print(f"[DEBUG-MAIN-1] 开始处理文件上传: display_name={display_name}, file_paths={file_paths}")
        if self.selected_project_path is None:
            print("[DEBUG-MAIN-ERROR] 未选择项目")
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return

        if not file_paths:
            print("[DEBUG-MAIN-ERROR] 未提供文件路径")
            return

        # 根据 display_name 来选择不同的处理逻辑
        try:
            if display_name == "母牛数据":
                print("[DEBUG-MAIN-2] 处理母牛数据上传")
                # 使用 Worker 处理母牛数据，并显示进度条
                self.progress_dialog = ProgressDialog(self)
                self.progress_dialog.set_task_info("上传并处理母牛数据")
                self.progress_dialog.show()
                print("[DEBUG-MAIN-3] 创建进度对话框")

                self.thread = QThread()
                self.worker = CowDataWorker(file_paths, self.selected_project_path)
                self.worker.moveToThread(self.thread)
                print("[DEBUG-MAIN-4] 创建worker和线程")

                # 连接信号与槽
                self.thread.started.connect(self.worker.run)
                self.worker.progress.connect(self.progress_dialog.update_progress)
                self.worker.message.connect(self.progress_dialog.update_info)
                self.worker.finished.connect(self.on_worker_finished)
                self.worker.finished.connect(self.thread.quit)
                self.worker.finished.connect(self.worker.deleteLater)
                self.thread.finished.connect(self.thread.deleteLater)
                self.worker.error.connect(self.on_worker_error)
                print("[DEBUG-MAIN-5] 连接信号槽")

                self.thread.start()
                print("[DEBUG-MAIN-6] 线程已启动")
            elif display_name == "配种记录":
                print("[DEBUG-MAIN-7] 处理配种记录上传")
                # 检查是否已上传母牛数据
                cow_data_file = self.selected_project_path / "standardized_data" / "processed_cow_data.xlsx"
                if not cow_data_file.exists():
                    print("[DEBUG-MAIN-ERROR] 未找到母牛数据文件")
                    QMessageBox.warning(self, "警告", "请先上传并处理母牛数据，再上传配种记录")
                    return
                
                # 使用进度对话框处理配种记录
                self.progress_dialog = ProgressDialog(self)
                self.progress_dialog.set_task_info("上传并处理配种记录")
                self.progress_dialog.show()
                
                # 创建线程处理配种记录
                self.breeding_thread = QThread()
                self.breeding_worker = BreedingDataWorker(file_paths, self.selected_project_path)
                self.breeding_worker.moveToThread(self.breeding_thread)
                
                # 连接信号与槽
                self.breeding_thread.started.connect(self.breeding_worker.run)
                self.breeding_worker.progress.connect(self.progress_dialog.update_progress)
                self.breeding_worker.message.connect(self.progress_dialog.update_info)
                self.breeding_worker.finished.connect(self.on_breeding_worker_finished)
                self.breeding_worker.finished.connect(self.breeding_thread.quit)
                self.breeding_worker.finished.connect(self.breeding_worker.deleteLater)
                self.breeding_thread.finished.connect(self.breeding_thread.deleteLater)
                self.breeding_worker.error.connect(self.on_worker_error)
                
                self.breeding_thread.start()
            elif display_name == "基因组检测数据":
                # 处理基因组检测数据
                print("[DEBUG-MAIN-8] 处理基因组检测数据上传")
                self.progress_dialog = ProgressDialog(self)
                self.progress_dialog.set_task_info("上传并处理基因组检测数据")
                self.progress_dialog.show()

                self.genomic_thread = QThread()
                self.genomic_worker = GenomicDataWorker(file_paths, self.selected_project_path)
                self.genomic_worker.moveToThread(self.genomic_thread)

                # 连接信号与槽
                self.genomic_thread.started.connect(self.genomic_worker.run)
                self.genomic_worker.progress.connect(self.progress_dialog.update_progress)
                self.genomic_worker.message.connect(self.progress_dialog.update_info)
                self.genomic_worker.finished.connect(self.on_genomic_worker_finished)
                self.genomic_worker.finished.connect(self.genomic_thread.quit)
                self.genomic_worker.finished.connect(self.genomic_worker.deleteLater)
                self.genomic_thread.finished.connect(self.genomic_thread.deleteLater)
                self.genomic_worker.error.connect(self.on_worker_error)

                self.genomic_thread.start()
            else:
                # 其他数据类型直接处理
                print(f"[DEBUG-MAIN-9] 处理其他类型数据上传: {display_name}")
                final_path = None
                if display_name == "体型外貌数据":
                    final_path = upload_and_standardize_body_data(file_paths, self.selected_project_path)
                elif display_name == "备选公牛数据":
                    print(f"[DEBUG-MAIN-BULL] 处理备选公牛数据上传")
                    final_path = upload_and_standardize_bull_data(file_paths, self.selected_project_path)
                    # 添加刷新冻精预览的调用
                    if hasattr(self, 'load_semen_preview'):
                        print("[DEBUG-MAIN-BULL] 上传成功，尝试刷新冻精预览...")
                        self.load_semen_preview()
                    else:
                        print("[DEBUG-MAIN-BULL] 警告: load_semen_preview 方法不存在")
                else:
                    raise ValueError(f"未知的数据类型: {display_name}")

                QMessageBox.information(self, "成功", f"{display_name}文件已成功上传并标准化，标准化文件路径：{final_path}")
        except ValueError as ve:
            if "请先上传并处理母牛数据" in str(ve):
                print(f"[DEBUG-MAIN-ERROR] 需要先上传母牛数据: {ve}")
                QMessageBox.warning(self, "需要母牛数据", "请先上传并处理母牛数据，再上传配种记录")
            else:
                print(f"[DEBUG-MAIN-ERROR] 数值错误: {ve}")
                QMessageBox.warning(self, "警告", str(ve))
        except NotImplementedError as nie:
            print(f"[DEBUG-MAIN-ERROR] 功能未实现: {nie}")
            QMessageBox.warning(self, "功能未实现", str(nie))
        except Exception as e:
            print(f"[DEBUG-MAIN-ERROR] 文件上传或标准化时发生错误: {e}")
            import traceback
            print(traceback.format_exc())
            QMessageBox.critical(self, "错误", f"文件上传或标准化时发生错误：{str(e)}")
            
    def on_breeding_worker_finished(self, final_path: Path):
        """处理配种记录Worker完成的信号"""
        print(f"[DEBUG-MAIN] 配种记录处理完成: {final_path}")
        self.progress_dialog.close()
        QMessageBox.information(self, "成功", f"配种记录已成功上传并标准化，标准化文件路径：{final_path}")
        # 可以在这里添加更新UI或刷新数据的代码

    # 添加一个新的处理函数 for genomic data
    def on_genomic_worker_finished(self, final_path: Path):
        """处理 Genomic Worker 完成的信号"""
        self.progress_dialog.close()
        QMessageBox.information(self, "成功", f"基因组检测数据已成功上传并标准化，标准化文件路径：{final_path}")

    def on_worker_finished(self, final_path: Path):
        """处理 Worker 完成的信号"""
        self.progress_dialog.close()
        QMessageBox.information(self, "成功", f"母牛数据已成功上传并标准化，标准化文件路径：{final_path}")

    def on_worker_error(self, error_message: str):
        """处理 Worker 发生错误的信号"""
        print(f"[DEBUG-MAIN-ERROR] Worker错误: {error_message}")
        
        # 使用try-except包装，避免因线程已删除导致的崩溃
        try:
            # 先停止所有可能正在运行的线程
            if hasattr(self, 'thread') and self.thread and self.thread.isRunning():
                self.thread.quit()
                self.thread.wait(100)  # 最多等待100ms
                
            if hasattr(self, 'breeding_thread') and self.breeding_thread and self.breeding_thread.isRunning():
                self.breeding_thread.quit()
                self.breeding_thread.wait(100)  # 最多等待100ms
                
            if hasattr(self, 'genomic_thread') and self.genomic_thread and self.genomic_thread.isRunning():
                self.genomic_thread.quit()
                self.genomic_thread.wait(100)  # 最多等待100ms
        except RuntimeError as e:
            print(f"[DEBUG-MAIN-ERROR] 停止线程时出错: {e}")
        
        # 然后关闭进度对话框
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
            
        # 显示错误消息
        QMessageBox.critical(self, "错误", f"上传或标准化数据时发生错误：\n{error_message}")

    def create_upload_cell(self, display_name: str, template_file: str):
        frame = QFrame()
        v_layout = QVBoxLayout(frame)

        # 减小内部边距和间距，让布局更紧凑
        v_layout.setContentsMargins(0, 0, 0, 0)     # 减小内部边距
        v_layout.setSpacing(5)  # 减小间距

        # 拖拽区域
        drag_area = DragDropArea(frame)
        drag_area.setMinimumHeight(200)  # 根据需要调整拖拽区域的高度
        
        # 拖拽完成后调用不同的处理逻辑
        if display_name == "基因组检测数据":
            drag_area.dropped.connect(lambda file_path: self.handle_file_upload([file_path], display_name))
        else:
            drag_area.dropped.connect(lambda file_path: self.handle_file_upload([file_path], display_name))

        v_layout.addWidget(drag_area, alignment=Qt.AlignmentFlag.AlignCenter)

        # 调整按钮样式，使其更大、更醒目
        button_style = """
        QPushButton {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 10px 20px;       /* 增加按钮内边距，使按钮看起来更大 */
            border-radius: 4px;
            font-size: 14px;          /* 增大字体 */
            min-width: 150px;         /* 设置按钮的最小宽度 */
        }
        QPushButton:hover {
            background-color: #2980b9;
        }
        """
        button_style_down = """
        QPushButton {
            background-color: #6f7f91;
            color: white;
            border: none;
            padding: 6px 12px;       /* 增加按钮内边距，使按钮看起来更大 */
            border-radius: 4px;
            font-size: 12px;          /* 增大字体 */
            min-width: 100px;         /* 设置按钮的最小宽度 */
        }
        QPushButton:hover {
            background-color: #2980b9;
        }
        """

        # 下载模板按钮
        download_btn = QPushButton(f"下载{display_name}模板")
        download_btn.setStyleSheet(button_style_down)
        download_btn.clicked.connect(lambda: self.download_template(template_file))
        # 将按钮与拖拽框距离缩短：此时按钮直接放在拖拽框下方
        v_layout.addWidget(download_btn, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)   # 将按钮与拖拽框距离缩短

        # 上传按钮
        upload_btn = QPushButton(f"上传{display_name}")
        upload_btn.setStyleSheet(button_style)
        # 上传按钮点击后显示文件对话框并调用 handle_file_upload
        upload_btn.clicked.connect(lambda: self.select_file_and_upload(display_name))
        v_layout.addWidget(upload_btn, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        return frame

    def download_template(self, template_file: str):
        """下载模板文件"""
        source = self.templates_path / template_file
        if not source.exists():
            QMessageBox.warning(self, "警告", f"模板文件{template_file}不存在！")
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "保存模板文件", template_file)
        if save_path:
            try:
                shutil.copy2(source, save_path)
                QMessageBox.information(self, "成功", f"已保存模板到: {save_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存模板失败: {str(e)}")

    def select_file_and_upload(self, display_name: str):
        """选择文件后调用通用处理函数"""
        if self.selected_project_path is None:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return

        # 打开文件选择对话框，支持Excel和CSV文件
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, 
            f"选择{display_name}文件", 
            "", 
            "Excel Files (*.xlsx *.xls);;CSV Files (*.csv)"
        )
        if not file_paths:
            return  # 用户未选择文件

        try:
            # 将用户选择的路径转为Path对象列表
            input_files = []
            for p in file_paths:
                try:
                    # 处理路径可能包含的中文字符
                    path_obj = Path(p)
                    # 检查路径是否存在
                    if not path_obj.exists():
                        raise FileNotFoundError(f"文件不存在: {p}")
                    input_files.append(path_obj)
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"处理文件路径时出错: {p}\n错误: {str(e)}")
                    return

            # 调用上传处理逻辑
            self.handle_file_upload(input_files, display_name)
        except Exception as e:
            import traceback
            error_msg = f"处理文件路径时出错: {str(e)}\n{traceback.format_exc()}"
            QMessageBox.critical(self, "错误", error_msg)
            logging.error(error_msg)

    def check_and_update_database_on_startup(self):
        """在应用启动时自动检查和更新数据库"""
        # Ensure the main window is visible before showing progress dialog
        if not self.isVisible():
            return
        
        # Force the window to update on Windows
        if sys.platform == 'win32':
            QApplication.processEvents()
            
        try:
            self.progress_dialog = ProgressDialog(self)
            self.progress_dialog.setWindowTitle("数据库更新")
            self.progress_dialog.title_label.setText("正在检查和更新本地数据库...")
            self.progress_dialog.progress_bar.setRange(0, 100)  # 显示0-100%进度
            self.progress_dialog.progress_bar.setValue(0)
            # Make sure the dialog is non-modal
            self.progress_dialog.setWindowModality(Qt.WindowModality.NonModal)
            self.progress_dialog.show()
        except Exception as e:
            logging.error(f"创建进度对话框失败: {e}")
            # If dialog creation fails, still try to update database
            pass

        # 创建线程和 worker
        self.db_update_thread = QThread()
        self.db_update_worker = DBUpdateWorker()
        self.db_update_worker.moveToThread(self.db_update_thread)

        # 连接信号与槽
        self.db_update_thread.started.connect(self.db_update_worker.run)
        self.db_update_worker.progress.connect(self.on_db_update_progress)
        self.db_update_worker.message.connect(self.on_db_update_message)
        self.db_update_worker.finished.connect(self.on_db_update_finished)
        self.db_update_worker.error.connect(self.on_db_update_error)
        self.db_update_worker.finished.connect(self.db_update_thread.quit)
        self.db_update_worker.finished.connect(self.db_update_worker.deleteLater)
        self.db_update_thread.finished.connect(self.db_update_thread.deleteLater)
        self.db_update_worker.error.connect(self.db_update_thread.quit)
        self.db_update_worker.error.connect(self.db_update_worker.deleteLater)

        # 延迟启动数据库检查线程，等待版本检查完成
        def start_db_check():
            logging.info("第二步：开始检查数据库更新...")
            self.db_update_thread.start()
        
        # 延迟1秒启动，确保版本检查先执行
        QTimer.singleShot(1000, start_db_check)

    def on_db_update_progress(self, progress: int):
        """处理数据库更新进度"""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.progress_bar.setValue(progress)
            # 在标题栏显示百分比
            self.progress_dialog.setWindowTitle(f"数据库更新 - {progress}%")

    def on_db_update_message(self, message: str):
        """处理数据库更新消息"""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.title_label.setText(message)

    def on_db_update_finished(self, version_info: str = ""):
        """处理数据库更新完成的信号"""
        try:
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.close()
                self.progress_dialog = None
        except:
            pass

        # 解析版本信息
        if version_info and '#' in version_info:
            version, update_time = version_info.split('#', 1)
            message = f"数据库版本已更新为 {version} ({update_time})"
        else:
            # 如果没有版本信息，从数据库获取
            from core.data.update_manager import get_local_db_version_with_time
            version, update_time = get_local_db_version_with_time()
            if version and update_time:
                message = f"数据库版本已更新为 {version} ({update_time})"
            else:
                # 最后备用消息
                message = "本地数据库已成功检查和更新。"

        # 更新侧边栏的数据库版本显示
        if hasattr(self, 'db_version_label'):
            try:
                from core.data.update_manager import get_local_db_version_with_time
                db_version, db_update_time = get_local_db_version_with_time()
                if db_version and db_update_time:
                    # 格式化日期
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(db_update_time)
                        formatted_time = dt.strftime('%Y-%m-%d')
                    except:
                        formatted_time = db_update_time[:10] if len(db_update_time) >= 10 else db_update_time

                    self.db_version_label.setText(f"数据库版本: {db_version}\n数据库更新时间: {formatted_time}")
                else:
                    self.db_version_label.setText("数据库版本: 未知")
            except Exception as e:
                logging.error(f"更新数据库版本显示时出错: {e}")
                self.db_version_label.setText("数据库版本: 获取失败")

        # 如果是 cs 用户，显示数据库存储位置
        if hasattr(self, 'username') and self.username == "cs":
            try:
                from core.data.update_manager import LOCAL_DB_PATH
                message += f"\n\n数据库本地存储位置：\n{str(LOCAL_DB_PATH)}"
            except Exception as e:
                logging.error(f"获取数据库路径时出错: {e}")

        logging.info(message)

        # 直接显示消息，不使用消息框避免阻塞
        # 或者可以使用定时器延迟显示
        if hasattr(self, 'username') and self.username == "cs":
            # 对于cs用户，仅记录日志，不显示消息框
            logging.info("数据库更新完成 - cs用户跳过消息框")
        else:
            # 对于其他用户，延迟显示消息框
            QTimer.singleShot(100, lambda: self.show_db_update_message(message))

    def show_db_update_message(self, message: str):
        """显示数据库更新完成消息"""
        try:
            QMessageBox.information(self, "更新完成", message)
        except Exception as e:
            logging.error(f"显示更新消息时出错: {e}")

    def on_db_update_error(self, error_message: str):
        """处理数据库更新错误的信号"""
        try:
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.close()
                self.progress_dialog = None
        except:
            pass

        # 记录详细错误到日志
        logging.error(f"数据库更新错误详情: {error_message}")

        # 判断错误类型并给出友好提示
        is_critical = False  # 是否是关键错误
        friendly_message = "数据库更新失败"

        # 检查是否是OSS下载失败
        if "下载失败" in error_message or "OSS" in error_message or "genetic-improve.oss" in error_message:
            is_critical = True
            friendly_message = "数据库下载失败\n\n数据库是程序运行的必要组件，必须下载成功才能继续。\n\n可能的原因：\n1. 网络连接不稳定\n2. 下载过程被中断\n3. 服务器暂时不可用\n\n请检查网络连接后重试。"
        elif "Can't connect to MySQL server" in error_message:
            friendly_message = "无法连接到数据库服务器，请检查您的网络连接。\n\n程序将使用本地数据库继续运行。"
        elif "nodename nor servname provided" in error_message:
            friendly_message = "网络连接异常，无法解析服务器地址。\n\n程序将使用本地数据库继续运行。"
        elif "timed out" in error_message.lower():
            is_critical = True  # 超时也可能是下载过程中断
            friendly_message = "连接超时\n\n数据库下载超时，请检查网络连接稳定性。\n\n数据库文件较大（132MB），需要稳定的网络连接。"
        elif "Access denied" in error_message:
            friendly_message = "数据库访问被拒绝。\n\n请联系管理员检查权限设置。"
        else:
            # 对于其他错误，只显示简短信息
            friendly_message = "数据库同步失败。\n\n程序将使用本地数据库继续运行。"

        # 显示错误对话框，如果是关键错误，提供重试选项
        if is_critical:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("数据库更新失败")
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setText(friendly_message)

            # 添加重试和退出按钮
            retry_button = msg_box.addButton("重试", QMessageBox.ButtonRole.AcceptRole)
            exit_button = msg_box.addButton("退出程序", QMessageBox.ButtonRole.RejectRole)

            msg_box.exec()

            if msg_box.clickedButton() == retry_button:
                # 重试数据库更新
                logging.info("用户选择重试数据库更新")
                QTimer.singleShot(500, self.check_and_update_database)
            else:
                # 退出程序
                logging.info("用户选择退出程序")
                QMessageBox.information(self, "退出程序", "由于数据库是必要组件，程序将退出。\n\n请修复网络问题后重新启动程序。")
                QApplication.quit()
        else:
            # 非关键错误，只显示警告
            QMessageBox.warning(self, "数据库同步提示", friendly_message)

    def show_sub_nav_menu(self, pos, sub_items):
        """显示子导航菜单"""
        menu = QMenu(self)
        for item in sub_items:
            action = menu.addAction(item)
            action.triggered.connect(lambda checked, text=item: self.handle_sub_nav_click(text))
        menu.exec(pos)

    def handle_sub_nav_click(self, text):
        """处理子导航项点击事件"""
        if text == "在群母牛关键性状计算":
            # TODO: 连接到 cow_traits_calc.py 的功能
            pass
        elif text == "在群母牛指数计算及排名":
            # TODO: 连接到 index_calc.py 的功能
            pass        


    def on_nav_item_entered(self, item):
        """处理鼠标进入导航项事件"""
        sub_items = item.data(Qt.ItemDataRole.UserRole)
        if sub_items:
            # 获取项目在视图中的位置
            rect = self.nav_list.visualItemRect(item)
            global_pos = self.nav_list.mapToGlobal(rect.topRight())
            self.show_sub_nav_menu(global_pos, sub_items)  

    def create_mating_page(self):
        """创建个体选配页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # 顶部 - 选配参数设置区域
        param_group = QGroupBox("选配参数设置")
        param_layout = QVBoxLayout()
        
        # 近交系数阈值设置
        inbreeding_layout = QHBoxLayout()
        inbreeding_label = QLabel("近交系数阈值:")
        self.inbreeding_combo = QComboBox()
        self.inbreeding_combo.addItems(["≤3.125%", "≤6.25%", "≤12.5%", "无视近交"])
        self.inbreeding_combo.setCurrentIndex(1)  # 默认选择6.25%
        inbreeding_layout.addWidget(inbreeding_label)
        inbreeding_layout.addWidget(self.inbreeding_combo)
        inbreeding_layout.addStretch()
        
        # 隐性基因控制设置
        gene_control_layout = QHBoxLayout()
        self.gene_control_checkbox = QCheckBox("控制隐性基因")
        self.gene_control_checkbox.setChecked(True)
        gene_control_layout.addWidget(self.gene_control_checkbox)
        gene_control_layout.addStretch()
        
        # 添加手动分组和分组更新按钮
        button_layout = QHBoxLayout()
        self.manual_group_btn = QPushButton("手动分组")
        update_group_btn = QPushButton("分组更新")
        self.auto_group_btn = QPushButton("自动分组")
        
        # 设置按钮样式
        button_style = """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """
        self.manual_group_btn.setStyleSheet(button_style)
        update_group_btn.setStyleSheet(button_style)
        self.auto_group_btn.setStyleSheet(button_style)

        # 连接按钮信号
        self.manual_group_btn.clicked.connect(self.on_manual_grouping)
        update_group_btn.clicked.connect(self.on_update_grouping)
        self.auto_group_btn.clicked.connect(self.on_auto_grouping)

        button_layout.addWidget(self.manual_group_btn)
        button_layout.addWidget(update_group_btn)
        button_layout.addWidget(self.auto_group_btn)
        button_layout.addStretch()
        
        param_layout.addLayout(inbreeding_layout)
        param_layout.addLayout(gene_control_layout)
        param_layout.addLayout(button_layout)
        param_group.setLayout(param_layout)
        
        # 中部 - 分组预览区域
        preview_group = QGroupBox("分组预览")
        preview_layout = QVBoxLayout()
        
        # 添加全选/取消全选按钮
        select_button_layout = QHBoxLayout()
        self.select_all_button = QPushButton("全选")
        self.select_all_button.setCheckable(True)
        self.select_all_button.clicked.connect(self.toggle_group_checkboxes)
        select_button_layout.addWidget(self.select_all_button)
        select_button_layout.addStretch()
        preview_layout.addLayout(select_button_layout)
        
        # 创建分组预览表格 - **确保列数为9**
        self.group_preview_table = QTableWidget()
        self.group_preview_table.setColumnCount(9) # 修正为9列
        self.group_preview_table.setHorizontalHeaderLabels([
            "勾选", "组名", "头数",
            "1选常规未分配", "2选常规未分配", "3选常规未分配",
            "1选性控未分配", "2选性控未分配", "3选性控未分配" # 确保这里也是9个标题
        ])

        # 应用预览表格样式（浅色模式下返回空字符串，保持默认样式）
        style = theme_manager.get_preview_table_style()
        if style:
            self.group_preview_table.setStyleSheet(style)
        
        # 设置列宽和样式
        self.group_preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.group_preview_table.setColumnWidth(0, 50)
        
        # 其他列使用Stretch模式
        for i in range(1, 9):
            self.group_preview_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            
        preview_layout.addWidget(self.group_preview_table)
        
        # 添加选配操作按钮
        mating_button_layout = QHBoxLayout()
        clear_mating_btn = QPushButton("清空选配")
        generate_recommendations_btn = QPushButton("执行个体选配")
        # start_mating_btn = QPushButton("开始选配")  # 隐藏开始选配按钮

        # 添加推送结果按钮
        self.push_result_btn = QPushButton("📤 推送结果")
        self.push_result_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                min-width: 120px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.push_result_btn.clicked.connect(self.on_push_mating_results)
        self.push_result_btn.setEnabled(False)  # 初始禁用，选配完成后启用

        clear_mating_btn.setStyleSheet(button_style)
        generate_recommendations_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                min-width: 150px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        # start_mating_btn.setStyleSheet(button_style)  # 隐藏开始选配按钮

        clear_mating_btn.clicked.connect(self.on_clear_mating)
        generate_recommendations_btn.clicked.connect(self.on_execute_complete_mating)
        # start_mating_btn.clicked.connect(self.on_start_mating)  # 隐藏开始选配按钮
        
        # 添加选配分配按钮
        allocate_mating_btn = QPushButton("选配分配")
        allocate_mating_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        allocate_mating_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #27ae60; }
            QPushButton:pressed { background-color: #229954; }
        """)
        allocate_mating_btn.clicked.connect(self.on_allocate_mating)
        
        mating_button_layout.addWidget(clear_mating_btn)
        mating_button_layout.addWidget(generate_recommendations_btn)
        mating_button_layout.addWidget(self.push_result_btn)  # 添加推送按钮
        # mating_button_layout.addWidget(allocate_mating_btn)  # 注释掉，使用一键完成
        # mating_button_layout.addWidget(start_mating_btn)  # 隐藏开始选配按钮
        mating_button_layout.addStretch()
        
        preview_layout.addLayout(mating_button_layout)
        preview_group.setLayout(preview_layout)
        
        # 底部 - 冻精预览区域
        semen_group = QGroupBox("冻精预览")
        semen_layout = QVBoxLayout()
        
        # 冻精预览标签页
        self.semen_tab_widget = QTabWidget()
        semen_layout.addWidget(self.semen_tab_widget)
        semen_group.setLayout(semen_layout)
        
        # 将所有区域添加到主布局
        layout.addWidget(param_group)
        layout.addWidget(preview_group)
        layout.addWidget(semen_group)
        
        # 设置整体样式
        style = """
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ccc;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QComboBox, QPushButton {
                min-width: 100px;
                padding: 5px;
            }
            QCheckBox {
                padding: 5px;
            }
            QLabel {
                font-size: 12px;
            }
            QTableWidget {
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 5px;
                border: none;
                border-right: 1px solid #ccc;
                border-bottom: 1px solid #ccc;
            }
        """
        page.setStyleSheet(style)
        
        # 加载分组和冻精预览数据
        self.load_group_preview()
        self.load_semen_preview()
        
        return page

    def load_group_preview(self):
        """加载分组预览数据"""
        if not self.selected_project_path:
            return
        
        index_file = self.selected_project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
        if not index_file.exists():
            return

        try:
            import pandas as pd
            
            # 读取指数文件
            df = pd.read_excel(index_file)
            
            # 只保留在场母牛
            df = df[(df['sex'] == '母') & (df['是否在场'] == '是')]
            
            # 检查是否有group列
            if 'group' not in df.columns:
                # 如果没有group列，创建一个空的分组预览表
                self.group_preview_table.setRowCount(0)
                return
            
            # 统计每个组的数量（包括空值）
            # 创建一个副本用于显示，避免修改原始数据
            display_df = df.copy()

            # 将空值替换为"未分组"以便统计和显示
            display_df['group'] = display_df['group'].fillna('未分组')
            display_df['group'] = display_df['group'].replace('', '未分组')  # 空字符串也算未分组

            # 将数字转换为字符串（如果有数字分组）
            display_df['group'] = display_df['group'].astype(str)

            # 统计每个组的数量
            group_counts = display_df.groupby('group').size().reset_index(name='count')
            
            # 清空现有表格
            self.group_preview_table.setRowCount(0)
            
            # 加载选配报告并计算未分配数量
            unassigned_counts = {
                '1选常规未分配': {},
                '2选常规未分配': {},
                '3选常规未分配': {},
                '1选性控未分配': {},
                '2选性控未分配': {},
                '3选性控未分配': {}
            }

            # 尝试读取选配报告
            report_files = [
                self.selected_project_path / "analysis_results" / "个体选配报告.xlsx",
                self.selected_project_path / "analysis_results" / "individual_mating_report.xlsx"
            ]

            report_df = None
            for report_file in report_files:
                if report_file.exists():
                    try:
                        report_df = pd.read_excel(report_file)
                        break
                    except:
                        pass

            # 如果找到报告，计算未分配数量
            if report_df is not None:
                # 检查列名是'group'还是'分组'
                group_col = 'group' if 'group' in report_df.columns else '分组' if '分组' in report_df.columns else None

                if group_col:
                    # 对每个组计算未分配数量
                    for group_name in display_df['group'].unique():
                        group_report = report_df[report_df[group_col] == group_name]
                        total_in_group = len(group_report)

                        if total_in_group > 0:
                            # 计算常规未分配
                            unassigned_counts['1选常规未分配'][group_name] = len(group_report[group_report['1选常规'].isna() | (group_report['1选常规'] == '')])
                            unassigned_counts['2选常规未分配'][group_name] = len(group_report[group_report['2选常规'].isna() | (group_report['2选常规'] == '')])
                            unassigned_counts['3选常规未分配'][group_name] = len(group_report[group_report['3选常规'].isna() | (group_report['3选常规'] == '')])

                            # 计算性控未分配
                            unassigned_counts['1选性控未分配'][group_name] = len(group_report[group_report['1选性控'].isna() | (group_report['1选性控'] == '')])
                            unassigned_counts['2选性控未分配'][group_name] = len(group_report[group_report['2选性控'].isna() | (group_report['2选性控'] == '')])
                            unassigned_counts['3选性控未分配'][group_name] = len(group_report[group_report['3选性控'].isna() | (group_report['3选性控'] == '')])
                        else:
                            # 如果报告中没有这个组，说明该组还未选配，全部为未分配
                            group_total = len(display_df[display_df['group'] == group_name])
                            for key in unassigned_counts:
                                unassigned_counts[key][group_name] = group_total
            else:
                # 如果没有报告，所有组的所有位置都是未分配（等于总数）
                for group_name in display_df['group'].unique():
                    group_total = len(display_df[display_df['group'] == group_name])
                    for key in unassigned_counts:
                        unassigned_counts[key][group_name] = group_total
            
            # 逐行填充表格
            self.group_preview_table.setRowCount(len(group_counts))
            for row, (_, group_row) in enumerate(group_counts.iterrows()):
                group_name = group_row['group']
                total_count = group_row['count']
                
                # 创建勾选框
                checkbox = QCheckBox()
                checkbox_container = QWidget()
                checkbox_layout = QHBoxLayout(checkbox_container)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                checkbox_layout.setContentsMargins(0, 0, 0, 0)
                self.group_preview_table.setCellWidget(row, 0, checkbox_container)
                
                # 设置组名和头数
                self.group_preview_table.setItem(row, 1, QTableWidgetItem(str(group_name)))
                self.group_preview_table.setItem(row, 2, QTableWidgetItem(str(total_count)))
                
                # 设置未分配数量列（6列），使用实际计算的值或总数作为默认值
                self.group_preview_table.setItem(row, 3, QTableWidgetItem(str(unassigned_counts['1选常规未分配'].get(group_name, total_count))))
                self.group_preview_table.setItem(row, 4, QTableWidgetItem(str(unassigned_counts['2选常规未分配'].get(group_name, total_count))))
                self.group_preview_table.setItem(row, 5, QTableWidgetItem(str(unassigned_counts['3选常规未分配'].get(group_name, total_count))))
                self.group_preview_table.setItem(row, 6, QTableWidgetItem(str(unassigned_counts['1选性控未分配'].get(group_name, total_count))))
                self.group_preview_table.setItem(row, 7, QTableWidgetItem(str(unassigned_counts['2选性控未分配'].get(group_name, total_count))))
                self.group_preview_table.setItem(row, 8, QTableWidgetItem(str(unassigned_counts['3选性控未分配'].get(group_name, total_count))))
            
            # 调整表格显示
            self.group_preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        except Exception as e:
            print(f"加载分组预览数据时出错: {str(e)}")
            import traceback
            print(traceback.format_exc())

    def load_semen_preview(self):
        """加载冻精预览，直接读写 processed_bull_data.xlsx"""
        if not self.selected_project_path:
            print("[SemenPreview] 未选择项目路径")
            return
        
        bull_file = self.selected_project_path / "standardized_data" / "processed_bull_data.xlsx"
        if not bull_file.exists():
            print(f"[SemenPreview] 备选公牛文件不存在: {bull_file}")
            if hasattr(self, 'semen_tab_widget'):
                self.semen_tab_widget.clear()
                empty_widget = QWidget()
                empty_layout = QVBoxLayout(empty_widget)
                empty_layout.addWidget(QLabel("请先上传备选公牛数据"))
                self.semen_tab_widget.addTab(empty_widget, "无数据")
            return
            
        engine = None
        try:
            import pandas as pd
            from sqlalchemy import create_engine, text
            from core.data.update_manager import LOCAL_DB_PATH

            print(f"[SemenPreview] 开始读取备选公牛文件: {bull_file}")
            df = pd.read_excel(bull_file)
            # 预处理，确保列存在且为字符串
            if 'bull_id' not in df.columns:
                 print("[SemenPreview] Error: processed_bull_data.xlsx 缺少 'bull_id' 列.")
                 return
            if 'semen_type' not in df.columns:
                 df['semen_type'] = '' # 如果缺少则添加空列
                 print("[SemenPreview] Warning: processed_bull_data.xlsx 缺少 'semen_type' 列, 已添加空列.")
            df['bull_id'] = df['bull_id'].astype(str).str.strip()
            df['semen_type'] = df['semen_type'].astype(str).str.strip()
            df = df[df['bull_id'].notna() & (df['bull_id'] != '') & (df['bull_id'].str.lower() != 'nan')]
            # 保留所有行，不去重（同一公牛可能有多种冻精类型）
            df = df.reset_index(drop=True)
            print(f"[SemenPreview] 文件中有效的公牛数据行数: {len(df)}")

            if hasattr(self, 'semen_tab_widget'):
                self.semen_tab_widget.clear()
            else:
                print("[SemenPreview] 错误：semen_tab_widget 未初始化")
                return

            # --- 支数加载逻辑 ---
            # 使用(bull_id, semen_type)作为复合键存储支数
            counts_dict = {}
            count_col_name = None
            if '支数' in df.columns:
                count_col_name = '支数'
            elif 'count' in df.columns:
                count_col_name = 'count'

            if count_col_name:
                print(f"[SemenPreview] 从文件列 '{count_col_name}' 加载支数...")
                # 确保列是数值类型，无效值转为0
                df[count_col_name] = pd.to_numeric(df[count_col_name], errors='coerce').fillna(0).astype(int)
                # 使用(bull_id, semen_type)复合键
                for _, row in df.iterrows():
                    key = (str(row['bull_id']), str(row['semen_type']))
                    counts_dict[key] = int(row[count_col_name])
                print(f"[SemenPreview] 加载了 {len(counts_dict)} 条支数记录（使用复合键）")
            else:
                print("[SemenPreview] 文件中未找到 '支数' 或 'count' 列，将创建 '支数' 列并初始化为0。")
                df['支数'] = 0 # 添加新列并初始化
                for _, row in df.iterrows():
                    key = (str(row['bull_id']), str(row['semen_type']))
                    counts_dict[key] = 0

            # --- 保存更新后的 DataFrame 回 processed_bull_data.xlsx ---
            # 在填充表格前先保存一次，确保支数信息持久化
            try:
                print(f"[SemenPreview] 尝试保存更新后的数据回: {bull_file}")
                # 删除classification列（如果存在）
                if 'classification' in df.columns:
                    df = df.drop(columns=['classification'])
                df.to_excel(bull_file, index=False)
                print(f"[SemenPreview] 已成功保存更新后的支数到: {bull_file}")
            except PermissionError:
                QMessageBox.critical(self, "保存失败", f"""无法保存更新后的备选公牛数据。
文件 {bull_file.name} 可能被其他程序占用。
请关闭文件后重试。""")
                return # 保存失败则不继续填充预览
            except Exception as e:
                print(f"[SemenPreview] 保存更新后的备选公牛数据失败: {e}")
                QMessageBox.critical(self, "保存失败", f"无法保存更新后的备选公牛数据: {e}")
                return # 保存失败则不继续填充预览

            # --- 填充预览表格 ---
            new_headers = [
                "冻精编号", 'NM$', 'TPI', 'MILK', 'FAT', 'FAT %', 'PROT', 'PROT%',
                'PL', 'DPR', 'UDC', 'FLC', 'RFI', "支数"
            ]
            trait_columns_db = [
                'NM$', 'TPI', 'MILK', 'FAT', 'FAT %', 'PROT', 'PROT%',
                'PL', 'DPR', 'UDC', 'FLC', 'RFI'
            ]

            self.semen_tables = {}
            engine = create_engine(f'sqlite:///{LOCAL_DB_PATH}')

            main_categories = ["常规", "性控"]
            # 直接使用semen_type筛选数据（不再使用classification）
            bull_data_by_category = {
                cat: df[df['semen_type'] == cat][['bull_id', 'semen_type']].values.tolist()
                for cat in main_categories
            }

            with engine.connect() as conn:
                for category in main_categories:
                    print(f"[SemenPreview] 创建标签页: {category}")
                    type_widget = QWidget()
                    type_layout = QVBoxLayout(type_widget)

                    semen_table = QTableWidget()
                    semen_table.setColumnCount(len(new_headers))
                    semen_table.setHorizontalHeaderLabels(new_headers)

                    # 应用预览表格样式（浅色模式下返回空字符串，保持默认样式）
                    style = theme_manager.get_preview_table_style()
                    if style:
                        semen_table.setStyleSheet(style)

                    bull_data_in_category = bull_data_by_category[category]
                    print(f"[SemenPreview] 类别 '{category}' 找到 {len(bull_data_in_category)} 条数据")
                    semen_table.setRowCount(len(bull_data_in_category))

                    for i, (bull_id, semen_type) in enumerate(bull_data_in_category):
                        # 设置冻精编号
                        id_item = QTableWidgetItem(bull_id)
                        id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        semen_table.setItem(i, 0, id_item)

                        # 查询数据库获取性状（只使用bull_id，不考虑semen_type）
                        trait_values = {}
                        try:
                            query_str = f"SELECT {', '.join(f'`{t}`' for t in trait_columns_db)} FROM bull_library WHERE `BULL NAAB` = :bull_id OR `BULL REG` = :bull_id LIMIT 1"
                            query = text(query_str)
                            result = conn.execute(query, {'bull_id': bull_id}).fetchone()
                            if result:
                                trait_values = dict(result._mapping)
                        except Exception as db_err:
                            print(f"[SemenPreview] DB Error querying traits for {bull_id}: {db_err}")

                        # 填充性状列
                        for j, trait_name in enumerate(trait_columns_db):
                            value = trait_values.get(trait_name, '')
                            trait_item = QTableWidgetItem(str(value))
                            trait_item.setFlags(trait_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                            trait_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            semen_table.setItem(i, j + 1, trait_item)

                        # 设置支数列 (使用复合键从 counts_dict 获取)
                        count_key = (bull_id, semen_type)
                        count_item = QTableWidgetItem(str(counts_dict.get(count_key, 0)))
                        count_item.setFlags(count_item.flags() | Qt.ItemFlag.ItemIsEditable)
                        count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        font = QFont()
                        font.setBold(True)
                        font.setUnderline(True)
                        count_item.setFont(font)
                        editable_color = QColor(255, 255, 224)
                        count_item.setBackground(editable_color)
                        semen_table.setItem(i, 13, count_item)

                    # 调整表格设置
                    # 设置表头可以调整大小
                    semen_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
                    # 设置冻精编号列较宽
                    semen_table.setColumnWidth(0, 150)  # 冻精编号列
                    # 设置其他列的默认宽度
                    for col in range(1, 13):  # 性状列
                        semen_table.setColumnWidth(col, 80)
                    semen_table.setColumnWidth(13, 60)  # 支数列
                    # 设置最小列宽
                    semen_table.horizontalHeader().setMinimumSectionSize(50)
                    # 允许最后一列拉伸以填充剩余空间
                    semen_table.horizontalHeader().setStretchLastSection(True)
                    header_item = semen_table.horizontalHeaderItem(13)
                    if header_item:
                        header_font = header_item.font()
                        header_font.setBold(True)
                        header_item.setFont(header_font)
                    semen_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
                    semen_table.cellChanged.connect(self.handle_semen_count_changed)

                    # 应用当前主题样式
                    style = theme_manager.get_preview_table_style()
                    if style:
                        semen_table.setStyleSheet(style)

                    type_layout.addWidget(semen_table)
                    self.semen_tables[category] = semen_table
                    self.semen_tab_widget.addTab(type_widget, category)

            # 移除延时保存，因为数据在填充前已保存
            # QTimer.singleShot(1000, self.save_all_semen_counts)
            print("[SemenPreview] 冻精预览加载完成")

        except Exception as e:
            print(f"[SemenPreview] 加载冻精预览数据时出错: {str(e)}")
            import traceback
            print(traceback.format_exc())
            QMessageBox.critical(self, "错误", f"加载冻精预览时出错: {e}") # 向用户显示错误
        finally:
            if engine:
                engine.dispose()
                print("[SemenPreview] 数据库连接已关闭")

    def handle_semen_count_changed(self, row, column):
        """当冻精预览表中单元格内容改变时触发，但不再自动保存"""
        if column == 13: # 检查是否是支数列
            current_tab_index = self.semen_tab_widget.currentIndex()
            if current_tab_index < 0: return

            current_widget = self.semen_tab_widget.widget(current_tab_index)
            if not current_widget: return

            layout = current_widget.layout()
            if not layout or layout.count() == 0: return
            table = layout.itemAt(0).widget()
            if not isinstance(table, QTableWidget): return

            item = table.item(row, column)
            bull_id_item = table.item(row, 0) # 获取同行的 bull_id
            if item and bull_id_item:
                new_value_str = item.text()

                if not new_value_str.isdigit():
                    print(f"[SemenCount] 无效输入: '{new_value_str}', 支数应为非负整数.")
                    QMessageBox.warning(self, "输入无效", "支数必须为非负整数。")
                    # 无效输入提示，但不会自动保存

    def on_start_mating(self):
        """开始选配按钮点击事件"""
        if not self.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return
        
        # 检查必要文件是否存在
        index_file = self.selected_project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
        if not index_file.exists():
            QMessageBox.warning(self, "警告", "请先进行母牛指数计算")
            return
            
        bull_file = self.selected_project_path / "standardized_data" / "processed_bull_data.xlsx"
        if not bull_file.exists():
            QMessageBox.warning(self, "警告", "请先上传备选公牛数据")
            return
            
        report_file = self.selected_project_path / "analysis_results" / "individual_mating_report.xlsx"
        if not report_file.exists():
            reply = QMessageBox.question(
                self, 
                "缺少推荐报告", 
                "未找到选配推荐报告，是否要先生成推荐报告？\n\n点击'是'将自动生成推荐报告，然后进行选配分配。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 先生成推荐报告，完成后自动开始选配
                self._generate_recommendations_then_match()
            return
        
        # 继续执行原有的选配逻辑
        self._execute_matching()
    
    def _generate_recommendations_then_match(self):
        """生成推荐报告后自动开始选配"""
        # 创建进度对话框
        self.progress_dialog = ProgressDialog(self)
        self.progress_dialog.setWindowTitle("生成推荐并执行选配")
        self.progress_dialog.set_task_info("正在生成推荐并执行选配...")
        self.progress_dialog.show()
        
        # 创建并启动推荐工作者
        self.recommendation_worker = RecommendationWorker(self.selected_project_path)
        
        # 连接信号 - 推荐完成后自动开始选配
        self.recommendation_worker.progress_updated.connect(
            lambda msg, progress: (
                self.progress_dialog.set_task_info(msg),
                self.progress_dialog.update_progress(progress)
            )[1]
        )
        self.recommendation_worker.recommendation_completed.connect(self._on_recommendation_completed_then_match)
        self.recommendation_worker.error_occurred.connect(self.on_recommendation_error)
        
        # 启动工作者
        self.recommendation_worker.start()
    
    def _on_recommendation_completed_then_match(self, output_file: Path):
        """推荐生成完成后自动开始选配"""
        # 不关闭进度对话框，继续显示选配进度
        self.progress_dialog.set_task_info("推荐生成完成，开始执行选配...")
        self.progress_dialog.update_progress(0)
        
        # 直接执行选配逻辑
        self._execute_matching()
    
    def _execute_matching(self):
        """执行选配的核心逻辑 - 重定向到新的分配方法"""
        # 直接调用新的选配分配方法
        self.on_allocate_mating()
    
    def _collect_semen_counts(self) -> dict:
        """收集冻精支数信息"""
        semen_counts = {}
        
        try:
            import pandas as pd
            bull_file = self.selected_project_path / "standardized_data" / "processed_bull_data.xlsx"
            df = pd.read_excel(bull_file)
            
            # 确保列存在
            if 'bull_id' in df.columns and '支数' in df.columns:
                for _, row in df.iterrows():
                    bull_id = str(row['bull_id']).strip()
                    count = row['支数']
                    if pd.notna(count) and count > 0:
                        semen_counts[bull_id] = int(count)
            
        except Exception as e:
            logger.error(f"收集冻精支数失败: {e}")
        
        return semen_counts
    
    def _get_inbreeding_threshold(self) -> float:
        """获取近交系数阈值"""
        threshold_text = self.inbreeding_combo.currentText()
        if "3.125%" in threshold_text:
            return 0.03125
        elif "6.25%" in threshold_text:
            return 0.0625
        elif "12.5%" in threshold_text:
            return 0.125
        else:  # 无视近交
            return 1.0
    
    def on_matching_completed(self, output_file: Path):
        """个体选配完成处理 - DEPRECATED: 此方法已废弃，保留仅用于兼容"""
        self.progress_dialog.close()
        
        # 显示成功消息
        QMessageBox.information(
            self, 
            "选配完成", 
            f"个体选配已完成！\n结果已保存至: {output_file.name}"
        )
        
        # 询问是否打开结果文件
        reply = QMessageBox.question(
            self,
            "打开结果", 
            "是否要打开选配结果文件？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                import os
                import platform
                
                system = platform.system()
                if system == 'Windows':
                    os.startfile(str(output_file))
                elif system == 'Darwin':
                    import subprocess
                    subprocess.call(['open', str(output_file)])
                else:  # Linux
                    import subprocess
                    subprocess.call(['xdg-open', str(output_file)])
                    
            except Exception as e:
                QMessageBox.warning(self, "警告", f"无法打开文件: {e}")
        
        # 更新分组预览
        self.load_group_preview()
    
    def on_matching_error(self, error_message: str):
        """个体选配错误处理 - DEPRECATED: 此方法已废弃，保留仅用于兼容"""
        self.progress_dialog.close()
        QMessageBox.critical(self, "选配失败", f"个体选配失败:\n{error_message}")

    def save_all_semen_counts(self):
        """保存所有标签页中的冻精支数"""
        if not self.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return
            
        bull_file = self.selected_project_path / "standardized_data" / "processed_bull_data.xlsx"
        if not bull_file.exists():
            QMessageBox.warning(self, "警告", "备选公牛数据文件不存在")
            return
            
        try:
            import pandas as pd
            # 读取文件
            df = pd.read_excel(bull_file)
            df['bull_id'] = df['bull_id'].astype(str).str.strip()
            
            # 确定支数列名
            count_col = '支数' if '支数' in df.columns else 'count' if 'count' in df.columns else None
            if not count_col:
                df['支数'] = 0  # 如果没有支数列，创建一个
                count_col = '支数'
            elif count_col != '支数':
                df.rename(columns={'count': '支数'}, inplace=True)
                count_col = '支数'
                
            # 收集所有标签页中的支数（使用复合键）
            counts_update = {}  # {(bull_id, semen_type): count}
            for tab_index in range(self.semen_tab_widget.count()):
                tab_name = self.semen_tab_widget.tabText(tab_index)
                tab_widget = self.semen_tab_widget.widget(tab_index)
                if not tab_widget: continue

                # 从标签页名称推断semen_type
                if '常规' in tab_name:
                    semen_type = '常规'
                elif '性控' in tab_name:
                    semen_type = '性控'
                else:
                    continue  # 跳过无法识别的标签页

                layout = tab_widget.layout()
                if not layout or layout.count() == 0: continue

                table = layout.itemAt(0).widget()
                if not isinstance(table, QTableWidget): continue

                # 遍历表格中的每一行，收集支数
                for row in range(table.rowCount()):
                    bull_id_item = table.item(row, 0)
                    count_item = table.item(row, 13)

                    if bull_id_item and count_item:
                        bull_id = bull_id_item.text()
                        count_text = count_item.text()

                        if count_text.isdigit():
                            # 使用(bull_id, semen_type)作为key
                            counts_update[(bull_id, semen_type)] = int(count_text)

            # 更新DataFrame（匹配bull_id和semen_type）
            for (bull_id, semen_type), count in counts_update.items():
                match_mask = (df['bull_id'] == bull_id) & (df['semen_type'] == semen_type)
                match_indices = df[match_mask].index
                if not match_indices.empty:
                    df.loc[match_indices[0], count_col] = count
            
            # 保存回文件
            df.to_excel(bull_file, index=False)
            print(f"[SaveCounts] 已保存所有冻精支数到 {bull_file}")
            
        except PermissionError:
            QMessageBox.critical(self, "保存失败", f"""无法保存更新后的备选公牛数据。
文件 {bull_file.name} 可能被其他程序占用。
请关闭文件后重试。""")
        except Exception as e:
            print(f"[SaveCounts] 保存支数时出错: {e}")
            import traceback
            print(traceback.format_exc())
            QMessageBox.critical(self, "保存错误", f"保存支数时发生错误: {e}")
    
    def _get_inbreeding_threshold(self):
        """获取近交系数阈值"""
        threshold_text = self.inbreeding_combo.currentText()
        if "3.125" in threshold_text:
            return 3.125
        elif "6.25" in threshold_text:
            return 6.25
        elif "12.5" in threshold_text:
            return 12.5
        else:  # 无视近交
            return 100.0
    
    def _collect_semen_counts(self):
        """收集冻精支数信息，返回{(bull_id, semen_type): count}"""
        semen_inventory = {}

        # 遍历所有标签页
        for tab_index in range(self.semen_tab_widget.count()):
            tab_name = self.semen_tab_widget.tabText(tab_index)
            tab_widget = self.semen_tab_widget.widget(tab_index)
            if not tab_widget:
                continue

            # 从标签页名称推断semen_type
            if '常规' in tab_name:
                semen_type = '常规'
            elif '性控' in tab_name:
                semen_type = '性控'
            else:
                continue  # 跳过无法识别的标签页

            layout = tab_widget.layout()
            if not layout or layout.count() == 0:
                continue

            table = layout.itemAt(0).widget()
            if not isinstance(table, QTableWidget):
                continue

            # 从表格中收集支数
            for row in range(table.rowCount()):
                bull_id_item = table.item(row, 0)  # 公牛ID
                count_item = table.item(row, 13)   # 支数

                if bull_id_item and count_item:
                    bull_id = bull_id_item.text()
                    count_text = count_item.text()

                    if count_text.isdigit():
                        # 使用(bull_id, semen_type)复合键
                        semen_inventory[(bull_id, semen_type)] = int(count_text)
                    else:
                        semen_inventory[(bull_id, semen_type)] = 0

        return semen_inventory

    def clear_mating_results(self):
        """清除选配结果文件"""
        if not self.selected_project_path:
            return

        # 清除选配相关的结果文件
        files_to_clear = [
            "个体选配报告.xlsx",
            "individual_mating_report.xlsx",
            "个体选配推荐矩阵.xlsx"
        ]

        for filename in files_to_clear:
            file_path = self.selected_project_path / "analysis_results" / filename
            if file_path.exists():
                try:
                    file_path.unlink()
                    print(f"已清除: {filename}")
                except Exception as e:
                    print(f"清除 {filename} 失败: {e}")

    def on_manual_grouping(self):
        """手动分组按钮点击事件"""
        if not self.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return

        # 如果当前是自动分组模式，需要确认切换
        if self.grouping_mode == 'auto':
            reply = QMessageBox.question(
                self,
                "切换分组模式",
                "切换到手动分组模式将：\n"
                "1. 清除当前的自动分组设置\n"
                "2. 清除已有的选配结果\n"
                "3. 需要您手动编辑分组\n\n"
                "是否确认切换到手动分组模式？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # 清除选配结果
            self.clear_mating_results()

            # 清除自动分组（将group列清空）
            try:
                index_file = self.selected_project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
                if index_file.exists():
                    df = pd.read_excel(index_file)
                    if 'group' in df.columns:
                        df['group'] = None  # 清空分组列
                        df.to_excel(index_file, index=False)
                        print("已清除自动分组设置")
            except Exception as e:
                print(f"清除自动分组失败: {e}")

        # 切换到手动分组模式
        self.grouping_mode = 'manual'
        self.update_grouping_buttons_state()

        index_file = self.selected_project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
        if not index_file.exists():
            QMessageBox.warning(self, "警告", "请先进行母牛群指数排名")
            return

        try:
            import os
            import platform

            system = platform.system()
            if system == 'Windows':
                os.startfile(str(index_file))
            elif system == 'Darwin':
                import subprocess
                subprocess.call(['open', str(index_file)])
            else: # Linux
                import subprocess
                subprocess.call(['xdg-open', str(index_file)])

            QMessageBox.information(self, "提示", "已打开指数文件，请在文件中手动编辑分组，完成后请点击'分组更新'按钮更新分组预览")

            # 更新分组预览（显示手动分组的内容）
            self.load_group_preview()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开文件时出错: {str(e)}")

    def on_update_grouping(self):
        """分组更新按钮点击事件"""
        if not self.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return

        # 检查是否存在指数计算结果文件
        index_file = self.selected_project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
        if not index_file.exists():
            QMessageBox.warning(self, "警告", "请先进行母牛群指数排名")
            return

        # 更新分组预览表
        self.load_group_preview()
        QMessageBox.information(self, "成功", "分组预览已更新")

    def update_grouping_buttons_state(self):
        """更新分组按钮状态，实现互斥效果"""
        if not self.manual_group_btn or not self.auto_group_btn:
            return

        # 定义激活和非激活状态的样式
        active_style = """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """

        inactive_style = """
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
                cursor: pointer;
            }
        """

        if self.grouping_mode == 'manual':
            # 手动分组模式：手动按钮激活样式，自动按钮非激活但可点击
            self.manual_group_btn.setStyleSheet(active_style)
            self.manual_group_btn.setEnabled(True)
            self.auto_group_btn.setStyleSheet(inactive_style)
            self.auto_group_btn.setEnabled(True)  # 保持启用状态
        elif self.grouping_mode == 'auto':
            # 自动分组模式：自动按钮激活样式，手动按钮非激活但可点击
            self.auto_group_btn.setStyleSheet(active_style)
            self.auto_group_btn.setEnabled(True)
            self.manual_group_btn.setStyleSheet(inactive_style)
            self.manual_group_btn.setEnabled(True)  # 保持启用状态
        else:
            # 未选择模式：两个按钮都显示激活样式
            self.manual_group_btn.setStyleSheet(active_style)
            self.manual_group_btn.setEnabled(True)
            self.auto_group_btn.setStyleSheet(active_style)
            self.auto_group_btn.setEnabled(True)

    def on_auto_grouping(self):
        """自动分组按钮点击事件"""
        if not self.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return

        # 如果当前是手动分组模式，需要确认切换
        if self.grouping_mode == 'manual':
            reply = QMessageBox.question(
                self,
                "切换分组模式",
                "切换到自动分组模式将：\n"
                "1. 清除当前的手动分组设置\n"
                "2. 清除已有的选配结果\n"
                "3. 使用系统自动分组策略\n\n"
                "是否确认切换到自动分组模式？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # 清除选配结果
            self.clear_mating_results()

            # 清除手动分组（将group列清空）
            try:
                index_file = self.selected_project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
                if index_file.exists():
                    df = pd.read_excel(index_file)
                    if 'group' in df.columns:
                        df['group'] = None  # 清空分组列
                        df.to_excel(index_file, index=False)
                        print("已清除手动分组设置")
            except Exception as e:
                print(f"清除手动分组失败: {e}")

        # 切换到自动分组模式
        self.grouping_mode = 'auto'
        self.update_grouping_buttons_state()

        # 检查是否存在指数计算结果文件
        index_file = self.selected_project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
        if not index_file.exists():
            QMessageBox.warning(self, "警告", "请先进行母牛群指数排名")
            return

        # 创建并显示自动分组对话框
        from gui.auto_grouping_dialog import AutoGroupingDialog
        auto_grouping_dialog = AutoGroupingDialog(self.selected_project_path, parent=self)
        auto_grouping_dialog.exec()

        # 对话框关闭后更新分组预览
        self.load_group_preview()

    def on_clear_mating(self):
        """清空选配按钮点击事件"""
        # 获取选中的组
        selected_groups = []
        for row in range(self.group_preview_table.rowCount()):
            checkbox_item = self.group_preview_table.cellWidget(row, 0)
            if checkbox_item and isinstance(checkbox_item, QWidget):
                # 获取QCheckBox控件
                checkbox = checkbox_item.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    group_name = self.group_preview_table.item(row, 1).text()
                    selected_groups.append(group_name)

        if not selected_groups:
            QMessageBox.warning(self, "警告", "请先选择要清空选配的组")
            return

        # 确认清空选配
        reply = QMessageBox.question(
            self,
            "确认清空",
            f"确定要清空以下组的选配结果吗？\n{', '.join(selected_groups)}\n\n"
            "这将清空这些组中母牛的常规和性控选配结果。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # 读取现有的选配报告
                report_files = [
                    self.selected_project_path / "analysis_results" / "个体选配报告.xlsx",
                    self.selected_project_path / "analysis_results" / "individual_mating_report.xlsx"
                ]

                cleared_count = 0
                for report_file in report_files:
                    if report_file.exists():
                        df = pd.read_excel(report_file)

                        # 检查列名是'group'还是'分组'
                        group_col = 'group' if 'group' in df.columns else '分组' if '分组' in df.columns else None

                        if group_col:
                            # 清空选中组的选配结果
                            for group in selected_groups:
                                mask = df[group_col] == group
                                if mask.any():
                                    # 清空性控选配列
                                    sexed_columns = ['1选性控', '2选性控', '3选性控', '性控备注']
                                    for col in sexed_columns:
                                        if col in df.columns:
                                            df.loc[mask, col] = None

                                    # 清空常规选配列
                                    regular_columns = ['1选常规', '2选常规', '3选常规', '常规备注']
                                    for col in regular_columns:
                                        if col in df.columns:
                                            df.loc[mask, col] = None

                                    cleared_count += mask.sum()

                        # 保存更新后的文件
                        df.to_excel(report_file, index=False)
                        print(f"已更新文件: {report_file.name}")

                if cleared_count > 0:
                    QMessageBox.information(
                        self,
                        "清空成功",
                        f"已成功清空 {len(selected_groups)} 个组共 {cleared_count} 头母牛的选配结果。"
                    )
                    # 刷新分组预览以更新未分配数量
                    self.load_group_preview()
                else:
                    QMessageBox.information(
                        self,
                        "提示",
                        f"所选组中没有找到选配结果。"
                    )

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "清空失败",
                    f"清空选配结果时发生错误：\n{str(e)}"
                )

    def toggle_group_checkboxes(self, checked):
        """处理全选/取消全选按钮点击事件"""
        # 当按钮被点击时，根据按钮的状态切换所有复选框
        for row in range(self.group_preview_table.rowCount()):
            checkbox_item = self.group_preview_table.cellWidget(row, 0)
            if checkbox_item and isinstance(checkbox_item, QWidget):
                checkbox = checkbox_item.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(checked)
        
        # 根据选中状态更新按钮文本
        self.select_all_button.setText("取消全选" if checked else "全选")

    def on_generate_recommendations(self):
        """生成选配推荐按钮点击事件"""
        if not self.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return
        
        # 检查必要文件是否存在
        index_file = self.selected_project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
        if not index_file.exists():
            QMessageBox.warning(self, "警告", "请先进行母牛指数计算")
            return
            
        bull_file = self.selected_project_path / "standardized_data" / "processed_bull_data.xlsx"
        if not bull_file.exists():
            QMessageBox.warning(self, "警告", "请先上传备选公牛数据")
            return
        
        # 创建进度对话框
        self.progress_dialog = ProgressDialog(self)
        self.progress_dialog.setWindowTitle("生成选配推荐")
        self.progress_dialog.set_task_info("正在生成选配推荐...")
        self.progress_dialog.show()
        
        # 创建并启动推荐工作者
        self.recommendation_worker = RecommendationWorker(self.selected_project_path)
        
        # 连接信号
        self.recommendation_worker.progress_updated.connect(
            lambda msg, progress: (
                self.progress_dialog.set_task_info(msg),
                self.progress_dialog.update_progress(progress)
            )[1]
        )
        self.recommendation_worker.recommendation_completed.connect(self.on_recommendation_completed)
        self.recommendation_worker.error_occurred.connect(self.on_recommendation_error)
        self.recommendation_worker.prerequisites_needed.connect(self.on_prerequisites_needed)
        
        # 启动工作者
        self.recommendation_worker.start()
    
    def on_recommendation_completed(self, output_file: Path):
        """推荐生成完成处理"""
        self.progress_dialog.close()
        
        # 显示成功消息
        message = (
            "选配推荐已生成！\n\n"
            "生成了以下文件：\n"
            f"1. 配对矩阵文件：{output_file.name}\n"
            f"   - 包含所有母牛×公牛的配对信息\n"
            f"   - 分别显示后代得分、近交系数、隐性基因状态\n\n"
            f"2. 推荐汇总文件：individual_mating_report.xlsx\n"
            f"   - 用于选配分配功能\n\n"
            "是否打开配对矩阵文件查看？"
        )
        
        reply = QMessageBox.information(
            self, 
            "推荐完成", 
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        # 如果用户选择查看，打开文件
        if reply == QMessageBox.StandardButton.Yes:
            try:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_file)))
            except Exception as e:
                QMessageBox.warning(self, "打开失败", f"无法打开文件: {str(e)}")
    
    def on_recommendation_error(self, error_message: str):
        """推荐生成错误处理"""
        self.progress_dialog.close()
        QMessageBox.critical(self, "推荐失败", f"生成选配推荐失败:\n{error_message}")
    
    def on_prerequisites_needed(self, message: str):
        """处理前置条件缺失"""
        QMessageBox.warning(
            self, 
            "前置条件提醒", 
            f"{message}\n\n系统将使用安全默认值继续生成推荐。"
        )
    
    def on_execute_complete_mating(self):
        """执行完整的个体选配流程（一键完成）"""
        if not self.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return

        # 获取选中的分组
        selected_groups = []
        for row in range(self.group_preview_table.rowCount()):
            checkbox_item = self.group_preview_table.cellWidget(row, 0)
            if checkbox_item and isinstance(checkbox_item, QWidget):
                checkbox = checkbox_item.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    group_name = self.group_preview_table.item(row, 1).text()
                    selected_groups.append(group_name)

        if not selected_groups:
            QMessageBox.warning(self, "警告", "请先在分组预览中勾选要进行选配的组")
            return

        # 保存冻精支数
        self.save_all_semen_counts()

        # 收集冻精库存
        semen_inventory = self._collect_semen_counts()

        # 检查库存
        all_zero = all(count == 0 for count in semen_inventory.values())
        if all_zero:
            QMessageBox.warning(
                self,
                "警告",
                "所有公牛的冻精支数都为0！\n\n"
                "请在「冻精预览」表格中设置冻精支数后再进行选配。"
            )
            return

        # 显示选配前确认对话框
        from gui.mating_confirmation_dialog import MatingConfirmationDialog
        confirm_dialog = MatingConfirmationDialog(self.selected_project_path, self)

        if confirm_dialog.exec() != QDialog.DialogCode.Accepted:
            # 用户取消了选配
            return

        # 获取用户的选择
        confirmation_result = confirm_dialog.get_confirmation_result()
        skip_missing_bulls = confirmation_result.get('skip_missing', False)

        # 获取参数
        inbreeding_threshold = self._get_inbreeding_threshold()
        control_defect_genes = self.gene_control_checkbox.isChecked()

        # 准备选配参数
        mating_params = {
            'bull_inventory': semen_inventory,
            'inbreeding_threshold': inbreeding_threshold,
            'control_defect_genes': control_defect_genes,
            'heifer_age_days': 420,
            'cycle_days': 21,
            'skip_missing_bulls': skip_missing_bulls,
            'selected_groups': selected_groups,  # 添加选中的分组
            'grouping_mode': self.grouping_mode  # 添加分组模式
        }

        # 使用多线程进度对话框
        from gui.mating_progress import MatingProgressDialog

        self.mating_dialog = MatingProgressDialog(
            self.selected_project_path,
            mating_params,
            self
        )

        # 连接完成信号
        self.mating_dialog.completed.connect(self.on_mating_completed)

        # 显示对话框（模态）
        self.mating_dialog.exec()

    def on_push_mating_results(self):
        """推送选配结果"""
        if not self.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择项目")
            return

        try:
            # 创建推送器
            pusher = MatingResultPusher(self.selected_project_path)

            # 准备推送数据
            push_data = pusher.prepare_push_data()
            if not push_data:
                # 检查是否是因为缺少farm_info.json
                farm_info_path = self.selected_project_path / "farm_info.json"
                if not farm_info_path.exists():
                    QMessageBox.warning(
                        self,
                        "缺少牧场信息",
                        f"请先创建牧场信息文件：\n{farm_info_path}\n\n"
                        f"文件格式示例：\n"
                        f'{{\n'
                        f'  "farm_code": "10001"\n'
                        f'}}'
                    )
                else:
                    QMessageBox.warning(self, "警告", "无法准备推送数据，请检查选配结果文件和牧场信息")
                return

            # 显示确认对话框，展示将要推送的数据
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QLabel

            confirm_dialog = QDialog(self)
            confirm_dialog.setWindowTitle("确认推送数据")
            confirm_dialog.setMinimumSize(600, 500)

            layout = QVBoxLayout()

            # 显示牧场信息
            info_label = QLabel(f"""
<b>牧场信息：</b><br>
牧场编号：{push_data.get('farm_code', '未设置')}<br>
<br>
<b>选配信息：</b><br>
母牛总数：{len(push_data.get('records', []))} 头<br>
            """)
            layout.addWidget(info_label)

            # 显示详细数据（JSON格式）
            detail_label = QLabel("<b>推送数据预览（JSON格式）：</b>")
            layout.addWidget(detail_label)

            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            import json
            text_edit.setText(json.dumps(push_data, ensure_ascii=False, indent=2))
            layout.addWidget(text_edit)

            # 按钮
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(confirm_dialog.accept)
            buttons.rejected.connect(confirm_dialog.reject)
            layout.addWidget(buttons)

            confirm_dialog.setLayout(layout)

            # 显示对话框
            if confirm_dialog.exec() != QDialog.DialogCode.Accepted:
                return

            # 执行推送（当前保存到本地）
            success = pusher.push_to_api()  # 暂时不传入URL，保存到本地

            if success:
                QMessageBox.information(
                    self,
                    "推送成功",
                    f"✅ 选配结果推送成功！\n\n"
                    f"测试模式：数据已保存到项目文件夹\n"
                    f"文件：api_push_data.json\n\n"
                    f"未来将推送到真实API服务器"
                )
            else:
                QMessageBox.critical(
                    self,
                    "推送失败",
                    "❌ 推送失败，请查看日志文件"
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "错误",
                f"推送过程中发生错误：\n{str(e)}"
            )

    def on_mating_completed(self, result: dict):
        """选配完成的处理"""
        if result['success']:
            # 启用推送按钮
            if hasattr(self, 'push_result_btn'):
                self.push_result_btn.setEnabled(True)

            # 构建成功消息
            message = f"""个体选配完成！

已生成完整的选配报告：
{result['report_path'].name}

报告包含了所有分组的母牛选配结果。

是否打开查看报告？"""

            reply = QMessageBox.question(
                self,
                "选配完成",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                try:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(result['report_path'])))
                except Exception as e:
                    QMessageBox.warning(self, "打开失败", f"无法打开文件: {str(e)}")

            # 更新分组预览
            self.load_group_preview()

        else:
            QMessageBox.critical(
                self,
                "选配失败",
                f"个体选配失败:\n{result.get('error', '未知错误')}"
            )

    def on_allocate_mating(self):
        """选配分配按钮点击事件"""
        if not self.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return
        
        # 检查必要文件是否存在
        report_file = self.selected_project_path / "analysis_results" / "individual_mating_report.xlsx"
        if not report_file.exists():
            reply = QMessageBox.question(
                self, 
                "缺少推荐报告", 
                "未找到选配推荐报告，请先生成推荐报告。\n\n是否现在生成？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.on_generate_recommendations()
            return
        
        # 获取选中的组
        selected_groups = []
        for row in range(self.group_preview_table.rowCount()):
            checkbox_item = self.group_preview_table.cellWidget(row, 0)
            if checkbox_item and isinstance(checkbox_item, QWidget):
                checkbox = checkbox_item.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    group_name = self.group_preview_table.item(row, 1).text()
                    selected_groups.append(group_name)
        
        if not selected_groups:
            QMessageBox.warning(self, "警告", "请先在分组预览中勾选要分配的组")
            return
        
        # 首先保存所有冻精支数
        self.save_all_semen_counts()
        
        # 收集冻精库存信息
        semen_inventory = self._collect_semen_counts()
        
        # 检查是否所有冻精支数都为0
        all_zero = all(count == 0 for count in semen_inventory.values())
        if all_zero:
            QMessageBox.warning(
                self, 
                "警告", 
                "所有公牛的冻精支数都为0！\n\n"
                "请在「冻精预览」表格中设置冻精支数后再进行分配。"
            )
            return
        
        # 创建进度对话框
        self.progress_dialog = ProgressDialog(self)
        self.progress_dialog.setWindowTitle("选配分配")
        self.progress_dialog.set_task_info("正在进行选配分配...")
        self.progress_dialog.show()
        
        # 执行分配
        try:
            from core.matching.cycle_based_matcher import CycleBasedMatcher
            
            # 创建匹配器
            matcher = CycleBasedMatcher()
            matcher.inbreeding_threshold = self._get_inbreeding_threshold()
            matcher.control_defect_genes = self.gene_control_checkbox.isChecked()
            
            # 加载数据
            self.progress_dialog.set_task_info("正在加载推荐数据...")
            self.progress_dialog.update_progress(10)
            
            recommendations_df = pd.read_excel(report_file)
            bull_data_path = self.selected_project_path / "standardized_data" / "processed_bull_data.xlsx"
            
            if not matcher.load_data(recommendations_df, bull_data_path):
                self.progress_dialog.close()
                QMessageBox.critical(self, "错误", "数据加载失败")
                return
            
            # 设置库存
            self.progress_dialog.set_task_info("正在设置冻精库存...")
            self.progress_dialog.update_progress(20)
            matcher.set_inventory(semen_inventory)
            
            # 执行分配
            self.progress_dialog.set_task_info("正在执行分配...")
            self.progress_dialog.update_progress(30)
            
            def progress_callback(message, progress):
                self.progress_dialog.set_task_info(message)
                self.progress_dialog.update_progress(30 + int(progress * 0.6))
            
            result_df = matcher.perform_allocation(selected_groups, progress_callback)
            
            # 保存结果
            self.progress_dialog.set_task_info("正在保存结果...")
            self.progress_dialog.update_progress(90)
            
            # 保存详细分配结果
            allocation_file = self.selected_project_path / "analysis_results" / "individual_allocation_result.xlsx"
            success = matcher.save_allocation_result(result_df, allocation_file)
            
            # 保存汇总信息
            summary_file = self.selected_project_path / "analysis_results" / "allocation_summary.xlsx"
            summary_df = matcher.get_allocation_summary()
            summary_df.to_excel(summary_file, index=False)
            
            self.progress_dialog.update_progress(100)
            self.progress_dialog.close()
            
            # 显示完成信息
            message = (
                f"选配分配完成！\n\n"
                f"已分配 {len(selected_groups)} 个组的母牛\n"
                f"分配结果已保存至:\n"
                f"- {allocation_file.name}\n"
                f"- {summary_file.name}\n\n"
                f"是否打开查看分配结果？"
            )
            
            reply = QMessageBox.question(
                self, 
                "分配完成", 
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(allocation_file)))
                except Exception as e:
                    QMessageBox.warning(self, "打开失败", f"无法打开文件: {str(e)}")
                    
        except Exception as e:
            self.progress_dialog.close()
            logger.error(f"选配分配失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            QMessageBox.critical(self, "错误", f"选配分配失败:\n{str(e)}")
    
    def on_generate_ppt(self):
        """生成PPT报告"""
        if not self.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return
            
        try:
            # 导入新的PPT生成器
            from core.report.ppt_generator import PPTGenerator
            
            # 获取用户名（从设置或默认值）
            username = getattr(self, 'username', '用户')
            
            # 创建输出文件夹路径
            output_folder = self.selected_project_path / "analysis_results"
            output_folder.mkdir(exist_ok=True)
            
            # 创建PPT生成器
            ppt_generator = PPTGenerator(str(output_folder), username)
            
            # 生成报告
            success = ppt_generator.generate_report(parent_widget=self)
            
            if not success:
                # 错误消息已经在generate_report中显示
                return
                
        except ImportError as e:
            # 如果新模块还未完全实现，回退到旧的实现
            logging.warning(f"无法导入新的PPT生成器: {e}")
            # 使用旧的PPT生成器
            try:
                from core.reporting.ppt import PPTGenerator as OldPPTGenerator
                
                # 获取牧场名称
                farm_name = self.selected_project_path.name
                
                # 创建PPT生成器
                ppt_generator = OldPPTGenerator(self.selected_project_path, farm_name)
                
                # 检查必要文件
                can_generate, error_msg = ppt_generator.check_required_files()
                if not can_generate:
                    # 解析缺少的文件类型
                    missing_analyses = []
                    if "系谱识别情况分析" in error_msg:
                        missing_analyses.append(("系谱识别情况分析", self.run_pedigree_analysis))
                    if "母牛关键性状指数" in error_msg:
                        missing_analyses.append(("母牛关键性状指数", self.run_cow_key_traits))
                    if "母牛育种指数" in error_msg:
                        missing_analyses.append(("母牛育种指数", self.run_cow_index_calculation))
                    
                    # 构建提示信息
                    missing_names = [name for name, _ in missing_analyses]
                    message = f"生成PPT报告需要先完成以下分析：\n\n• " + "\n• ".join(missing_names)
                    message += "\n\n是否现在自动执行这些分析？"
                    
                    reply = QMessageBox.question(
                        self,
                        "缺少必要分析",
                        message,
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        # 执行缺失的分析
                        for name, func in missing_analyses:
                            try:
                                QMessageBox.information(self, "提示", f"正在执行{name}...")
                                QApplication.processEvents()
                                func()
                            except Exception as e:
                                QMessageBox.critical(self, "错误", f"执行{name}时出错：{str(e)}")
                                return
                        
                        # 重新检查文件
                        can_generate, error_msg = ppt_generator.check_required_files()
                        if not can_generate:
                            QMessageBox.warning(self, "错误", "部分分析执行失败，无法生成PPT报告。")
                            return
                    else:
                        return
                    
                # 创建进度对话框
                progress_dialog = ProgressDialog(self)
                progress_dialog.setWindowTitle("生成PPT报告")
                progress_dialog.set_task_info("正在生成PPT报告...")
                progress_dialog.show()
                
                # 生成PPT
                def progress_callback(message, progress):
                    progress_dialog.set_task_info(message)
                    progress_dialog.update_progress(progress)
                    QApplication.processEvents()
                    
                ppt_generator.generate_ppt(progress_callback)
                
                progress_dialog.close()
                
                # 询问是否打开
                output_file = self.selected_project_path / "analysis_results" / f"{farm_name}牧场遗传改良项目专项服务报告.pptx"
                reply = QMessageBox.information(
                    self,
                    "生成成功",
                    f"PPT报告已生成！\n\n是否立即打开查看？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    try:
                        QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_file)))
                    except Exception as e:
                        QMessageBox.warning(self, "打开失败", f"无法打开文件: {str(e)}")
                        
            except Exception as e:
                QMessageBox.critical(self, "生成失败", f"生成PPT报告时发生错误：\n{str(e)}")

    def on_generate_excel_report(self):
        """生成Excel综合报告"""
        if not self.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return

        try:
            from core.excel_report import ExcelReportGenerator

            # 获取用户名（从设置或默认值）
            service_staff = getattr(self, 'username', '未指定')

            # 创建进度对话框
            progress_dialog = ProgressDialog(self)
            progress_dialog.setWindowTitle("生成Excel综合报告")
            progress_dialog.set_task_info("正在生成Excel综合报告...")
            progress_dialog.show()
            QApplication.processEvents()

            # 创建Excel报告生成器
            generator = ExcelReportGenerator(self.selected_project_path, service_staff)

            # 生成报告
            progress_dialog.update_progress(50)
            QApplication.processEvents()

            success, result = generator.generate()

            progress_dialog.close()

            if success:
                # 生成成功
                reply = QMessageBox.information(
                    self,
                    "生成成功",
                    f"Excel综合报告已生成！\n\n文件位置：\n{result}\n\n是否立即打开查看？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )

                if reply == QMessageBox.StandardButton.Yes:
                    try:
                        from pathlib import Path
                        QDesktopServices.openUrl(QUrl.fromLocalFile(str(result)))
                    except Exception as e:
                        QMessageBox.warning(self, "打开失败", f"无法打开文件: {str(e)}")
            else:
                # 生成失败
                error_msg = result

                # 检查是否是缺少必要文件
                if "缺少必要文件" in error_msg:
                    message = f"{error_msg}\n\n提示：请先完成以下分析：\n"
                    message += "• 系谱识别分析\n"
                    message += "• 育种性状分析\n"
                    message += "• 公牛使用分析（如果需要）\n"
                    message += "\n这些分析会生成Excel报告所需的数据文件。"

                    QMessageBox.warning(self, "缺少必要文件", message)
                else:
                    QMessageBox.critical(self, "生成失败", f"生成Excel报告时发生错误：\n{error_msg}")

        except Exception as e:
            progress_dialog.close()
            QMessageBox.critical(self, "生成失败", f"生成Excel报告时发生错误：\n{str(e)}")
            import traceback
            traceback.print_exc()

    def load_benchmark_farms(self):
        """加载对比数据（对比牧场+外部参考数据）到表格"""
        try:
            logging.info("开始加载对比数据...")

            # 在清空表格前，先保存当前的选择状态（从内存中的 self.selected_comparisons）
            current_selections = self.selected_comparisons.copy() if hasattr(self, 'selected_comparisons') else []
            logging.info(f"当前内存中的选择: {len(current_selections)} 个")

            # 强制重新加载配置文件（确保获取最新数据）
            self.benchmark_manager.config = self.benchmark_manager._load_config()
            logging.info("已重新加载配置文件")

            # 清空表格
            self.comparison_sources_table.setRowCount(0)

            # 加载所有对比牧场
            farms = self.benchmark_manager.get_all_farms()
            logging.info(f"加载到 {len(farms)} 个对比牧场")

            # 加载所有外部参考数据
            references = self.benchmark_manager.get_all_reference_data()
            logging.info(f"加载到 {len(references)} 个外部参考数据")

            # 使用当前内存中的选择（优先），如果没有则从配置加载
            if current_selections:
                saved_comparisons = current_selections
                logging.info(f"使用当前选择状态: {len(saved_comparisons)} 个")
            else:
                saved_comparisons = self.benchmark_manager.get_selected_comparisons()
                if not saved_comparisons:
                    saved_comparisons = []
                logging.info(f"从配置文件加载选择: {len(saved_comparisons)} 个")

            # 添加对比牧场行
            for farm in farms:
                logging.info(f"添加对比牧场: {farm['name']}")
                self._add_comparison_source_row(
                    source_type='farm',
                    source_id=farm['id'],
                    name=farm['name'],
                    saved_comparisons=saved_comparisons
                )

            # 添加外部参考数据行
            for ref in references:
                logging.info(f"添加外部参考: {ref['name']}")
                self._add_comparison_source_row(
                    source_type='reference',
                    source_id=ref['id'],
                    name=ref['name'],
                    saved_comparisons=saved_comparisons
                )

            # 刷新完成后，重新构建 selected_comparisons 列表
            self.selected_comparisons = saved_comparisons

            logging.info(f"✓ 对比数据加载完成，表格共有 {self.comparison_sources_table.rowCount()} 行")
            logging.info(f"✓ 选中状态已恢复: {len(self.selected_comparisons)} 个")

        except Exception as e:
            logging.error(f"加载对比数据失败: {e}", exc_info=True)

    def _add_comparison_source_row(self, source_type: str, source_id: str, name: str, saved_comparisons: list):
        """
        添加对比数据行到表格

        Args:
            source_type: 'farm' 或 'reference'
            source_id: 数据源ID
            name: 显示名称
            saved_comparisons: 已保存的选择列表
        """
        row = self.comparison_sources_table.rowCount()
        self.comparison_sources_table.insertRow(row)

        # 查找是否已被选中，以及对应的颜色
        is_checked = False
        color = None
        for comp in saved_comparisons:
            if source_type == 'farm' and comp.get('farm_id') == source_id:
                is_checked = True
                color = comp.get('color')
                break
            elif source_type == 'reference' and comp.get('reference_id') == source_id:
                is_checked = True
                color = comp.get('color')
                break

        # 如果未分配颜色，分配默认颜色
        if color is None:
            color_index = row % len(self.comparison_colors)
            color = self.comparison_colors[color_index]

        # 第0列：复选框
        from PyQt6.QtWidgets import QCheckBox
        checkbox = QCheckBox()
        checkbox.setChecked(is_checked)
        checkbox.setStyleSheet("QCheckBox { margin-left: 10px; }")
        checkbox.stateChanged.connect(lambda state, r=row: self._on_comparison_checkbox_changed(r, state))
        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.addWidget(checkbox)
        checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self.comparison_sources_table.setCellWidget(row, 0, checkbox_widget)

        # 第1列：类型
        type_label = "对比牧场" if source_type == 'farm' else "外部参考"
        type_item = QTableWidgetItem(type_label)
        type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if source_type == 'reference':
            type_item.setForeground(QBrush(QColor("#e67e22")))  # 橙色标识外部参考
        self.comparison_sources_table.setItem(row, 1, type_item)

        # 第2列：名称
        name_item = QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        name_item.setData(Qt.ItemDataRole.UserRole, {
            'type': source_type,
            'id': source_id,
            'color': color
        })
        self.comparison_sources_table.setItem(row, 2, name_item)

        # 第3列：摘要
        summary_text = self._generate_summary_text(source_type, source_id)
        summary_item = QTableWidgetItem(summary_text)
        summary_item.setFlags(summary_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        summary_item.setForeground(QBrush(QColor("#7f8c8d")))  # 灰色字体
        self.comparison_sources_table.setItem(row, 3, summary_item)

        # 第4列：颜色按钮
        color_btn = QPushButton()
        color_btn.setFixedSize(60, 25)
        color_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: 1px solid #7f8c8d;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                border: 2px solid #2c3e50;
            }}
        """)
        color_btn.clicked.connect(lambda checked, r=row: self._change_comparison_source_color(r))
        color_widget = QWidget()
        color_layout = QHBoxLayout(color_widget)
        color_layout.addWidget(color_btn)
        color_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        color_layout.setContentsMargins(0, 0, 0, 0)
        self.comparison_sources_table.setCellWidget(row, 4, color_widget)

    def _generate_summary_text(self, source_type: str, source_id: str) -> str:
        """
        生成数据源摘要文本

        Args:
            source_type: 'farm' 或 'reference'
            source_id: 数据源ID

        Returns:
            摘要文本
        """
        try:
            if source_type == 'farm':
                # 对比牧场：在群母牛665头,202x年 - 2024年，在群牛总计数据预览（显示前3项）
                farm = self.benchmark_manager.get_farm_by_id(source_id)
                if not farm:
                    return "数据加载失败"

                data_summary = farm.get('data_summary', {})
                present_summary = data_summary.get('present_summary', {})

                # 获取头数
                cow_count = present_summary.get('cow_count', 0)

                # 获取年份范围
                year_rows = present_summary.get('year_rows', [])
                year_range = ""
                if year_rows:
                    # 过滤掉"总计"行
                    actual_years = [y for y in year_rows if '总计' not in str(y)]
                    if actual_years:
                        # 提取纯年份（去掉"年"和"及以前"）
                        first_year = actual_years[0]
                        last_year = actual_years[-1]

                        match_first = re.search(r'(\d{4})', first_year)
                        match_last = re.search(r'(\d{4})', last_year)

                        if match_first and match_last:
                            year_range = f"{match_first.group(1)}年 - {match_last.group(1)}年"

                # 获取总计数据（前3项）
                data = present_summary.get('data', {})
                total_data = None
                for year_key in data.keys():
                    if '总计' in str(year_key):
                        total_data = data[year_key]
                        break

                trait_preview = ""
                if total_data:
                    # 获取前3个性状（排除头数）
                    traits = present_summary.get('traits', [])
                    preview_items = []
                    for trait in traits[:3]:
                        value = total_data.get(trait)
                        if value is not None:
                            # 保留2位小数
                            try:
                                formatted_value = f"{float(value):.2f}"
                            except (ValueError, TypeError):
                                formatted_value = str(value)
                            preview_items.append(f"{trait}={formatted_value}")

                    if preview_items:
                        trait_preview = ", ".join(preview_items)

                # 组合摘要
                parts = []
                if cow_count > 0:
                    parts.append(f"在群母牛{cow_count}头")
                if year_range:
                    parts.append(year_range)
                if trait_preview:
                    parts.append(trait_preview)

                return ", ".join(parts) if parts else "暂无数据"

            else:  # reference
                # 外部参考：57个性状, 202x年 - 2024年，最后1年数据预览（显示前3项）
                reference = self.benchmark_manager.get_reference_by_id(source_id)
                if not reference:
                    return "数据加载失败"

                data_summary = reference.get('data_summary', {})
                present_summary = data_summary.get('present_summary', {})

                # 获取性状数量
                traits = present_summary.get('traits', [])
                trait_count = len(traits)

                # 获取年份范围
                year_rows = present_summary.get('year_rows', [])
                year_range = ""
                if year_rows:
                    # 过滤掉"总计"行
                    actual_years = [y for y in year_rows if '总计' not in str(y)]
                    if actual_years:
                        # 提取纯年份（去掉"年"和"及以前"）
                        first_year = actual_years[0]
                        last_year = actual_years[-1]

                        match_first = re.search(r'(\d{4})', first_year)
                        match_last = re.search(r'(\d{4})', last_year)

                        if match_first and match_last:
                            year_range = f"{match_first.group(1)}年 - {match_last.group(1)}年"

                # 获取最后一年的数据（前3项）
                data = present_summary.get('data', {})
                latest_year_data = None
                latest_year_str = None
                if year_rows:
                    # 获取最后一年（排除"总计"）
                    actual_years = [y for y in year_rows if '总计' not in str(y)]
                    if actual_years:
                        latest_year = actual_years[-1]
                        latest_year_data = data.get(latest_year)
                        # 提取纯年份用于显示
                        match = re.search(r'(\d{4})', latest_year)
                        if match:
                            latest_year_str = match.group(1)

                trait_preview = ""
                if latest_year_data and latest_year_str:
                    # 获取前3个性状
                    preview_items = []
                    for trait in traits[:3]:
                        value = latest_year_data.get(trait)
                        if value is not None:
                            # 保留2位小数
                            try:
                                formatted_value = f"{float(value):.2f}"
                            except (ValueError, TypeError):
                                formatted_value = str(value)
                            preview_items.append(f"{trait}={formatted_value}")

                    if preview_items:
                        # 添加年份前缀
                        trait_preview = f"{latest_year_str}年平均数据：" + ", ".join(preview_items)

                # 组合摘要
                parts = []
                if trait_count > 0:
                    parts.append(f"{trait_count}个性状")
                if year_range:
                    parts.append(year_range)
                if trait_preview:
                    parts.append(trait_preview)

                return ", ".join(parts) if parts else "暂无数据"

        except Exception as e:
            logging.error(f"生成摘要文本失败: {e}", exc_info=True)
            return "摘要生成失败"

    def _on_comparison_checkbox_changed(self, row: int, state: int):
        """处理复选框状态变化"""
        name_item = self.comparison_sources_table.item(row, 2)
        if not name_item:
            return

        data = name_item.data(Qt.ItemDataRole.UserRole)
        source_type = data['type']
        source_id = data['id']
        color = data['color']

        is_checked = (state == Qt.CheckState.Checked.value)

        # 更新 selected_comparisons
        if is_checked:
            # 添加到选择列表
            if source_type == 'farm':
                if not any(c.get('farm_id') == source_id for c in self.selected_comparisons):
                    self.selected_comparisons.append({
                        'farm_id': source_id,
                        'color': color
                    })
            else:  # reference
                if not any(c.get('reference_id') == source_id for c in self.selected_comparisons):
                    self.selected_comparisons.append({
                        'reference_id': source_id,
                        'color': color
                    })
        else:
            # 从选择列表移除
            if source_type == 'farm':
                self.selected_comparisons = [c for c in self.selected_comparisons if c.get('farm_id') != source_id]
            else:  # reference
                self.selected_comparisons = [c for c in self.selected_comparisons if c.get('reference_id') != source_id]

        # 保存选择
        self.save_selected_comparisons()
        logging.info(f"{'选中' if is_checked else '取消选中'} {data['type']}: {name_item.text()}")

    def _change_comparison_source_color(self, row: int):
        """修改对比数据源的颜色"""
        from PyQt6.QtWidgets import QColorDialog

        name_item = self.comparison_sources_table.item(row, 2)
        if not name_item:
            return

        data = name_item.data(Qt.ItemDataRole.UserRole)
        source_type = data['type']
        source_id = data['id']
        current_color = QColor(data['color'])

        # 打开颜色选择对话框
        color = QColorDialog.getColor(current_color, self, "选择对比线颜色")

        if color.isValid():
            new_color = color.name()

            # 更新数据
            data['color'] = new_color
            name_item.setData(Qt.ItemDataRole.UserRole, data)

            # 更新颜色按钮显示
            color_widget = self.comparison_sources_table.cellWidget(row, 4)
            if color_widget:
                color_btn = color_widget.layout().itemAt(0).widget()
                color_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {new_color};
                        border: 1px solid #7f8c8d;
                        border-radius: 3px;
                    }}
                    QPushButton:hover {{
                        border: 2px solid #2c3e50;
                    }}
                """)

            # 更新 selected_comparisons 中的颜色
            for comp in self.selected_comparisons:
                if source_type == 'farm' and comp.get('farm_id') == source_id:
                    comp['color'] = new_color
                    break
                elif source_type == 'reference' and comp.get('reference_id') == source_id:
                    comp['color'] = new_color
                    break

            # 保存选择
            self.save_selected_comparisons()
            logging.info(f"已修改 {source_type} 颜色: {name_item.text()} -> {new_color}")

    def save_selected_comparisons(self):
        """保存选择的对比牧场"""
        self.benchmark_manager.save_selected_comparisons(self.selected_comparisons)
        logging.info(f"已保存 {len(self.selected_comparisons)} 个对比选择")

    def open_benchmark_manager(self):
        """打开对比牧场管理对话框"""
        try:
            from gui.benchmark_dialog import BenchmarkDialog

            dialog = BenchmarkDialog(self)
            dialog.exec()

            # 注意：对话框关闭时会自动通过closeEvent刷新数据，无需手动调用

        except Exception as e:
            logging.error(f"打开对比牧场管理器失败: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"打开对比牧场管理器失败：\n{str(e)}")

    def preview_comparison_data(self, row, column):
        """预览对比数据"""
        try:
            # 获取行数据
            name_item = self.comparison_sources_table.item(row, 2)
            if not name_item:
                return

            data = name_item.data(Qt.ItemDataRole.UserRole)
            source_type = data['type']
            source_id = data['id']

            # 根据类型获取数据
            if source_type == 'farm':
                farm = self.benchmark_manager.get_farm_by_id(source_id)
                if not farm:
                    QMessageBox.warning(self, "警告", "未找到该对比牧场数据")
                    return

                # 显示对比牧场数据预览
                self._show_farm_preview(farm)

            else:  # reference
                reference = self.benchmark_manager.get_reference_by_id(source_id)
                if not reference:
                    QMessageBox.warning(self, "警告", "未找到该外部参考数据")
                    return

                # 显示外部参考数据预览
                self._show_reference_preview(reference)

        except Exception as e:
            logging.error(f"预览对比数据失败: {e}", exc_info=True)
            QMessageBox.warning(self, "预览失败", f"预览数据时发生错误：\n{str(e)}")

    def _show_farm_preview(self, farm):
        """显示对比牧场数据预览"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QTabWidget, QWidget, QTableWidget, QTableWidgetItem

        dialog = QDialog(self)
        dialog.setWindowTitle(f"对比牧场预览 - {farm['name']}")
        dialog.setMinimumSize(1000, 700)

        layout = QVBoxLayout(dialog)

        # 基本信息
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(150)

        content = f"<h2>{farm['name']}</h2>"
        content += f"<p><b>描述：</b>{farm.get('description', '无')}</p>"
        content += f"<p><b>添加日期：</b>{farm.get('added_date', '未知')[:10]}</p>"
        content += f"<p><b>最后更新：</b>{farm.get('last_updated', '未知')[:10]}</p>"

        info_text.setHtml(content)
        layout.addWidget(info_text)

        # Tab控件，分别显示在群母牛和全部母牛数据
        tab_widget = QTabWidget()

        # 在群母牛Tab
        if 'data_summary' in farm and 'present_summary' in farm['data_summary']:
            present = farm['data_summary']['present_summary']
            present_tab = self._create_data_preview_table(present)
            tab_widget.addTab(present_tab, f"在群母牛 ({present.get('cow_count', 0)}头)")

        # 全部母牛Tab
        if 'data_summary' in farm and 'all_summary' in farm['data_summary']:
            all_cows = farm['data_summary']['all_summary']
            all_tab = self._create_data_preview_table(all_cows)
            tab_widget.addTab(all_tab, f"全部母牛 ({all_cows.get('cow_count', 0)}头)")

        layout.addWidget(tab_widget)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def _create_data_preview_table(self, data_summary):
        """创建数据预览表格"""
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QLabel

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 获取年份和性状
        year_rows = data_summary.get('year_rows', [])
        traits = data_summary.get('traits', [])
        data = data_summary.get('data', {})

        # 检查是否有有效数据
        has_data = False
        for year_data in data.values():
            if any(v is not None for v in year_data.values()):
                has_data = True
                break

        # 如果没有有效数据，显示提示信息
        if not has_data:
            warning_label = QLabel(
                "⚠️ 该文件中所有性状数据都为空\n\n"
                "请确保：\n"
                "1. 已在Excel文件中填写实际数值\n"
                "2. 数据格式正确（数字类型）\n"
                "3. 列名格式正确（平均TPI、平均NM$等）\n\n"
                "建议：下载模板文件，参考示例数据格式"
            )
            warning_label.setStyleSheet("""
                QLabel {
                    color: #e74c3c;
                    background-color: #fdecea;
                    border: 2px solid #e74c3c;
                    border-radius: 5px;
                    padding: 20px;
                    font-size: 14px;
                }
            """)
            warning_label.setWordWrap(True)
            layout.addWidget(warning_label)

        # 创建表格
        table = QTableWidget()

        # 设置表格大小
        table.setRowCount(len(year_rows))
        table.setColumnCount(len(traits) + 1)  # +1 for year column

        # 设置表头
        headers = ['年份'] + [t.replace('平均', '') for t in traits]
        table.setHorizontalHeaderLabels(headers)

        # 填充数据
        for row_idx, year in enumerate(year_rows):
            # 年份列
            year_item = QTableWidgetItem(str(year))
            table.setItem(row_idx, 0, year_item)

            # 性状数据列
            year_data = data.get(str(year), {})
            for col_idx, trait in enumerate(traits):
                value = year_data.get(trait)
                if value is not None:
                    value_item = QTableWidgetItem(f"{value:.2f}")
                else:
                    value_item = QTableWidgetItem("-")
                table.setItem(row_idx, col_idx + 1, value_item)

        # 设置表格样式
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        # 为性状列设置固定宽度，避免列太多时每列太窄
        for i in range(1, len(headers)):
            table.setColumnWidth(i, 100)  # 每列100像素宽度

        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(False)  # 禁用最后一列自动拉伸

        layout.addWidget(table)

        return widget

    def _show_reference_preview(self, reference):
        """显示外部参考数据预览"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton

        dialog = QDialog(self)
        dialog.setWindowTitle(f"外部参考数据预览 - {reference['name']}")
        dialog.setMinimumSize(1000, 700)

        layout = QVBoxLayout(dialog)

        # 基本信息
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(150)

        content = f"<h2>{reference['name']}</h2>"
        content += f"<p><b>描述：</b>{reference.get('description', '无')}</p>"
        content += f"<p><b>添加日期：</b>{reference.get('added_date', '未知')[:10]}</p>"
        content += f"<p><b>最后更新：</b>{reference.get('last_updated', '未知')[:10]}</p>"
        content += f"<p><b>用途：</b><span style='color: #e67e22;'>仅用于折线图对比，不添加到表格</span></p>"

        info_text.setHtml(content)
        layout.addWidget(info_text)

        # 显示数据表格
        if 'data_summary' in reference and 'present_summary' in reference['data_summary']:
            data = reference['data_summary']['present_summary']
            data_table = self._create_data_preview_table(data)
            layout.addWidget(data_table)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def run_pedigree_analysis(self):
        """运行系谱识别情况分析"""
        if not self.selected_project_path:
            raise Exception("未选择项目")
            
        # 检查母牛数据是否存在
        cow_data_file = self.selected_project_path / "standardized_data" / "processed_cow_data.xlsx"
        if not cow_data_file.exists():
            raise Exception("请先上传母牛数据")
            
        try:
            # 读取母牛数据
            cow_df = pd.read_excel(cow_data_file)
            
            # 创建并运行系谱分析计算
            from core.breeding_calc.pedigree_analysis import PedigreeAnalysis
            analyzer = PedigreeAnalysis()
            
            # 执行分析
            result_df = analyzer.analyze_pedigree_completeness(
                cow_df, 
                self.selected_project_path
            )
            
            # 保存结果
            output_file = self.selected_project_path / "analysis_results" / "结果-系谱识别情况分析.xlsx"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            result_df.to_excel(output_file, index=False)
            
            return True
            
        except Exception as e:
            raise Exception(f"系谱识别分析失败: {str(e)}")
    
    def run_cow_key_traits(self):
        """运行母牛关键性状分析"""
        # 直接调用关键性状页面的计算方法
        if hasattr(self, 'cow_key_traits_page'):
            # 触发计算
            self.cow_key_traits_page.on_calculate()
            return True
        else:
            raise Exception("关键性状分析页面未初始化")
    
    def run_cow_index_calculation(self):
        """运行母牛育种指数计算"""
        # 直接调用指数计算页面的计算方法
        if hasattr(self, 'index_calculation_page'):
            # 触发计算
            self.index_calculation_page.on_calculate()
            return True
        else:
            raise Exception("指数计算页面未初始化")
    
    def show_about_dialog(self):
        """显示关于对话框"""
        from version import get_version, get_version_info, get_version_history
        
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle("关于")
        about_dialog.setMinimumWidth(600)
        about_dialog.setMinimumHeight(500)
        
        layout = QVBoxLayout(about_dialog)
        
        # 软件标题
        title_label = QLabel("伊利奶牛选配")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                padding: 20px;
                color: black;
            }
        """)
        layout.addWidget(title_label)
        
        # 版本信息
        version_info = get_version_info()
        if version_info:
            version_label = QLabel(f"版本：{version_info['version']}")
            version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            version_label.setStyleSheet("""
                QLabel {
                    font-size: 16px;
                    padding: 5px;
                    color: black;
                }
            """)
            layout.addWidget(version_label)
            
            date_label = QLabel(f"发布日期：{version_info['date']}")
            date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            date_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    padding: 5px;
                    color: black;
                }
            """)
            layout.addWidget(date_label)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)
        
        # 版本历史
        history_label = QLabel("版本更新内容：")
        history_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 10px 10px 5px 10px;
                color: black;
            }
        """)
        layout.addWidget(history_label)
        
        # 创建文本浏览器显示更新历史
        history_browser = QTextBrowser()
        history_browser.setStyleSheet("""
            QTextBrowser {
                border: 1px solid #ddd;
                padding: 10px;
                background-color: #f8f9fa;
                color: black;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        
        # 构建更新历史文本
        history_text = ""
        version_history = get_version_history()
        for version in version_history:
            history_text += f"<h3>版本 {version['version']} ({version['date']})</h3>"
            history_text += "<ul>"
            for change in version['changes']:
                history_text += f"<li>{change}</li>"
            history_text += "</ul><br>"
        
        history_browser.setHtml(history_text)
        layout.addWidget(history_browser)
        
        # 版权信息
        copyright_label = QLabel("© 2025 伊利奶牛选配开发团队")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                padding: 10px;
                color: black;
            }
        """)
        layout.addWidget(copyright_label)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 30px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        close_btn.clicked.connect(about_dialog.close)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        about_dialog.exec()

class GroupDesignDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("分组方式设计")
        self.setMinimumWidth(800)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 创建分组策略设置页面
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # 添加参数设置
        param_form_layout = QFormLayout()
        
        self.reserve_age = QSpinBox()
        self.reserve_age.setRange(0, 1000)
        self.reserve_age.setSuffix(" 天")
        self.reserve_age.setValue(420)  # 默认值
        
        self.cycle_days = QSpinBox()
        self.cycle_days.setRange(0, 365)
        self.cycle_days.setSuffix(" 天")
        self.cycle_days.setValue(21)  # 默认值
        
        param_form_layout.addRow("后备牛开配日龄:", self.reserve_age)
        param_form_layout.addRow("选配周期:", self.cycle_days)
        
        main_layout.addLayout(param_form_layout)
        
        # 添加策略表
        strategy_table_label = QLabel("配种策略设置:")
        main_layout.addWidget(strategy_table_label)
        
        # 创建选配策略表
        self.strategy_table = StrategyTableManager.create_strategy_table(main_widget)
        
        main_layout.addWidget(self.strategy_table)
        layout.addWidget(main_widget)
        
        # 添加保存按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept(self):
        """保存分组方式设计"""
        strategy_name, ok = QInputDialog.getText(
            self, "保存分组方式", "请输入分组方式名称:"
        )
        
        if ok and strategy_name:
            try:
                # 准备策略数据
                strategy_data = {
                    "params": {
                        "reserve_age": self.reserve_age.value(),
                        "cycle_days": self.cycle_days.value()
                    },
                    "strategy_table": StrategyTableManager.get_strategy_table_data(self.strategy_table)
                }
                
                # 保存策略
                from core.grouping.group_manager import GroupManager
                GroupManager.save_strategy(strategy_name, strategy_data)
                super().accept()
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存分组方式时发生错误：{str(e)}")

    def get_strategy_table_data(self):
        """获取策略表数据"""
        data = []
        for row in range(self.strategy_table.rowCount()):
            # 跳过分隔行或无效行
            if row >= self.strategy_table.rowCount():
                continue
                
            # 检查是否有有效的分组名称单元格
            name_item = self.strategy_table.item(row, 0)
            if name_item is None:
                continue
                
            # 获取比例，如果为空或无效则设为0
            ratio_item = self.strategy_table.item(row, 1)
            ratio_text = ratio_item.text() if ratio_item is not None else "0"
            try:
                ratio = float(ratio_text or "0")
            except ValueError:
                ratio = 0
                
            # 安全地获取配种方法
            breeding_methods = []
            for col in range(2, 6):
                combo = self.strategy_table.cellWidget(row, col)
                if combo is not None:
                    breeding_methods.append(combo.currentText())
                else:
                    # 如果下拉框不存在，添加默认值
                    breeding_methods.append("常规冻精")
            
            row_data = {
                "group": name_item.text(),
                "ratio": ratio,
                "breeding_methods": breeding_methods
            }
            data.append(row_data)
        return data

class ClassifySemenDialog(QDialog):
    """用于手动分类未识别冻精编号的对话框"""
    def __init__(self, unclassified_bull_ids, parent=None):
        super().__init__(parent)
        self.unclassified_bull_ids = unclassified_bull_ids # 输入改为 bull_ids
        self.classifications = {}
        self.setWindowTitle("冻精分类") # 修改标题
        self.setMinimumWidth(400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        label = QLabel("发现以下无法自动识别的冻精编号，请手动分类：") # 修改提示文字
        layout.addWidget(label)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["冻精编号", "选择分类"]) # 修改列标题
        self.table.setRowCount(len(self.unclassified_bull_ids))

        self.combos = []
        for i, bull_id in enumerate(self.unclassified_bull_ids):
            original_item = QTableWidgetItem(bull_id) # 显示 bull_id
            original_item.setFlags(original_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, original_item)

            combo = QComboBox()
            combo.addItems(["常规", "性控"])
            self.table.setCellWidget(i, 1, combo)
            self.combos.append(combo)

        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept(self):
        for i, bull_id in enumerate(self.unclassified_bull_ids):
            self.classifications[bull_id] = self.combos[i].currentText() # key 改为 bull_id
        super().accept()

    def get_classifications(self):
        return self.classifications
  
