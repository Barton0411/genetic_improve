# core/breeding_calc/cow_traits_calc.py
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, 
    QListWidget, QListWidgetItem, QAbstractItemView, QMessageBox    # 添加 QListWidgetItem
)
from PyQt6.QtCore import Qt, QThread  # 修改这行，添加 QThread
import pandas as pd
# Removed sqlalchemy dependency
import datetime
from core.breeding_calc.traits_calculation import TraitsCalculation
from core.data.update_manager import LOCAL_DB_PATH
from PyQt6.QtWidgets import QMainWindow  # 添加这行
import numpy as np
from pathlib import Path
from sklearn.linear_model import LinearRegression

from gui.progress import ProgressDialog
from gui.worker import TraitsCalculationWorker
from PyQt6.QtWidgets import QMainWindow
import time
import datetime
from PyQt6.QtCore import QThread, QObject, pyqtSignal, pyqtSlot
from gui.progress import ProgressDialog
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, 
    QListWidget, QListWidgetItem, QAbstractItemView, QMessageBox, QMainWindow  # 添加 QMainWindow
)


# 添加性状翻译字典
TRAITS_TRANSLATION = {
    'TPI': '育种综合指数', 'NM$': '净利润值', 'CM$': '奶酪净值', 'FM$': '液奶净值', 'GM$': '放牧净值',
    'MILK': '产奶量', 'FAT': '乳脂量', 'PROT': '乳蛋白量', 'FAT %': '乳脂率', 'PROT%': '乳蛋白率',
    'SCS': '体细胞指数', 'DPR': '女儿怀孕率', 'HCR': '青年牛受胎率', 'CCR': '成母牛受胎率', 'PL': '生产寿命',
    'SCE': '配种产犊难易度', 'DCE': '女儿产犊难易度', 'SSB': '配种死胎率', 'DSB': '女儿死淘率',
    'PTAT': '体型综合指数', 'UDC': '乳房综合指数', 'FLC': '肢蹄综合指数', 'BDC': '体重综合指数',
    'ST': '体高', 'SG': '强壮度', 'BD': '体深', 'DF': '乳用特征', 'RA': '尻角度', 'RW': '尻宽',
    'LS': '后肢侧视', 'LR': '后肢后视', 'FA': '蹄角度', 'FLS': '肢蹄评分', 'FU': '前方附着',
    'UH': '后房高度', 'UW': '后方宽度', 'UC': '悬韧带', 'UD': '乳房深度', 'FT': '前乳头位置',
    'RT': '后乳头位置', 'TL': '乳头长度', 'FE': '饲料效率指数', 'FI': '繁殖力指数', 'HI': '健康指数',
    'LIV': '存活率', 'GL': '妊娠长度', 'MAST': '乳房炎抗病性', 'MET': '子宫炎抗病性', 'RP': '胎衣不下抗病性',
    'KET': '酮病抗病性', 'DA': '变胃抗病性', 'MFV': '产后瘫抗病性', 'EFC': '首次产犊月龄',
    'HLiv': '后备牛存活率', 'FS': '饲料节约指数', 'RFI': '剩余饲料采食量', 'Milk Speed': '排乳速度','SCR':'配种受胎率',
    'Eval Date': '数据日期',
    'BULL NAAB':'公牛 NAAB',
    'BULL REG':'公牛 REG',
    'MMGS REG':'外曾外祖父 REG',    
    'SIRE REG':'父亲 REG',
    'MGS REG':'外祖父 REG',
    'GIB':'个体近交指数-G',
    'MW':'早发肌无力',
    'HH1':'荷斯坦繁殖缺陷1型',
    'HH2':'荷斯坦繁殖缺陷2型',
    'HH3':'荷斯坦繁殖缺陷3型',
    'HH4':'荷斯坦繁殖缺陷4型',
    'HH5':'荷斯坦繁殖缺陷5型',
    'HH6':'荷斯坦繁殖缺陷6型',
    'HMW':'早发肌无力-单倍型',
    'BLAD':'牛白细胞粘附缺陷病',
    'Chondrodysplasia':'软骨发育异常',
    'Citrullinemia':'瓜氨酸血症',
    'DUMPS':'尿苷单磷酸合成酶缺乏',
    'Factor XI':'凝血因子 XI缺乏',
    'CVM':'犊牛脊椎畸形综合征',
    'Brachyspina':'短脊椎综合症征',
    'Mulefoot':'单趾畸形',
    'Cholesterol deficiency Deficiency Carrier':'胆固醇缺乏症携带者',
    'Beta Casein A/B':'β酪蛋白 A/B',
    'Beta Lactoglobulin':'β乳球蛋白',
    'Beta Casein A2':'β酪蛋白A2',
    'Kappa Casein I (ABE)':'卡帕酪蛋白I',
    'GM$':'放牧净价值',
    'Name':'牛短名',
    'Reg Name':'注册名',
    'Haplo Types':'单倍型',
    'RCC':'隐性遗传缺陷携带者',
    'Cholesterol deficiency':'胆固醇缺乏症',
    'Upload Date':'数据上传日期',
    'Recessives':'隐性基因'






    
}

class CowKeyTraitsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 注释掉或删除这一行，因为我们会在每次计算时重新创建
        # self.traits_calculator = TraitsCalculation()   # <-- 删除这一行
        
        self.default_traits = [
            'NM$', 'TPI', 'MILK', 'FAT', 'FAT %', 'PROT', 'PROT%', 
            'SCS', 'PL', 'DPR', 'PTAT', 'UDC', 'FLC', 'RFI'
        ]
        
        self.all_traits = [
            'TPI', 'NM$', 'CM$', 'FM$', 'GM$', 'MILK', 'FAT', 'PROT', 
            'FAT %', 'PROT%', 'SCS', 'DPR', 'HCR', 'CCR', 'SCR','PL', 'SCE', 
            'DCE', 'SSB', 'DSB', 'PTAT', 'UDC', 'FLC', 'BDC', 'ST', 'SG', 
            'BD', 'DF', 'RA', 'RW', 'LS', 'LR', 'FA', 'FLS', 'FU', 'UH', 
            'UW', 'UC', 'UD', 'FT', 'RT', 'TL', 'FE', 'FI', 'HI', 'LIV', 
            'GL', 'MAST', 'MET', 'RP', 'KET', 'DA', 'MFV', 'EFC', 'HLiv', 
            'FS', 'RFI', 'Milk Speed'
        ]
        
        self.required_trait = 'NM$'
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        
        # 左侧：全部性状列表
        left_layout = QVBoxLayout()
        left_label = QLabel("全部性状")
        self.all_traits_list = QListWidget()

        # 修改添加性状的方式，显示中英文
        for trait in self.all_traits:
            item = QListWidgetItem(f"{trait} - {TRAITS_TRANSLATION[trait]}")
            # 存储英文性状名称作为数据
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
        confirm_button = QPushButton("确认")  # 添加确认按钮
        confirm_button.clicked.connect(self.start_cow_traits_calculation)  # 添加点击事件处理
        
        button_layout.addStretch()
        button_layout.addWidget(add_button)
        button_layout.addWidget(remove_button)
        button_layout.addWidget(select_all_button)
        button_layout.addWidget(reset_button)
        button_layout.addWidget(confirm_button)  # 添加确认按钮到布局
        button_layout.addStretch()
        layout.addLayout(button_layout)

        # 右侧：已选择性状列表
        right_layout = QVBoxLayout()
        right_label = QLabel("已选择性状\n（可拖拽调整顺序）")
        self.selected_traits_list = QListWidget()

        # 修改添加默认性状的方式，显示中英文
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
            trait = item.data(Qt.ItemDataRole.UserRole)
            if trait != self.required_trait:
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

    # 在 CowKeyTraitsPage 类中添加新的方法

    def start_cow_traits_calculation(self):
        """开始关键性状计算流程"""
        # 获取主窗口实例
        main_window = self.get_main_window()
        if not main_window:
            QMessageBox.warning(self, "警告", "无法获取主窗口")
            return
        
        if not hasattr(main_window, 'selected_project_path') or not main_window.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return

        try:
            # 每次计算前创建新的计算器实例
            self.traits_calculator = TraitsCalculation() 
            # 创建进度对话框
            self.progress_dialog = ProgressDialog(self)
            self.progress_dialog.show()

            # 获取选中的性状列表
            selected_traits = self.get_selected_traits()
            
            # 定义进度回调函数，能接收进度值和消息
            def progress_callback(progress_value, message=None):
                print(f"[DEBUG-COW-CALLBACK] 收到回调: progress={progress_value}, message={message}")  # 添加调试输出
                if progress_value is not None:
                    print(f"[DEBUG-COW-CALLBACK] 更新进度条: {progress_value}")
                    self.progress_dialog.update_progress(progress_value)
                if message is not None:
                    print(f"[DEBUG-COW-CALLBACK] 更新信息: {message}")
                    self.progress_dialog.update_info(message)
            
            # 先测试回调函数是否工作
            print("[DEBUG-COW-CALLBACK] 测试回调函数...")
            progress_callback(10, "测试消息：母牛性状计算回调函数工作正常")
            
            # 执行计算
            success, message = self.traits_calculator.process_data(
                main_window, 
                selected_traits,
                progress_callback=progress_callback
            )

            if success:
                self.progress_dialog.close()
                QMessageBox.information(self, "完成", "关键性状计算完成！")
            else:
                self.progress_dialog.close()
                QMessageBox.critical(self, "错误", f"计算过程中发生错误：{message}")

        except Exception as e:
            self.progress_dialog.close()
            import traceback
            error_msg = f"计算过程中发生错误：{str(e)}"
            if "处理年度数据失败" in str(e):
                error_msg = "计算过程中发生错误：\n处理年度数据失败\n\n可能原因：\n1. 数据中缺少有效的出生年份信息\n2. 出生年份数据格式不正确\n3. 数据文件损坏或格式异常\n\n建议检查上传的母牛数据文件"
            QMessageBox.critical(self, "错误", error_msg)
            print(f"详细错误信息: {traceback.format_exc()}")
        finally:
                # 添加资源清理代码
                if hasattr(self, 'progress_dialog'):
                    self.progress_dialog.close()
                if hasattr(self.traits_calculator, 'engine'):
                    self.traits_calculator.engine.dispose()  # <-- 添加这一行


    def perform_cow_traits_calculation(self, main_window, progress_callback=None, task_info_callback=None):
        """执行关键性状计算的核心逻辑"""
        try:
            # 创建进度对话框
            progress_dialog = ProgressDialog(self)
            progress_dialog.setWindowTitle("关键性状计算进度")
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
                    # 如果有外部回调，也调用它
                    if progress_callback:
                        try:
                            progress_callback(progress_value, message)
                        except TypeError:
                            # 向后兼容：如果外部回调只接受一个参数
                            progress_callback(progress_value)
                if message is not None:
                    progress_dialog.update_info(message)
                
            def update_task_info(task_info):
                progress_dialog.set_task_info(task_info)
                if task_info_callback:
                    task_info_callback(task_info)
                
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

    def on_calculation_finished(self):
        """计算完成的处理"""
        self.progress_dialog.close()
        QMessageBox.information(self, "完成", "关键性状计算流程已完成")

    def on_calculation_error(self, error_message):
        """计算错误的处理"""
        self.progress_dialog.close()
        QMessageBox.critical(self, "错误", f"处理过程中发生错误：{error_message}")

    def get_main_window(self):
        """获取主窗口实例"""
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        return parent