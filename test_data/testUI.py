class MatchingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # 创建水平分割布局
        top_layout = QHBoxLayout()
        bottom_layout = QHBoxLayout()
        
        # 左侧区域 (50%): 群体选择
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 胎次选择
        lactation_group = QGroupBox("胎次选择")
        lactation_layout = QVBoxLayout()
        # 添加胎次选择控件
        lactation_group.setLayout(lactation_layout)
        
        # 分组选择
        group_group = QGroupBox("分组选择")
        group_layout = QVBoxLayout()
        # 添加分组选择控件
        group_group.setLayout(group_layout)
        
        # 母牛列表
        cow_list_group = QGroupBox("母牛列表")
        cow_list_layout = QVBoxLayout()
        # 添加母牛列表控件
        cow_list_group.setLayout(cow_list_layout)
        
        left_layout.addWidget(lactation_group)
        left_layout.addWidget(group_group)
        left_layout.addWidget(cow_list_group)
        
        # 中间区域 (10%): 选配参数
        middle_widget = QWidget()
        middle_layout = QVBoxLayout(middle_widget)
        
        # 选配参数设置
        params_group = QGroupBox("选配参数")
        params_layout = QVBoxLayout()
        # 添加参数设置控件
        params_group.setLayout(params_layout)
        
        middle_layout.addWidget(params_group)
        
        # 右侧区域 (30%): 冻精分配
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 性控冻精分配
        sexed_group = QGroupBox("性控冻精分配")
        sexed_layout = QVBoxLayout()
        # 添加性控冻精分配控件
        sexed_group.setLayout(sexed_layout)
        
        # 常规冻精分配
        regular_group = QGroupBox("常规冻精分配")
        regular_layout = QVBoxLayout()
        # 添加常规冻精分配控件
        regular_group.setLayout(regular_layout)
        
        # 分配结果预览
        preview_group = QGroupBox("分配结果预览")
        preview_layout = QVBoxLayout()
        # 添加预览控件
        preview_group.setLayout(preview_layout)
        
        right_layout.addWidget(sexed_group)
        right_layout.addWidget(regular_group)
        right_layout.addWidget(preview_group)
        
        # 添加左右区域到顶部布局
        top_layout.addWidget(left_widget, 50)
        top_layout.addWidget(middle_widget, 10)
        top_layout.addWidget(right_widget, 30)
        
        # 底部按钮区域 (10%)
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        
        # 添加操作按钮
        start_btn = QPushButton("开始选配")
        save_btn = QPushButton("保存结果")
        export_btn = QPushButton("导出报告")
        
        button_layout.addWidget(start_btn)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(export_btn)
        
        # 将所有布局添加到主布局
        main_layout.addLayout(top_layout, 90)
        main_layout.addWidget(button_widget, 10)