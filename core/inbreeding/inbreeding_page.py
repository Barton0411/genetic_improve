from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QTableView, QFrame, QSplitter
)
from PyQt6.QtCore import Qt
from .models import InbreedingDetailModel, AbnormalDetailModel, StatisticsModel

class InbreedingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        
        # 创建左右分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧明细表区域 (50%)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        detail_label = QLabel("明细表")
        self.detail_table = QTableView()
        self.detail_model = InbreedingDetailModel()
        self.detail_table.setModel(self.detail_model)
        
        left_layout.addWidget(detail_label)
        left_layout.addWidget(self.detail_table)
        
        # 右侧区域 (50%)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 右上异常明细表 (25%)
        abnormal_label = QLabel("异常明细表")
        self.abnormal_table = QTableView()
        self.abnormal_model = AbnormalDetailModel()
        self.abnormal_table.setModel(self.abnormal_model)
        
        # 右中统计表 (15%)
        stats_label = QLabel("统计表")
        self.stats_table = QTableView()
        self.stats_model = StatisticsModel()
        self.stats_table.setModel(self.stats_model)
        
        # 右下按钮区域 (10%)
        button_layout = QHBoxLayout()
        self.mated_bull_btn = QPushButton("已配公牛计算")
        self.candidate_bull_btn = QPushButton("备选公牛计算")
        
        # 设置按钮样式
        button_style = """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """
        self.mated_bull_btn.setStyleSheet(button_style)
        self.candidate_bull_btn.setStyleSheet(button_style)
        
        button_layout.addWidget(self.mated_bull_btn)
        button_layout.addWidget(self.candidate_bull_btn)
        button_layout.addStretch()
        
        # 添加到右侧布局
        right_layout.addWidget(abnormal_label)
        right_layout.addWidget(self.abnormal_table, stretch=25)
        right_layout.addWidget(stats_label)
        right_layout.addWidget(self.stats_table, stretch=15)
        right_layout.addLayout(button_layout)
        
        # 添加到分割器
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        
        # 设置分割比例
        splitter.setStretchFactor(0, 1)  # 左侧 50%
        splitter.setStretchFactor(1, 1)  # 右侧 50%
        
        main_layout.addWidget(splitter)
        
        # 连接按钮信号
        self.mated_bull_btn.clicked.connect(self.calculate_mated_bulls)
        self.candidate_bull_btn.clicked.connect(self.calculate_candidate_bulls)

    def calculate_mated_bulls(self):
        """计算已配公牛的近交系数"""
        pass

    def calculate_candidate_bulls(self):
        """计算备选公牛的近交系数"""
        pass 