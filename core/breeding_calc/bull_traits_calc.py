from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, 
    QListWidget, QListWidgetItem, QAbstractItemView, QMessageBox,
    QMainWindow
)
from PyQt6.QtCore import Qt
import pandas as pd
from sqlalchemy import create_engine, text
import datetime
from core.breeding_calc.traits_calculation import TraitsCalculation
from core.data.update_manager import LOCAL_DB_PATH

# 复用已有的性状翻译字典
from core.breeding_calc.cow_traits_calc import TRAITS_TRANSLATION

class BullKeyTraitsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化默认性状列表
        self.default_traits = [
            'NM$', 'TPI', 'MILK', 'FAT', 'FAT %', 'PROT', 'PROT%', 
            'SCS', 'PL', 'DPR', 'PTAT', 'UDC', 'FLC', 'RFI', 'Eval Date'
        ]
        
        # 初始化所有可用性状列表
        self.all_traits = [
            'TPI', 'NM$', 'CM$', 'FM$', 'GM$', 'MILK', 'FAT', 'PROT', 
            'FAT %', 'PROT%', 'SCS', 'DPR', 'HCR', 'CCR', 'SCR','PL', 'SCE', 
            'DCE', 'SSB', 'DSB', 'PTAT', 'UDC', 'FLC', 'BDC', 'ST', 'SG', 
            'BD', 'DF', 'RA', 'RW', 'LS', 'LR', 'FA', 'FLS', 'FU', 'UH', 
            'UW', 'UC', 'UD', 'FT', 'RT', 'TL', 'FE', 'FI', 'HI', 'LIV', 
            'GL', 'MAST', 'MET', 'RP', 'KET', 'DA', 'MFV', 'EFC', 'HLiv', 
            'FS', 'RFI', 'Milk Speed', 'Eval Date'
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
        add_button = QPushButton("添加 >>")
        add_button.clicked.connect(self.add_trait)
        remove_button = QPushButton("<< 移除")
        remove_button.clicked.connect(self.remove_trait)
        select_all_button = QPushButton("全选")
        select_all_button.clicked.connect(self.select_all_traits)
        reset_button = QPushButton("恢复默认")
        reset_button.clicked.connect(self.reset_traits)
        confirm_button = QPushButton("确认")
        confirm_button.clicked.connect(self.start_bull_traits_calculation)
        
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


    def start_bull_traits_calculation(self):
        """开始公牛关键性状计算流程"""
        # 获取主窗口实例
        main_window = self.get_main_window()
        if not main_window:
            QMessageBox.warning(self, "警告", "无法获取主窗口")
            return
            
        if not main_window.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return

        try:
            # 检查备选公牛数据文件是否存在
            bull_data_path = main_window.selected_project_path / "standardized_data" / "processed_bull_data.xlsx"
            if not bull_data_path.exists():
                QMessageBox.warning(self, "警告", "未找到备选公牛数据文件，请先上传并处理备选公牛数据")
                return

            # 读取备选公牛数据
            try:
                bull_df = pd.read_excel(bull_data_path)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"读取备选公牛数据文件失败：{str(e)}")
                return

            # 获取选中的性状列表
            selected_traits = self.get_selected_traits()
            if not selected_traits:
                QMessageBox.warning(self, "警告", "请至少选择一个性状")
                return

            # 连接本地数据库
            try:
                engine = create_engine(f'sqlite:///{LOCAL_DB_PATH}')
            except Exception as e:
                QMessageBox.critical(self, "错误", f"连接本地数据库失败：{str(e)}")
                return

            # 处理每个公牛的性状数据
            missing_bulls = []
            trait_data = []

            for idx, row in bull_df.iterrows():
                bull_id = str(row['bull_id'])
                if pd.isna(bull_id) or bull_id.strip() == '':
                    continue

                try:
                    with engine.connect() as conn:
                        # 先尝试用 BULL NAAB 查询
                        result = conn.execute(
                            text("SELECT * FROM bull_library WHERE `BULL NAAB`=:bull_id"),
                            {"bull_id": bull_id}
                        ).fetchone()
                        
                        if not result:
                            # 如果找不到，再尝试用 BULL REG 查询
                            result = conn.execute(
                                text("SELECT * FROM bull_library WHERE `BULL REG`=:bull_id"),
                                {"bull_id": bull_id}
                            ).fetchone()

                        if result:
                            # 提取性状数据
                            bull_data = dict(row)  # 保留原始数据
                            result_dict = dict(result._mapping)
                            for trait in selected_traits:
                                bull_data[trait] = result_dict.get(trait)
                            trait_data.append(bull_data)
                        else:
                            missing_bulls.append(bull_id)
                            # 对于缺失的公牛，保留原始数据，性状值设为空
                            bull_data = dict(row)
                            for trait in selected_traits:
                                bull_data[trait] = None
                            trait_data.append(bull_data)
                            
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"查询公牛 {bull_id} 的性状数据时发生错误：{str(e)}")
                    return

            # 如果有缺失的公牛，上传到云端数据库并提示用户
            if missing_bulls:
                try:
                    # 通过API上传缺失公牛信息
                    from api.api_client import get_api_client
                    api_client = get_api_client()

                    username = main_window.username if hasattr(main_window, 'username') else 'unknown'

                    # 准备上传数据
                    bulls_data = []
                    for bull_id in missing_bulls:
                        bulls_data.append({
                            'bull': bull_id,
                            'source': 'bull_key_traits',
                            'time': datetime.datetime.now().isoformat(),
                            'user': username
                        })

                    # 调用API上传
                    success = api_client.upload_missing_bulls(bulls_data)

                    if success:
                        # 提示用户
                        QMessageBox.warning(
                            self,
                            "警告",
                            f"以下公牛在数据库中未找到：\n{', '.join(missing_bulls)}\n"
                            "这些信息已记录到云端数据库。\n"
                            "结果文件中这些公牛的性状值将显示为空。"
                        )
                    else:
                        raise Exception("API上传失败")

                except Exception as e:
                    QMessageBox.warning(
                        self,
                        "警告",
                        f"上传缺失公牛信息时发生错误：{str(e)}\n"
                        f"缺失的公牛：{', '.join(missing_bulls)}"
                    )

            # 生成结果DataFrame
            result_df = pd.DataFrame(trait_data)

            # 保存结果文件
            output_path = main_window.selected_project_path / "analysis_results" / "processed_bull_data_key_traits.xlsx"
            while True:
                try:
                    result_df.to_excel(output_path, index=False)
                    QMessageBox.information(self, "成功", "公牛关键性状计算完成！")
                    break
                except PermissionError:
                    reply = QMessageBox.question(
                        self,
                        "文件被占用",
                        f"文件 {output_path.name} 正在被其他程序使用。\n"
                        "请关闭该文件后点击'重试'继续，或点击'取消'停止操作。",
                        QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel
                    )
                    if reply == QMessageBox.StandardButton.Cancel:
                        return
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"保存结果文件时发生错误：{str(e)}")
                    return

        except Exception as e:
            QMessageBox.critical(self, "错误", f"计算过程中发生错误：{str(e)}")
            return

    def get_main_window(self):
        """获取主窗口实例"""
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        return parent

    def perform_bull_traits_calculation(self, main_window):
        """执行公牛关键性状计算"""
        try:
            # 创建进度对话框
            from gui.progress import ProgressDialog
            progress_dialog = ProgressDialog(self)
            progress_dialog.setWindowTitle("公牛关键性状计算进度")
            progress_dialog.show()

            # 获取选中的性状
            selected_traits = self.get_selected_traits()
            if not selected_traits:
                progress_dialog.close()
                return False, "请至少选择一个性状"

            # 创建计算实例
            traits_calculator = TraitsCalculation()
            
            def update_progress(progress_value, message=None):
                """更新进度，能接收进度值和消息两个参数"""
                if progress_value is not None:
                    progress_dialog.update_progress(progress_value)
                if message is not None:
                    progress_dialog.update_info(message)
                
            def update_task_info(task_info):
                progress_dialog.set_task_info(task_info)
                
            # 执行计算
            success, message = traits_calculator.process_data(
                main_window, 
                selected_traits,
                progress_callback=update_progress,
                task_info_callback=update_task_info
            )
            
            # 关闭进度对话框
            progress_dialog.close()
            
            if progress_dialog.cancelled:
                return False, "用户取消了操作"
                
            return success, message

        except Exception as e:
            if 'progress_dialog' in locals():
                progress_dialog.close()
            return False, str(e)