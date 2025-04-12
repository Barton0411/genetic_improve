import sys
import os
import shutil
from pathlib import Path
import json
import logging

from PyQt6.QtCore import (
    Qt, QDir, QUrl, pyqtSignal, QThread, QTimer
)
from PyQt6.QtGui import (
    QFileSystemModel, QDesktopServices, QBrush, QPalette, QPixmap
)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QFileDialog, QMessageBox, QLabel, 
    QListWidget, QListWidgetItem, QStackedWidget, QInputDialog, 
    QFrame, QTreeView, QGridLayout, QAbstractItemView, QMenu, QGraphicsOpacityEffect,
    QStackedLayout, QGroupBox, QComboBox, QCheckBox, QTableWidget, QTableWidgetItem, 
    QHeaderView, QLineEdit, QTabWidget, QFormLayout, QSpinBox, QDialogButtonBox, 
    QDialog, QProgressDialog, QApplication, QTextBrowser, QSizePolicy
)
import warnings

from core.inbreeding.inbreeding_page import InbreedingPage
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
            strategy_table.setItem(i, 0, name_item)
            
            # 添加分配比例输入
            ratio_item = QTableWidgetItem("0")
            strategy_table.setItem(i, 1, ratio_item)
            
            # 添加配种方式选择下拉框
            for j in range(2, 6):
                combo = QComboBox()
                combo.addItems(["常规冻精", "普通性控", "超级性控", "肉牛冻精", "胚胎"])
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
                            }
                            QComboBox::drop-down {
                                subcontrol-origin: padding;
                                subcontrol-position: right center;
                                width: 15px;
                                border-left: none;
                            }
                            QComboBox::down-arrow {
                                width: 8px;
                                height: 8px;
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
        super().__init__()
        self.settings = Settings()
        self.username = username
        self.content_stack = QStackedWidget()
        self.selected_project_path = None
        self.templates_path = Path(__file__).parent.parent / "templates"
        
        # 创建所有页面实例
        self.cow_key_traits_page = CowKeyTraitsPage(parent=self)
        self.bull_key_traits_page = BullKeyTraitsPage(parent=self)
        self.index_calculation_page = IndexCalculationPage(parent=self)
        self.mated_bull_key_traits_page = MatedBullKeyTraitsPage(parent=self)
        # 添加新的近交分析页面实例
        self.inbreeding_page = InbreedingPage(parent=self)  # 新增
        
        self.setup_ui()
        self.check_and_update_database_on_startup()

    def setup_ui(self):
        self.setWindowTitle("奶牛育种智选报告专家")
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
        nav_frame.setStyleSheet("""
            QFrame {
                background-color: #2c3e50;
                border: none;
            }
        """)
        nav_layout = QVBoxLayout(nav_frame)
        
        # 修改导航项结构，使用嵌套列表表示父子关系
        nav_items = [
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
                background-color: #2c3e50;
                border: none;
            }
            QListWidget::item {
                color: white;
                padding: 10px;
                margin: 2px 0px;
            }
            QListWidget::item:selected {
                background-color: #34495e;
            }
            QListWidget::item:hover {
                background-color: #3498db;
            }
        """)

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
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(0)  # 移除按钮间距
        
        # 创建按钮样式
        normal_style = """
            QPushButton {
                background-color: #f0f0f0;
                color: #333;
                border: none;
                font-size: 14px;
                padding: 10px 30px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """

        selected_style = """
            QPushButton {
                background-color: #3498db;  /* 蓝色背景 */
                color: white;              /* 白色文字 */
                border: none;
                font-size: 14px;
                padding: 10px 30px;
                min-width: 120px;
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
        self.create_project_page()         # 第0页：项目管理
        self.create_upload_page()          # 第1页：数据上传 
        genetic_analysis_page = self.create_genetic_analysis_page()  # 第2页：关键育种性状分析
        self.content_stack.addWidget(genetic_analysis_page)
        self.content_stack.addWidget(self.index_calculation_page)    # 第3页：指数计算排名
        self.content_stack.addWidget(self.inbreeding_page)          # 第4页：近交分析页面
        self.content_stack.addWidget(self.create_mating_page())     # 第5页：个体选配页面

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

    def on_file_double_clicked(self, index):
        """双击文件时打开文件"""
        if not index.isValid():
            return
        file_path = self.file_system_model.filePath(index)
        if Path(file_path).is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        else:
            # 如果是文件夹，可根据需要选择性实现进入目录的逻辑
            pass

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
        用户确认选择后更改选中项的样式表，以使选中项颜色更显眼
        """
        self.nav_list.setStyleSheet("""
            QListWidget {
                background-color: #2c3e50;
                border: none;
                outline: none; /* 移除列表焦点框 */
            }
                                    
            QListWidget:focus {
                outline: none; /* 移除获得焦点时的虚线轮廓 */
                border: none;
            }

            QListWidget::item {
                color: white;
                padding: 10px;
                margin: 2px 0px;
            }
            QListWidget::item:selected {
                background-color: #3498db; /* 明亮的蓝色背景 */
                outline: none; /* 移除选中项的虚线框 */
            }

            QListWidget::item:focus {
                outline: none; /* 移除项目获得焦点时的虚线框 */
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
                    final_path = upload_and_standardize_bull_data(file_paths, self.selected_project_path)
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
        self.progress_dialog.close()
        QMessageBox.critical(self, "错误", f"上传或标准化母牛数据时发生错误：\n{error_message}")

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
        self.progress_dialog = ProgressDialog(self)
        self.progress_dialog.setWindowTitle("数据库更新")
        self.progress_dialog.title_label.setText("正在检查和更新本地数据库...")
        self.progress_dialog.progress_bar.setRange(0, 0)  # 不显示具体进度
        self.progress_dialog.show()

        # 创建线程和 worker
        self.db_update_thread = QThread()
        self.db_update_worker = DBUpdateWorker()
        self.db_update_worker.moveToThread(self.db_update_thread)

        # 连接信号与槽
        self.db_update_thread.started.connect(self.db_update_worker.run)
        self.db_update_worker.finished.connect(self.on_db_update_finished)
        self.db_update_worker.error.connect(self.on_db_update_error)
        self.db_update_worker.finished.connect(self.db_update_thread.quit)
        self.db_update_worker.finished.connect(self.db_update_worker.deleteLater)
        self.db_update_thread.finished.connect(self.db_update_thread.deleteLater)
        self.db_update_worker.error.connect(self.db_update_thread.quit)
        self.db_update_worker.error.connect(self.db_update_worker.deleteLater)

        # 启动线程
        self.db_update_thread.start()

    def on_db_update_finished(self):
        """处理数据库更新完成的信号"""
        self.progress_dialog.close()
        QMessageBox.information(self, "更新完成", "本地数据库已成功检查和更新。")

    def on_db_update_error(self, error_message: str):
        """处理数据库更新错误的信号"""
        self.progress_dialog.close()
        QMessageBox.critical(self, "更新错误", f"数据库更新过程中发生错误：\n{error_message}")

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

        # 创建左右分栏布局
        h_layout = QHBoxLayout()
        
        # 左侧面板 - 参数设置和分组设计
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # 1. 选配参数设置区域
        param_group = QGroupBox("选配参数设置")
        param_layout = QVBoxLayout()
        
        # 近交系数阈值设置
        inbreeding_layout = QHBoxLayout()
        inbreeding_label = QLabel("近交系数阈值:")
        self.inbreeding_combo = QComboBox()
        self.inbreeding_combo.addItems(["≤3.125%", "≤6.25%", "≤12.5%", "无视近交"])
        inbreeding_layout.addWidget(inbreeding_label)
        inbreeding_layout.addWidget(self.inbreeding_combo)
        inbreeding_layout.addStretch()
        
        # 隐性基因控制设置
        gene_control_layout = QHBoxLayout()
        self.gene_control_checkbox = QCheckBox("控制隐性基因")
        self.gene_control_checkbox.setChecked(True)
        gene_control_layout.addWidget(self.gene_control_checkbox)
        gene_control_layout.addStretch()
        
        param_layout.addLayout(inbreeding_layout)
        param_layout.addLayout(gene_control_layout)
        param_group.setLayout(param_layout)
        
        # 2. 分组设计区域
        design_group = QGroupBox("分组方式设计")
        design_layout = QVBoxLayout()
        
        # 创建分组策略设置页面
        strategy_widget = QWidget()
        strategy_layout = QVBoxLayout(strategy_widget)
        strategy_layout.setContentsMargins(0, 0, 0, 0)  # 减少内边距
        strategy_layout.setSpacing(5)  # 减少组件间距
        
        # 添加参数设置
        param_form_layout = QFormLayout()
        param_form_layout.setContentsMargins(0, 0, 0, 0)  # 减少内边距
        param_form_layout.setVerticalSpacing(5)  # 减少垂直间距
        
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
        
        strategy_layout.addLayout(param_form_layout)
        
        # 添加策略表
        strategy_table_label = QLabel("配种策略设置:")
        strategy_layout.addWidget(strategy_table_label)
        
        # 创建选配策略表
        self.strategy_table = StrategyTableManager.create_strategy_table(strategy_widget)
        
        strategy_layout.addWidget(self.strategy_table)
        design_layout.addWidget(strategy_widget)
        
        # 紧凑布局，减少各组件间距
        design_layout.setSpacing(5)  # 减少组件间距
        strategy_layout.setSpacing(5)  # 减少组件间距
        
        # 让策略区域紧凑显示，不拉伸
        strategy_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        
        # 添加已保存策略列表 - 修改为垂直布局
        saved_strategies_layout = QVBoxLayout()  # 改为垂直布局 QVBoxLayout
        saved_strategies_label = QLabel("已保存策略:")
        saved_strategies_label.setFixedHeight(80)  # 设置标签固定高度
        saved_strategies_layout.addWidget(saved_strategies_label)  # 先添加标签

        self.strategies_list = QListWidget()
        self.strategies_list.setMaximumHeight(130)  # 设置列表框高度
        self.strategies_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 2px;
                background-color: white;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 2px;
            }
        """)
        saved_strategies_layout.addWidget(self.strategies_list)  # 再添加列表框
        design_layout.addLayout(saved_strategies_layout)
        
        # 底部按钮布局 - 极简风格
        button_layout = QHBoxLayout()
        button_style = """
            QPushButton {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 2px;
                padding: 4px 8px;
                min-width: 80px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e9e9e9;
            }
            QPushButton:pressed {
                background-color: #d5d5d5;
            }
        """
        
        load_strategy_btn = QPushButton("加载策略")
        load_strategy_btn.setStyleSheet(button_style)
        load_strategy_btn.clicked.connect(self.load_selected_strategy)
        
        delete_strategy_btn = QPushButton("删除策略")
        delete_strategy_btn.setStyleSheet(button_style)
        delete_strategy_btn.clicked.connect(self.delete_selected_strategy)
        
        save_strategy_btn = QPushButton("保存方式")
        save_strategy_btn.setStyleSheet(button_style)
        save_strategy_btn.clicked.connect(self.save_group_strategy)
        
        apply_strategy_btn = QPushButton("应用方式")
        apply_strategy_btn.setStyleSheet(button_style)
        apply_strategy_btn.clicked.connect(self.apply_group_strategy)
        
        explain_logic_btn = QPushButton("逻辑说明")
        explain_logic_btn.setStyleSheet(button_style)
        explain_logic_btn.clicked.connect(self.show_group_logic_explanation)
        
        button_layout.addWidget(load_strategy_btn)
        button_layout.addWidget(delete_strategy_btn)
        button_layout.addWidget(save_strategy_btn)
        button_layout.addWidget(apply_strategy_btn)
        button_layout.addWidget(explain_logic_btn)
        button_layout.addStretch()
        
        # 添加按钮到布局
        design_layout.addLayout(button_layout)
        
        # 减少布局的边距
        design_layout.setContentsMargins(5, 5, 5, 5)
        
        design_group.setLayout(design_layout)
        
        # 将分组和参数设置添加到左侧面板
        left_layout.addWidget(param_group)
        left_layout.addWidget(design_group)
        
        # 右侧面板 - 分组预览
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 分组预览区域
        preview_group = QGroupBox("分组预览")
        preview_layout = QVBoxLayout()
        
        # 创建预览表格
        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(4)
        self.preview_table.setHorizontalHeaderLabels(["耳标号", "胎次", "DIM", "分组"])
        preview_layout.addWidget(self.preview_table)
        
        preview_group.setLayout(preview_layout)
        right_layout.addWidget(preview_group)
        
        # 添加左右面板到水平布局
        h_layout.addWidget(left_panel, stretch=1)
        h_layout.addWidget(right_panel, stretch=1)
        
        # 将水平布局添加到主布局
        layout.addLayout(h_layout)
        
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
                min-width: 150px;
                padding: 5px;
            }
            QCheckBox {
                padding: 5px;
            }
            QLabel {
                font-size: 12px;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
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
        
        # 加载已保存的策略列表
        self.load_strategy_list()
        
        return page

    def load_strategy_list(self):
        """加载已保存的策略列表"""
        from core.grouping.group_manager import GroupManager
        self.strategies_list.clear()
        strategies = GroupManager.list_strategies()
        self.strategies_list.addItems(strategies)

    def load_selected_strategy(self):
        """加载选中的策略"""
        if not self.strategies_list.currentItem():
            QMessageBox.warning(self, "警告", "请先选择一个策略")
            return

        try:
            from core.grouping.group_manager import GroupManager
            strategy_name = self.strategies_list.currentItem().text()
            
            # 创建临时的GroupManager实例来加载策略
            group_manager = GroupManager(self.selected_project_path)
            group_manager.load_strategy(strategy_name)
            
            # 更新界面上的参数
            params = group_manager.strategy['params']
            self.reserve_age.setValue(params.get('reserve_age', 0))
            self.cycle_days.setValue(params.get('cycle_days', 0))
            
            # 使用策略表格管理器加载策略
            StrategyTableManager.load_strategy_to_table(self.strategy_table, group_manager.strategy)
            
            QMessageBox.information(self, "成功", f"已加载策略：{strategy_name}")
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"加载策略错误详情: {error_details}")
            QMessageBox.critical(self, "错误", f"加载策略时发生错误：{str(e)}\n\n请检查是否选择了正确的牧场项目。")

    def delete_selected_strategy(self):
        """删除选中的策略"""
        if not self.strategies_list.currentItem():
            QMessageBox.warning(self, "警告", "请先选择一个策略")
            return

        strategy_name = self.strategies_list.currentItem().text()
        reply = QMessageBox.question(
            self, 
            "确认删除", 
            f'确定要删除策略"{strategy_name}"吗？此操作不可恢复！',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                from core.grouping.group_manager import GroupManager
                GroupManager.delete_strategy(strategy_name)
                self.load_strategy_list()  # 刷新列表
                QMessageBox.information(self, "成功", "策略已删除")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除策略时发生错误：{str(e)}")

    def save_group_strategy(self):
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
                QMessageBox.information(self, "成功", "分组方式已保存")
                
                # 刷新策略列表
                self.load_saved_strategies()
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存分组方式时发生错误：{str(e)}")

    def apply_group_strategy(self):
        """应用当前的临时分组策略"""
        if not self.check_index_file_exists():
            return
        
        # 确保项目路径存在
        if self.selected_project_path is None:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return
            
        try:
            from core.grouping.group_manager import GroupManager
            
            # 获取控件值
            reserve_age = self.reserve_age.value() if hasattr(self, 'reserve_age') else 420
            cycle_days = self.cycle_days.value() if hasattr(self, 'cycle_days') else 21
            
            # 构建分组策略
            current_strategy = {
                "params": {
                    "reserve_age": reserve_age,
                    "cycle_days": cycle_days
                },
                "strategy_table": StrategyTableManager.get_strategy_table_data(self.strategy_table)
            }
            
            # 打印调试信息
            print(f"项目路径: {self.selected_project_path}")
            print(f"策略参数: {current_strategy['params']}")
            
            # 创建进度对话框
            progress = ProgressDialog(self)
            progress.setWindowTitle("分组进度")
            progress.set_task_info("正在准备分组数据...")
            progress.show()
            
            try:
                # 创建临时策略并应用
                group_manager = GroupManager(self.selected_project_path)
                
                # 添加详细错误处理
                try:
                    # 真正的分组处理
                    df = group_manager.apply_temp_strategy(current_strategy, progress_callback=progress)
                    
                    # 直接更新到原始指数文件，而不是创建新文件
                    progress.set_task_info("正在更新分组结果到指数计算文件...")
                    index_file = self.selected_project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
                    
                    # 读取原始指数文件
                    import pandas as pd
                    try:
                        index_df = pd.read_excel(index_file)
                        
                        # 如果index_df中已有group列，先删除
                        if 'group' in index_df.columns:
                            index_df = index_df.drop(columns=['group'])
                        
                        # 只保留group列进行更新
                        group_col = df[['cow_id', 'group']]
                        
                        # 将group列合并到原始指数文件
                        index_df = pd.merge(index_df, group_col, on='cow_id', how='left')
                        
                        # 保存更新后的文件
                        index_df.to_excel(index_file, index=False)
                        
                        # 显示分组统计信息
                        group_counts = df.groupby('group').size().reset_index(name='count')
                        group_stats = "\n".join([f"{row['group']}: {row['count']}头" for _, row in group_counts.iterrows()])
                        
                        # 完成处理，确保进度对话框关闭
                        progress.set_task_info("分组完成")
                        progress.update_progress(100)
                        
                        # 使用QTimer延迟关闭，确保UI更新
                        QTimer.singleShot(500, progress.close)
                        
                        # 在进度条关闭后显示成功消息
                        QTimer.singleShot(600, lambda: QMessageBox.information(
                            self, "成功", f"分组完成！\n分组统计：\n{group_stats}\n\n结果已更新到：\n{index_file}"
                        ))
                        
                    except Exception as e:
                        raise Exception(f"更新指数文件时发生错误: {str(e)}")
                
                except Exception as e:
                    # 出错时也确保关闭进度对话框
                    progress.close()
                    
                    error_message = str(e)
                    import traceback
                    error_traceback = traceback.format_exc()
                    print(f"错误详情: {error_traceback}")
                    QMessageBox.critical(self, "错误", f"应用分组策略时发生错误：{error_message}\n\n请检查控制台输出以获取详细信息。")
                
            except Exception as e:
                # 发生异常时关闭进度对话框
                progress.close()
                QMessageBox.critical(self, "错误", f"初始化分组过程时发生错误：{str(e)}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"应用分组策略时发生错误：{str(e)}")

    def update_preview_table(self, df):
        """更新预览表格"""
        self.preview_table.setRowCount(len(df))
        
        # 设置表格数据
        for i, (_, row) in enumerate(df.iterrows()):
            self.preview_table.setItem(i, 0, QTableWidgetItem(str(row['cow_id'])))
            self.preview_table.setItem(i, 1, QTableWidgetItem(str(row['lac'])))
            self.preview_table.setItem(i, 2, QTableWidgetItem(str(row['DIM'])))
            self.preview_table.setItem(i, 3, QTableWidgetItem(str(row['group'])))
        
        # 调整列宽
        self.preview_table.resizeColumnsToContents()

    def check_index_file_exists(self):
        """检查指数计算结果文件是否存在"""
        if not self.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return False
        
        index_file = self.selected_project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
        if not index_file.exists():
            QMessageBox.warning(self, "警告", "请先进行牛只指数计算排名")
            return False
        
        return True

    def on_manual_grouping(self):
        """手动分组按钮点击事件"""
        if not self.check_index_file_exists():
            return
        
        # 打开指数文件进行编辑
        index_file = self.selected_project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
        os.startfile(str(index_file))

    def on_group_design(self):
        """分组方式设计按钮点击事件"""
        dialog = GroupDesignDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_saved_strategies()  # 重新加载策略列表

    def on_apply_strategy(self):
        """应用选中的分组方式"""
        if not self.strategies_list.currentItem():
            QMessageBox.warning(self, "警告", "请先选择一个分组方式")
            return
        
        if not self.check_index_file_exists():
            return
            
        # 确保项目路径存在
        if self.selected_project_path is None:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return
        
        try:
            from core.grouping.group_manager import GroupManager
            
            strategy_name = self.strategies_list.currentItem().text()
            
            # 打印调试信息
            print(f"应用策略: {strategy_name}")
            print(f"项目路径: {self.selected_project_path}")
            
            # 创建GroupManager实例
            try:
                group_manager = GroupManager(self.selected_project_path)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建GroupManager实例失败: {str(e)}")
                import traceback
                print(f"错误详情:\n{traceback.format_exc()}")
                return
            
            # 显示进度对话框
            progress = ProgressDialog(self)
            progress.setWindowTitle("分组进度")
            progress.set_task_info("正在应用分组策略...")
            progress.show()
            
            try:
                # 应用分组策略
                df = group_manager.apply_grouping(strategy_name)
                
                # 获取分组统计
                summary = group_manager.get_group_summary()
                
                # 显示分组结果
                msg = "分组完成！\n\n分组统计：\n"
                for _, row in summary.iterrows():
                    msg += f"{row['分组']}: {row['数量']}头\n"
                
                progress.set_task_info("分组完成")
                progress.update_progress(100)
                QMessageBox.information(self, "成功", msg)
                
            finally:
                # 确保进度对话框被关闭
                progress.close()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"应用分组策略时发生错误：{str(e)}")

    def on_delete_strategy(self):
        """删除选中的分组方式"""
        if not self.strategies_list.currentItem():
            QMessageBox.warning(self, "警告", "请先选择一个分组方式")
            return
            
        strategy_name = self.strategies_list.currentItem().text()
        reply = QMessageBox.question(self, "确认删除", 
                                   f"确定要删除分组方式 '{strategy_name}' 吗？",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                                   
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from core.grouping.group_manager import GroupManager
                GroupManager.delete_strategy(strategy_name)
                self.load_saved_strategies()  # 重新加载策略列表
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除分组方式时发生错误：{str(e)}")

    def load_saved_strategies(self):
        """加载已保存的分组方式列表"""
        self.strategies_list.clear()
        from core.grouping.group_manager import GroupManager
        for strategy_name in GroupManager.list_strategies():
            self.strategies_list.addItem(strategy_name)

    def start_breeding(self):
        """开始选配"""
        QMessageBox.information(self, "提示", "选配功能正在开发中...")

    def show_group_logic_explanation(self):
        """显示分组逻辑说明对话框"""
        explanation = """
<h3>分组逻辑详细说明</h3>

<p><b>基础筛选：</b>只考虑在场母牛（"是否在场" = "是"且sex = "母"）</p>

<h4>1. 牛只分类</h4>
<ul>
<li><b>后备牛：</b>胎次(lac) = 0</li>
<li><b>成母牛：</b>胎次(lac) > 0</li>
</ul>

<h4>2. 后备牛分组</h4>
<ul>
<li><b>已孕牛：</b>repro_status 为 "初检孕" 或 "复检孕"</li>
<li><b>难孕牛：</b>日龄 ≥ 18×30.8(约553天) 且未孕</li>
<li><b>周期分组：</b>对普通后备牛（非已孕/难孕）按日龄分周期
  <ul>
  <li>第1周期：18×30.8 > 日龄 ≥ (后备牛开配日龄-选配周期*1)</li>
  <li>第2周期：(后备牛开配日龄-选配周期*1) > 日龄 ≥ (后备牛开配日龄-选配周期*2)</li>
  <li>第n周期：(后备牛开配日龄-选配周期*(n-1)) > 日龄 ≥ (后备牛开配日龄-选配周期*n)</li>
  </ul>
</li>
</ul>

<h4>3. 成母牛分组</h4>
<ul>
<li><b>已孕牛：</b>repro_status 为 "初检孕" 或 "复检孕"</li>
<li><b>难孕牛：</b>泌乳天数(DIM) ≥ 150 且未孕</li>
<li><b>未孕牛：</b>非已孕且非难孕的成母牛</li>
</ul>

<h4>4. 遗传物质分配规则</h4>
<ol>
<li><b>已孕牛和难孕牛：</b>统一使用非性控</li>
<li><b>后备牛各周期：</b>
  <ul>
  <li>先按ranking排序（从小到大）</li>
  <li>根据配置的比例将每个周期内的牛分为A/B/C组：
    <ul>
    <li>A组：取排名前X%的牛（如前50%）</li>
    <li>B组：取排名接下来Y%的牛（如50%-80%）</li>
    <li>C组：取排名最后Z%的牛（如80%-100%）</li>
    </ul>
  </li>
  <li>对每组牛根据配种次数应用不同的配种方法：
    <ul>
    <li>第1次配种：使用各组设定的第1次配种方法</li>
    <li>第2次配种：使用各组设定的第2次配种方法</li>
    <li>第3次配种：使用各组设定的第3次配种方法</li>
    <li>第4次及以上配种：使用各组设定的第4次+配种方法</li>
    </ul>
  </li>
  </ul>
</li>
<li><b>成母牛未孕牛：</b>同样按ranking排序并分为A/B/C组，应用各自的配种策略</li>
</ol>

<h4>5. 性控/非性控判定</h4>
<ul>
<li><b>性控方法：</b>"普通性控"、"超级性控"</li>
<li><b>非性控方法：</b>"常规冻精"、"肉牛冻精"、"胚胎"</li>
</ul>

<h4>6. 结果标记</h4>
<ul>
<li>后备牛：后备牛第X周期+性控/非性控</li>
<li>后备牛特殊：后备牛已孕牛+非性控、后备牛难孕牛+非性控</li>
<li>成母牛：成母牛未孕牛+性控/非性控</li>
<li>成母牛特殊：成母牛已孕牛+非性控、成母牛难孕牛+非性控</li>
</ul>

<p>举例：某后备牛属于第1周期，ranking在该周期牛只前30%（属于A组），配种次数为1，A组第2次配种设置为"超级性控"，则该牛标记为 "后备牛第1周期+性控"</p>
"""
        
        # 创建对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("分组逻辑说明")
        dialog.setMinimumSize(800, 600)
        
        # 创建布局
        layout = QVBoxLayout(dialog)
        
        # 创建文本浏览器并设置富文本
        text_browser = QTextBrowser()
        text_browser.setHtml(explanation)
        layout.addWidget(text_browser)
        
        # 添加关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
        
        # 显示对话框
        dialog.exec()

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
  
