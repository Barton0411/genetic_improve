from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGraphicsView, QGraphicsScene, QGraphicsItem
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPen, QBrush, QColor, QPainter, QFont
from .pedigree_visualizer import PedigreeTreeView

class PedigreeTreeWidget(QWidget):
    def __init__(self, calculator, animal_id):
        super().__init__()
        self.calculator = calculator
        self.animal_id = animal_id
        self.initUI()

    def initUI(self):
        # 主布局
        main_layout = QVBoxLayout()
        
        # 添加标题
        title = QLabel(f"血缘系谱图 - {self.animal_id}")
        title.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #333333;
                padding: 10px;
            }
        """)
        main_layout.addWidget(title)
        
        # 添加系谱树视图
        self.tree_view = PedigreeTreeView(self.calculator, self.animal_id)
        main_layout.addWidget(self.tree_view)
        
        # 添加图例
        legend_layout = QHBoxLayout()
        
        # 公牛图例
        bull_label = QLabel("■ 公牛")
        bull_label.setStyleSheet("color: #4682B4;")
        legend_layout.addWidget(bull_label)
        
        # 母牛图例
        cow_label = QLabel("■ 母牛")
        cow_label.setStyleSheet("color: #FFB6C1;")
        legend_layout.addWidget(cow_label)
        
        # 共同祖先图例
        common_label = QLabel("■ 共同祖先")
        common_label.setStyleSheet("color: #FF4500;")
        legend_layout.addWidget(common_label)
        
        # 未知祖先图例
        unknown_label = QLabel("■ 未知祖先")
        unknown_label.setStyleSheet("color: #808080;")
        legend_layout.addWidget(unknown_label)
        
        legend_layout.addStretch()
        main_layout.addLayout(legend_layout)
        
        self.setLayout(main_layout) 