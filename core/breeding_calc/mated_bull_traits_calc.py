# core/breeding_calc/mated_bull_traits_calc.py
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, 
    QListWidget, QListWidgetItem, QAbstractItemView, QMessageBox,
    QMainWindow
)
from PyQt6.QtCore import Qt
import pandas as pd
import sqlite3
from core.data.update_manager import LOCAL_DB_PATH
from core.breeding_calc.cow_traits_calc import TRAITS_TRANSLATION
from gui.progress import ProgressDialog

class MatedBullKeyTraitsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化默认性状列表
        self.default_traits = [
            'NM$', 'TPI', 'MILK', 'FAT', 'FAT %', 'PROT', 'PROT%', 
            'SCS', 'PL', 'DPR', 'PTAT', 'UDC', 'FLC', 'RFI', 'FS', 'Eval Date'
        ]
        
        # 初始化所有可用性状列表
        self.all_traits = [
            'TPI', 'NM$', 'CM$', 'FM$', 'GM$', 'MILK', 'FAT', 'PROT', 
            'FAT %', 'PROT%', 'SCS', 'DPR', 'HCR', 'CCR', 'PL', 'SCE', 
            'DCE', 'SSB', 'DSB', 'PTAT', 'UDC', 'FLC', 'BDC', 'ST', 'SG', 
            'BD', 'DF', 'RA', 'RW', 'LS', 'LR', 'FA', 'FLS', 'FU', 'UH', 
            'UW', 'UC', 'UD', 'FT', 'RT', 'TL', 'FE', 'FI', 'HI', 'LIV', 
            'GL', 'MAST', 'MET', 'RP', 'KET', 'DA', 'MFV', 'EFC', 'HLiv', 
            'FS', 'RFI', 'Milk Speed', 'Eval Date', 'SCR', 'BULL NAAB',
            'BULL REG',
            'MMGS REG',
            'SIRE REG',
            'MGS REG',
            'GIB',
            'MW',
            'HH1',
            'HH2',
            'HH3',
            'HH4',
            'HH5',
            'HH6',
            'HMW',
            'BLAD',
            'Chondrodysplasia',
            'Citrullinemia',
            'DUMPS',
            'Factor XI',
            'CVM',
            'Brachyspina',
            'Mulefoot',
            'Cholesterol deficiency Deficiency Carrier',
            'Beta Casein A/B',
            'Beta Lactoglobulin',
            'Beta Casein A2',
            'Kappa Casein I (ABE)',
            'GM$',
            'Name',
            'Reg Name',
            'Haplo Types',
            'RCC',
            'Cholesterol deficiency',
            # 'Upload Date',
            'Recessives'

        ]
        
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        
        # 左侧：全部性状列表
        left_layout = QVBoxLayout()
        left_label = QLabel("全部性状")
        self.all_traits_list = QListWidget()

        # 添加性状，显示中英文
        for trait in self.all_traits:
            item = QListWidgetItem(f"{trait} - {TRAITS_TRANSLATION[trait]}")
            item.setData(Qt.ItemDataRole.UserRole, trait)
            self.all_traits_list.addItem(item)

        self.all_traits_list.itemDoubleClicked.connect(self.add_trait)
        left_layout.addWidget(left_label)
        left_layout.addWidget(self.all_traits_list)
        layout.addLayout(left_layout)

        # 中间：按钮区域
        button_layout = QVBoxLayout()

        # 定义按钮样式
        button_style = """
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
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """

        add_button = QPushButton("添加 >>")
        add_button.setStyleSheet(button_style)
        add_button.clicked.connect(self.add_trait)

        remove_button = QPushButton("<< 移除")
        remove_button.setStyleSheet(button_style)
        remove_button.clicked.connect(self.remove_trait)

        select_all_button = QPushButton("全选")
        select_all_button.setStyleSheet(button_style)
        select_all_button.clicked.connect(self.select_all_traits)

        reset_button = QPushButton("恢复默认")
        reset_button.setStyleSheet(button_style)
        reset_button.clicked.connect(self.reset_traits)

        confirm_button = QPushButton("确认")
        confirm_button.setStyleSheet(button_style)
        confirm_button.clicked.connect(self.start_mated_bull_traits_calculation)
        
        button_layout.addStretch()
        button_layout.addWidget(add_button)
        button_layout.addWidget(remove_button)
        button_layout.addWidget(select_all_button)
        button_layout.addWidget(reset_button)
        button_layout.addWidget(confirm_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        # 右侧：已选择性状列表
        right_layout = QVBoxLayout()
        right_label = QLabel("已选择性状\n（可拖拽调整顺序）")
        self.selected_traits_list = QListWidget()

        # 添加默认性状
        for trait in self.default_traits:
            item = QListWidgetItem(f"{trait} - {TRAITS_TRANSLATION[trait]}")
            item.setData(Qt.ItemDataRole.UserRole, trait)
            self.selected_traits_list.addItem(item)

        self.selected_traits_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.selected_traits_list.itemDoubleClicked.connect(self.remove_trait)
        right_layout.addWidget(right_label)
        right_layout.addWidget(self.selected_traits_list)
        layout.addLayout(right_layout)

        # 设置布局的伸缩因子
        layout.setStretch(0, 2)  # 左侧列表
        layout.setStretch(1, 1)  # 中间按钮区域
        layout.setStretch(2, 2)  # 右侧列表

    def add_trait(self, item=None):
        if not item:
            item = self.all_traits_list.currentItem()
        if item:
            trait = item.data(Qt.ItemDataRole.UserRole)
            if not self.is_trait_selected(trait):
                new_item = QListWidgetItem(f"{trait} - {TRAITS_TRANSLATION[trait]}")
                new_item.setData(Qt.ItemDataRole.UserRole, trait)
                self.selected_traits_list.addItem(new_item)

    def remove_trait(self, item=None):
        if not item:
            item = self.selected_traits_list.currentItem()
        if item:
            self.selected_traits_list.takeItem(self.selected_traits_list.row(item))

    def is_trait_selected(self, trait):
        for i in range(self.selected_traits_list.count()):
            item = self.selected_traits_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == trait:
                return True
        return False

    def select_all_traits(self):
        self.selected_traits_list.clear()
        for trait in self.all_traits:
            item = QListWidgetItem(f"{trait} - {TRAITS_TRANSLATION[trait]}")
            item.setData(Qt.ItemDataRole.UserRole, trait)
            self.selected_traits_list.addItem(item)

    def reset_traits(self):
        self.selected_traits_list.clear()
        for trait in self.default_traits:
            item = QListWidgetItem(f"{trait} - {TRAITS_TRANSLATION[trait]}")
            item.setData(Qt.ItemDataRole.UserRole, trait)
            self.selected_traits_list.addItem(item)

    def get_selected_traits(self):
        return [self.selected_traits_list.item(i).data(Qt.ItemDataRole.UserRole) 
                for i in range(self.selected_traits_list.count())]

    def start_mated_bull_traits_calculation(self):
        """开始已配公牛关键性状计算"""
        # 获取主窗口
        main_window = self.get_main_window()
        if not main_window:
            return

        try:
            # 创建进度对话框
            progress_dialog = ProgressDialog(self)
            progress_dialog.setWindowTitle("已配公牛关键性状计算")
            progress_dialog.show()

            # 1. 读取配种记录
            progress_dialog.set_task_info("读取配种记录")
            progress_dialog.update_progress(10)
            
            breeding_data_path = main_window.selected_project_path / "standardized_data" / "processed_breeding_data.xlsx"
            if not breeding_data_path.exists():
                progress_dialog.close()
                QMessageBox.warning(self, "警告", "未找到已标准化的配种记录")
                return
            
            breeding_df = pd.read_excel(breeding_data_path)
            breeding_df['配种年份'] = pd.to_datetime(breeding_df['配种日期']).dt.year
            print(f"读取到 {len(breeding_df)} 条配种记录")

            # 2. 把配种记录按牛号长度分为两组
            progress_dialog.set_task_info("处理公牛ID")
            progress_dialog.update_progress(20)
            
            short_ids = breeding_df[breeding_df['冻精编号'].str.len() <= 10]['冻精编号'].unique()
            long_ids = breeding_df[breeding_df['冻精编号'].str.len() > 10]['冻精编号'].unique()
            print(f"短ID公牛数量: {len(short_ids)}, 长ID公牛数量: {len(long_ids)}")

            # 3. 从数据库读取性状数据
            progress_dialog.set_task_info("获取公牛性状数据")
            progress_dialog.update_progress(30)
            
            selected_traits = self.get_selected_traits()

            if not selected_traits:
                progress_dialog.close()
                QMessageBox.warning(self, "警告", "请至少选择一个性状")
                return

            # 检查数据库文件是否存在，如果不存在则自动下载
            import os
            if not os.path.exists(LOCAL_DB_PATH):
                progress_dialog.set_task_info("数据库不存在，正在自动下载...")
                progress_dialog.update_progress(15)

                from core.data.bull_library_downloader import ensure_bull_library_exists
                if not ensure_bull_library_exists(LOCAL_DB_PATH):
                    progress_dialog.close()
                    QMessageBox.critical(self, "错误",
                        f"无法自动下载数据库。\n"
                        f"请检查网络连接后重试。")
                    return

                progress_dialog.set_task_info("数据库下载完成")

            # 使用sqlite3直接连接
            conn = sqlite3.connect(LOCAL_DB_PATH)
            try:
                # 检查bull_library表是否存在
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bull_library'")
                if not cursor.fetchone():
                    conn.close()
                    progress_dialog.close()
                    QMessageBox.critical(self, "错误",
                        "数据库中缺少bull_library表。\n"
                        "请点击菜单栏的'数据库更新'来更新数据库。")
                    return

                traits_data = []
                
                # 处理短ID公牛
                if len(short_ids) > 0:
                    progress_dialog.set_task_info("处理短ID公牛")
                    progress_dialog.update_progress(40)
                    
                    # 为每个ID创建参数名
                    param_names = [f':id{i}' for i in range(len(short_ids))]
                    params_dict = {f'id{i}': id_val for i, id_val in enumerate(short_ids)}
                    
                    # 构建查询语句
                    placeholders = ','.join(['?' for _ in short_ids])
                    naab_query = f"""SELECT `BULL NAAB` as bull_id, {
                        ','.join(f'`{trait}`' for trait in selected_traits)
                        } FROM bull_library WHERE `BULL NAAB` IN ({placeholders})"""

                    naab_df = pd.read_sql(naab_query, conn, params=list(short_ids))
                    traits_data.append(naab_df)
                    print(f"获取到 {len(naab_df)} 个短ID公牛的性状数据")
                
                # 处理长ID公牛
                if len(long_ids) > 0:
                    progress_dialog.set_task_info("处理长ID公牛")
                    progress_dialog.update_progress(60)
                    
                    # 为每个ID创建参数名
                    param_names = [f':id{i}' for i in range(len(long_ids))]
                    params_dict = {f'id{i}': id_val for i, id_val in enumerate(long_ids)}
                    
                    # 构建查询语句
                    placeholders = ','.join(['?' for _ in long_ids])
                    reg_query = f"""SELECT `BULL REG` as bull_id, {
                        ','.join(f'`{trait}`' for trait in selected_traits)
                        } FROM bull_library WHERE `BULL REG` IN ({placeholders})"""

                    reg_df = pd.read_sql(reg_query, conn, params=list(long_ids))
                    traits_data.append(reg_df)
                    print(f"获取到 {len(reg_df)} 个长ID公牛的性状数据")

                if traits_data:
                    bull_traits_df = pd.concat(traits_data, ignore_index=True)
                else:
                    bull_traits_df = pd.DataFrame(columns=['bull_id'] + selected_traits)
            finally:
                conn.close()

            # 4. 通过merge一次性关联数据
            progress_dialog.set_task_info("合并数据")
            progress_dialog.update_progress(80)
            
            result_df = pd.merge(
                breeding_df,
                bull_traits_df,
                left_on='冻精编号',
                right_on='bull_id',
                how='left'
            ).drop('bull_id', axis=1)

            # 5. 保存结果
            progress_dialog.set_task_info("保存结果")
            progress_dialog.update_progress(90)
            
            output_path = main_window.selected_project_path / "analysis_results" / "processed_mated_bull_traits.xlsx"
            result_df.to_excel(output_path, index=False)
            
            progress_dialog.update_progress(100)
            progress_dialog.close()
            
            QMessageBox.information(self, "成功", "已配公牛关键性状分析完成！")

        except Exception as e:
            if 'progress_dialog' in locals():
                progress_dialog.close()
            QMessageBox.critical(self, "错误", f"计算过程中发生错误：{str(e)}")

    def get_main_window(self):
        """获取主窗口实例"""
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        return parent