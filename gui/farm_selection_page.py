"""
伊起牛牧场数据对接页面 - 支持多选模式
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QMessageBox, QTableWidget, QTableWidgetItem,
    QDialog, QListWidget, QProgressDialog, QGroupBox, QFrame,
    QTreeWidget, QTreeWidgetItem, QCheckBox, QSplitter,
    QHeaderView, QButtonGroup, QRadioButton, QListWidgetItem,
    QAbstractItemView, QComboBox, QInputDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QBrush
from pathlib import Path
from datetime import datetime
import logging
import pandas as pd

from api.yqn_api_client import YQNApiClient
from api.hmy_api_client import HMYApiClient
from core.data.hmy_data_converter import HMYDataConverter
from core.data.yqn_data_converter import YQNDataConverter
from config.hmy_access import is_hmy_user_allowed
from utils.file_manager import FileManager
from core.data.uploader import upload_and_standardize_cow_data


HMY_CLASSIFICATION_OPTIONS = (
    ("大区", "area"),
    ("有机(HP)", "organic_hp"),
    ("热应激区域", "heat_stress"),
    ("牛源模式", "source_mode"),
    ("A2", "a2"),
    ("DHA", "dha"),
)


def _category_name(value) -> str:
    """把缺失分类统一归入“其他”组。"""
    normalized = str(value or "").strip()
    return normalized or "其他"


def _group_sort_key(name: str):
    """“其他”固定排在正常分类之后。"""
    if name == "是":
        return (0, name)
    if name == "否":
        return (1, name)
    if name == "其他":
        return (3, name)
    return (2, name)


def group_hmy_farms(farms: list, field: str) -> dict:
    """按慧牧云指定分类维度组织牧场。"""
    groups = {}
    for farm in farms:
        group_name = _category_name(farm.get(field))
        groups.setdefault(group_name, []).append(farm)
    return {
        name: groups[name]
        for name in sorted(groups, key=_group_sort_key)
    }


class DataDownloadWorker(QThread):
    """后台下载和处理数据的工作线程"""
    progress = pyqtSignal(int, str)  # (百分比, 状态消息)
    finished = pyqtSignal(Path)  # Excel文件路径
    error = pyqtSignal(str)  # 错误消息

    def __init__(
        self,
        api_client,
        farms,
        project_path,
        is_merged=False,
        local_farms=None,
    ):
        """
        初始化下载工作线程

        参数:
            api_client: API客户端
            farms: 牧场列表 [{"code": ..., "name": ..., "cow_count": ...}, ...]
            project_path: 项目路径
            is_merged: 是否为合并模式（多选）
        """
        super().__init__()
        self.api_client = api_client
        self.farms = farms
        self.project_path = project_path
        self.is_merged = is_merged
        self.local_farms = local_farms or []
        self.logger = logging.getLogger(__name__)

    def run(self):
        """执行数据下载和标准化流程"""
        try:
            total_farms = len(self.farms)
            all_api_data = []

            # 步骤1: 下载各牧场牛群数据
            for i, farm in enumerate(self.farms):
                farm_code = farm['code']
                farm_name = farm['name']

                progress_pct = int(10 + (i / total_farms) * 15)
                self.progress.emit(progress_pct, f"正在下载 {farm_name} 数据...")

                api_data = self.api_client.get_farm_herd(farm_code)
                cow_count = len(api_data.get('data', []))
                farm['cow_count'] = cow_count  # 更新实际数量

                all_api_data.append((farm_code, api_data))
                self.logger.info(f"下载牧场 {farm_code} 数据完成: {cow_count} 头")
                if cow_count:
                    farm_raw_dir = (
                        self.project_path
                        / "raw_data"
                        / "farms"
                        / str(farm_code)
                    )
                    YQNDataConverter.convert_herd_to_excel(
                        api_data, farm_raw_dir / "cow_data.xlsx"
                    )

            # 步骤2: 合并数据（如果是多选模式）
            self.progress.emit(25, "正在合并数据...")
            if self.is_merged:
                merged_data = YQNDataConverter.merge_herd_data(all_api_data)
            else:
                # 单选模式，直接使用
                merged_data = all_api_data[0][1]

            total_cows = len(merged_data.get('data', []))
            self.progress.emit(28, f"数据合并完成，共 {total_cows} 头")

            # 步骤3: 转换为Excel
            self.progress.emit(28, "正在转换数据格式...")
            raw_data_dir = self.project_path / "raw_data"
            raw_data_dir.mkdir(parents=True, exist_ok=True)

            excel_path = raw_data_dir / "cow_data.xlsx"

            # 使用转换器（不需要再添加前缀，merge_herd_data已处理）
            YQNDataConverter.convert_herd_to_excel(merged_data, excel_path)
            self.progress.emit(32, "数据格式转换完成")

            # 步骤3.5: 下载配种记录
            self.progress.emit(32, "正在下载配种记录...")
            try:
                all_breeding_data = []
                for i, farm in enumerate(self.farms):
                    farm_code = farm['code']
                    farm_name = farm['name']
                    progress_pct = int(32 + (i / total_farms) * 10)
                    self.progress.emit(progress_pct, f"正在下载 {farm_name} 配种记录...")

                    breeding_data = self.api_client.get_breeding_records(farm_code)
                    all_breeding_data.append((farm_code, breeding_data))

                    # 统计记录数
                    data = breeding_data.get("data", {})
                    count = len(data.get("rows", [])) if isinstance(data, dict) else 0
                    self.logger.info(f"下载牧场 {farm_code} 配种记录完成: {count} 条")
                    if count:
                        farm_raw_dir = (
                            self.project_path
                            / "raw_data"
                            / "farms"
                            / str(farm_code)
                        )
                        YQNDataConverter.convert_breeding_records_to_excel(
                            breeding_data,
                            farm_raw_dir / "breeding_records.xlsx",
                        )

                # 合并配种记录（多牧场时加站号前缀）
                self.progress.emit(42, "正在转换配种记录...")
                merged_breeding = YQNDataConverter.merge_breeding_records(
                    all_breeding_data, force_prefix=self.is_merged
                )

                if merged_breeding:
                    # 构建合并后的 api_data 格式供转换方法使用
                    merged_breeding_api = {"data": {"rows": merged_breeding}}
                    breeding_excel_path = raw_data_dir / "breeding_records.xlsx"
                    YQNDataConverter.convert_breeding_records_to_excel(
                        merged_breeding_api, breeding_excel_path
                    )
                    self.progress.emit(45, f"配种记录下载完成，共 {len(merged_breeding)} 条")
                else:
                    self.logger.warning("配种记录为空，跳过")
                    self.progress.emit(45, "配种记录为空，已跳过")

            except Exception as e:
                self.logger.warning(f"配种记录下载失败（不影响主流程）: {e}")
                self.progress.emit(45, f"配种记录下载失败: {str(e)[:50]}，继续处理...")

            # 步骤4: 标准化处理
            self.progress.emit(50, "正在进行数据标准化...")

            def standardize_progress(*args):
                if len(args) == 2:
                    pct, msg = args
                elif len(args) == 1:
                    pct = args[0]
                    msg = f"{pct}%"
                else:
                    return

                try:
                    mapped_pct = 60 + int(pct * 0.28)
                    self.progress.emit(mapped_pct, f"标准化: {msg}")
                except Exception as e:
                    self.logger.warning(f"进度回调出错: {e}, args={args}")

            standardized_path = upload_and_standardize_cow_data(
                input_files=[excel_path],
                project_path=self.project_path,
                progress_callback=standardize_progress,
                source_system="伊起牛"
            )

            self.progress.emit(88, "牛群数据标准化完成")

            # 步骤4.5: 配种记录标准化
            breeding_excel = self.project_path / "raw_data" / "breeding_records.xlsx"
            if breeding_excel.exists():
                self.progress.emit(90, "正在标准化配种记录...")
                try:
                    from core.data.uploader import upload_and_standardize_breeding_data
                    upload_and_standardize_breeding_data(
                        input_files=[breeding_excel],
                        project_path=self.project_path,
                        source_system="伊起牛"
                    )
                    self.progress.emit(93, "配种记录标准化完成")
                except Exception as e:
                    self.logger.warning(f"配种记录标准化失败（不影响主流程）: {e}")

            # 步骤4.6: 下载冻精库存并标准化为备选公牛
            self.progress.emit(93, "正在下载冻精库存...")
            try:
                all_stock_records = []
                for farm in self.farms:
                    farm_code = farm['code']
                    farm_name = farm['name']
                    self.progress.emit(93, f"正在下载 {farm_name} 冻精库存...")

                    stock_data = self.api_client.get_stock_detail(farm_code)
                    stock_records = stock_data.get("data", [])
                    all_stock_records.extend(stock_records)
                    self.logger.info(f"下载牧场 {farm_code} 冻精库存: {len(stock_records)} 条")

                if all_stock_records:
                    merged_stock_data = {"code": 200, "data": all_stock_records}
                    semen_inventory_path = raw_data_dir / "semen_inventory.xlsx"
                    YQNDataConverter.convert_stock_to_semen_inventory(
                        merged_stock_data, semen_inventory_path
                    )
                    in_stock = sum(1 for r in all_stock_records if r.get("stockSum", 0) > 0)
                    self.progress.emit(95, f"冻精库存下载完成，{in_stock} 种有库存")

                    # 自动标准化为备选公牛数据
                    self.progress.emit(96, "正在标准化冻精库存为备选公牛...")
                    from core.data.uploader import upload_and_standardize_bull_data
                    upload_and_standardize_bull_data(
                        input_files=[semen_inventory_path],
                        project_path=self.project_path,
                        progress_callback=None
                    )
                    self.progress.emit(98, "备选公牛数据标准化完成")
                else:
                    self.logger.warning("冻精库存为空，跳过")
                    self.progress.emit(95, "冻精库存为空，已跳过")

            except Exception as e:
                self.logger.warning(f"冻精库存下载/标准化失败（不影响主流程）: {e}")
                self.progress.emit(95, f"冻精库存处理失败: {str(e)[:50]}，继续处理...")

            self.progress.emit(98, "正在合并本地补充牧场...")
            from core.data.composite_farm_manager import (
                finalize_composite_project,
            )

            finalize_composite_project(
                self.project_path,
                self.farms,
                self.local_farms,
                data_source="伊起牛",
                ids_are_prefixed=self.is_merged,
                progress_callback=lambda pct, msg: self.progress.emit(
                    98 + int(pct * 0.02), msg
                ),
            )

            # 步骤5: 完成
            self.progress.emit(100, "牧场项目创建成功!")
            self.finished.emit(excel_path)

        except Exception as e:
            self.logger.exception("数据下载处理失败")
            self.error.emit(f"处理失败: {str(e)}")


class HMYDataDownloadWorker(QThread):
    """慧牧云牛群数据下载和标准化线程（不读取配种记录或冻精库存）。"""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(Path)
    error = pyqtSignal(str)

    def __init__(
        self,
        api_client,
        farms,
        project_path,
        is_merged=False,
        local_farms=None,
    ):
        super().__init__()
        self.api_client = api_client
        self.farms = farms
        self.project_path = Path(project_path)
        self.is_merged = is_merged
        self.local_farms = local_farms or []

    def run(self):
        try:
            all_api_data = []
            total_farms = len(self.farms)
            for index, farm in enumerate(self.farms):
                pct = 5 + int(index / max(total_farms, 1) * 45)
                self.progress.emit(pct, f"正在下载 {farm['name']} 牛群数据...")
                api_data = self.api_client.get_farm_herd(farm["code"])
                farm["cow_count"] = len(api_data.get("data") or [])
                all_api_data.append((farm["code"], api_data))
                if farm["cow_count"]:
                    farm_raw_dir = (
                        self.project_path
                        / "raw_data"
                        / "farms"
                        / str(farm["code"])
                    )
                    HMYDataConverter.convert_herd_to_excel(
                        api_data, farm_raw_dir / "cow_data.xlsx"
                    )

            self.progress.emit(55, "正在合并牛群数据...")
            if self.is_merged:
                merged_data = HMYDataConverter.merge_herd_data(all_api_data)
            else:
                merged_data = all_api_data[0][1]

            raw_dir = self.project_path / "raw_data"
            raw_dir.mkdir(parents=True, exist_ok=True)
            excel_path = raw_dir / "cow_data.xlsx"
            HMYDataConverter.convert_herd_to_excel(merged_data, excel_path)

            self.progress.emit(65, "正在标准化慧牧云牛群数据...")

            def standardize_progress(*args):
                if not args:
                    return
                value = args[0]
                message = args[1] if len(args) > 1 else ""
                try:
                    numeric_value = float(value)
                except (TypeError, ValueError):
                    # 标准化器有少量仅发送文字状态的回调。
                    self.progress.emit(65, f"标准化: {message or value}")
                    return
                self.progress.emit(
                    65 + int(numeric_value * 0.3),
                    f"标准化: {message or value}",
                )

            upload_and_standardize_cow_data(
                input_files=[excel_path],
                project_path=self.project_path,
                progress_callback=standardize_progress,
                source_system="慧牧云",
            )
            self.progress.emit(95, "正在合并本地补充牧场...")
            from core.data.composite_farm_manager import (
                finalize_composite_project,
            )

            finalize_composite_project(
                self.project_path,
                self.farms,
                self.local_farms,
                data_source="慧牧云",
                ids_are_prefixed=self.is_merged,
                progress_callback=lambda pct, msg: self.progress.emit(
                    95 + int(pct * 0.05), msg
                ),
            )
            self.progress.emit(100, "慧牧云牧场项目创建成功")
            self.finished.emit(excel_path)
        except Exception as exc:
            logging.getLogger(__name__).exception("慧牧云数据下载处理失败")
            self.error.emit(f"处理失败: {exc}")


class FarmListItem(QWidget):
    """牧场列表项（带勾选框）"""

    checked_changed = pyqtSignal(str, bool)  # farm_code, is_checked

    def __init__(self, farm_data: dict, parent=None):
        super().__init__(parent)
        self.farm_data = farm_data
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        # 勾选框
        self.checkbox = QCheckBox()
        self.checkbox.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(self.checkbox)

        # 站号
        code_label = QLabel(str(self.farm_data.get('farmCode', '')))
        code_label.setFixedWidth(90)
        code_label.setStyleSheet("font-size: 12px; color: #606266;")
        layout.addWidget(code_label)

        # 牧场名称 (字段为 name)
        name_label = QLabel(self.farm_data.get('name', ''))
        name_label.setStyleSheet("font-size: 13px; color: #303133;")
        layout.addWidget(name_label, 1)

    def _on_checkbox_changed(self, state):
        is_checked = state == Qt.CheckState.Checked.value
        farm_code = self.farm_data.get('farmCode', '')
        self.checked_changed.emit(farm_code, is_checked)

    def mousePressEvent(self, event):
        """点击整行任意位置切换勾选"""
        self.checkbox.setChecked(not self.checkbox.isChecked())

    def is_checked(self):
        return self.checkbox.isChecked()

    def set_checked(self, checked: bool):
        self.checkbox.setChecked(checked)


class LocalFarmListItem(QWidget):
    """本地补充牧场列表项。"""

    checked_changed = pyqtSignal(str, bool)
    view_requested = pyqtSignal(str)
    reupload_requested = pyqtSignal(str)
    remove_requested = pyqtSignal(str)

    def __init__(self, farm_data: dict, parent=None):
        super().__init__(parent)
        self.farm_data = farm_data
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        self.checkbox = QCheckBox()
        self.checkbox.stateChanged.connect(
            lambda state: self.checked_changed.emit(
                str(self.farm_data.get("farmCode", "")),
                state == Qt.CheckState.Checked.value,
            )
        )
        layout.addWidget(self.checkbox)

        code = str(self.farm_data.get("farmCode", ""))
        code_label = QLabel(code)
        code_label.setFixedWidth(90)
        code_label.setStyleSheet("font-size: 12px; color: #606266;")
        layout.addWidget(code_label)

        name_label = QLabel(str(self.farm_data.get("name", "")))
        name_label.setStyleSheet("font-size: 13px; color: #303133;")
        layout.addWidget(name_label, 1)

        source_label = QLabel(
            f"本地·{self.farm_data.get('source_system', '')} "
            f"({self.farm_data.get('cow_count', 0)}头)"
        )
        source_label.setStyleSheet("font-size: 11px; color: #909399;")
        layout.addWidget(source_label)

        button_style = """
            QPushButton {
                padding: 3px 6px; color: #606266; background: white;
                border: 1px solid #dcdfe6; border-radius: 3px;
            }
            QPushButton:hover { background: #f5f7fa; }
        """
        view_button = QPushButton("详情")
        view_button.setFixedWidth(48)
        view_button.setStyleSheet(button_style)
        view_button.clicked.connect(lambda: self.view_requested.emit(code))
        layout.addWidget(view_button)

        reupload_button = QPushButton("重传")
        reupload_button.setFixedWidth(48)
        reupload_button.setStyleSheet(button_style)
        reupload_button.clicked.connect(
            lambda: self.reupload_requested.emit(code)
        )
        layout.addWidget(reupload_button)

        remove_button = QPushButton("移除")
        remove_button.setFixedWidth(48)
        remove_button.setStyleSheet(button_style)
        remove_button.clicked.connect(
            lambda: self.remove_requested.emit(code)
        )
        layout.addWidget(remove_button)

    def set_checked(self, checked: bool):
        self.checkbox.setChecked(checked)


class FarmSelectionPage(QWidget):
    """牧场数据对接页面，支持伊起牛和慧牧云。"""

    project_created = pyqtSignal(Path)  # 项目创建完成信号，携带项目路径
    user_name_fetched = pyqtSignal(str)  # 获取到用户真实姓名

    def __init__(self, yqn_token=None, username=None, parent=None):
        super().__init__(parent)
        self.yqn_token = yqn_token
        self.username = username  # 登录账号，作为姓名获取失败时的 fallback
        self.hmy_access_allowed = is_hmy_user_allowed(username)
        if yqn_token:
            self.data_source = "伊起牛"
        elif self.hmy_access_allowed:
            self.data_source = "慧牧云"
        else:
            self.data_source = ""
        self.api_client = None
        self.all_farms = []  # 所有牧场数据
        self.selected_farms = {}  # 已选牧场 {farm_code: farm_data}
        self.local_farms = {}  # 本地补充牧场 {farm_code: farm_data}
        self.local_farm_list_items = {}
        self.current_region = None  # 当前选中的区域
        self.current_group_farms = []  # 当前分组或搜索结果中的牧场
        self.farm_list_items = {}  # farm_code -> FarmListItem
        self.logger = logging.getLogger(__name__)

        self.init_ui()

        from PyQt6.QtCore import QTimer
        if self.data_source:
            QTimer.singleShot(500, lambda: self.switch_data_source(self.data_source))

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 顶部标题栏
        header_layout = QHBoxLayout()
        header_layout.setSpacing(20)

        # 标题
        title_label = QLabel("🐄 牧场数据对接")
        title_font = QFont("微软雅黑", 16, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #303133;")
        header_layout.addWidget(title_label)

        self.source_buttons = {}
        for source in ("伊起牛", "慧牧云"):
            button = QPushButton(source)
            button.setCheckable(True)
            button.setMinimumWidth(90)
            button.clicked.connect(
                lambda checked=False, selected=source: self.switch_data_source(selected)
            )
            self.source_buttons[source] = button
            header_layout.addWidget(button)

        header_layout.addStretch()

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索牧场名称或站号...")
        self.search_input.setFixedWidth(200)
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 6px 12px;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #409eff;
            }
        """)
        self.search_input.returnPressed.connect(self._do_search)
        header_layout.addWidget(self.search_input)

        # 搜索按钮
        self.search_btn = QPushButton("搜索")
        self.search_btn.setFixedWidth(60)
        self.search_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                background-color: #409eff;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #66b1ff;
            }
            QPushButton:pressed {
                background-color: #3a8ee6;
            }
        """)
        self.search_btn.clicked.connect(self._do_search)
        header_layout.addWidget(self.search_btn)

        layout.addLayout(header_layout)

        # 主内容区域（左右分栏）
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background-color: #e4e7ed; }")

        # 左侧面板：状态筛选 + 区域树
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(15)

        # 状态筛选
        status_group = QGroupBox("状态筛选")
        self.status_filter_widget = status_group
        status_group.setStyleSheet("""
            QGroupBox {
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #e4e7ed;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(10, 10, 10, 10)

        self.status_group = QButtonGroup(self)
        status_options = [("可用", "0"), ("关停", "1"), ("全部", "all")]

        for i, (label, value) in enumerate(status_options):
            radio = QRadioButton(label)
            radio.setProperty("status_value", value)
            radio.setStyleSheet("font-size: 12px; font-weight: normal;")
            self.status_group.addButton(radio, i)
            status_layout.addWidget(radio)
            if i == 0:  # 默认选中"可用"
                radio.setChecked(True)

        self.status_group.buttonClicked.connect(self.on_status_changed)

        # 排除Z牧场复选框（默认勾选）
        self.exclude_z_checkbox = QCheckBox("排除Z牧场")
        self.exclude_z_checkbox.setChecked(True)
        self.exclude_z_checkbox.setStyleSheet("font-size: 12px; font-weight: normal;")
        self.exclude_z_checkbox.setToolTip("排除牧场名称以Z结尾的牧场")
        self.exclude_z_checkbox.stateChanged.connect(self.on_status_changed)
        status_layout.addWidget(self.exclude_z_checkbox)

        status_group.setLayout(status_layout)
        left_layout.addWidget(status_group)

        # 牧场类型筛选（多选，两列布局）
        type_group = QGroupBox("牧场类型")
        self.type_filter_widget = type_group
        type_group.setStyleSheet("""
            QGroupBox {
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #e4e7ed;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        type_layout = QVBoxLayout()
        type_layout.setContentsMargins(10, 10, 10, 10)
        type_layout.setSpacing(5)

        # 牧场类型选项：(显示名称, 实际值)
        self.farm_type_options = [
            ("主要供应商", "主要供应商"),
            ("大型牧业", "大型牧业"),
            ("合资牧场", "合资牧场"),
            ("社会奶源", "社会奶源"),
            ("畜牧公司", "畜牧公司"),
            ("其他(1)", "1"),
            ("其他(2)", "2"),
            ("未分类", None),
        ]

        # 两列布局
        from PyQt6.QtWidgets import QGridLayout
        type_grid = QGridLayout()
        type_grid.setSpacing(2)

        self.farm_type_checkboxes = []
        for i, (label, value) in enumerate(self.farm_type_options):
            cb = QCheckBox(label)
            cb.setProperty("type_value", value)
            cb.setStyleSheet("font-size: 11px; font-weight: normal;")
            # 默认只选中"社会奶源"
            cb.setChecked(value == "社会奶源")
            cb.stateChanged.connect(self.on_status_changed)
            row = i // 3
            col = i % 3
            type_grid.addWidget(cb, row, col)
            self.farm_type_checkboxes.append(cb)

        type_layout.addLayout(type_grid)

        # 全选/取消全选按钮
        type_btn_layout = QHBoxLayout()
        type_btn_layout.setSpacing(5)
        select_all_btn = QPushButton("全选")
        select_all_btn.setFixedHeight(22)
        select_all_btn.setStyleSheet("font-size: 11px;")
        select_all_btn.clicked.connect(self._select_all_farm_types)
        deselect_all_btn = QPushButton("取消")
        deselect_all_btn.setFixedHeight(22)
        deselect_all_btn.setStyleSheet("font-size: 11px;")
        deselect_all_btn.clicked.connect(self._deselect_all_farm_types)
        type_btn_layout.addWidget(select_all_btn)
        type_btn_layout.addWidget(deselect_all_btn)
        type_layout.addLayout(type_btn_layout)

        type_group.setLayout(type_layout)
        left_layout.addWidget(type_group)

        # 慧牧云分类方式
        classification_group = QGroupBox("分类方式")
        self.classification_widget = classification_group
        classification_group.setStyleSheet("""
            QGroupBox {
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #e4e7ed;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        classification_layout = QVBoxLayout(classification_group)
        classification_layout.setContentsMargins(10, 10, 10, 10)
        self.classification_combo = QComboBox()
        for label, field in HMY_CLASSIFICATION_OPTIONS:
            self.classification_combo.addItem(label, field)
        self.classification_combo.setStyleSheet(
            "font-size: 12px; padding: 4px 8px;"
        )
        self.classification_combo.currentIndexChanged.connect(
            self.on_hmy_classification_changed
        )
        classification_layout.addWidget(self.classification_combo)
        left_layout.addWidget(classification_group)
        classification_group.setVisible(False)

        # 区域树
        self.tree_group = QGroupBox("大区/区域")
        self.tree_group.setStyleSheet("""
            QGroupBox {
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #e4e7ed;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        tree_layout = QVBoxLayout()
        tree_layout.setContentsMargins(5, 5, 5, 5)

        self.region_tree = QTreeWidget()
        self.region_tree.setHeaderHidden(True)
        self.region_tree.setStyleSheet("""
            QTreeWidget {
                border: none;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 5px 2px;
            }
            QTreeWidget::item:hover {
                background-color: #ecf5ff;
            }
            QTreeWidget::item:selected {
                background-color: #409eff;
                color: white;
            }
        """)
        self.region_tree.itemClicked.connect(self.on_region_selected)
        tree_layout.addWidget(self.region_tree)
        self.tree_group.setLayout(tree_layout)
        left_layout.addWidget(self.tree_group, 1)

        splitter.addWidget(left_panel)

        # 右侧面板：牧场列表
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(10)

        # 牧场列表标题
        list_header = QHBoxLayout()
        self.region_title_label = QLabel("请选择区域")
        self.region_title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #303133;")
        list_header.addWidget(self.region_title_label)

        list_header.addStretch()

        self.add_local_farm_btn = QPushButton("添加本地牧场")
        self.add_local_farm_btn.setToolTip(
            "为当前伊起牛或慧牧云接口项目补充接口中没有的牧场"
        )
        self.add_local_farm_btn.setStyleSheet(
            """
            QPushButton {
                padding: 6px 12px; color: #67c23a; background: white;
                border: 1px solid #67c23a; border-radius: 4px;
                font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background: #f0f9eb; }
            QPushButton:disabled {
                color: #c0c4cc; border-color: #dcdfe6;
            }
            """
        )
        self.add_local_farm_btn.clicked.connect(self.on_add_local_farm)
        list_header.addWidget(self.add_local_farm_btn)

        self.select_group_btn = QPushButton("全选当前分组")
        self.select_group_btn.setEnabled(False)
        self.select_group_btn.setToolTip("选择当前大区、区域或分类中的全部牧场")
        self.select_group_btn.setStyleSheet(
            "font-size: 12px; padding: 4px 10px;"
        )
        self.select_group_btn.clicked.connect(
            lambda: self.set_current_group_checked(True)
        )
        list_header.addWidget(self.select_group_btn)

        self.deselect_group_btn = QPushButton("取消当前分组")
        self.deselect_group_btn.setEnabled(False)
        self.deselect_group_btn.setToolTip("取消当前大区、区域或分类中的全部牧场")
        self.deselect_group_btn.setStyleSheet(
            "font-size: 12px; padding: 4px 10px;"
        )
        self.deselect_group_btn.clicked.connect(
            lambda: self.set_current_group_checked(False)
        )
        list_header.addWidget(self.deselect_group_btn)

        self.selected_count_label = QLabel("已选: 0个")
        self.selected_count_label.setStyleSheet("font-size: 13px; color: #409eff; font-weight: bold;")
        list_header.addWidget(self.selected_count_label)

        right_layout.addLayout(list_header)

        # 牧场列表
        self.farm_list = QListWidget()
        self.farm_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e4e7ed;
                border-radius: 4px;
                font-size: 13px;
            }
            QListWidget::item {
                border-bottom: 1px solid #f2f6fc;
            }
            QListWidget::item:hover {
                background-color: #f5f7fa;
            }
        """)
        self.farm_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        right_layout.addWidget(self.farm_list, 1)

        self.local_farm_group = QGroupBox("本地补充牧场")
        local_layout = QVBoxLayout(self.local_farm_group)
        local_layout.setContentsMargins(5, 8, 5, 5)
        self.local_farm_list = QListWidget()
        self.local_farm_list.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.local_farm_list.setMaximumHeight(150)
        self.local_farm_list.setStyleSheet(
            """
            QListWidget {
                border: 1px solid #d9ecff; border-radius: 4px;
                background: #f8fbff;
            }
            QListWidget::item { border-bottom: 1px solid #edf5ff; }
            """
        )
        local_layout.addWidget(self.local_farm_list)
        self.local_farm_group.setVisible(False)
        right_layout.addWidget(self.local_farm_group)

        # 多选警告提示（初始隐藏）
        self.warning_frame = QFrame()
        self.warning_frame.setStyleSheet("""
            QFrame {
                background-color: #fdf6ec;
                border: 1px solid #faecd8;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        warning_layout = QVBoxLayout(self.warning_frame)
        warning_layout.setContentsMargins(12, 10, 12, 10)
        warning_layout.setSpacing(5)

        warning_title = QLabel("⚠️ 多选模式注意事项")
        warning_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #e6a23c;")
        warning_layout.addWidget(warning_title)

        warning_items = [
            "· 牛号和母亲号将添加牧场站号前缀避免重号",
            "· 分析功能将根据当前数据源和已上传数据动态开放"
        ]
        for item in warning_items:
            item_label = QLabel(item)
            item_label.setStyleSheet("font-size: 11px; color: #909399;")
            item_label.setWordWrap(True)
            warning_layout.addWidget(item_label)

        self.warning_frame.setVisible(False)
        right_layout.addWidget(self.warning_frame)

        splitter.addWidget(right_panel)

        # 设置左右面板比例
        splitter.setSizes([250, 550])

        layout.addWidget(splitter, 1)

        # 底部按钮区域
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.preview_btn = QPushButton("预览选中数据")
        self.preview_btn.clicked.connect(self.on_preview_clicked)
        self.preview_btn.setEnabled(False)
        self.preview_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 25px;
                background-color: #409eff;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #66b1ff;
            }
            QPushButton:disabled {
                background-color: #c0c4cc;
            }
        """)
        bottom_layout.addWidget(self.preview_btn)

        self.create_btn = QPushButton("创建牧场项目")
        self.create_btn.clicked.connect(self.on_create_project_clicked)
        self.create_btn.setEnabled(False)
        self.create_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 25px;
                background-color: #67c23a;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #85ce61;
            }
            QPushButton:disabled {
                background-color: #c0c4cc;
            }
        """)
        bottom_layout.addWidget(self.create_btn)

        self.auto_report_btn = QPushButton("创建项目并自动生成报告")
        self.auto_report_btn.clicked.connect(self.on_auto_report_clicked)
        self.auto_report_btn.setEnabled(False)
        self.auto_report_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 25px;
                background-color: #e6a23c;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ebb563;
            }
            QPushButton:disabled {
                background-color: #c0c4cc;
            }
        """)
        bottom_layout.addWidget(self.auto_report_btn)

        layout.addLayout(bottom_layout)
        if not self.yqn_token:
            self.source_buttons["伊起牛"].setEnabled(False)
            self.source_buttons["伊起牛"].setToolTip("伊起牛数据源需要伊起牛账号登录")
        if not self.hmy_access_allowed:
            self.source_buttons["慧牧云"].setEnabled(False)
            self.source_buttons["慧牧云"].setToolTip("当前账号未开通慧牧云功能")
            if not self.yqn_token:
                self.region_title_label.setText("当前账号没有可用的数据源")
    # 无伊起牛 token 时保留慧牧云入口。
    def show_no_token_message(self):
        """显示无token提示"""
        self.source_buttons["伊起牛"].setEnabled(False)

    def _update_source_button_styles(self):
        active = """
            QPushButton { background:#409eff; color:white; border:1px solid #3a8ee6;
                          border-radius:4px; padding:7px 18px; font-weight:bold; }
        """
        normal = """
            QPushButton { background:#ffffff; color:#409eff; border:1px solid #409eff;
                          border-radius:4px; padding:7px 18px; font-weight:bold; }
            QPushButton:hover { background:#ecf5ff; }
        """
        for source, button in self.source_buttons.items():
            button.setChecked(source == self.data_source)
            button.setStyleSheet(active if source == self.data_source else normal)

    def switch_data_source(self, source: str):
        """切换牧场数据来源，不允许跨来源混合选择。"""
        if source == self.data_source and self.api_client is not None:
            self._update_source_button_styles()
            return
        if source == "伊起牛" and not self.yqn_token:
            QMessageBox.information(self, "提示", "伊起牛数据源需要使用伊起牛账号登录")
            return
        if source == "慧牧云" and not self.hmy_access_allowed:
            QMessageBox.information(
                self,
                "未开通",
                "当前账号未开通慧牧云功能。",
            )
            return

        if self.selected_farms or self.local_farms:
            reply = QMessageBox.question(
                self,
                "确认切换数据源",
                "切换接口数据源会清空当前勾选和已暂存的本地补充牧场，"
                "是否继续？",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._update_source_button_styles()
                return

        self._clear_local_farms()
        self.data_source = source
        self.selected_farms.clear()
        self.all_farms = []
        self.current_group_farms = []
        self.farm_list.clear()
        self.farm_list_items.clear()
        self.region_tree.clear()
        self.select_group_btn.setEnabled(False)
        self.deselect_group_btn.setEnabled(False)
        self.update_selection_ui()
        self._update_source_button_styles()

        is_hmy = source == "慧牧云"
        self.status_filter_widget.setVisible(not is_hmy)
        self.type_filter_widget.setVisible(not is_hmy)
        self.classification_widget.setVisible(is_hmy)
        if is_hmy:
            for checkbox in self.farm_type_checkboxes:
                checkbox.blockSignals(True)
                checkbox.setChecked(checkbox.property("type_value") is None)
                checkbox.blockSignals(False)
        else:
            for checkbox in self.farm_type_checkboxes:
                checkbox.blockSignals(True)
                checkbox.setChecked(
                    checkbox.property("type_value") == "社会奶源"
                )
                checkbox.blockSignals(False)

        try:
            if is_hmy:
                self.api_client = HMYApiClient()
                self.login_user_name = self.username or ""
                result = self.api_client.get_farm_list()
                self.all_farms = result.get("data", [])
                self.build_region_tree()
                self.select_first_region_group()
            else:
                self.init_api_client()
        except Exception as exc:
            self.api_client = None
            QMessageBox.critical(self, "数据源初始化失败", str(exc))

    def on_add_local_farm(self):
        """为当前接口项目添加一个本地补充牧场。"""
        if not self.data_source or self.api_client is None:
            QMessageBox.warning(
                self, "数据源不可用", "请先选择可用的接口数据源"
            )
            return

        source_system, accepted = QInputDialog.getItem(
            self,
            "选择牧场数据源",
            "请选择本地补充文件的数据来源：",
            ["伊起牛", "优源-DC305", "慧牧云"],
            0,
            False,
        )
        if not accepted:
            return

        from gui.local_farm_dialog import LocalFarmUploadDialog
        from core.data.composite_farm_manager import cleanup_local_farm

        dialog = LocalFarmUploadDialog(source_system, self)
        if (
            dialog.exec() != QDialog.DialogCode.Accepted
            or not dialog.result_farm
        ):
            return

        farm = dialog.result_farm
        farm_code = str(farm.get("farmCode", "")).strip()
        interface_codes = {
            str(item.get("farmCode", "")).strip()
            for item in self.all_farms
        }
        if farm_code in interface_codes:
            cleanup_local_farm(farm)
            QMessageBox.warning(
                self,
                "牧场编号重复",
                "该牧场编号已存在于当前接口牧场清单中，"
                "不能同时作为本地补充牧场添加。",
            )
            return
        if farm_code in self.local_farms:
            cleanup_local_farm(farm)
            QMessageBox.warning(
                self,
                "牧场编号重复",
                "已经添加过相同牧场编号的本地补充牧场。",
            )
            return

        self.local_farms[farm_code] = farm
        self.selected_farms[farm_code] = farm
        self._refresh_local_farm_list()
        self.update_selection_ui()

    def _refresh_local_farm_list(self):
        self.local_farm_list.clear()
        self.local_farm_list_items.clear()
        for farm_code, farm in self.local_farms.items():
            item = QListWidgetItem(self.local_farm_list)
            item.setSizeHint(QSize(0, 40))
            widget = LocalFarmListItem(farm)
            widget.checked_changed.connect(self._on_local_farm_checked)
            widget.view_requested.connect(self._show_local_farm_summary)
            widget.reupload_requested.connect(self._reupload_local_farm)
            widget.remove_requested.connect(self._remove_local_farm)
            widget.set_checked(farm_code in self.selected_farms)
            self.local_farm_list.setItemWidget(item, widget)
            self.local_farm_list_items[farm_code] = widget
        self.local_farm_group.setVisible(bool(self.local_farms))

    def _on_local_farm_checked(self, farm_code: str, checked: bool):
        if checked:
            farm = self.local_farms.get(farm_code)
            if farm:
                self.selected_farms[farm_code] = farm
        else:
            self.selected_farms.pop(farm_code, None)
        self.update_selection_ui()

    def _remove_local_farm(self, farm_code: str):
        from core.data.composite_farm_manager import cleanup_local_farm

        farm = self.local_farms.pop(farm_code, None)
        self.selected_farms.pop(farm_code, None)
        if farm:
            cleanup_local_farm(farm)
        self._refresh_local_farm_list()
        self.update_selection_ui()

    def _show_local_farm_summary(self, farm_code: str):
        farm = self.local_farms.get(farm_code)
        if not farm:
            return
        breeding_text = (
            f"{farm.get('breeding_count', 0)} 条"
            if farm.get("has_breeding_records")
            else "未上传"
        )
        QMessageBox.information(
            self,
            "本地补充牧场详情",
            f"牧场编号：{farm_code}\n"
            f"牧场名称：{farm.get('name', '')}\n"
            f"数据来源：{farm.get('source_system', '')}\n"
            f"有效母牛：{farm.get('cow_count', 0)} 头\n"
            f"配种记录：{breeding_text}",
        )

    def _reupload_local_farm(self, farm_code: str):
        old_farm = self.local_farms.get(farm_code)
        if not old_farm:
            return

        from gui.local_farm_dialog import LocalFarmUploadDialog
        from core.data.composite_farm_manager import cleanup_local_farm

        dialog = LocalFarmUploadDialog(
            old_farm.get("source_system", "伊起牛"), self
        )
        if (
            dialog.exec() != QDialog.DialogCode.Accepted
            or not dialog.result_farm
        ):
            return

        new_farm = dialog.result_farm
        new_code = str(new_farm.get("farmCode", "")).strip()
        interface_codes = {
            str(item.get("farmCode", "")).strip()
            for item in self.all_farms
        }
        other_local_codes = set(self.local_farms) - {farm_code}
        if new_code in interface_codes or new_code in other_local_codes:
            cleanup_local_farm(new_farm)
            QMessageBox.warning(
                self,
                "牧场编号重复",
                "重新上传后的牧场编号与现有牧场重复。",
            )
            return

        was_selected = farm_code in self.selected_farms
        cleanup_local_farm(old_farm)
        self.local_farms.pop(farm_code, None)
        self.selected_farms.pop(farm_code, None)
        self.local_farms[new_code] = new_farm
        if was_selected:
            self.selected_farms[new_code] = new_farm
        self._refresh_local_farm_list()
        self.update_selection_ui()

    def _clear_local_farms(self):
        from core.data.composite_farm_manager import cleanup_local_farm

        for farm in self.local_farms.values():
            cleanup_local_farm(farm)
        self.local_farms.clear()
        self.local_farm_list_items.clear()
        if hasattr(self, "local_farm_list"):
            self.local_farm_list.clear()
        if hasattr(self, "local_farm_group"):
            self.local_farm_group.setVisible(False)

    def _build_selected_farm_specs(self):
        """构建工作线程使用的接口牧场和本地牧场定义。"""
        interface_farms = []
        local_farms = []
        for farm in self.selected_farms.values():
            if farm.get("source_kind") == "local":
                local_farms.append(
                    {
                        "code": str(farm.get("farmCode", "")).strip(),
                        "name": str(farm.get("name", "")).strip(),
                        "cow_count": int(farm.get("cow_count", 0)),
                        "breeding_count": int(
                            farm.get("breeding_count", 0)
                        ),
                        "has_breeding_records": bool(
                            farm.get("has_breeding_records", False)
                        ),
                        "source_kind": "local",
                        "source_system": farm.get("source_system", ""),
                        "staging_path": farm.get("staging_path", ""),
                    }
                )
            else:
                interface_farms.append(
                    {
                        "code": str(
                            farm.get("farmCode", "")
                        ).strip(),
                        "name": str(farm.get("name", "")).strip(),
                        "cow_count": 0,
                        "has_breeding_records": (
                            self.data_source == "伊起牛"
                        ),
                        "source_kind": "api",
                        "source_system": self.data_source,
                    }
                )
        return interface_farms, local_farms

    def init_api_client(self):
        """初始化API客户端并加载牧场列表"""
        self.logger.info("开始初始化伊起牛API客户端")

        try:
            self.api_client = YQNApiClient(self.yqn_token)
            self.logger.info("API客户端对象已创建")

            # 获取用户信息（含姓名）
            try:
                user_info_result = self.api_client.get_user_info()
                # user 可能在顶层或 data 下
                user_data = user_info_result.get("data") or user_info_result
                user_obj = user_data.get("user") or {}
                self.login_user_name = (
                    user_obj.get("nickName")
                    or user_obj.get("realName")
                    or user_obj.get("userName")
                    or ""
                )
                self.logger.info(f"✓ 获取用户姓名: {self.login_user_name}")
                if self.login_user_name:
                    self.user_name_fetched.emit(self.login_user_name)
            except Exception as e:
                self.logger.warning(f"获取用户信息失败: {e}")
                self.login_user_name = ""

            # 获取牧场列表（带大区/区域信息）
            self.logger.info("正在调用 get_farm_list() API...")
            farm_list_result = self.api_client.get_farm_list()

            # 提取牧场列表 - data 是数组
            self.all_farms = farm_list_result.get("data", [])

            self.logger.info(f"✓ 已加载 {len(self.all_farms)} 个牧场")

            if self.all_farms:
                # 构建区域树
                self.build_region_tree()
                self.select_first_region_group()
            else:
                self.logger.warning("⚠️ 牧场列表为空!")
                QMessageBox.warning(
                    self,
                    "提示",
                    "您的账号下没有可用的牧场数据"
                )

        except Exception as e:
            self.logger.exception(f"初始化API客户端失败: {e}")

            # 确保all_farms不是None
            if self.all_farms is None:
                self.all_farms = []

            QMessageBox.critical(
                self,
                "初始化失败",
                f"无法连接到伊起牛服务器:\n{str(e)}\n\n请检查网络连接或稍后重试"
            )

    def build_region_tree(self):
        """构建大区/区域树"""
        self.region_tree.clear()

        # 获取当前状态筛选
        status_filter = self.get_current_status_filter()

        # 过滤牧场
        # 字段说明: isAvailable=1 表示可用, isAvailable=0 表示关停
        exclude_z = self.exclude_z_checkbox.isChecked()
        selected_types = self.get_selected_farm_types()

        filtered_farms = []
        for farm in self.all_farms:
            is_available = farm.get('isAvailable', 1)
            farm_name = farm.get('name', '')
            farm_type = farm.get('farmType')

            # status_filter: "0"=可用, "1"=关停, "all"=全部
            if status_filter == "0" and is_available != 1:
                continue
            if status_filter == "1" and is_available != 0:
                continue

            # 排除名称以Z结尾的牧场
            if exclude_z and farm_name.endswith('Z'):
                continue

            # 牧场类型筛选
            if farm_type not in selected_types:
                continue

            filtered_farms.append(farm)

        if self.data_source == "慧牧云":
            classification_label = self.classification_combo.currentText()
            classification_field = self.classification_combo.currentData()
            grouped_farms = group_hmy_farms(
                filtered_farms,
                classification_field,
            )
            for group_name, farms in grouped_farms.items():
                group_item = QTreeWidgetItem(
                    [f"{group_name} ({len(farms)}个)"]
                )
                group_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {
                        "type": "hmy_group",
                        "name": group_name,
                        "classification": classification_label,
                        "farms": farms,
                    },
                )
                self.region_tree.addTopLevelItem(group_item)

            self.tree_group.setTitle(
                f"{classification_label} (共{len(filtered_farms)}个)"
            )
            return

        # 检查是否有大区/区域信息
        # 字段说明: area=大区, region=区域
        has_region_info = any(
            farm.get('area') or farm.get('region')
            for farm in filtered_farms
        )

        if has_region_info:
            # 按大区和区域组织数据
            big_areas = {}
            for farm in filtered_farms:
                big_area = _category_name(farm.get('area'))
                area = _category_name(farm.get('region'))

                if big_area not in big_areas:
                    big_areas[big_area] = {}
                if area not in big_areas[big_area]:
                    big_areas[big_area][area] = []
                big_areas[big_area][area].append(farm)

            # 构建树
            for big_area in sorted(big_areas, key=_group_sort_key):
                areas = big_areas[big_area]
                big_area_item = QTreeWidgetItem([big_area])
                big_area_farms = [
                    farm
                    for area_farms in areas.values()
                    for farm in area_farms
                ]
                big_area_item.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "big_area",
                    "name": big_area,
                    "farms": big_area_farms
                })

                total_farms = 0
                for area in sorted(areas, key=_group_sort_key):
                    farms = areas[area]
                    area_item = QTreeWidgetItem([f"{area} ({len(farms)}个)"])
                    area_item.setData(0, Qt.ItemDataRole.UserRole, {
                        "type": "area",
                        "name": area,
                        "big_area": big_area,
                        "farms": farms
                    })
                    big_area_item.addChild(area_item)
                    total_farms += len(farms)

                big_area_item.setText(0, f"{big_area} ({total_farms}个)")
                self.region_tree.addTopLevelItem(big_area_item)
        else:
            # 没有区域信息，创建单一节点"全部牧场"
            all_farms_item = QTreeWidgetItem([f"全部牧场 ({len(filtered_farms)}个)"])
            all_farms_item.setData(0, Qt.ItemDataRole.UserRole, {
                "type": "area",
                "name": "全部牧场",
                "big_area": "",
                "farms": filtered_farms
            })
            self.region_tree.addTopLevelItem(all_farms_item)

        # 展开所有节点
        self.region_tree.expandAll()

        # 更新标题显示合计数
        self.tree_group.setTitle(f"大区/区域 (共{len(filtered_farms)}个)")

    def select_first_region_group(self):
        """显示第一个分组，避免数据加载后右侧保持空白。"""
        first_item = self.region_tree.topLevelItem(0)
        if not first_item:
            self.current_group_farms = []
            self.select_group_btn.setEnabled(False)
            self.deselect_group_btn.setEnabled(False)
            return
        self.region_tree.setCurrentItem(first_item)
        self.on_region_selected(first_item, 0)

    def on_hmy_classification_changed(self, _index=None):
        """切换慧牧云分类维度并显示第一个分组。"""
        if self.data_source != "慧牧云" or not self.all_farms:
            return
        self.build_region_tree()
        self.select_first_region_group()

    def get_current_status_filter(self) -> str:
        """获取当前状态筛选值"""
        checked_btn = self.status_group.checkedButton()
        if checked_btn:
            return checked_btn.property("status_value")
        return "0"  # 默认可用

    def on_status_changed(self, button=None):
        """状态筛选变化"""
        self.build_region_tree()
        self.select_first_region_group()

    def _select_all_farm_types(self):
        """全选所有牧场类型"""
        for cb in self.farm_type_checkboxes:
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
        self.on_status_changed()

    def _deselect_all_farm_types(self):
        """取消全选所有牧场类型"""
        for cb in self.farm_type_checkboxes:
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        self.on_status_changed()

    def get_selected_farm_types(self) -> list:
        """获取选中的牧场类型"""
        selected = []
        for cb in self.farm_type_checkboxes:
            if cb.isChecked():
                selected.append(cb.property("type_value"))
        return selected
        self.region_title_label.setText("请选择区域")

    def on_region_selected(self, item, column):
        """区域选择变化"""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if data.get("type") in {"area", "big_area", "hmy_group"}:
            farms = data.get("farms", [])
            area_name = data.get("name", "")
            classification = data.get("classification")
            if classification:
                title = f"{classification}：{area_name}"
            else:
                title = area_name
            self.region_title_label.setText(
                f"{title} ({len(farms)}个牧场)"
            )
            self.current_region = area_name
            self.current_group_farms = list(farms)
            has_farms = bool(farms)
            self.select_group_btn.setEnabled(has_farms)
            self.deselect_group_btn.setEnabled(has_farms)
            self.populate_farm_list(farms)

    def populate_farm_list(self, farms: list):
        """填充牧场列表"""
        self.farm_list.setUpdatesEnabled(False)
        self.farm_list.clear()
        self.farm_list_items.clear()

        item_size = QSize(0, 36)

        for farm in farms:
            farm_code = farm.get('farmCode', '')

            # 创建列表项
            item = QListWidgetItem(self.farm_list)
            item.setSizeHint(item_size)

            # 创建自定义widget
            farm_widget = FarmListItem(farm)
            farm_widget.checked_changed.connect(self.on_farm_checked_changed)

            # 如果之前已选中，恢复选中状态
            if farm_code in self.selected_farms:
                farm_widget.set_checked(True)

            self.farm_list.setItemWidget(item, farm_widget)
            self.farm_list_items[farm_code] = farm_widget

        self.farm_list.setUpdatesEnabled(True)

    def on_farm_checked_changed(self, farm_code: str, is_checked: bool):
        """牧场勾选状态变化"""
        if is_checked:
            # 查找完整的farm数据
            for farm in self.all_farms:
                if farm.get('farmCode') == farm_code:
                    self.selected_farms[farm_code] = farm
                    break
        else:
            if farm_code in self.selected_farms:
                del self.selected_farms[farm_code]

        self.update_selection_ui()

    def set_current_group_checked(self, checked: bool):
        """批量选择或取消当前大区、区域、分类或搜索结果。"""
        for farm in self.current_group_farms:
            farm_code = str(farm.get("farmCode", "")).strip()
            if not farm_code:
                continue
            if checked:
                self.selected_farms[farm_code] = farm
            else:
                self.selected_farms.pop(farm_code, None)

        for farm_code, farm_widget in self.farm_list_items.items():
            farm_widget.checkbox.blockSignals(True)
            farm_widget.set_checked(farm_code in self.selected_farms)
            farm_widget.checkbox.blockSignals(False)

        self.update_selection_ui()

    def update_selection_ui(self):
        """更新选择相关的UI"""
        count = len(self.selected_farms)
        local_count = sum(
            1
            for farm in self.selected_farms.values()
            if farm.get("source_kind") == "local"
        )
        interface_count = count - local_count
        self.selected_count_label.setText(
            f"已选: {count}个（接口{interface_count}/本地{local_count}）"
        )

        # 多选警告
        self.warning_frame.setVisible(count >= 2)

        # 按钮状态
        self.preview_btn.setEnabled(count > 0)
        self.create_btn.setEnabled(count > 0)
        self.auto_report_btn.setEnabled(count > 0)

    def on_search_changed(self, text: str):
        """搜索文本变化 - 搜索范围为所有牧场，不受左侧筛选限制"""
        text = text.strip().lower()

        if not text:
            # 搜索清空时，恢复当前区域选择的牧场列表
            selected_items = self.region_tree.selectedItems()
            if selected_items:
                self.on_region_selected(selected_items[0], 0)
            else:
                self.farm_list.clear()
                self.farm_list_items.clear()
                self.current_group_farms = []
                self.select_group_btn.setEnabled(False)
                self.deselect_group_btn.setEnabled(False)
                self.region_title_label.setText("请选择区域")
            return

        # 在所有牧场中搜索匹配项
        matched_farms = []
        for farm in self.all_farms:
            farm_code = str(farm.get('farmCode', '')).lower()
            farm_name = str(farm.get('name', '')).lower()
            if text in farm_code or text in farm_name:
                matched_farms.append(farm)

        self.region_title_label.setText(f"搜索结果 ({len(matched_farms)}个)")
        self.current_group_farms = matched_farms
        has_matches = bool(matched_farms)
        self.select_group_btn.setEnabled(has_matches)
        self.deselect_group_btn.setEnabled(has_matches)
        self.populate_farm_list(matched_farms)

    def _do_search(self):
        """防抖后执行搜索"""
        self.on_search_changed(self.search_input.text())

    def on_preview_clicked(self):
        """预览按钮点击"""
        if not self.selected_farms:
            QMessageBox.warning(self, "提示", "请先选择牧场")
            return

        # 显示选中牧场的汇总信息
        farm_list = list(self.selected_farms.values())

        info_lines = ["已选择的牧场：\n"]
        for i, farm in enumerate(farm_list, 1):
            code = farm.get('farmCode', '')
            name = farm.get('name', '')
            if farm.get("source_kind") == "local":
                source = f"本地·{farm.get('source_system', '')}"
            else:
                source = f"接口·{self.data_source}"
            info_lines.append(f"{i}. {code} - {name}（{source}）")

        info_lines.append(f"\n合计: {len(farm_list)} 个牧场")

        if len(farm_list) >= 2:
            info_lines.append("\n⚠️ 多选模式注意：")
            info_lines.append("• 牛号和母亲号将添加牧场站号前缀")
            if self.data_source == "伊起牛":
                info_lines.append("• 部分功能将被禁用")

        QMessageBox.information(self, "预览选中数据", "\n".join(info_lines))

    def on_create_project_clicked(self):
        """创建项目按钮点击"""
        if not self.selected_farms:
            QMessageBox.warning(self, "提示", "请先选择牧场")
            return

        interface_farms, local_farms = self._build_selected_farm_specs()
        if not interface_farms:
            QMessageBox.warning(
                self,
                "缺少接口牧场",
                "接口复合项目至少需要勾选一个接口牧场。",
            )
            return
        farm_list = interface_farms + local_farms
        is_merged = len(farm_list) > 1

        # 确认对话框
        if is_merged:
            restriction_text = ""
            if self.data_source == "伊起牛":
                restriction_text = "• 基因组检测、体型外貌、个体选配功能将被禁用\n"
            confirm_msg = (
                f"即将创建{self.data_source}合并牧场项目\n\n"
                f"包含 {len(interface_farms)} 个接口牧场"
                f"和 {len(local_farms)} 个本地补充牧场\n\n"
                f"⚠️ 注意：\n"
                f"• 牛号和母亲号将添加牧场站号前缀\n"
                f"{restriction_text}\n"
                f"是否继续?"
            )
        else:
            farm = farm_list[0]
            confirm_msg = (
                f"即将为牧场 '{farm.get('name', '')}' 创建项目\n\n"
                f"系统将自动下载并标准化牛群数据\n\n"
                f"是否继续?"
            )

        reply = QMessageBox.question(
            self,
            "确认创建",
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.create_farm_project()

    def create_farm_project(self):
        """创建牧场项目"""
        if self.data_source == "慧牧云" and not self.hmy_access_allowed:
            QMessageBox.warning(self, "未开通", "当前账号未开通慧牧云功能。")
            return

        interface_farms, local_farms = self._build_selected_farm_specs()
        if not interface_farms:
            QMessageBox.warning(
                self, "缺少接口牧场", "接口复合项目至少需要一个接口牧场。"
            )
            return
        farms_info = interface_farms + local_farms
        is_merged = len(farms_info) > 1

        try:
            # 创建项目文件夹
            from config.settings import Settings
            settings = Settings()
            base_path = Path(settings.get_default_storage())

            if is_merged:
                project_path = FileManager.create_merged_project(
                    base_path, farms_info, data_source=self.data_source
                )
            else:
                project_path = FileManager.create_project(base_path, farms_info[0]['name'])
                # 单选也保存元数据
                FileManager.save_project_metadata(
                    project_path, farms_info, data_source=self.data_source
                )

            self.logger.info(f"项目文件夹已创建: {project_path}")

            # 创建进度对话框
            progress_dialog = QProgressDialog(self)
            progress_dialog.setWindowTitle("创建项目")
            progress_dialog.setLabelText("正在准备...")
            progress_dialog.setRange(0, 100)
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.setCancelButton(None)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.show()

            # 创建后台工作线程
            worker_class = (
                HMYDataDownloadWorker
                if self.data_source == "慧牧云"
                else DataDownloadWorker
            )
            self.worker = worker_class(
                self.api_client,
                interface_farms,
                project_path,
                is_merged,
                local_farms=local_farms,
            )

            # 连接信号
            self.worker.progress.connect(
                lambda pct, msg: self.on_worker_progress(progress_dialog, pct, msg)
            )
            self.worker.finished.connect(
                lambda path: self.on_worker_finished(progress_dialog, project_path, path, is_merged)
            )
            self.worker.error.connect(
                lambda err: self.on_worker_error(progress_dialog, project_path, err)
            )

            # 启动线程
            self.worker.start()

        except Exception as e:
            self.logger.exception("创建项目失败")
            QMessageBox.critical(
                self,
                "创建失败",
                f"无法创建项目文件夹:\n{str(e)}"
            )

    def on_worker_progress(self, dialog, percentage, message):
        """工作线程进度更新"""
        dialog.setValue(percentage)
        dialog.setLabelText(message)

    def on_worker_finished(self, dialog, project_path, excel_path, is_merged):
        """工作线程完成"""
        dialog.close()

        # 构建成功消息
        if is_merged:
            farm_count = len(self.selected_farms)
            restricted_text = ""
            if self.data_source == "伊起牛":
                restricted_text = (
                    "\n⚠️ 以下功能已禁用:\n"
                    "• 基因组检测数据上传\n"
                    "• 体型外貌数据上传\n"
                    "• 个体选配"
                )
            success_msg = (
                f"合并牧场项目已创建成功!\n\n"
                f"项目位置: {project_path}\n\n"
                f"已完成:\n"
                f"✅ {farm_count} 个牧场数据已合并处理\n"
                f"✅ 牛号和母亲号已添加牧场前缀\n"
                f"✅ 数据已自动标准化\n"
                f"✅ 已生成 merged_farms.txt 说明文件"
                f"{restricted_text}"
            )
        else:
            farm = list(self.selected_farms.values())[0]
            # 检查备选公牛数据是否已自动生成
            from pathlib import Path
            bull_file = Path(project_path) / "standardized_data" / "processed_bull_data.xlsx"
            bull_ready = bull_file.exists()

            if self.data_source == "慧牧云":
                local_breeding_ready = any(
                    farm.get("source_kind") == "local"
                    and farm.get("has_breeding_records")
                    for farm in self.selected_farms.values()
                )
                breeding_line = (
                    "✅ 本地补充牧场配种记录已合并\n"
                    if local_breeding_ready
                    else "ℹ️ 慧牧云接口配种记录暂不可用\n"
                )
                completed_lines = (
                    "✅ 牛群明细已自动下载\n"
                    "✅ 数据已自动标准化\n"
                    f"{breeding_line}"
                    "ℹ️ 选配结果推送暂不可用"
                )
            else:
                completed_lines = (
                    "✅ 牛群明细已自动下载\n"
                    "✅ 配种记录已自动下载\n"
                    "✅ 冻精库存已自动下载并标准化\n"
                    "✅ 数据已自动标准化"
                )
            if bull_ready:
                completed_lines += f"\n✅ 备选公牛已从冻精库存自动生成"

            pending_lines = ""
            pending_items = []
            if not bull_ready:
                pending_items.append("⚠️ 备选公牛清单")
            pending_items.append("⚠️ 体型外貌数据 (可选)")
            pending_items.append("⚠️ 基因组数据 (可选)")
            if pending_items:
                pending_lines = "\n\n待手动上传:\n" + "\n".join(pending_items)

            success_msg = (
                f"牧场项目已创建成功!\n\n"
                f"项目位置: {project_path}\n\n"
                f"已完成:\n"
                f"{completed_lines}"
                f"{pending_lines}"
            )

        QMessageBox.information(self, "创建成功", success_msg)

        # 重置状态
        self.selected_farms.clear()
        self._clear_local_farms()
        self.update_selection_ui()

        # 更新列表中的勾选状态
        for farm_code, widget in self.farm_list_items.items():
            widget.set_checked(False)

        self.logger.info(f"项目创建完成: {project_path}")

        # 通知主窗口自动选择新创建的项目
        self.project_created.emit(project_path)

    def on_worker_error(self, dialog, project_path, error_message):
        """工作线程错误"""
        dialog.close()

        self.logger.error(f"项目创建失败: {error_message}")

        # 尝试清理失败的项目文件夹
        try:
            import shutil
            if project_path.exists():
                shutil.rmtree(project_path)
                self.logger.info(f"已清理失败的项目文件夹: {project_path}")
        except Exception as e:
            self.logger.warning(f"清理项目文件夹失败: {e}")

        QMessageBox.critical(
            self,
            "创建失败",
            f"项目创建过程中发生错误:\n\n{error_message}\n\n"
            f"请检查网络连接或稍后重试"
        )

    # ============ 自动报告功能 ============

    def on_auto_report_clicked(self):
        """创建项目并自动生成报告按钮点击"""
        if not self.selected_farms:
            QMessageBox.warning(self, "提示", "请先选择牧场")
            return

        interface_farms, local_farms = self._build_selected_farm_specs()
        if not interface_farms:
            QMessageBox.warning(
                self,
                "缺少接口牧场",
                "接口复合项目至少需要勾选一个接口牧场。",
            )
            return

        if self.data_source == "慧牧云":
            local_breeding_ready = any(
                farm.get("source_kind") == "local"
                and farm.get("has_breeding_records")
                for farm in self.selected_farms.values()
            )
            breeding_text = (
                "本地补充牧场的配种记录将参与可用分析；"
                if local_breeding_ready
                else "配种记录和已配公牛分析将跳过；"
            )
            confirm_msg = (
                "即将创建慧牧云项目并自动生成当前可用报告\n\n"
                "系统将自动执行:\n"
                "1. 下载并标准化牛群数据\n"
                "2. 在群母牛关键育种性状分析\n"
                "3. 母牛群指数排名 (NM$权重)\n"
                "4. 生成当前可用的Excel和PPT报告\n\n"
                f"{breeding_text}"
                "推送功能将跳过；"
                "备选公牛需在项目创建后手动上传。\n\n"
                "整个过程可能需要几分钟，是否继续?"
            )
        else:
            confirm_msg = (
                "即将创建项目并自动生成报告\n\n"
                "系统将自动执行以下步骤:\n"
                "1. 下载并标准化牛群数据\n"
                "2. 在群母牛关键育种数据分析\n"
                "3. 备选公牛关键育种数据分析\n"
                "4. 已配公牛关键育种数据分析\n"
                "5. 母牛群指数排名 (NM$权重)\n"
                "6. 备选公牛指数排名 (NM$权重)\n"
                "7. 近交系数及隐性基因分析\n"
                "8. 生成Excel综合报告\n"
                "9. 生成PPT汇报材料\n\n"
                "注意：不会自动进行个体选配\n\n"
                "整个过程可能需要几分钟，是否继续?"
            )

        reply = QMessageBox.question(
            self,
            "确认创建",
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._start_auto_report()

    def _start_auto_report(self):
        """启动自动报告生成流程"""
        if self.data_source == "慧牧云" and not self.hmy_access_allowed:
            QMessageBox.warning(self, "未开通", "当前账号未开通慧牧云功能。")
            return

        interface_farms, local_farms = self._build_selected_farm_specs()
        if not interface_farms:
            QMessageBox.warning(
                self, "缺少接口牧场", "接口复合项目至少需要一个接口牧场。"
            )
            return
        farms_info = interface_farms + local_farms
        is_merged = len(farms_info) > 1

        try:
            # 创建项目文件夹
            from config.settings import Settings
            settings = Settings()
            base_path = Path(settings.get_default_storage())

            if is_merged:
                project_path = FileManager.create_merged_project(
                    base_path, farms_info, data_source=self.data_source
                )
            else:
                project_path = FileManager.create_project(base_path, farms_info[0]['name'])
                FileManager.save_project_metadata(
                    project_path, farms_info, data_source=self.data_source
                )

            self.logger.info(f"项目文件夹已创建: {project_path}")

            # 创建进度对话框
            from gui.progress import ProgressDialog
            # 使用主窗口作为真实父级并设为窗口级模态，确保处理期间
            # 始终位于主窗口上方，同时不会压住其他应用。
            main_window = self.window()
            progress_dialog = ProgressDialog(main_window)
            progress_dialog.setWindowTitle("创建项目并自动生成报告")
            progress_dialog.setWindowModality(
                Qt.WindowModality.WindowModal
            )
            progress_dialog.setWindowFlag(
                Qt.WindowType.WindowMinimizeButtonHint, False
            )
            progress_dialog.set_task_info("正在准备...")
            progress_dialog.adjustSize()
            dialog_geometry = progress_dialog.frameGeometry()
            dialog_geometry.moveCenter(main_window.frameGeometry().center())
            progress_dialog.move(dialog_geometry.topLeft())
            progress_dialog.show()
            progress_dialog.raise_()
            progress_dialog.activateWindow()

            # 自动报告为无人值守流程，强制关闭对比牧场总开关：
            # 避免历史勾选残留导致自动生成的报告静默带上对比牧场。
            # 需要对比时请走手动生成 Excel 报告并在弹窗中确认。
            try:
                from core.benchmark import BenchmarkManager
                BenchmarkManager().set_comparison_enabled(False)
            except Exception as e:
                self.logger.warning(f"关闭对比牧场总开关失败（不影响生成）: {e}")

            # 创建 AutoReportWorker
            from gui.auto_report_worker import AutoReportWorker
            self.auto_worker = AutoReportWorker(
                self.api_client,
                interface_farms,
                project_path,
                is_merged,
                service_staff=getattr(self, 'login_user_name', None) or '',
                data_source=self.data_source,
                local_farms=local_farms,
            )

            # 连接信号
            self.auto_worker.progress.connect(
                lambda pct, msg: self._on_auto_report_progress(progress_dialog, pct, msg)
            )
            self.auto_worker.finished.connect(
                lambda results: self._on_auto_report_finished(progress_dialog, project_path, results)
            )
            self.auto_worker.error.connect(
                lambda err: self.on_worker_error(progress_dialog, project_path, err)
            )

            # 连接并行子任务进度信号
            self.auto_worker.parallel_start.connect(
                lambda tasks: progress_dialog.show_sub_tasks(tasks)
            )
            self.auto_worker.sub_task_progress.connect(
                lambda task_id, pct: progress_dialog.update_sub_task(task_id, pct)
            )
            self.auto_worker.sub_task_done.connect(
                lambda task_id, ok: progress_dialog.complete_sub_task(task_id, ok)
            )
            self.auto_worker.parallel_end.connect(
                lambda: progress_dialog.hide_sub_tasks()
            )

            # 启动线程
            self.auto_worker.start()

        except Exception as e:
            self.logger.exception("创建自动报告项目失败")
            QMessageBox.critical(
                self,
                "创建失败",
                f"无法创建项目文件夹:\n{str(e)}"
            )

    def _on_auto_report_progress(self, dialog, percentage, message):
        """自动报告进度更新"""
        dialog.update_progress(percentage)
        dialog.set_task_info(message)

    def _on_auto_report_finished(self, dialog, project_path, results):
        """自动报告生成完成 - 显示汇总对话框"""
        # 计算总用时（从进度对话框的开始时间）
        import time as _time
        elapsed_seconds = _time.time() - dialog._start_time
        elapsed_min, elapsed_sec = divmod(int(elapsed_seconds), 60)
        elapsed_text = f"{elapsed_min}分{elapsed_sec:02d}秒"

        dialog.close()

        success_items = results.get('success_items', [])
        failed_items = results.get('failed_items', [])
        excel_path = results.get('excel_path')
        ppt_path = results.get('ppt_path')

        # 构建汇总对话框
        summary_dialog = QDialog(self)
        summary_dialog.setWindowTitle("自动报告完成")
        summary_dialog.setMinimumWidth(500)
        layout = QVBoxLayout(summary_dialog)

        # 标题
        if failed_items:
            title = QLabel("报告生成完成（部分步骤失败）")
        else:
            title = QLabel("报告生成完成")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 总用时
        time_label = QLabel(f"总用时: {elapsed_text}")
        time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_label.setStyleSheet("color: #7f8c8d; font-size: 13px;")
        layout.addWidget(time_label)

        # 成功项：2列网格 + 绿色对勾
        if success_items:
            success_label = QLabel("成功项目:")
            bold_font = success_label.font()
            bold_font.setBold(True)
            success_label.setFont(bold_font)
            success_label.setStyleSheet("color: #27ae60;")
            layout.addWidget(success_label)

            from PyQt6.QtWidgets import QGridLayout
            grid = QGridLayout()
            grid.setSpacing(6)
            for i, item in enumerate(success_items):
                label = QLabel(f"  \u2713  {item}")
                label.setStyleSheet("color: #2c3e50; font-size: 13px;")
                grid.addWidget(label, i // 2, i % 2)
            layout.addLayout(grid)

        # 失败项
        if failed_items:
            fail_label = QLabel("失败项目:")
            fail_font = fail_label.font()
            fail_font.setBold(True)
            fail_label.setFont(fail_font)
            fail_label.setStyleSheet("color: #e74c3c;")
            layout.addWidget(fail_label)
            for name, err in failed_items:
                err_short = err[:80] if len(err) > 80 else err
                err_label = QLabel(f"  \u2717  {name}: {err_short}")
                err_label.setStyleSheet("color: #c0392b; font-size: 13px;")
                layout.addWidget(err_label)

        # 提示
        layout.addSpacing(8)
        tip_label = QLabel("个体选配需手动执行")
        tip_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        layout.addWidget(tip_label)

        # 按钮样式
        primary_style = """
            QPushButton {
                background-color: #3498db; color: white;
                border: none; border-radius: 6px;
                padding: 8px 20px; font-size: 13px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """
        secondary_style = """
            QPushButton {
                background-color: white; color: #333;
                border: 1px solid #ddd; border-radius: 6px;
                padding: 8px 20px; font-size: 13px;
            }
            QPushButton:hover { background-color: #f5f5f5; }
        """
        close_style = """
            QPushButton {
                background-color: transparent; color: #999;
                border: none; padding: 8px 16px; font-size: 13px;
            }
            QPushButton:hover { color: #666; }
        """

        # 按钮区域
        layout.addSpacing(8)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        if excel_path:
            btn_open_excel = QPushButton("打开Excel报告")
            btn_open_excel.setStyleSheet(primary_style)
            btn_open_excel.clicked.connect(
                lambda: self._open_file(excel_path)
            )
            btn_layout.addWidget(btn_open_excel)

        if ppt_path:
            btn_open_ppt = QPushButton("打开PPT报告")
            btn_open_ppt.setStyleSheet(primary_style)
            btn_open_ppt.clicked.connect(
                lambda: self._open_file(ppt_path)
            )
            btn_layout.addWidget(btn_open_ppt)

        btn_open_folder = QPushButton("打开项目文件夹")
        btn_open_folder.setStyleSheet(secondary_style)
        btn_open_folder.clicked.connect(
            lambda: self._open_path(str(project_path))
        )
        btn_layout.addWidget(btn_open_folder)

        btn_close = QPushButton("关闭")
        btn_close.setStyleSheet(close_style)
        btn_close.clicked.connect(summary_dialog.accept)
        btn_layout.addWidget(btn_close)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        summary_dialog.exec()

        # 重置状态
        self.selected_farms.clear()
        self._clear_local_farms()
        self.update_selection_ui()

        for farm_code, widget in self.farm_list_items.items():
            widget.set_checked(False)

        self.logger.info(f"自动报告项目完成: {project_path}")

        # 通知主窗口自动选择新创建的项目
        self.project_created.emit(project_path)

    def _open_path(self, path):
        """用系统文件管理器打开文件夹"""
        import subprocess, sys
        if sys.platform == 'darwin':
            subprocess.Popen(['open', path])
        elif sys.platform == 'win32':
            subprocess.Popen(['explorer', path])
        else:
            subprocess.Popen(['xdg-open', path])

    def _open_file(self, file_path):
        """用系统默认应用打开文件"""
        import subprocess, sys
        if sys.platform == 'darwin':
            subprocess.Popen(['open', file_path])
        elif sys.platform == 'win32':
            import os
            os.startfile(file_path)
        else:
            subprocess.Popen(['xdg-open', file_path])
