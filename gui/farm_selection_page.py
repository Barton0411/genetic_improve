"""
伊起牛牧场数据选择页面
用于演示数据平台对接功能
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QGroupBox, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
import json
from pathlib import Path


class FarmButton(QPushButton):
    """牧场按钮组件"""
    def __init__(self, farm_code, farm_name, parent=None):
        super().__init__(f"{farm_code} {farm_name}", parent)
        self.farm_code = farm_code
        self.farm_name = farm_name
        self.setCheckable(True)
        self.setMinimumWidth(180)
        self.setMaximumWidth(250)
        self.setStyleSheet("""
            QPushButton {
                background-color: #f5f7fa;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                padding: 8px 12px;
                text-align: left;
                font-size: 13px;
                color: #303133;
            }
            QPushButton:hover {
                background-color: #ecf5ff;
                border-color: #409eff;
                color: #409eff;
            }
            QPushButton:checked {
                background-color: #409eff;
                border-color: #409eff;
                color: white;
                font-weight: bold;
            }
        """)


class RegionCollapsible(QWidget):
    """可折叠的区域组件"""
    farmSelected = pyqtSignal(str, str, str, str, str)

    def __init__(self, region_name, farms, parent=None):
        super().__init__(parent)
        self.region_name = region_name
        self.farms = farms
        self.farm_buttons = []
        self.is_expanded = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # 标题栏（可点击展开/收起）
        title_widget = QWidget()
        title_widget.setStyleSheet("""
            QWidget {
                background-color: #f0f2f5;
                border-radius: 4px;
            }
            QWidget:hover {
                background-color: #e8eaed;
            }
        """)
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(8, 6, 8, 6)

        self.toggle_btn = QPushButton(f"▶ {self.region_name} ({len(self.farms)}个牧场)")
        self.toggle_btn.setFlat(True)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                font-size: 13px;
                color: #606266;
                border: none;
                background: transparent;
            }
        """)
        self.toggle_btn.clicked.connect(self.toggle_content)
        title_layout.addWidget(self.toggle_btn)

        layout.addWidget(title_widget)

        # 内容区域（折叠时不显示）
        self.content_widget = QWidget()
        content_layout = QHBoxLayout(self.content_widget)
        content_layout.setContentsMargins(8, 5, 8, 5)
        content_layout.setSpacing(6)

        # 创建牧场按钮
        for farm in self.farms:
            btn = FarmButton(farm['code'], farm['name'])
            btn.clicked.connect(lambda checked, b=btn: self.on_farm_clicked(b))
            self.farm_buttons.append(btn)
            content_layout.addWidget(btn)

        content_layout.addStretch()
        self.content_widget.setVisible(False)  # 默认折叠

        layout.addWidget(self.content_widget)

    def toggle_content(self):
        """切换展开/折叠状态"""
        self.is_expanded = not self.is_expanded
        self.content_widget.setVisible(self.is_expanded)
        icon = "▼" if self.is_expanded else "▶"
        self.toggle_btn.setText(f"{icon} {self.region_name} ({len(self.farms)}个牧场)")

    def on_farm_clicked(self, clicked_btn):
        """牧场按钮点击事件"""
        # 取消其他按钮的选中状态
        for btn in self.farm_buttons:
            if btn != clicked_btn:
                btn.setChecked(False)

        # 如果当前按钮被选中，发送信号
        if clicked_btn.isChecked():
            self.farmSelected.emit(
                self.region_name,
                clicked_btn.farm_code,
                clicked_btn.farm_name,
                "",
                ""
            )

    def clear_selection(self):
        """清除所有选中状态"""
        for btn in self.farm_buttons:
            btn.setChecked(False)


