# core/breeding_calc/cow_traits_calc.py
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, 
    QListWidget, QListWidgetItem, QAbstractItemView, QMessageBox    # 添加 QListWidgetItem
)
from PyQt6.QtCore import Qt, QThread  # 修改这行，添加 QThread
import pandas as pd
from sqlalchemy import create_engine, text
import datetime
from core.breeding_calc.traits_calculation import TraitsCalculation
from core.data.update_manager import (
    CLOUD_DB_HOST, CLOUD_DB_PORT, CLOUD_DB_USER, 
    CLOUD_DB_PASSWORD, CLOUD_DB_NAME, LOCAL_DB_PATH
)
from PyQt6.QtWidgets import QMainWindow  # 添加这行
import numpy as np
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
            QMessageBox.critical(self, "错误", f"处理过程中发生错误：{str(e)}")
        finally:
                # 添加资源清理代码
                if hasattr(self, 'progress_dialog'):
                    self.progress_dialog.close()
                if hasattr(self.traits_calculator, 'engine'):
                    self.traits_calculator.engine.dispose()  # <-- 添加这一行


    def process_cow_key_traits_by_year(self, detail_path, progress_callback=None):
        """处理年度关键性状数据"""
        print("开始处理年度关键性状数据...")
        
        try:
            # 1. 读取详细数据文件
            df = pd.read_excel(detail_path)
            
            # 2. 获取出生年份范围
            min_year = df['birth_year'].min()
            max_year = df['birth_year'].max()
            print(f"出生年份范围: {min_year} - {max_year}")

            # 3. 准备所有性状的数据
            results = {}
            
            # 4. 获取默认值（从999HO99999）
            default_values = {}
            engine = create_engine(f'sqlite:///{LOCAL_DB_PATH}')
            with engine.connect() as conn:
                default_bull = conn.execute(
                    text("SELECT * FROM bull_library WHERE `BULL NAAB`='999HO99999'")
                ).fetchone()
                if default_bull:
                    default_bull_dict = dict(default_bull._mapping)
                    for trait in self.get_selected_traits():
                        default_values[trait] = default_bull_dict.get(trait, 0)
                else:
                    print("警告: 未找到默认公牛999HO99999")
                    for trait in self.get_selected_traits():
                        default_values[trait] = 0
                        
            # 5. 处理每个性状
            total_traits = len(self.get_selected_traits())
            for idx, trait in enumerate(self.get_selected_traits(), 1):
                # 更新进度
                if progress_callback:
                    progress = int((idx / total_traits) * 100)
                    progress_callback(progress)
                    
                print(f"处理性状: {trait}")
                trait_col = f'sire_{trait}'
                
                # 5.1 如果性状列不存在，直接使用默认值处理所有年份
                if trait_col not in df.columns:
                    print(f"性状列 {trait_col} 不存在，使用默认值")
                    all_years = pd.DataFrame({'birth_year': range(min_year, max_year + 1)})
                    all_years['mean'] = default_values[trait]
                    all_years['interpolated'] = True
                else:
                    # 原有的计算逻辑
                    yearly_means = df.groupby('birth_year').agg({
                        trait_col: ['count', 'mean']
                    }).reset_index()
                    yearly_means.columns = ['birth_year', 'count', 'mean']
                    
                    # 5.2 筛选数据量>=10的年份
                    valid_years = yearly_means[yearly_means['count'] >= 10]
                    
                    if len(valid_years) > 1:
                        # 有多个有效年份，进行正常回归
                        X = valid_years['birth_year'].values.reshape(-1, 1)
                        y = valid_years['mean'].values
                        reg = LinearRegression().fit(X, y)
                        
                        # 生成所有年份的预测值
                        all_years = pd.DataFrame({'birth_year': range(min_year, max_year + 1)})
                        all_years['mean'] = reg.predict(all_years['birth_year'].values.reshape(-1, 1))
                        all_years['interpolated'] = ~all_years['birth_year'].isin(valid_years['birth_year'])
                        
                    elif len(valid_years) == 1:
                        # 只有一个有效年份
                        valid_year = valid_years['birth_year'].iloc[0]
                        valid_mean = valid_years['mean'].iloc[0]
                        
                        if valid_year == min_year:
                            # 使用最小年份+1的默认值
                            points = {
                                valid_year: valid_mean,
                                valid_year + 1: default_values[trait]
                            }
                            slope = default_values[trait] - valid_mean  # 计算斜率
                        else:
                            # 使用最小年份的默认值
                            points = {
                                min_year: default_values[trait],
                                valid_year: valid_mean
                            }
                            slope = (valid_mean - default_values[trait]) / (valid_year - min_year)  # 计算斜率
                        
                        # 使用这两个点创建线性方程
                        all_years = pd.DataFrame({'birth_year': range(min_year, max_year + 1)})
                        all_years['mean'] = all_years['birth_year'].apply(
                            lambda x: points.get(x, 
                                # 如果年份大于最大已知年份，使用线性外推
                                valid_mean + slope * (x - valid_year) if x > valid_year else
                                # 否则使用线性插值
                                np.interp(x, list(points.keys()), list(points.values())))
                        )
                        all_years['interpolated'] = ~all_years['birth_year'].isin([valid_year])
                        
                    else:
                        # 没有有效年份，全部使用默认值
                        all_years = pd.DataFrame({'birth_year': range(min_year, max_year + 1)})
                        all_years['mean'] = default_values[trait]
                        all_years['interpolated'] = True
                
                # 保存处理结果到字典中
                results[trait] = all_years
            
            # 6. 尝试保存所有结果到Excel
            output_path = detail_path.parent / 'processed_cow_data_key_traits_mean_by_year.xlsx'
            while True:
                try:
                    with pd.ExcelWriter(output_path) as writer:
                        for trait, data in results.items():
                            data.to_excel(writer, sheet_name=trait, index=False)
                    print("年度关键性状数据处理完成")
                    break
                except PermissionError:
                    reply = QMessageBox.question(
                        self,
                        "文件被占用",
                        f"文件 {output_path.name} 正在被其他程序使用。\n请关闭该文件后点击'重试'继续，或点击'取消'停止操作。",
                        QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel
                    )
                    if reply == QMessageBox.StandardButton.Cancel:
                        return False
            
            return True
            
        except Exception as e:
            print(f"处理年度关键性状数据时发生错误: {str(e)}")
            raise

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

    def calculate_cow_key_traits_scores(self, detail_path, yearly_path, progress_callback=None):
        """计算母牛关键性状得分"""
        print("开始计算母牛关键性状得分...")
        
        try:
            # 1. 读取详细数据文件和年度数据文件
            print("读取详细数据文件...")
            df = pd.read_excel(detail_path)
            
            # 2. 确保所有日期列的格式正确
            print("处理日期列...")
            date_columns = ['birth_date', 'birth_date_dam', 'birth_date_mgd']
            for col in date_columns:
                if col in df.columns:
                    # 尝试转换日期，对于无效日期使用NaT
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    # 记录无效日期的数量
                    invalid_dates = df[col].isna().sum()
                    if invalid_dates > 0:
                        print(f"警告: {col} 列中有 {invalid_dates} 个无效日期")
            
            # 3. 从日期提取年份，同时处理无效日期
            print("提取年份...")
            df['birth_year'] = df['birth_date'].dt.year
            df['dam_birth_year'] = df['birth_date_dam'].dt.year
            df['mgd_birth_year'] = df['birth_date_mgd'].dt.year
            
            # 4. 读取所有年度数据到字典中
            print("读取年度数据...")
            yearly_data = {}
            with pd.ExcelFile(yearly_path) as xls:
                for trait in self.get_selected_traits():
                    yearly_data[trait] = pd.read_excel(xls, sheet_name=trait)
                    # 将birth_year设为索引以便快速查找
                    yearly_data[trait].set_index('birth_year', inplace=True)
                    # 记录可用的年份范围
                    print(f"性状 {trait} 的年度数据范围: {yearly_data[trait].index.min()} - {yearly_data[trait].index.max()}")
            
            # 5. 获取默认公牛999HO99999的性状值
            print("获取默认公牛数据...")
            engine = create_engine(f'sqlite:///{LOCAL_DB_PATH}')
            default_values = {}
            with engine.connect() as conn:
                default_bull = conn.execute(
                    text("SELECT * FROM bull_library WHERE `BULL NAAB`='999HO99999'")
                ).fetchone()
                if default_bull:
                    default_bull_dict = dict(default_bull._mapping)
                    for trait in self.get_selected_traits():
                        default_values[trait] = default_bull_dict.get(trait, 0)
                    print(f"获取到默认公牛性状值: {default_values}")
                else:
                    print("警告: 未找到默认公牛999HO99999，使用0作为默认值")
                    for trait in self.get_selected_traits():
                        default_values[trait] = 0

            # 6. 设置权重
            weights = {
                'sire': 0.5,
                'mgs': 0.25,
                'mmgs': 0.125,
                'default': 0.125  # 999HO99999的权重
            }
            
            # 7. 为每个性状计算加权得分
            print("开始计算加权得分...")
            total_traits = len(self.get_selected_traits())
            total_rows = len(df)
            
            for trait_idx, trait in enumerate(self.get_selected_traits(), 1):
                print(f"处理性状: {trait}")
                score_column = f'{trait}_score'
                df[score_column] = 0.0  # 初始化得分列
                
                for index, row in df.iterrows():
                    # 更新进度
                    if progress_callback:
                        current_position = (trait_idx - 1) * total_rows + index + 1
                        progress = int((current_position / (total_traits * total_rows)) * 100)
                        progress_callback(progress)

                    trait_score = 0.0
                    
                    # 处理sire
                    sire_col = f'sire_{trait}'
                    if pd.isna(row[sire_col]):
                        # 尝试从年度数据获取
                        if pd.notna(row['birth_year']):
                            birth_year = int(row['birth_year'])  # 确保年份是整数
                            if birth_year in yearly_data[trait].index:
                                trait_score += weights['sire'] * yearly_data[trait].loc[birth_year, 'mean']
                            else:
                                print(f"警告: 找不到出生年份 {birth_year} 的年度数据，使用默认值")
                                trait_score += weights['sire'] * default_values[trait]
                        else:
                            trait_score += weights['sire'] * default_values[trait]
                    else:
                        trait_score += weights['sire'] * row[sire_col]

                    # 处理mgs
                    mgs_col = f'mgs_{trait}'
                    if pd.isna(row[mgs_col]):
                        # 尝试从年度数据获取，使用母亲出生年份
                        if pd.notna(row['dam_birth_year']):
                            dam_birth_year = int(row['dam_birth_year'])
                            if dam_birth_year in yearly_data[trait].index:
                                trait_score += weights['mgs'] * yearly_data[trait].loc[dam_birth_year, 'mean']
                            else:
                                print(f"警告: 找不到母亲出生年份 {dam_birth_year} 的年度数据，使用默认值")
                                trait_score += weights['mgs'] * default_values[trait]
                        else:
                            trait_score += weights['mgs'] * default_values[trait]
                    else:
                        trait_score += weights['mgs'] * row[mgs_col]

                    # 处理mmgs
                    mmgs_col = f'mmgs_{trait}'
                    if pd.isna(row[mmgs_col]):
                        # 尝试从年度数据获取，使用母亲的母亲出生年份
                        if pd.notna(row['mgd_birth_year']):
                            mgd_birth_year = int(row['mgd_birth_year'])
                            if mgd_birth_year in yearly_data[trait].index:
                                trait_score += weights['mmgs'] * yearly_data[trait].loc[mgd_birth_year, 'mean']
                            else:
                                print(f"警告: 找不到外祖母出生年份 {mgd_birth_year} 的年度数据，使用默认值")
                                trait_score += weights['mmgs'] * default_values[trait]
                        else:
                            trait_score += weights['mmgs'] * default_values[trait]
                    else:
                        trait_score += weights['mmgs'] * row[mmgs_col]

                    # 添加999HO99999的权重
                    trait_score += weights['default'] * default_values[trait]
                    
                    df.at[index, score_column] = trait_score
                    
                # 打印每个性状的得分统计信息
                print(f"性状 {trait} 得分统计:")
                print(df[score_column].describe())
                    
            # 8. 保存结果
            print("保存计算结果...")
            output_path = detail_path.parent / "processed_cow_data_key_traits_scores_pidgree.xlsx"
            if not self.save_results_with_retry(df, output_path):
                print("用户取消了得分数据保存操作")
                return False
                
            print("母牛关键性状得分计算完成")
            return True
            
        except Exception as e:
            print(f"计算母牛关键性状得分时发生错误: {str(e)}")
            raise

    def update_with_genomic_data(self, pedigree_path, genomic_path, progress_callback=None):
        """用基因组数据更新关键性状得分"""
        print("开始用基因组数据更新关键性状得分...")
        
        try:
            # 1. 读取系谱计算的得分文件
            df_pedigree = pd.read_excel(pedigree_path)
            
            # 2. 读取基因组数据
            df_genomic = pd.read_excel(genomic_path)
            
            # 3. 为所有性状得分添加来源列，默认为"P"(系谱)
            score_columns = [col for col in df_pedigree.columns if col.endswith('_score')]
            for col in score_columns:
                df_pedigree[f"{col}_source"] = "P"
                
            # 4. 用基因组数据更新得分
            total_traits = len(self.get_selected_traits())
            total_rows = len(df_pedigree)

    
            for trait_idx, trait in enumerate(self.get_selected_traits(), 1):
                score_col = f"{trait}_score"
                source_col = f"{trait}_score_source"

                # 遍历每一行数据
                for row_idx, (idx, row) in enumerate(df_pedigree.iterrows(), 1):
                    # 更新进度
                    if progress_callback:
                        current_position = (trait_idx - 1) * total_rows + row_idx
                        progress = int((current_position / (total_traits * total_rows)) * 100)
                        progress_callback(progress)
                        
                    cow_id = row['cow_id']
                    # 查找对应的基因组数据
                    genomic_row = df_genomic[df_genomic['cow_id'] == cow_id]
                    
                    if not genomic_row.empty and trait in genomic_row.columns:
                        # 如果找到基因组数据且该性状有值
                        if pd.notna(genomic_row[trait].iloc[0]):
                            # 更新得分和来源标记
                            df_pedigree.at[idx, score_col] = genomic_row[trait].iloc[0]
                            df_pedigree.at[idx, source_col] = "G"
                            print(f"母牛 {cow_id} 的 {trait} 更新为基因组数据")
            
            # 5. 添加一个总结列，显示有多少个性状使用了基因组数据
            genomic_count = df_pedigree[[col for col in df_pedigree.columns if col.endswith('_source')]].apply(
                lambda x: (x == "G").sum(), axis=1
            )
            df_pedigree['genomic_traits_count'] = genomic_count
            
            # 6. 保存结果
            output_path = pedigree_path.parent / "processed_cow_data_key_traits_scores_genomic.xlsx"
            if not self.save_results_with_retry(df_pedigree, output_path):
                print("用户取消了基因组数据更新结果保存")
                return False
            
            print("基因组数据更新完成")
            return True
            
        except Exception as e:
            print(f"更新基因组数据时发生错误: {str(e)}")
            raise

    def save_results_with_retry(self, df, output_path):
        """尝试保存结果，如果文件被占用提示用户并重试"""
        while True:
            try:
                df.to_excel(output_path, index=False)
                print(f"结果已保存到: {output_path}")
                return True
            except PermissionError:
                reply = QMessageBox.question(
                    self,
                    "文件被占用",
                    f"文件 {output_path.name} 正在被其他程序使用。\n请关闭该文件后点击'重试'继续，或点击'取消'停止操作。",
                    QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel
                )
                if reply == QMessageBox.StandardButton.Cancel:
                    return False
                

    def get_main_window(self):
        """获取主窗口实例"""
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        return parent