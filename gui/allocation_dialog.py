"""
选配分配对话框
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QTableWidget, QTableWidgetItem, QMessageBox,
                             QProgressBar, QGroupBox, QCheckBox, QHeaderView)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from pathlib import Path
import pandas as pd
import logging

from core.matching.cycle_based_matcher import CycleBasedMatcher

logger = logging.getLogger(__name__)

class AllocationWorker(QThread):
    """分配工作线程"""
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    
    def __init__(self, matcher, selected_groups):
        super().__init__()
        self.matcher = matcher
        self.selected_groups = selected_groups
        
    def run(self):
        try:
            result = self.matcher.perform_allocation(
                self.selected_groups,
                lambda msg, prog: self.progress.emit(msg, prog)
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class AllocationDialog(QDialog):
    """选配分配对话框"""
    
    def __init__(self, parent=None, project_path=None):
        super().__init__(parent)
        self.project_path = project_path
        self.matcher = CycleBasedMatcher()
        self.result_df = None
        
        self.init_ui()
        self.load_data()
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("选配分配")
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # 1. 库存信息区
        inventory_group = QGroupBox("冻精库存信息")
        inventory_layout = QVBoxLayout(inventory_group)
        
        self.inventory_label = QLabel("正在加载库存信息...")
        inventory_layout.addWidget(self.inventory_label)
        
        self.inventory_table = QTableWidget()
        self.inventory_table.setMaximumHeight(200)
        inventory_layout.addWidget(self.inventory_table)
        
        layout.addWidget(inventory_group)
        
        # 2. 分组选择区
        group_group = QGroupBox("选择要分配的分组")
        group_layout = QVBoxLayout(group_group)
        
        self.group_table = QTableWidget()
        self.group_table.setMaximumHeight(200)
        group_layout.addWidget(self.group_table)
        
        # 全选/取消按钮
        btn_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("全选周期组")
        self.select_all_btn.clicked.connect(self.select_all_cycles)
        self.clear_btn = QPushButton("清除选择")
        self.clear_btn.clicked.connect(self.clear_selection)
        btn_layout.addWidget(self.select_all_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        group_layout.addLayout(btn_layout)
        
        layout.addWidget(group_group)
        
        # 3. 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 4. 状态信息
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # 5. 按钮区
        button_layout = QHBoxLayout()
        
        self.allocate_btn = QPushButton("开始分配")
        self.allocate_btn.clicked.connect(self.start_allocation)
        
        self.save_btn = QPushButton("保存结果")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_results)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.allocate_btn)
        button_layout.addWidget(self.save_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
    def load_data(self):
        """加载数据"""
        if not self.project_path:
            self.status_label.setText("错误：未指定项目路径")
            return
            
        # 加载推荐数据
        recommendations_file = self.project_path / "analysis_results" / "individual_mating_report.xlsx"
        if not recommendations_file.exists():
            self.status_label.setText("错误：未找到选配推荐报告，请先生成推荐")
            self.allocate_btn.setEnabled(False)
            return
            
        try:
            recommendations_df = pd.read_excel(recommendations_file)
            
            # 加载公牛数据
            bull_data_path = self.project_path / "standardized_data" / "processed_bull_data.xlsx"
            if not self.matcher.load_data(recommendations_df, bull_data_path):
                # 检查是否所有库存都是0
                if self.matcher.check_zero_inventory():
                    QMessageBox.warning(
                        self,
                        "库存为空",
                        "所有公牛的冻精库存都为0。\n\n"
                        "请先在「冻精预览」表中设置各公牛的库存数量，\n"
                        "然后再进行分配。"
                    )
                    self.allocate_btn.setEnabled(False)
                    
            # 显示库存信息
            self.show_inventory()
            
            # 显示分组信息
            self.show_groups(recommendations_df)
            
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            self.status_label.setText(f"加载数据失败: {str(e)}")
            self.allocate_btn.setEnabled(False)
            
    def show_inventory(self):
        """显示库存信息"""
        inventory_df = self.matcher.get_inventory_summary()
        
        # 统计信息
        total_regular = inventory_df[inventory_df['冻精类型'] == '常规']['当前库存'].sum()
        total_sexed = inventory_df[inventory_df['冻精类型'] == '性控']['当前库存'].sum()
        
        self.inventory_label.setText(
            f"常规冻精总库存: {total_regular} 支，性控冻精总库存: {total_sexed} 支"
        )
        
        # 显示详细表格
        self.inventory_table.setRowCount(len(inventory_df))
        self.inventory_table.setColumnCount(3)
        self.inventory_table.setHorizontalHeaderLabels(['公牛号', '类型', '库存'])
        
        for i, row in inventory_df.iterrows():
            self.inventory_table.setItem(i, 0, QTableWidgetItem(row['公牛号']))
            self.inventory_table.setItem(i, 1, QTableWidgetItem(row['冻精类型']))
            self.inventory_table.setItem(i, 2, QTableWidgetItem(str(row['当前库存'])))
            
        self.inventory_table.resizeColumnsToContents()
        
    def show_groups(self, recommendations_df):
        """显示分组信息"""
        # 统计各分组数量
        groups = recommendations_df['group'].value_counts()
        
        self.group_table.setRowCount(len(groups))
        self.group_table.setColumnCount(3)
        self.group_table.setHorizontalHeaderLabels(['选择', '分组名称', '母牛数量'])
        
        self.group_checkboxes = []
        
        for i, (group_name, count) in enumerate(groups.items()):
            # 复选框
            checkbox = QCheckBox()
            # 默认选中周期组
            if isinstance(group_name, str) and '周期' in group_name:
                checkbox.setChecked(True)
            self.group_checkboxes.append((checkbox, group_name))
            
            # 添加到表格
            self.group_table.setCellWidget(i, 0, checkbox)
            self.group_table.setItem(i, 1, QTableWidgetItem(str(group_name)))
            self.group_table.setItem(i, 2, QTableWidgetItem(str(count)))
            
        self.group_table.resizeColumnsToContents()
        
    def select_all_cycles(self):
        """选中所有周期组"""
        for checkbox, group_name in self.group_checkboxes:
            if isinstance(group_name, str) and '周期' in group_name:
                checkbox.setChecked(True)
                
    def clear_selection(self):
        """清除所有选择"""
        for checkbox, _ in self.group_checkboxes:
            checkbox.setChecked(False)
            
    def get_selected_groups(self):
        """获取选中的分组"""
        selected = []
        for checkbox, group_name in self.group_checkboxes:
            if checkbox.isChecked():
                selected.append(group_name)
        return selected
        
    def start_allocation(self):
        """开始分配"""
        selected_groups = self.get_selected_groups()
        
        if not selected_groups:
            QMessageBox.warning(self, "警告", "请至少选择一个分组")
            return
            
        # 再次检查库存
        if self.matcher.check_zero_inventory():
            QMessageBox.warning(
                self,
                "库存为空",
                "所有公牛的冻精库存都为0。\n\n"
                "请先在「冻精预览」表中设置各公牛的库存数量。"
            )
            return
            
        # 确认分配
        reply = QMessageBox.question(
            self,
            "确认分配",
            f"将要为 {len(selected_groups)} 个分组进行选配分配。\n\n"
            "分配将按照以下规则进行：\n"
            "- 1选：严格按照库存比例分配\n"
            "- 2选、3选：在有库存的公牛中平均分配\n"
            "- 优先级：周期数小的优先\n\n"
            "是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
            
        # 禁用按钮
        self.allocate_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 创建工作线程
        self.worker = AllocationWorker(self.matcher, selected_groups)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.allocation_finished)
        self.worker.error.connect(self.allocation_error)
        self.worker.start()
        
    def update_progress(self, message, progress):
        """更新进度"""
        self.status_label.setText(message)
        self.progress_bar.setValue(progress)
        
    def allocation_finished(self, result_df):
        """分配完成"""
        self.result_df = result_df
        self.progress_bar.setVisible(False)
        self.allocate_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        
        # 显示结果摘要
        if not result_df.empty:
            summary = self.matcher.get_allocation_summary()
            
            # 显示使用情况
            used_regular = summary[summary['冻精类型'] == '常规']['已使用'].sum()
            used_sexed = summary[summary['冻精类型'] == '性控']['已使用'].sum()
            
            QMessageBox.information(
                self,
                "分配完成",
                f"分配已完成！\n\n"
                f"共分配 {len(result_df)} 头母牛\n"
                f"使用常规冻精: {used_regular} 支\n"
                f"使用性控冻精: {used_sexed} 支\n\n"
                f"请点击「保存结果」保存分配方案。"
            )
            
            # 更新库存显示
            self.show_inventory()
        else:
            QMessageBox.warning(self, "分配失败", "未能成功分配任何母牛")
            
    def allocation_error(self, error_msg):
        """分配出错"""
        self.progress_bar.setVisible(False)
        self.allocate_btn.setEnabled(True)
        QMessageBox.critical(self, "分配错误", f"分配过程中出现错误：\n{error_msg}")
        
    def save_results(self):
        """保存结果"""
        if self.result_df is None or self.result_df.empty:
            return
            
        try:
            output_file = self.project_path / "analysis_results" / "individual_allocation_result.xlsx"
            self.matcher.save_allocation_result(self.result_df, output_file)
            
            # 保存汇总
            summary_file = self.project_path / "analysis_results" / "allocation_summary.xlsx"
            summary_df = self.matcher.get_allocation_summary()
            summary_df.to_excel(summary_file, index=False)
            
            QMessageBox.information(
                self,
                "保存成功",
                f"分配结果已保存至：\n"
                f"- {output_file.name}\n"
                f"- {summary_file.name}"
            )
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存文件时出错：\n{str(e)}")