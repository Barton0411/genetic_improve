from PyQt6.QtCore import Qt, QAbstractTableModel
import pandas as pd
from PyQt6.QtGui import QBrush

class InbreedingDetailModel(QAbstractTableModel):
    """明细表数据模型"""
    def __init__(self):
        super().__init__()
        self.df = pd.DataFrame()  # 初始化一个空的DataFrame
        
        # 定义基因列表
        self.defect_genes = [
            "HH1", "HH2", "HH3", "HH4", "HH5", "HH6", 
            "BLAD", "Chondrodysplasia", "Citrullinemia",
            "DUMPS", "Factor XI", "CVM", "Brachyspina",
            "Mulefoot", "Cholesterol deficiency", "MW"
        ]
        
        # 定义列名映射
        self.column_names = {
            '耳号': '耳号',
            '父号': '父号',
            '配种公牛': '配种公牛',
            **{gene: gene for gene in self.defect_genes}
        }
        
        # 定义状态颜色映射
        self.status_colors = {
            'NO safe': QBrush(Qt.GlobalColor.red),
            'safe': QBrush(Qt.GlobalColor.green),
            'missing cow data': QBrush(Qt.GlobalColor.yellow),
            'missing bull data': QBrush(Qt.GlobalColor.yellow),
            'missing data': QBrush(Qt.GlobalColor.gray)
        }

    def rowCount(self, parent=None):
        return len(self.df)

    def columnCount(self, parent=None):
        return len(self.column_names)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
            
        if role == Qt.ItemDataRole.DisplayRole:
            value = self.df.iloc[index.row(), index.column()]
            return str(value)
            
        elif role == Qt.ItemDataRole.BackgroundRole:
            value = self.df.iloc[index.row(), index.column()]
            if isinstance(value, str):
                return self.status_colors.get(value)
                
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return list(self.column_names.values())[section]
            else:
                return str(section + 1)
        return None

    def update_data(self, data):
        """更新模型数据"""
        self.beginResetModel()
        self.df = data
        self.endResetModel()


class AbnormalDetailModel(QAbstractTableModel):
    """异常明细表数据模型"""
    def __init__(self):
        super().__init__()
        self.df = pd.DataFrame()
        
        # 定义列名映射
        self.column_names = {
            '耳号': '耳号',
            '父号': '父号',
            '配种公牛': '配种公牛',
            '异常类型': '异常类型',
            '状态': '状态'
        }

    def rowCount(self, parent=None):
        return len(self.df)

    def columnCount(self, parent=None):
        return len(self.column_names)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
            
        if role == Qt.ItemDataRole.DisplayRole:
            value = self.df.iloc[index.row(), index.column()]
            return str(value)
            
        elif role == Qt.ItemDataRole.BackgroundRole:
            # 如果是NO safe状态，显示红色背景
            if index.column() == list(self.column_names.keys()).index('状态'):
                value = self.df.iloc[index.row(), index.column()]
                if value == 'NO safe':
                    return QBrush(Qt.GlobalColor.red)
                    
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return list(self.column_names.values())[section]
            else:
                return str(section + 1)
        return None

    def update_data(self, data):
        """更新模型数据"""
        self.beginResetModel()
        self.df = data
        self.endResetModel()


class StatisticsModel(QAbstractTableModel):
    """统计表数据模型"""
    def __init__(self):
        super().__init__()
        self.df = pd.DataFrame()

    def rowCount(self, parent=None):
        return len(self.df)

    def columnCount(self, parent=None):
        return len(self.df.columns) if not self.df.empty else 0

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
            
        if role == Qt.ItemDataRole.DisplayRole:
            value = self.df.iloc[index.row(), index.column()]
            return str(value)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self.df.columns[section]
            else:
                return str(section + 1)
        return None

    def update_data(self, data):
        """更新模型数据"""
        self.beginResetModel()
        self.df = data
        self.endResetModel()