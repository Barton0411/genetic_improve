"""
伊起牛牧场数据对接页面
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QMessageBox, QTableWidget, QTableWidgetItem,
    QDialog, QListWidget, QProgressDialog, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from pathlib import Path
from datetime import datetime
import logging
import pandas as pd

from api.yqn_api_client import YQNApiClient
from core.data.yqn_data_converter import YQNDataConverter
from utils.file_manager import FileManager
from core.data.uploader import upload_and_standardize_cow_data


class DataDownloadWorker(QThread):
    """后台下载和处理数据的工作线程"""
    progress = pyqtSignal(int, str)  # (百分比, 状态消息)
    finished = pyqtSignal(Path)  # Excel文件路径
    error = pyqtSignal(str)  # 错误消息

    def __init__(self, api_client, farm_code, project_path, farm_name):
        super().__init__()
        self.api_client = api_client
        self.farm_code = farm_code
        self.project_path = project_path
        self.farm_name = farm_name
        self.logger = logging.getLogger(__name__)

    def run(self):
        """执行数据下载和标准化流程"""
        try:
            # 步骤1: 下载牛群数据 (20%)
            self.progress.emit(10, "正在连接伊起牛服务器...")
            api_data = self.api_client.get_farm_herd(self.farm_code)
            self.progress.emit(20, f"已下载 {len(api_data.get('data', []))} 头牛只数据")

            # 步骤2: 转换为Excel (40%)
            self.progress.emit(30, "正在转换数据格式...")
            raw_data_dir = self.project_path / "raw_data"
            raw_data_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            excel_path = raw_data_dir / f"牛群明细_{self.farm_name}_{timestamp}.xlsx"

            YQNDataConverter.convert_herd_to_excel(api_data, excel_path)
            self.progress.emit(40, "数据格式转换完成")

            # 步骤3: 标准化处理 (60-95%)
            self.progress.emit(50, "正在进行数据标准化...")

            def standardize_progress(*args):
                """标准化进度回调 - 映射到60-95%，支持1或2个参数"""
                if len(args) == 2:
                    pct, msg = args
                elif len(args) == 1:
                    pct = args[0]
                    msg = f"{pct}%"
                else:
                    return

                try:
                    mapped_pct = 60 + int(pct * 0.35)
                    self.progress.emit(mapped_pct, f"标准化: {msg}")
                except Exception as e:
                    self.logger.warning(f"进度回调出错: {e}, args={args}")

            standardized_path = upload_and_standardize_cow_data(
                input_files=[excel_path],
                project_path=self.project_path,
                progress_callback=standardize_progress,
                source_system="伊起牛"
            )

            self.progress.emit(95, "数据标准化完成")

            # 步骤4: 完成 (100%)
            self.progress.emit(100, "牧场项目创建成功!")
            self.finished.emit(excel_path)

        except Exception as e:
            self.logger.exception("数据下载处理失败")
            self.error.emit(f"处理失败: {str(e)}")


class FarmSelectDialog(QDialog):
    """牧场选择对话框 - 当搜索到多个匹配牧场时使用"""

    def __init__(self, farms, parent=None):
        super().__init__(parent)
        self.farms = farms
        self.selected_farm = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("选择牧场")
        self.setFixedSize(400, 300)

        layout = QVBoxLayout(self)

        # 提示
        tip_label = QLabel(f"找到 {len(self.farms)} 个匹配的牧场，请选择：")
        tip_label.setStyleSheet("font-size: 14px; color: #606266; padding: 10px;")
        layout.addWidget(tip_label)

        # 牧场列表
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)

        for farm in self.farms:
            farm_code = farm.get("farmCode", "")
            farm_name = farm.get("farmName", "")
            self.list_widget.addItem(f"{farm_code} - {farm_name}")

        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:hover {
                background-color: #ecf5ff;
            }
            QListWidget::item:selected {
                background-color: #409eff;
                color: white;
            }
        """)
        layout.addWidget(self.list_widget)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        confirm_btn = QPushButton("确定")
        confirm_btn.clicked.connect(self.on_confirm)
        confirm_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 20px;
                background-color: #409eff;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #66b1ff;
            }
        """)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 20px;
                background-color: #f5f7fa;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #ecf5ff;
            }
        """)

        btn_layout.addWidget(confirm_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def on_item_double_clicked(self, item):
        """双击直接确认"""
        self.on_confirm()

    def on_confirm(self):
        """确认选择"""
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            self.selected_farm = self.farms[current_row]
            self.accept()
        else:
            QMessageBox.warning(self, "提示", "请先选择一个牧场")


class FarmSelectionPage(QWidget):
    """伊起牛牧场数据对接页面"""

    def __init__(self, yqn_token=None, parent=None):
        super().__init__(parent)
        self.yqn_token = yqn_token
        self.api_client = None
        self.user_farms = []
        self.current_farm = None
        self.logger = logging.getLogger(__name__)

        self.init_ui()

        # 如果有token，初始化API客户端
        if self.yqn_token:
            self.logger.info(f"FarmSelectionPage: 检测到token，长度={len(self.yqn_token)}")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, self.init_api_client)  # 延迟500ms确保UI已完全初始化
        else:
            self.logger.warning("FarmSelectionPage: 未检测到token!")

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # 顶部区域 - 标题和描述
        header_widget = QWidget()
        header_widget.setStyleSheet("""
            QWidget {
                background-color: #f5f7fa;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 20, 20, 20)
        header_layout.setSpacing(10)

        # 标题
        title_label = QLabel("🐄 伊起牛牧场数据对接")
        title_font = QFont("微软雅黑", 18, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #303133; background: transparent; padding: 0;")
        header_layout.addWidget(title_label)

        # 描述文字
        desc_label = QLabel(
            "快速对接伊起牛平台，一键导入牧场数据\n"
            "支持自动下载牛群结构、自动数据标准化、自动创建项目"
        )
        desc_label.setStyleSheet("""
            color: #606266;
            font-size: 13px;
            line-height: 1.6;
            background: transparent;
            padding: 0;
        """)
        desc_label.setWordWrap(True)
        header_layout.addWidget(desc_label)

        layout.addWidget(header_widget)

        # 搜索栏
        search_group = QGroupBox("搜索牧场")
        search_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #dcdfe6;
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

        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(10, 10, 10, 10)

        search_label = QLabel("输入站号或名称:")
        search_label.setStyleSheet("font-size: 13px; color: #606266; font-weight: normal;")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("例如: 10042 或 牧场名称...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #409eff;
            }
        """)
        self.search_input.returnPressed.connect(self.on_preview_clicked)

        self.preview_btn = QPushButton("预览")
        self.preview_btn.clicked.connect(self.on_preview_clicked)
        self.preview_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 20px;
                background-color: #409eff;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #66b1ff;
            }
            QPushButton:disabled {
                background-color: #c0c4cc;
            }
        """)

        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.preview_btn)
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)

        # 使用指南卡片（空状态时显示）
        self.guide_widget = QWidget()
        self.guide_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(227, 242, 253, 0.4), stop:1 rgba(243, 229, 245, 0.4));
                border-radius: 8px;
                border: 2px solid rgba(187, 222, 251, 0.5);
            }
        """)
        guide_layout = QVBoxLayout(self.guide_widget)
        guide_layout.setContentsMargins(30, 30, 30, 30)
        guide_layout.setSpacing(20)

        # 指南标题
        guide_title = QLabel("📋 使用指南")
        guide_title.setFont(QFont("微软雅黑", 15, QFont.Weight.Bold))
        guide_title.setStyleSheet("color: #1976d2; background: transparent;")
        guide_layout.addWidget(guide_title)

        # 步骤说明
        steps_text = """
        <div style='line-height: 1.8;'>
        <p style='margin: 10px 0; font-size: 13px;'><b style='color: #1976d2; font-size: 16px;'>① 搜索牧场</b><br/>
        <span style='color: #424242;'>在上方输入框中输入牧场站号（如: 10042）或牧场名称</span></p>

        <p style='margin: 10px 0; font-size: 13px;'><b style='color: #1976d2; font-size: 16px;'>② 预览数据</b><br/>
        <span style='color: #424242;'>点击"预览"按钮，系统将显示该牧场的基本信息和前20条牛只数据</span></p>

        <p style='margin: 10px 0; font-size: 13px;'><b style='color: #1976d2; font-size: 16px;'>③ 创建项目</b><br/>
        <span style='color: #424242;'>确认信息无误后，点击"建立牧场项目"按钮，系统将自动：</span><br/>
        <span style='color: #616161; margin-left: 20px;'>• 下载完整牛群数据</span><br/>
        <span style='color: #616161; margin-left: 20px;'>• 转换为标准格式</span><br/>
        <span style='color: #616161; margin-left: 20px;'>• 进行数据标准化处理</span><br/>
        <span style='color: #616161; margin-left: 20px;'>• 创建完整的牧场项目</span></p>
        </div>
        """
        steps_label = QLabel(steps_text)
        steps_label.setStyleSheet("background: transparent; color: #424242;")
        steps_label.setWordWrap(True)
        guide_layout.addWidget(steps_label)

        # 提示信息
        tip_label = QLabel("💡 提示：整个过程全自动完成，您只需等待即可！")
        tip_label.setStyleSheet("""
            background-color: #fff3cd;
            color: #856404;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #ffc107;
            font-size: 13px;
            font-weight: bold;
        """)
        guide_layout.addWidget(tip_label)

        guide_layout.addStretch()
        layout.addWidget(self.guide_widget, 1)  # 占据剩余空间

        # 牧场信息卡片
        self.info_group = QGroupBox("牧场信息")
        self.info_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #f9fafb;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(15, 15, 15, 15)
        info_layout.setSpacing(8)

        self.farm_name_label = QLabel("牧场名称: -")
        self.farm_code_label = QLabel("站号: -")
        self.cow_count_label = QLabel("牛只总数: -")

        for label in [self.farm_name_label, self.farm_code_label, self.cow_count_label]:
            label.setStyleSheet("font-size: 13px; color: #606266; font-weight: normal;")
            info_layout.addWidget(label)

        self.info_group.setLayout(info_layout)
        self.info_group.setVisible(False)  # 初始隐藏
        layout.addWidget(self.info_group)

        # 数据预览表格
        self.preview_group = QGroupBox("数据预览 (前20条)")
        self.preview_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #dcdfe6;
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

        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(10, 10, 10, 10)

        self.preview_table = QTableWidget()
        self.preview_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                gridline-color: #ebeef5;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #f5f7fa;
                padding: 8px;
                border: none;
                border-right: 1px solid #ebeef5;
                border-bottom: 1px solid #ebeef5;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        preview_layout.addWidget(self.preview_table)
        self.preview_group.setLayout(preview_layout)
        self.preview_group.setVisible(False)  # 初始隐藏
        layout.addWidget(self.preview_group, 1)  # 表格占据主要空间

        # 底部操作按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.create_btn = QPushButton("建立牧场项目")
        self.create_btn.clicked.connect(self.on_create_project_clicked)
        self.create_btn.setEnabled(False)
        self.create_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 30px;
                background-color: #67c23a;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 15px;
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
        layout.addLayout(bottom_layout)

        # 如果没有token，显示提示信息
        if not self.yqn_token:
            self.show_no_token_message()

    def show_no_token_message(self):
        """显示无token提示"""
        msg_label = QLabel(
            "⚠️ 此功能仅对伊起牛账号登录用户开放\n\n"
            "请使用伊起牛账号登录后使用此功能"
        )
        msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #909399;
                padding: 50px;
                background-color: #f9fafb;
                border: 1px dashed #dcdfe6;
                border-radius: 8px;
            }
        """)
        self.layout().insertWidget(1, msg_label)

        # 禁用所有交互控件
        self.search_input.setEnabled(False)
        self.preview_btn.setEnabled(False)

    def init_api_client(self):
        """初始化API客户端并加载用户牧场列表"""
        self.logger.info("=" * 50)
        self.logger.info("开始初始化伊起牛API客户端")
        self.logger.info(f"Token存在: {bool(self.yqn_token)}")
        self.logger.info(f"Token长度: {len(self.yqn_token) if self.yqn_token else 0}")

        try:
            self.api_client = YQNApiClient(self.yqn_token)
            self.logger.info("API客户端对象已创建")

            # 获取用户牧场列表
            self.logger.info("正在调用 get_user_info() API...")
            user_info = self.api_client.get_user_info()
            self.logger.info(f"API调用成功，响应code: {user_info.get('code')}")

            # 提取牧场列表 - farms字段直接在顶层，不在data里！
            self.user_farms = user_info.get("farms", [])
            self.logger.info(f"✓ 已加载 {len(self.user_farms)} 个牧场")

            # 调试：打印前3个牧场的完整数据结构
            if self.user_farms:
                self.logger.info("=== 牧场数据结构调试 ===")
                for i, farm in enumerate(self.user_farms[:3]):
                    self.logger.info(f"牧场 {i+1}: {farm}")
                self.logger.info("======================")
            else:
                self.logger.warning("⚠️ 牧场列表为空!")
                QMessageBox.warning(
                    self,
                    "提示",
                    "您的账号下没有可用的牧场数据"
                )

        except Exception as e:
            self.logger.error("=" * 50)
            self.logger.error("初始化API客户端失败!")
            self.logger.exception(f"异常详情: {e}")
            self.logger.error("=" * 50)

            # 确保user_farms不是None
            if self.user_farms is None:
                self.user_farms = []

            QMessageBox.critical(
                self,
                "初始化失败",
                f"无法连接到伊起牛服务器:\n{str(e)}\n\n请检查网络连接或稍后重试"
            )
        finally:
            self.logger.info(f"初始化完成，user_farms长度: {len(self.user_farms)}")
            self.logger.info("=" * 50)

    def on_preview_clicked(self):
        """预览按钮点击事件"""
        keyword = self.search_input.text().strip()

        if not keyword:
            QMessageBox.warning(self, "提示", "请输入站号或牧场名称")
            return

        if not self.api_client:
            QMessageBox.warning(self, "错误", "API客户端未初始化")
            return

        try:
            # 调试日志
            self.logger.info(f"开始搜索: 关键词='{keyword}', 可用牧场数={len(self.user_farms)}")
            if self.user_farms:
                sample_codes = [f.get("farmCode", "N/A") for f in self.user_farms[:5]]
                self.logger.info(f"前5个牧场站号: {sample_codes}")

            # 搜索牧场
            matched_farms = self.api_client.search_farms(keyword, self.user_farms)

            if not matched_farms:
                # 生成可用牧场列表提示
                available_farms = "\n".join([
                    f"  {f.get('farmCode', 'N/A')} - {f.get('farmName', 'N/A')}"
                    for f in self.user_farms[:10]  # 只显示前10个
                ])
                more_hint = f"\n  ... 还有 {len(self.user_farms) - 10} 个牧场" if len(self.user_farms) > 10 else ""

                QMessageBox.information(
                    self,
                    "未找到",
                    f"没有找到匹配 '{keyword}' 的牧场\n\n"
                    f"您的账号下有 {len(self.user_farms)} 个牧场：\n\n"
                    f"{available_farms}{more_hint}\n\n"
                    f"请检查输入是否正确"
                )
                return

            # 多个匹配时弹出选择对话框
            if len(matched_farms) > 1:
                dialog = FarmSelectDialog(matched_farms, self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    selected_farm = dialog.selected_farm
                else:
                    return  # 用户取消选择
            else:
                selected_farm = matched_farms[0]

            # 加载并预览牧场数据
            self.load_and_preview_farm(selected_farm)

        except Exception as e:
            self.logger.exception("搜索牧场失败")
            QMessageBox.critical(
                self,
                "错误",
                f"搜索失败: {str(e)}"
            )

    def load_and_preview_farm(self, farm):
        """加载并预览牧场数据"""
        farm_code = farm.get("farmCode", "")
        farm_name = farm.get("farmName", "")

        self.logger.info(f"加载牧场数据: {farm_code} - {farm_name}")

        # 显示等待对话框
        progress = QProgressDialog("正在加载牧场数据...", "取消", 0, 0, self)
        progress.setWindowTitle("请稍候")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)  # 不允许取消
        progress.show()

        try:
            # 获取牛群数据
            api_data = self.api_client.get_farm_herd(farm_code)
            records = api_data.get("data", [])

            if not records:
                progress.close()
                QMessageBox.warning(
                    self,
                    "无数据",
                    f"牧场 {farm_name} 没有牛群数据"
                )
                return

            # 保存当前牧场信息
            self.current_farm = {
                "code": farm_code,
                "name": farm_name,
                "cow_count": len(records),
                "api_data": api_data
            }

            # 隐藏使用指南，显示数据预览
            self.guide_widget.setVisible(False)

            # 更新牧场信息显示
            self.farm_name_label.setText(f"牧场名称: {farm_name}")
            self.farm_code_label.setText(f"站号: {farm_code}")
            self.cow_count_label.setText(f"牛只总数: {len(records)} 头")
            self.info_group.setVisible(True)

            # 生成预览数据
            preview_df = YQNDataConverter.preview_data(api_data, limit=20)

            # 更新预览表格
            self.update_preview_table(preview_df)
            self.preview_group.setVisible(True)

            # 启用创建项目按钮
            self.create_btn.setEnabled(True)

            progress.close()

            self.logger.info(f"预览加载成功: {len(records)} 头牛，显示前 {len(preview_df)} 条")

        except Exception as e:
            progress.close()
            self.logger.exception("加载牧场数据失败")
            QMessageBox.critical(
                self,
                "加载失败",
                f"无法加载牧场数据:\n{str(e)}"
            )

    def update_preview_table(self, df):
        """更新预览表格"""
        if df.empty:
            return

        # 设置表格行列数
        self.preview_table.setRowCount(len(df))
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setHorizontalHeaderLabels(df.columns.tolist())

        # 填充数据
        for i in range(len(df)):
            for j in range(len(df.columns)):
                value = df.iloc[i, j]
                # 处理日期和NaN值
                if pd.isna(value):
                    item_text = ""
                elif isinstance(value, pd.Timestamp):
                    item_text = value.strftime('%Y-%m-%d')
                else:
                    item_text = str(value)

                item = QTableWidgetItem(item_text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.preview_table.setItem(i, j, item)

        # 调整列宽
        self.preview_table.resizeColumnsToContents()

        # 限制最大列宽
        for col in range(self.preview_table.columnCount()):
            if self.preview_table.columnWidth(col) > 150:
                self.preview_table.setColumnWidth(col, 150)

    def on_create_project_clicked(self):
        """建立牧场项目按钮点击事件"""
        if not self.current_farm:
            QMessageBox.warning(self, "提示", "请先预览牧场数据")
            return

        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认创建",
            f"即将为牧场 '{self.current_farm['name']}' 创建项目\n\n"
            f"包含 {self.current_farm['cow_count']} 头牛只的数据\n"
            f"系统将自动下载并标准化牛群数据\n\n"
            f"是否继续?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.create_farm_project()

    def create_farm_project(self):
        """创建牧场项目并开始数据处理"""
        farm_name = self.current_farm['name']
        farm_code = self.current_farm['code']

        try:
            # 创建项目文件夹 - 使用与手动创建项目相同的存储位置
            from config.settings import Settings
            settings = Settings()
            base_path = Path(settings.get_default_storage())
            project_path = FileManager.create_project(base_path, farm_name)

            self.logger.info(f"项目文件夹已创建: {project_path}")

            # 创建进度对话框
            progress_dialog = QProgressDialog(self)
            progress_dialog.setWindowTitle("创建项目")
            progress_dialog.setLabelText("正在准备...")
            progress_dialog.setRange(0, 100)
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.setCancelButton(None)  # 不允许取消
            progress_dialog.setMinimumDuration(0)
            progress_dialog.show()

            # 创建后台工作线程
            self.worker = DataDownloadWorker(
                self.api_client,
                farm_code,
                project_path,
                farm_name
            )

            # 连接信号
            self.worker.progress.connect(
                lambda pct, msg: self.on_worker_progress(progress_dialog, pct, msg)
            )
            self.worker.finished.connect(
                lambda path: self.on_worker_finished(progress_dialog, project_path, path)
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

    def on_worker_finished(self, dialog, project_path, excel_path):
        """工作线程完成"""
        dialog.close()

        # 显示成功消息
        QMessageBox.information(
            self,
            "创建成功",
            f"牧场项目已创建成功!\n\n"
            f"项目位置: {project_path}\n\n"
            f"已完成:\n"
            f"✅ 牛群明细已自动下载 ({self.current_farm['cow_count']} 头)\n"
            f"✅ 数据已自动标准化\n\n"
            f"待手动上传:\n"
            f"⚠️ 配种记录\n"
            f"⚠️ 备选公牛清单\n"
            f"⚠️ 冻精库存\n"
            f"⚠️ 体型外貌数据 (可选)\n"
            f"⚠️ 基因组数据 (可选)"
        )

        # 重置状态
        self.current_farm = None
        self.search_input.clear()
        self.info_group.setVisible(False)
        self.preview_group.setVisible(False)
        self.create_btn.setEnabled(False)

        self.logger.info(f"项目创建完成: {project_path}")

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
