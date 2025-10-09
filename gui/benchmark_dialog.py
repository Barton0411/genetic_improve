"""
对比牧场管理对话框
"""

import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QInputDialog, QFileDialog,
    QHeaderView, QLabel, QLineEdit, QTextEdit, QDialogButtonBox,
    QGroupBox, QFormLayout, QTabWidget, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor

from core.benchmark import BenchmarkManager

logger = logging.getLogger(__name__)


class BenchmarkDialog(QDialog):
    """对比牧场管理对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("对比牧场管理")
        self.setMinimumSize(800, 500)

        # 初始化对比牧场管理器
        self.benchmark_manager = BenchmarkManager()

        self.setup_ui()
        self.load_farms()
        self.load_reference_data()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 创建Tab控件
        self.tab_widget = QTabWidget()

        # Tab 1: 对比牧场
        farm_tab = self.create_farm_tab()
        self.tab_widget.addTab(farm_tab, "对比牧场")

        # Tab 2: 外部参考数据
        reference_tab = self.create_reference_tab()
        self.tab_widget.addTab(reference_tab, "外部参考数据")

        layout.addWidget(self.tab_widget)

        # 底部关闭按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def create_farm_tab(self):
        """创建对比牧场Tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 说明标签
        info_label = QLabel("管理对比牧场数据。可以添加历史牧场的关键育种性状分析结果，用于表格和折线图对比。")
        info_label.setStyleSheet("color: #7f8c8d; padding: 10px;")
        layout.addWidget(info_label)

        # 牧场列表表格
        self.farm_table = QTableWidget()
        self.farm_table.setColumnCount(4)
        self.farm_table.setHorizontalHeaderLabels(["牧场名称", "描述", "添加日期", "最后更新"])
        self.farm_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.farm_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.farm_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.farm_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.farm_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.farm_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.farm_table.setAlternatingRowColors(True)
        layout.addWidget(self.farm_table)

        # 按钮组
        button_layout = QHBoxLayout()

        self.add_btn = QPushButton("添加牧场")
        self.add_btn.clicked.connect(self.add_farm)
        button_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("编辑牧场")
        self.edit_btn.clicked.connect(self.edit_farm)
        button_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("删除牧场")
        self.delete_btn.clicked.connect(self.delete_farm)
        button_layout.addWidget(self.delete_btn)

        self.update_data_btn = QPushButton("更新数据")
        self.update_data_btn.clicked.connect(self.update_farm_data)
        button_layout.addWidget(self.update_data_btn)

        button_layout.addStretch()

        layout.addLayout(button_layout)

        return tab

    def create_reference_tab(self):
        """创建外部参考数据Tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 说明标签
        info_label = QLabel("管理外部参考数据（如行业数据、参测牛数据等）。仅用于折线图对比，不会添加到表格中。")
        info_label.setStyleSheet("color: #7f8c8d; padding: 10px;")
        layout.addWidget(info_label)

        # 外部参考数据列表表格
        self.reference_table = QTableWidget()
        self.reference_table.setColumnCount(4)
        self.reference_table.setHorizontalHeaderLabels(["参考数据名称", "描述", "添加日期", "最后更新"])
        self.reference_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.reference_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.reference_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.reference_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.reference_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.reference_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.reference_table.setAlternatingRowColors(True)
        layout.addWidget(self.reference_table)

        # 按钮组
        button_layout = QHBoxLayout()

        self.add_ref_btn = QPushButton("添加参考数据")
        self.add_ref_btn.clicked.connect(self.add_reference_data)
        button_layout.addWidget(self.add_ref_btn)

        self.download_template_btn = QPushButton("下载模板")
        self.download_template_btn.clicked.connect(self.download_reference_template)
        button_layout.addWidget(self.download_template_btn)

        self.delete_ref_btn = QPushButton("删除参考数据")
        self.delete_ref_btn.clicked.connect(self.delete_reference_data)
        button_layout.addWidget(self.delete_ref_btn)

        button_layout.addStretch()

        layout.addLayout(button_layout)

        return tab

    def load_farms(self):
        """加载牧场列表"""
        self.farm_table.setRowCount(0)

        farms = self.benchmark_manager.get_all_farms()

        for farm in farms:
            row = self.farm_table.rowCount()
            self.farm_table.insertRow(row)

            # 牧场名称
            name_item = QTableWidgetItem(farm['name'])
            name_item.setData(Qt.ItemDataRole.UserRole, farm['id'])  # 存储farm_id
            self.farm_table.setItem(row, 0, name_item)

            # 描述
            desc_item = QTableWidgetItem(farm.get('description', ''))
            self.farm_table.setItem(row, 1, desc_item)

            # 添加日期
            added_date = farm.get('added_date', '')[:10]  # 只显示日期部分
            date_item = QTableWidgetItem(added_date)
            self.farm_table.setItem(row, 2, date_item)

            # 最后更新
            last_updated = farm.get('last_updated', '')[:10]
            updated_item = QTableWidgetItem(last_updated)
            self.farm_table.setItem(row, 3, updated_item)

    def add_farm(self):
        """添加牧场"""
        dialog = AddFarmDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            farm_name = dialog.farm_name
            description = dialog.description
            excel_file_path = dialog.excel_file_path

            if not farm_name:
                QMessageBox.warning(self, "警告", "请输入牧场名称")
                return

            if not excel_file_path:
                QMessageBox.warning(self, "警告", "请选择Excel文件")
                return

            # 添加牧场
            success = self.benchmark_manager.add_farm(
                farm_name=farm_name,
                description=description,
                excel_file_path=excel_file_path
            )

            if success:
                QMessageBox.information(self, "成功", f"牧场 '{farm_name}' 已添加")
                self.load_farms()
            else:
                QMessageBox.warning(self, "失败", "添加牧场失败，请检查日志")

    def edit_farm(self):
        """编辑牧场"""
        current_row = self.farm_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择一个牧场")
            return

        farm_id = self.farm_table.item(current_row, 0).data(Qt.ItemDataRole.UserRole)
        farm = self.benchmark_manager.get_farm_by_id(farm_id)

        if not farm:
            QMessageBox.warning(self, "错误", "未找到牧场信息")
            return

        dialog = EditFarmDialog(self, farm)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name = dialog.farm_name
            new_description = dialog.description

            success = self.benchmark_manager.update_farm(
                farm_id=farm_id,
                name=new_name if new_name != farm['name'] else None,
                description=new_description if new_description != farm.get('description', '') else None
            )

            if success:
                QMessageBox.information(self, "成功", "牧场信息已更新")
                self.load_farms()
            else:
                QMessageBox.warning(self, "失败", "更新牧场信息失败")

    def delete_farm(self):
        """删除牧场"""
        current_row = self.farm_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择一个牧场")
            return

        farm_id = self.farm_table.item(current_row, 0).data(Qt.ItemDataRole.UserRole)
        farm_name = self.farm_table.item(current_row, 0).text()

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除牧场 '{farm_name}' 吗？\n\n这将删除所有相关数据，此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success = self.benchmark_manager.delete_farm(farm_id)

            if success:
                QMessageBox.information(self, "成功", f"牧场 '{farm_name}' 已删除")
                self.load_farms()
            else:
                QMessageBox.warning(self, "失败", "删除牧场失败")

    def update_farm_data(self):
        """更新牧场数据"""
        current_row = self.farm_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择一个牧场")
            return

        farm_id = self.farm_table.item(current_row, 0).data(Qt.ItemDataRole.UserRole)
        farm_name = self.farm_table.item(current_row, 0).text()

        # 选择Excel文件
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"选择 '{farm_name}' 的新数据文件",
            "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )

        if file_path:
            file_path = Path(file_path)

            # 验证文件
            from core.benchmark import TraitsExcelParser
            parser = TraitsExcelParser(file_path)

            is_valid, error_msg = parser.validate()
            if not is_valid:
                QMessageBox.warning(self, "文件验证失败", error_msg)
                return

            success = self.benchmark_manager.update_farm(
                farm_id=farm_id,
                excel_file_path=file_path
            )

            if success:
                QMessageBox.information(self, "成功", f"牧场 '{farm_name}' 的数据已更新")
                self.load_farms()
            else:
                QMessageBox.warning(self, "失败", "更新牧场数据失败")

    # === 外部参考数据管理方法 ===

    def load_reference_data(self):
        """加载外部参考数据列表"""
        self.reference_table.setRowCount(0)

        references = self.benchmark_manager.get_all_reference_data()

        for ref in references:
            row = self.reference_table.rowCount()
            self.reference_table.insertRow(row)

            # 参考数据名称
            name_item = QTableWidgetItem(ref['name'])
            name_item.setData(Qt.ItemDataRole.UserRole, ref['id'])
            self.reference_table.setItem(row, 0, name_item)

            # 描述
            desc_item = QTableWidgetItem(ref.get('description', ''))
            self.reference_table.setItem(row, 1, desc_item)

            # 添加日期
            added_date = ref.get('added_date', '')[:10]
            date_item = QTableWidgetItem(added_date)
            self.reference_table.setItem(row, 2, date_item)

            # 最后更新
            last_updated = ref.get('last_updated', '')[:10]
            updated_item = QTableWidgetItem(last_updated)
            self.reference_table.setItem(row, 3, updated_item)

    def add_reference_data(self):
        """添加外部参考数据"""
        dialog = AddReferenceDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            ref_name = dialog.ref_name
            description = dialog.description
            excel_file_path = dialog.excel_file_path

            if not ref_name:
                QMessageBox.warning(self, "警告", "请输入参考数据名称")
                return

            if not excel_file_path:
                QMessageBox.warning(self, "警告", "请选择Excel文件")
                return

            # 添加参考数据
            success = self.benchmark_manager.add_reference_data(
                name=ref_name,
                description=description,
                excel_file_path=excel_file_path
            )

            if success:
                QMessageBox.information(self, "成功", f"外部参考数据 '{ref_name}' 已添加")
                self.load_reference_data()
            else:
                QMessageBox.warning(self, "失败", "添加外部参考数据失败，请检查日志")

    def delete_reference_data(self):
        """删除外部参考数据"""
        current_row = self.reference_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择一个参考数据")
            return

        ref_id = self.reference_table.item(current_row, 0).data(Qt.ItemDataRole.UserRole)
        ref_name = self.reference_table.item(current_row, 0).text()

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除外部参考数据 '{ref_name}' 吗？\n\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success = self.benchmark_manager.delete_reference_data(ref_id)

            if success:
                QMessageBox.information(self, "成功", f"外部参考数据 '{ref_name}' 已删除")
                self.load_reference_data()
            else:
                QMessageBox.warning(self, "失败", "删除外部参考数据失败")

    def download_reference_template(self):
        """下载外部参考数据模板"""
        import shutil

        # 让用户选择保存位置
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存外部参考数据模板",
            "外部参考数据模板.xlsx",
            "Excel Files (*.xlsx);;All Files (*)"
        )

        if file_path:
            from pathlib import Path
            file_path = Path(file_path)

            # 使用项目中的模板文件（已填充示例数据）
            template_path = Path(__file__).parent.parent / "templates" / "外部参考数据模板.xlsx"

            try:
                # 复制模板文件
                shutil.copy(template_path, file_path)

                QMessageBox.information(
                    self, "成功",
                    f"外部参考数据模板已保存到:\n{file_path}\n\n"
                    f"模板包含57个性状列和示例数据，请按格式填写您的数据后导入。"
                )
            except Exception as e:
                logger.error(f"复制模板文件失败: {e}", exc_info=True)
                QMessageBox.warning(self, "失败", f"保存模板失败:\n{str(e)}")


class AddFarmDialog(QDialog):
    """添加牧场对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加对比牧场")
        self.setMinimumWidth(500)

        self.farm_name = ""
        self.description = ""
        self.excel_file_path = None

        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 表单
        form_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如: 示范牧场2024")
        form_layout.addRow("牧场名称*:", self.name_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("例如: 2024年度示范牧场数据，用于对比分析")
        self.desc_edit.setMaximumHeight(80)
        form_layout.addRow("描述:", self.desc_edit)

        layout.addLayout(form_layout)

        # 数据文件选择
        file_group = QGroupBox("数据文件*")
        file_layout = QVBoxLayout()

        info_label = QLabel('请选择"关键育种性状分析结果.xlsx"文件')
        info_label.setStyleSheet("color: #7f8c8d;")
        file_layout.addWidget(info_label)

        file_btn_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText("未选择文件")
        file_btn_layout.addWidget(self.file_path_edit)

        self.browse_btn = QPushButton("选择Excel文件...")
        self.browse_btn.clicked.connect(self.browse_file)
        file_btn_layout.addWidget(self.browse_btn)

        file_layout.addLayout(file_btn_layout)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # 数据预览
        preview_group = QGroupBox("数据预览")
        preview_layout = QVBoxLayout()

        self.preview_label = QLabel("请先选择Excel文件")
        self.preview_label.setStyleSheet("""
            QLabel {
                color: #7f8c8d;
                padding: 10px;
                background-color: #f9f9f9;
                border: 1px dashed #bdc3c7;
                border-radius: 4px;
            }
        """)
        self.preview_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_label)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept_dialog)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def browse_file(self):
        """浏览Excel文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择关键育种性状分析结果文件",
            "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )

        if file_path:
            file_path = Path(file_path)

            # 验证文件
            from core.benchmark import TraitsExcelParser
            parser = TraitsExcelParser(file_path)

            is_valid, error_msg = parser.validate()
            if not is_valid:
                QMessageBox.warning(self, "文件验证失败", error_msg)
                return

            # 显示预览
            preview_text = parser.get_preview_info()
            if preview_text:
                self.preview_label.setText(preview_text)
                self.preview_label.setStyleSheet("""
                    QLabel {
                        color: #27ae60;
                        padding: 10px;
                        background-color: #e8f8f5;
                        border: 1px solid #27ae60;
                        border-radius: 4px;
                    }
                """)

            self.excel_file_path = file_path
            self.file_path_edit.setText(str(file_path))

    def accept_dialog(self):
        """确认对话框"""
        self.farm_name = self.name_edit.text().strip()
        self.description = self.desc_edit.toPlainText().strip()

        if not self.farm_name:
            QMessageBox.warning(self, "警告", "请输入牧场名称")
            return

        if not self.excel_file_path:
            QMessageBox.warning(self, "警告", "请选择Excel文件")
            return

        self.accept()


class EditFarmDialog(QDialog):
    """编辑牧场对话框"""

    def __init__(self, parent=None, farm_info=None):
        super().__init__(parent)
        self.setWindowTitle("编辑对比牧场")
        self.setMinimumWidth(500)

        self.farm_info = farm_info or {}
        self.farm_name = ""
        self.description = ""

        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 表单
        form_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setText(self.farm_info.get('name', ''))
        form_layout.addRow("牧场名称*:", self.name_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setText(self.farm_info.get('description', ''))
        self.desc_edit.setMaximumHeight(80)
        form_layout.addRow("描述:", self.desc_edit)

        layout.addLayout(form_layout)

        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept_dialog)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept_dialog(self):
        """确认对话框"""
        self.farm_name = self.name_edit.text().strip()
        self.description = self.desc_edit.toPlainText().strip()

        if not self.farm_name:
            QMessageBox.warning(self, "警告", "请输入牧场名称")
            return

        self.accept()


# === 外部参考数据Dialog添加到BenchmarkDialog类 ===

class AddReferenceDialog(QDialog):
    """添加外部参考数据对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加外部参考数据")
        self.setMinimumWidth(500)

        self.ref_name = ""
        self.description = ""
        self.excel_file_path = None

        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 表单
        form_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如: 参测牛数据2024")
        form_layout.addRow("参考数据名称*:", self.name_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("例如: 2024年度参测牛遗传进展数据")
        self.desc_edit.setMaximumHeight(80)
        form_layout.addRow("描述:", self.desc_edit)

        layout.addLayout(form_layout)

        # 数据文件选择
        file_group = QGroupBox("数据文件*")
        file_layout = QVBoxLayout()

        info_label = QLabel('请选择外部参考数据Excel文件（需按模板格式填写）')
        info_label.setStyleSheet("color: #7f8c8d;")
        file_layout.addWidget(info_label)

        file_btn_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText("未选择文件")
        file_btn_layout.addWidget(self.file_path_edit)

        self.browse_btn = QPushButton("选择Excel文件...")
        self.browse_btn.clicked.connect(self.browse_file)
        file_btn_layout.addWidget(self.browse_btn)

        file_layout.addLayout(file_btn_layout)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # 数据预览
        preview_group = QGroupBox("数据预览")
        preview_layout = QVBoxLayout()

        self.preview_label = QLabel("请先选择Excel文件")
        self.preview_label.setStyleSheet("""
            QLabel {
                color: #7f8c8d;
                padding: 10px;
                background-color: #f9f9f9;
                border: 1px dashed #bdc3c7;
                border-radius: 4px;
            }
        """)
        self.preview_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_label)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept_dialog)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def browse_file(self):
        """浏览Excel文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择外部参考数据文件",
            "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )

        if file_path:
            from pathlib import Path
            file_path = Path(file_path)

            # 验证文件
            from core.benchmark import ReferenceDataParser
            parser = ReferenceDataParser(file_path)

            is_valid, error_msg = parser.validate()
            if not is_valid:
                QMessageBox.warning(self, "文件验证失败", error_msg)
                return

            # 显示预览
            preview_text = parser.get_preview_info()
            if preview_text:
                self.preview_label.setText(preview_text)
                self.preview_label.setStyleSheet("""
                    QLabel {
                        color: #27ae60;
                        padding: 10px;
                        background-color: #e8f8f5;
                        border: 1px solid #27ae60;
                        border-radius: 4px;
                    }
                """)

            self.excel_file_path = file_path
            self.file_path_edit.setText(str(file_path))

    def accept_dialog(self):
        """确认对话框"""
        self.ref_name = self.name_edit.text().strip()
        self.description = self.desc_edit.toPlainText().strip()

        if not self.ref_name:
            QMessageBox.warning(self, "警告", "请输入参考数据名称")
            return

        if not self.excel_file_path:
            QMessageBox.warning(self, "警告", "请选择Excel文件")
            return

        self.accept()