class AreaWidget(QWidget):
    """大区卡片组件 - 固定显示，不可折叠"""
    farmSelected = pyqtSignal(str, str, str, str, str)

    def __init__(self, area_name, area_data, parent=None):
        super().__init__(parent)
        self.area_name = area_name
        self.area_data = area_data
        self.region_groups = []
        self.init_ui()

    def init_ui(self):
        # 整体卡片容器
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 卡片
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e4e7ed;
                border-radius: 8px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(15, 12, 15, 15)
        card_layout.setSpacing(10)

        # 标题
        title_label = QLabel(f"🌏 {self.area_name}")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #303133;
                padding-bottom: 5px;
                border-bottom: 2px solid #409eff;
            }
        """)
        card_layout.addWidget(title_label)

        # 滚动区域（容纳所有区域）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 5, 0, 0)
        scroll_layout.setSpacing(8)

        # 创建区域分组（可折叠）
        for region in self.area_data['regions']:
            region_group = RegionCollapsible(region['name'], region['farms'])
            region_group.farmSelected.connect(self.on_farm_selected)
            self.region_groups.append(region_group)
            scroll_layout.addWidget(region_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        card_layout.addWidget(scroll)

        main_layout.addWidget(card)

    def on_farm_selected(self, region_name, farm_code, farm_name, area_name, region_full_name):
        """转发牧场选择信号"""
        self.farmSelected.emit(self.area_name, farm_code, farm_name, region_name, "")

    def clear_selection(self):
        """清除所有选中状态"""
        for group in self.region_groups:
            group.clear_selection()


class FarmSelectionPage(QWidget):
    """牧场选择页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_farm = None
        self.area_widgets = []
        self.init_ui()
        self.load_demo_data()

    def init_ui(self):
        from PyQt6.QtWidgets import QGridLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 搜索栏
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 搜索：")
        search_label.setStyleSheet("font-size: 14px; color: #606266;")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入牧场名称或编号（如：00213）...")
        self.search_input.textChanged.connect(self.filter_farms)
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

        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(lambda: self.search_input.clear())
        clear_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                background-color: #f5f7fa;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #ecf5ff;
                border-color: #409eff;
                color: #409eff;
            }
        """)

        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(clear_btn)
        layout.addLayout(search_layout)

        # 2x2网格布局容纳4个大区卡片
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(15)
        layout.addLayout(self.grid_layout, 1)  # 设置stretch为1，让网格占据主要空间

        # 底部状态栏
        bottom_widget = QWidget()
        bottom_widget.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                padding: 12px;
            }
        """)
        bottom_layout = QHBoxLayout(bottom_widget)

        self.status_label = QLabel("当前选择：未选择")
        self.status_label.setStyleSheet("font-size: 14px; color: #606266;")
        bottom_layout.addWidget(self.status_label, 1)

        confirm_btn = QPushButton("确认选择")
        confirm_btn.clicked.connect(self.confirm_selection)
        confirm_btn.setStyleSheet("""
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
        bottom_layout.addWidget(confirm_btn)

        layout.addWidget(bottom_widget)

    def load_demo_data(self):
        """加载演示数据"""
        # 生成演示数据 - 4个大区
        demo_data = {
            "areas": [
                {"name": "东部大区", "regions": self.generate_regions("东部", "00")},
                {"name": "南部大区", "regions": self.generate_regions("南部", "10")},
                {"name": "西部大区", "regions": self.generate_regions("西部", "20")},
                {"name": "北部大区", "regions": self.generate_regions("北部", "30")}
            ]
        }

        # 2x2网格布局位置
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]

        # 创建大区组件并放入网格
        for i, (area_data, pos) in enumerate(zip(demo_data['areas'], positions)):
            area_widget = AreaWidget(area_data['name'], area_data)
            area_widget.farmSelected.connect(self.on_farm_selected)
            self.area_widgets.append(area_widget)
            self.grid_layout.addWidget(area_widget, pos[0], pos[1])

    def generate_regions(self, area_prefix, code_prefix):
        """生成区域数据"""
        regions = []
        for i in range(1, 6):  # 5个区域
            farms = []
            farm_count = 3 if i <= 3 else 2  # 前3个区域各3个牧场，后2个区域各2个牧场
            for j in range(farm_count):
                farm_code = f"{code_prefix}{i}{j+1:02d}"
                farm_name = f"{area_prefix}区域{i}牧场{chr(65+j)}"
                farms.append({"code": farm_code, "name": farm_name})

            regions.append({
                "name": f"区域{i}",
                "farms": farms
            })
        return regions

    def on_farm_selected(self, area_name, farm_code, farm_name, region_name, _):
        """牧场选中事件"""
        self.selected_farm = {
            "area": area_name,
            "region": region_name,
            "code": farm_code,
            "name": farm_name
        }

        # 更新状态显示
        self.status_label.setText(
            f"当前选择：{area_name} - {region_name} - {farm_code} {farm_name}"
        )

        # 清除其他大区的选中状态
        for widget in self.area_widgets:
            if widget.area_name != area_name:
                widget.clear_selection()

    def filter_farms(self, text):
        """搜索过滤"""
        if not text:
            # 显示所有
            for widget in self.area_widgets:
                widget.setVisible(True)
                for group in widget.region_groups:
                    group.setVisible(True)
                    for btn in group.farm_buttons:
                        btn.setVisible(True)
            return

        text = text.lower()
        has_match = False

        for area_widget in self.area_widgets:
            area_has_match = False
            for region_group in area_widget.region_groups:
                region_has_match = False
                for btn in region_group.farm_buttons:
                    # 匹配牧场编号或名称
                    if text in btn.farm_code.lower() or text in btn.farm_name.lower():
                        btn.setVisible(True)
                        region_has_match = True
                        has_match = True
                    else:
                        btn.setVisible(False)

                region_group.setVisible(region_has_match)
                if region_has_match:
                    area_has_match = True

            area_widget.setVisible(area_has_match)
            # 如果有匹配结果，自动展开该大区
            if area_has_match and text:
                area_widget.expand()

    def confirm_selection(self):
        """确认选择"""
        if self.selected_farm:
            QMessageBox.information(
                self,
                "演示模式",
                f"您选择了：\n\n"
                f"大区：{self.selected_farm['area']}\n"
                f"区域：{self.selected_farm['region']}\n"
                f"牧场编号：{self.selected_farm['code']}\n"
                f"牧场名称：{self.selected_farm['name']}\n\n"
                f"这是演示界面，不会执行实际操作。"
            )
        else:
            QMessageBox.warning(self, "提示", "请先选择一个牧场")
