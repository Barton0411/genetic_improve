# core/breeding_calc/index_page.py

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QPushButton,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QSpinBox, QScrollArea, QInputDialog, QMainWindow
)
from PyQt6.QtCore import Qt
import json

from .index_calculation import IndexCalculation, TRAIT_SD
from .cow_traits_calc import TRAITS_TRANSLATION  # 从 cow_traits_calc.py 导入 TRAITS_TRANSLATION
from gui.theme_manager import theme_manager  # 导入主题管理器
from gui.progress import ProgressDialog  # 导入进度对话框

class IndexCalculationPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.index_calculator = IndexCalculation()
        self.trait_inputs = {}  # 存储性状输入框
        self.current_weight_name = None
        self.setup_ui()
        # 初始化时就更新权重列表
        try:
            self.update_weight_list()
        except Exception as e:
            import logging
            logging.warning(f"Failed to update weight list during initialization: {e}")
            # 继续初始化，避免崩溃

    def setup_ui(self):
        main_layout = QHBoxLayout(self)

        # 标题和说明
        title_label = QLabel("牛只指数计算排名")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        guide_label = QLabel("请先设置权重，或从已有权重中选择，然后进行指数计算。所有权重的绝对值之和必须等于100。")
        guide_label.setWordWrap(True)

        # 主布局区域
        content_layout = QHBoxLayout()

        # 左侧权重设定区域 (1/2)
        left_widget = self.create_weight_setting_area()
        content_layout.addWidget(left_widget, stretch=2)

        # 右侧区域 (1/2)
        right_layout = QVBoxLayout()

        # 右上权重选择区域 (1/4)
        weight_selection = self.create_weight_selection_area()
        right_layout.addWidget(weight_selection, stretch=1)

        # 右下按钮区域 (1/4)
        button_area = self.create_button_area()
        right_layout.addWidget(button_area, stretch=1)

        content_layout.addLayout(right_layout, stretch=2)

        # 组合所有布局
        layout = QVBoxLayout()
        layout.addWidget(title_label)
        layout.addWidget(guide_label)
        layout.addLayout(content_layout)
        main_layout.addLayout(layout)

        # 初始更新权重列表
        self.update_weight_list()

    def create_weight_setting_area(self):
        """创建左侧权重设定区域"""
        # 使用QScrollArea来支持滚动
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QGridLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 添加表头
        layout.addWidget(QLabel("性状"), 0, 0)
        layout.addWidget(QLabel("权重"), 0, 1)


        # 添加所有性状及其输入框
        row = 1
        for trait, sd in TRAIT_SD.items():
            # 性状名称（英文 - 中文）
            trait_label = QLabel(f"{trait} - {TRAITS_TRANSLATION[trait]}")
            layout.addWidget(trait_label, row, 0)

            # 权重输入框
            weight_input = QSpinBox()
            weight_input.setRange(-100, 100)  # 允许正负权重
            weight_input.setValue(0)
            weight_input.valueChanged.connect(self.update_weight_sum)
            self.trait_inputs[trait] = weight_input
            layout.addWidget(weight_input, row, 1)

            """ # 标准差显示
            sd_label = QLabel(str(sd))
            layout.addWidget(sd_label, row, 2)"""

            row += 1

        # 添加权重总和显示
        self.sum_label = QLabel("当前权重绝对值之和: 0")
        layout.addWidget(self.sum_label, row, 0, 1, 3)

        scroll.setWidget(container)
        return scroll

    def create_weight_selection_area(self):
        """创建右上权重选择区域"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("已有权重配置"))
        
        self.weight_list = QListWidget()
        self.weight_list.itemClicked.connect(self.on_weight_selected)
        layout.addWidget(self.weight_list)

        return widget

    def create_button_area(self):
        """创建右下按钮区域"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 创建按钮
        self.new_weight_btn = QPushButton("新建权重")
        self.delete_weight_btn = QPushButton("删除权重")
        self.cow_index_btn = QPushButton("母牛群指数排名")
        self.bull_index_btn = QPushButton("备选公牛指数排名")

        # 根据主题设置按钮样式
        button_style = theme_manager.get_button_style_for_index_calc()
        for btn in [self.new_weight_btn, self.delete_weight_btn,
                   self.cow_index_btn, self.bull_index_btn]:
            btn.setStyleSheet(button_style)

        # 连接信号
        self.new_weight_btn.clicked.connect(self.save_new_weight)
        self.delete_weight_btn.clicked.connect(self.delete_weight)
        self.cow_index_btn.clicked.connect(self.calculate_cow_index)
        self.bull_index_btn.clicked.connect(self.calculate_bull_index)

        # 初始禁用一些按钮
        self.delete_weight_btn.setEnabled(False)
        self.cow_index_btn.setEnabled(False)
        self.bull_index_btn.setEnabled(False)

        # 添加按钮到布局
        for btn in [self.new_weight_btn, self.delete_weight_btn, 
                   self.cow_index_btn, self.bull_index_btn]:
            layout.addWidget(btn)

        layout.addStretch()
        return widget

    def get_main_window(self):
        """获取主窗口实例"""
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        return parent

    def update_weight_sum(self):
        """更新权重总和显示"""
        total = sum(abs(input_widget.value()) for input_widget in self.trait_inputs.values())
        self.sum_label.setText(f"当前权重绝对值之和: {total}")
        
        # 根据总和是否为100启用或禁用新建按钮
        self.new_weight_btn.setEnabled(abs(total - 100) < 0.0001)

    def update_weight_list(self):
        """更新权重列表"""
        self.weight_list.clear()
 
        try:
            # 直接从计算器加载权重
            weights = self.index_calculator.load_weights()
            for name in weights.keys():
                item = QListWidgetItem(name)
                item.setData(Qt.ItemDataRole.UserRole, name)
                self.weight_list.addItem(item)
        except Exception as e:
            import logging
            logging.error(f"Error loading weights: {e}")
            # 如果加载失败，至少保证程序不崩溃

    def on_weight_selected(self, item):
        """处理权重选择"""
        weight_name = item.data(Qt.ItemDataRole.UserRole)
        self.current_weight_name = weight_name
        
        # 获取权重数据
        weights = self.index_calculator.load_weights()  # 不需要项目路径
        weight_values = weights.get(weight_name, {})
        
        # 更新输入框
        for trait, input_widget in self.trait_inputs.items():
            input_widget.setValue(weight_values.get(trait, 0))
            
        # 启用/禁用按钮
        is_system_weight = weight_name in ['NM$权重', 'TPI权重']
        self.delete_weight_btn.setEnabled(not is_system_weight)
        self.cow_index_btn.setEnabled(True)
        self.bull_index_btn.setEnabled(True)

    def save_new_weight(self):
        """保存新权重配置"""
        # 权重保存不需要项目路径，删除相关检查
        # 获取权重名称
        name, ok = QInputDialog.getText(
            self, "新建权重", "请输入权重配置名称："
        )
        if not ok or not name:
            return
            
        if name in ['NM$权重', 'TPI权重']:
            QMessageBox.warning(self, "警告", "不能使用系统预设权重名称")
            return

        # 收集权重值
        weight_values = {}
        for trait, input_widget in self.trait_inputs.items():
            value = input_widget.value()
            if value != 0:  # 只保存非零权重
                weight_values[trait] = value

        # 保存权重
        if self.index_calculator.save_custom_weight(name, weight_values):
            self.update_weight_list()
            QMessageBox.information(self, "成功", "权重配置已保存")
        else:
            QMessageBox.warning(self, "错误", "保存权重配置失败")

    def delete_weight(self):
            """删除当前选中的权重配置"""
            if not self.current_weight_name:
                return
                
            if self.current_weight_name in ['NM$权重', 'TPI权重']:
                QMessageBox.warning(self, "警告", "不能删除系统预设权重")
                return

            reply = QMessageBox.question(
                self,
                "确认删除",
                f"确定要删除权重配置'{self.current_weight_name}'吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                if self.index_calculator.delete_custom_weight(self.current_weight_name):
                    self.update_weight_list()
                    self.current_weight_name = None
                    self.delete_weight_btn.setEnabled(False)
                    self.cow_index_btn.setEnabled(False)
                    self.bull_index_btn.setEnabled(False)
                    QMessageBox.information(self, "成功", "权重配置已删除")
                else:
                    QMessageBox.warning(self, "错误", "删除权重配置失败")

    def calculate_cow_index(self):
        """计算母牛群指数排名"""
        if not self.current_weight_name:
            QMessageBox.warning(self, "警告", "请先选择一个权重配置")
            return

        main_window = self.get_main_window()
        if not main_window or not main_window.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return

        # 创建进度对话框
        self.progress_dialog = ProgressDialog(self)
        self.progress_dialog.setWindowTitle("母牛群指数计算进度")
        self.progress_dialog.set_task_info("正在计算母牛群指数排名...")
        self.progress_dialog.show()

        try:
            # 定义进度回调函数
            def progress_callback(progress_value, message=None):
                if progress_value is not None:
                    self.progress_dialog.update_progress(progress_value)
                if message is not None:
                    self.progress_dialog.update_info(message)

            def task_info_callback(task_info):
                self.progress_dialog.set_task_info(task_info)

            success, message = self.index_calculator.process_cow_index(
                main_window, self.current_weight_name,
                progress_callback=progress_callback,
                task_info_callback=task_info_callback
            )

            self.progress_dialog.close()

            if success:
                QMessageBox.information(self, "完成", "母牛群指数计算完成！")
            else:
                QMessageBox.warning(self, "错误", f"计算失败：{message}")

        except Exception as e:
            self.progress_dialog.close()
            QMessageBox.critical(self, "错误", f"计算过程中发生错误：{str(e)}")
        finally:
            if hasattr(self, 'progress_dialog'):
                self.progress_dialog.close()

    def calculate_bull_index(self):
        """计算备选公牛指数排名"""
        if not self.current_weight_name:
            QMessageBox.warning(self, "警告", "请先选择一个权重配置")
            return

        main_window = self.get_main_window()
        if not main_window or not main_window.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return

        # 创建进度对话框
        self.progress_dialog = ProgressDialog(self)
        self.progress_dialog.setWindowTitle("备选公牛指数计算进度")
        self.progress_dialog.set_task_info("正在计算备选公牛指数排名...")
        self.progress_dialog.show()

        try:
            # 定义进度回调函数
            def progress_callback(progress_value, message=None):
                if progress_value is not None:
                    self.progress_dialog.update_progress(progress_value)
                if message is not None:
                    self.progress_dialog.update_info(message)

            def task_info_callback(task_info):
                self.progress_dialog.set_task_info(task_info)

            success, message = self.index_calculator.process_bull_index(
                main_window, self.current_weight_name,
                progress_callback=progress_callback,
                task_info_callback=task_info_callback
            )

            self.progress_dialog.close()

            if success:
                QMessageBox.information(self, "完成", "备选公牛指数计算完成！")
            else:
                QMessageBox.warning(self, "错误", f"计算失败：{message}")

        except Exception as e:
            self.progress_dialog.close()
            QMessageBox.critical(self, "错误", f"计算过程中发生错误：{str(e)}")
        finally:
            if hasattr(self, 'progress_dialog'):
                self.progress_dialog.close()