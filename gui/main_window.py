import sys
import os
import shutil
from pathlib import Path

from PyQt6.QtCore import (
    Qt, QDir, QUrl, pyqtSignal, QThread, Qt
)
from PyQt6.QtGui import (
    QFileSystemModel, QDesktopServices, QBrush, QPalette, QPixmap
)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QFileDialog, QMessageBox, QLabel, 
    QListWidget, QListWidgetItem, QStackedWidget, QInputDialog, 
    QFrame, QTreeView, QGridLayout, QAbstractItemView, QMenu,QGraphicsOpacityEffect,
    QStackedLayout
)
import warnings
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
from gui.worker import CowDataWorker, GenomicDataWorker
from gui.progress import ProgressDialog
from gui.db_update_worker import DBUpdateWorker
from core.breeding_calc.bull_traits_calc import BullKeyTraitsPage  
from core.breeding_calc.index_page import IndexCalculationPage
from core.breeding_calc.mated_bull_traits_calc import MatedBullKeyTraitsPage  
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QFileDialog, QMessageBox, QLabel, 
    QListWidget, QListWidgetItem, QStackedWidget, QInputDialog, 
    QFrame, QTreeView
)
from PyQt6.QtCore import Qt, QDir
from PyQt6.QtGui import QFileSystemModel, QPixmap
from pathlib import Path


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
        
        # 先创建所有页面实例，仅创建一次
        self.cow_key_traits_page = CowKeyTraitsPage(parent=self)
        self.bull_key_traits_page = BullKeyTraitsPage(parent=self)
        self.index_calculation_page = IndexCalculationPage(parent=self)
        self.mated_bull_key_traits_page = MatedBullKeyTraitsPage(parent=self)
        
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
            ("关键育种性状分析", "chart", []), # 移除子导航
            ("牛只指数计算排名", "chart", []),
            ("配种记录分析", "analysis", []),
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
                # 第2页为关键育种性状分析页面
                self.content_stack.setCurrentIndex(2)
            elif text == "牛只指数计算排名":
                # 第3页为指数计算页面
                self.content_stack.setCurrentIndex(3)
                
            self.update_nav_selected_style()

    # 新增“数据上传”页面函数
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
        if self.selected_project_path is None:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return

        if not file_paths:
            return

        # 根据 display_name 来选择不同的处理逻辑
        try:
            if display_name == "母牛数据":
                # 使用 Worker 处理母牛数据，并显示进度条
                self.progress_dialog = ProgressDialog(self)
                self.progress_dialog.set_task_info("上传并处理母牛数据", 0, 100)
                self.progress_dialog.show()

                self.thread = QThread()
                self.worker = CowDataWorker(file_paths, self.selected_project_path)
                self.worker.moveToThread(self.thread)

                # 连接信号与槽
                self.thread.started.connect(self.worker.run)
                self.worker.progress.connect(self.progress_dialog.update_progress)
                self.worker.message.connect(self.progress_dialog.update_info)
                self.worker.finished.connect(self.on_worker_finished)
                self.worker.finished.connect(self.thread.quit)
                self.worker.finished.connect(self.worker.deleteLater)
                self.thread.finished.connect(self.thread.deleteLater)
                self.worker.error.connect(self.on_worker_error)

                self.thread.start()
            elif display_name == "基因组检测数据":
                # 处理基因组检测数据
                self.progress_dialog = ProgressDialog(self)
                self.progress_dialog.set_task_info("上传并处理基因组检测数据", 0, 100)
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
                final_path = None
                if display_name == "母牛数据":
                    final_path = upload_and_standardize_cow_data(file_paths, self.selected_project_path)
                elif display_name == "配种记录":
                    final_path = upload_and_standardize_breeding_data(file_paths, self.selected_project_path)
                elif display_name == "体型外貌数据":
                    final_path = upload_and_standardize_body_data(file_paths, self.selected_project_path)
                elif display_name == "备选公牛数据":
                    final_path = upload_and_standardize_bull_data(file_paths, self.selected_project_path)
                else:
                    raise ValueError(f"未知的数据类型: {display_name}")

                QMessageBox.information(self, "成功", f"{display_name}文件已成功上传并标准化，标准化文件路径：{final_path}")
        except NotImplementedError as nie:
            QMessageBox.warning(self, "功能未实现", str(nie))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"文件上传或标准化时发生错误：{str(e)}")

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

        # 将用户选择的路径转为Path对象列表
        input_files = [Path(p) for p in file_paths]

        # 调用上传处理逻辑
        self.handle_file_upload(input_files, display_name)

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

