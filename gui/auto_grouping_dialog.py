from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QWidget, QFormLayout, QSpinBox, QListWidget, QGroupBox,
    QMessageBox, QInputDialog, QTextBrowser, QTableWidgetItem
)
from PyQt6.QtCore import Qt, QTimer

from gui.progress import ProgressDialog
from core.grouping.group_manager import GroupManager
from gui.main_window import StrategyTableManager

class AutoGroupingDialog(QDialog):
    """自动分组对话框"""
    def __init__(self, project_path, parent=None):
        super().__init__(parent)
        self.project_path = project_path
        self.parent_window = parent
        self.setWindowTitle("自动分组")
        self.setMinimumSize(800, 600)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 分组方式设计
        design_group = QGroupBox("分组方式设计")
        design_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: #2c3e50;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        design_layout = QVBoxLayout()
        
        # 创建分组策略设置页面
        strategy_widget = QWidget()
        strategy_layout = QVBoxLayout(strategy_widget)
        strategy_layout.setContentsMargins(0, 0, 0, 0)  # 减少内边距
        strategy_layout.setSpacing(5)  # 减少组件间距
        
        # 添加参数设置
        param_form_layout = QFormLayout()
        param_form_layout.setContentsMargins(0, 0, 0, 0)  # 减少内边距
        param_form_layout.setVerticalSpacing(5)  # 减少垂直间距
        
        self.reserve_age = QSpinBox()
        self.reserve_age.setRange(0, 1000)
        self.reserve_age.setSuffix(" 天")
        self.reserve_age.setValue(420)  # 默认值
        self.reserve_age.setStyleSheet("""
            QSpinBox {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                padding: 3px;
                min-height: 25px;
                font-size: 13px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 15px;
            }
        """)
        
        self.cycle_days = QSpinBox()
        self.cycle_days.setRange(0, 365)
        self.cycle_days.setSuffix(" 天")
        self.cycle_days.setValue(21)  # 默认值
        self.cycle_days.setStyleSheet("""
            QSpinBox {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                padding: 3px;
                min-height: 25px;
                font-size: 13px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 15px;
            }
        """)
        
        # 设置标签样式
        reserve_label = QLabel("后备牛开配日龄:")
        reserve_label.setStyleSheet("color: #2c3e50; font-size: 13px;")
        cycle_label = QLabel("选配周期:")
        cycle_label.setStyleSheet("color: #2c3e50; font-size: 13px;")
        
        param_form_layout.addRow(reserve_label, self.reserve_age)
        param_form_layout.addRow(cycle_label, self.cycle_days)
        
        strategy_layout.addLayout(param_form_layout)
        
        # 添加策略表
        strategy_table_label = QLabel("配种策略设置:")
        strategy_table_label.setStyleSheet("color: #2c3e50; font-size: 13px; font-weight: bold;")
        strategy_layout.addWidget(strategy_table_label)
        
        # 创建选配策略表
        self.strategy_table = StrategyTableManager.create_strategy_table(strategy_widget)
        
        # 设置表格样式以改善字体对比度
        self.strategy_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                color: #2c3e50;
                font-size: 13px;
                border: 1px solid #ddd;
            }
            QTableWidget::item {
                color: #2c3e50;
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                color: #2c3e50;
                font-weight: bold;
                padding: 5px;
                border: 1px solid #ddd;
            }
            QComboBox {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                padding: 3px;
                min-height: 25px;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #2c3e50;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #2c3e50;
                selection-background-color: #3498db;
                selection-color: white;
            }
        """)
        
        strategy_layout.addWidget(self.strategy_table)
        design_layout.addWidget(strategy_widget)
        
        # 已保存策略列表
        saved_strategies_layout = QVBoxLayout()
        saved_strategies_label = QLabel("已保存策略:")
        saved_strategies_label.setStyleSheet("color: #2c3e50; font-size: 13px; font-weight: bold;")
        saved_strategies_layout.addWidget(saved_strategies_label)

        self.strategies_list = QListWidget()
        self.strategies_list.setMaximumHeight(130)
        self.strategies_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 2px;
                background-color: white;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 2px;
            }
        """)
        # 连接点击事件，自动加载选中的策略
        self.strategies_list.itemClicked.connect(self.load_selected_strategy)
        saved_strategies_layout.addWidget(self.strategies_list)
        design_layout.addLayout(saved_strategies_layout)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_style = """
            QPushButton {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 2px;
                padding: 4px 8px;
                min-width: 80px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e9e9e9;
            }
            QPushButton:pressed {
                background-color: #d5d5d5;
            }
        """
        
        # 应用策略按钮样式（更醒目的颜色）
        apply_button_style = """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: 1px solid #45a049;
                border-radius: 2px;
                padding: 4px 8px;
                min-width: 80px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """
        
        # 按钮顺序：添加策略、删除策略、应用策略、逻辑说明
        add_strategy_btn = QPushButton("添加策略")
        add_strategy_btn.setStyleSheet(button_style)
        add_strategy_btn.clicked.connect(self.save_group_strategy)
        
        delete_strategy_btn = QPushButton("删除策略")
        delete_strategy_btn.setStyleSheet(button_style)
        delete_strategy_btn.clicked.connect(self.delete_selected_strategy)
        
        apply_strategy_btn = QPushButton("应用策略")
        apply_strategy_btn.setStyleSheet(apply_button_style)
        apply_strategy_btn.clicked.connect(self.apply_group_strategy)
        
        explain_logic_btn = QPushButton("逻辑说明")
        explain_logic_btn.setStyleSheet(button_style)
        explain_logic_btn.clicked.connect(self.show_group_logic_explanation)
        
        button_layout.addWidget(add_strategy_btn)
        button_layout.addWidget(delete_strategy_btn)
        button_layout.addWidget(apply_strategy_btn)
        button_layout.addWidget(explain_logic_btn)
        button_layout.addStretch()
        
        design_layout.addLayout(button_layout)
        design_group.setLayout(design_layout)
        
        # 添加到主布局
        layout.addWidget(design_group)
        
        # 对话框底部按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)
        
        # 加载已保存的策略列表
        self.load_strategy_list()
        
    def load_strategy_list(self):
        """加载已保存的策略列表"""
        try:
            self.strategies_list.clear()
            strategies = GroupManager.list_strategies()
            self.strategies_list.addItems(strategies)
        except Exception as e:
            print(f"加载策略列表时出错: {str(e)}")
        
    def load_selected_strategy(self):
        """加载选中的策略"""
        if not self.strategies_list.currentItem():
            QMessageBox.warning(self, "警告", "请先选择一个策略")
            return

        try:
            strategy_name = self.strategies_list.currentItem().text()
            
            # 创建临时的GroupManager实例来加载策略
            group_manager = GroupManager(self.project_path)
            group_manager.load_strategy(strategy_name)
            
            # 更新界面上的参数
            params = group_manager.strategy['params']
            self.reserve_age.setValue(params.get('reserve_age', 0))
            self.cycle_days.setValue(params.get('cycle_days', 0))
            
            # 使用策略表格管理器加载策略
            StrategyTableManager.load_strategy_to_table(self.strategy_table, group_manager.strategy)
            
            # 将成功消息改为状态栏提示或窗口标题更新，而不是弹窗
            self.setWindowTitle(f"自动分组 - 已加载策略：{strategy_name}")
            print(f"已成功加载策略：{strategy_name}")
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"加载策略错误详情: {error_details}")
            QMessageBox.critical(self, "错误", f"加载策略时发生错误：{str(e)}")
            
    def delete_selected_strategy(self):
        """删除选中的策略"""
        if not self.strategies_list.currentItem():
            QMessageBox.warning(self, "警告", "请先选择一个策略")
            return

        strategy_name = self.strategies_list.currentItem().text()
        reply = QMessageBox.question(
            self, 
            "确认删除", 
            f'确定要删除策略"{strategy_name}"吗？此操作不可恢复！',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                GroupManager.delete_strategy(strategy_name)
                self.load_strategy_list()  # 刷新列表
                QMessageBox.information(self, "成功", "策略已删除")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除策略时发生错误：{str(e)}")
                
    def save_group_strategy(self):
        """保存分组方式设计"""
        strategy_name, ok = QInputDialog.getText(
            self, "添加策略", "请输入策略名称:"
        )
        
        if ok and strategy_name:
            try:
                # 准备策略数据
                strategy_data = {
                    "params": {
                        "reserve_age": self.reserve_age.value(),
                        "cycle_days": self.cycle_days.value()
                    },
                    "strategy_table": StrategyTableManager.get_strategy_table_data(self.strategy_table)
                }
                
                # 保存策略
                GroupManager.save_strategy(strategy_name, strategy_data)
                QMessageBox.information(self, "成功", "策略已添加")
                
                # 刷新策略列表
                self.load_strategy_list()
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"添加策略时发生错误：{str(e)}")
                
    def apply_group_strategy(self):
        """应用当前的临时分组策略"""
        try:
            # 获取控件值
            reserve_age = self.reserve_age.value()
            cycle_days = self.cycle_days.value()
            
            # 构建分组策略
            current_strategy = {
                "params": {
                    "reserve_age": reserve_age,
                    "cycle_days": cycle_days
                },
                "strategy_table": StrategyTableManager.get_strategy_table_data(self.strategy_table)
            }
            
            # 创建进度对话框
            progress = ProgressDialog(self)
            progress.setWindowTitle("分组进度")
            progress.set_task_info("正在准备分组数据...")
            progress.show()
            
            try:
                # 创建临时策略并应用
                group_manager = GroupManager(self.project_path)
                
                # 添加详细错误处理
                try:
                    # 真正的分组处理
                    df = group_manager.apply_temp_strategy(current_strategy, progress_callback=progress)
                    
                    # 直接更新到原始指数文件
                    progress.set_task_info("正在更新分组结果到指数计算文件...")
                    index_file = self.project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
                    
                    # 读取原始指数文件
                    import pandas as pd
                    try:
                        index_df = pd.read_excel(index_file)
                        
                        # 如果index_df中已有group列，先删除
                        if 'group' in index_df.columns:
                            index_df = index_df.drop(columns=['group'])
                        
                        # 只保留group列进行更新
                        group_col = df[['cow_id', 'group']]
                        
                        # 将group列合并到原始指数文件
                        index_df = pd.merge(index_df, group_col, on='cow_id', how='left')
                        
                        # 保存更新后的文件
                        index_df.to_excel(index_file, index=False)
                        
                        # 显示分组统计信息
                        group_counts = df.groupby('group').size().reset_index(name='count')
                        group_stats = "\n".join([f"{row['group']}: {row['count']}头" for _, row in group_counts.iterrows()])
                        
                        # 完成处理，确保进度对话框关闭
                        progress.set_task_info("分组完成")
                        progress.update_progress(100)
                        
                        # 使用QTimer延迟关闭，确保UI更新
                        QTimer.singleShot(500, progress.close)
                        
                        # 在进度条关闭后显示成功消息
                        QTimer.singleShot(600, lambda: QMessageBox.information(
                            self, "成功", f"分组完成！\n分组统计：\n{group_stats}\n\n结果已更新到：\n{index_file}"
                        ))
                        
                    except Exception as e:
                        raise Exception(f"更新指数文件时发生错误: {str(e)}")
                
                except Exception as e:
                    # 出错时也确保关闭进度对话框
                    progress.close()
                    
                    error_message = str(e)
                    import traceback
                    error_traceback = traceback.format_exc()
                    print(f"错误详情: {error_traceback}")
                    QMessageBox.critical(self, "错误", f"应用分组策略时发生错误：{error_message}")
                
            except Exception as e:
                # 发生异常时关闭进度对话框
                progress.close()
                QMessageBox.critical(self, "错误", f"初始化分组过程时发生错误：{str(e)}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"应用分组策略时发生错误：{str(e)}")
            
    def show_group_logic_explanation(self):
        """显示分组逻辑说明对话框"""
        explanation = """
<h3>分组逻辑详细说明</h3>

<p><b>基础筛选：</b>只考虑在场母牛（"是否在场" = "是"且sex = "母"）</p>

<h4>1. 牛只分类</h4>
<ul>
<li><b>后备牛：</b>胎次(lac) = 0</li>
<li><b>成母牛：</b>胎次(lac) > 0</li>
</ul>

<h4>2. 后备牛分组</h4>
<ul>
<li><b>已孕牛：</b>repro_status 为 "初检孕" 或 "复检孕"</li>
<li><b>难孕牛：</b>日龄 ≥ 18×30.8(约553天) 且未孕</li>
<li><b>周期分组：</b>对普通后备牛（非已孕/难孕）按日龄分周期
  <ul>
  <li>第1周期：18×30.8 > 日龄 ≥ (后备牛开配日龄-选配周期*1)</li>
  <li>第2周期：(后备牛开配日龄-选配周期*1) > 日龄 ≥ (后备牛开配日龄-选配周期*2)</li>
  <li>第n周期：(后备牛开配日龄-选配周期*(n-1)) > 日龄 ≥ (后备牛开配日龄-选配周期*n)</li>
  </ul>
</li>
</ul>

<h4>3. 成母牛分组</h4>
<ul>
<li><b>已孕牛：</b>repro_status 为 "初检孕" 或 "复检孕"</li>
<li><b>难孕牛：</b>泌乳天数(DIM) ≥ 150 且未孕</li>
<li><b>未孕牛：</b>非已孕且非难孕的成母牛</li>
</ul>

<h4>4. 遗传物质分配规则</h4>
<ol>
<li><b>已孕牛和难孕牛：</b>统一使用非性控</li>
<li><b>后备牛各周期：</b>
  <ul>
  <li>先按ranking排序（从小到大）</li>
  <li>根据配置的比例将每个周期内的牛分为A/B/C组：
    <ul>
    <li>A组：取排名前X%的牛（如前50%）</li>
    <li>B组：取排名接下来Y%的牛（如50%-80%）</li>
    <li>C组：取排名最后Z%的牛（如80%-100%）</li>
    </ul>
  </li>
  <li>对每组牛根据配种次数应用不同的配种方法：
    <ul>
    <li>第1次配种：使用各组设定的第1次配种方法</li>
    <li>第2次配种：使用各组设定的第2次配种方法</li>
    <li>第3次配种：使用各组设定的第3次配种方法</li>
    <li>第4次及以上配种：使用各组设定的第4次+配种方法</li>
    </ul>
  </li>
  </ul>
</li>
<li><b>成母牛未孕牛：</b>同样按ranking排序并分为A/B/C组，应用各自的配种策略</li>
</ol>

<h4>5. 性控/非性控判定</h4>
<ul>
<li><b>性控方法：</b>"普通性控"、"超级性控"</li>
<li><b>非性控方法：</b>"常规冻精"、"肉牛冻精"、"胚胎"</li>
</ul>

<h4>6. 结果标记</h4>
<ul>
<li>后备牛：后备牛第X周期+性控/非性控</li>
<li>后备牛特殊：后备牛已孕牛+非性控、后备牛难孕牛+非性控</li>
<li>成母牛：成母牛未孕牛+性控/非性控</li>
<li>成母牛特殊：成母牛已孕牛+非性控、成母牛难孕牛+非性控</li>
</ul>

<p>举例：某后备牛属于第1周期，ranking在该周期牛只前30%（属于A组），配种次数为1，A组第2次配种设置为"超级性控"，则该牛标记为 "后备牛第1周期+性控"</p>
"""
        
        # 创建对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("分组逻辑说明")
        dialog.setMinimumSize(800, 600)
        
        # 创建布局
        layout = QVBoxLayout(dialog)
        
        # 创建文本浏览器并设置富文本
        text_browser = QTextBrowser()
        text_browser.setHtml(explanation)
        layout.addWidget(text_browser)
        
        # 添加关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
        
        # 显示对话框
        dialog.exec() 