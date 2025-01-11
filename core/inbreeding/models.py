from PyQt6.QtCore import Qt, QAbstractTableModel
import pandas as pd

class InbreedingDetailModel(QAbstractTableModel):
    """明细表数据模型"""
    def __init__(self):
        super().__init__()
        self.df = pd.DataFrame()  # 初始化一个空的DataFrame
        self.headers = [
            '母牛号', '公牛号', '近交系数', 
            'HH1', 'HH2', 'HH3', 'HH4', 'HH5', 'HH6',
            'HCD'
        ]

    def rowCount(self, parent=None):
        return len(self.df)

    def columnCount(self, parent=None):
        return len(self.headers)

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
                return self.headers[section]
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
        self.headers = [
            '母牛号', '公牛号', '异常类型', '异常值'
        ]

    def rowCount(self, parent=None):
        return len(self.df)

    def columnCount(self, parent=None):
        return len(self.headers)

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
                return self.headers[section]
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
        self.headers = [
            '异常类型', '数量'
        ]

    def rowCount(self, parent=None):
        return len(self.df)

    def columnCount(self, parent=None):
        return len(self.headers)

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
                return self.headers[section]
            else:
                return str(section + 1)
        return None

    def update_data(self, data):
        """更新模型数据"""
        self.beginResetModel()
        self.df = data
        self.endResetModel() 