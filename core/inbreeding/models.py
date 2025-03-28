from PyQt6.QtCore import Qt, QAbstractTableModel
import pandas as pd
from PyQt6.QtGui import QBrush, QColor

class InbreedingDetailModel(QAbstractTableModel):
    """明细表数据模型"""
    def __init__(self):
        super().__init__()
        self.df = pd.DataFrame()  # 初始化一个空的DataFrame
        self.display_columns = []
        self.sort_column = None  # 当前排序的列
        self.sort_order = Qt.SortOrder.AscendingOrder  # 排序顺序
        
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
            '近交系数': '近交系数',
        }
        
        # 添加基因列和原始值列
        for gene in self.defect_genes:
            self.column_names[gene] = gene
            self.column_names[f"{gene}(母)"] = f"{gene}(母)"
            self.column_names[f"{gene}(公)"] = f"{gene}(公)"
        
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
        return len(self.display_columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """获取单元格数据"""
        if not index.isValid() or not self.df.empty and (index.row() >= len(self.df) or index.column() >= len(self.display_columns)):
            return None
            
        if role == Qt.ItemDataRole.DisplayRole:
            col_name = self.display_columns[index.column()]
            value = self.df.iloc[index.row()][col_name]
            
            # 格式化基因数据
            if col_name in self.defect_genes or col_name.endswith('(母)') or col_name.endswith('(公)'):
                return self._format_gene_value(value)
            
            return str(value)
            
        elif role == Qt.ItemDataRole.BackgroundRole:
            col_name = self.display_columns[index.column()]
            if col_name in self.defect_genes:
                value = self.df.iloc[index.row()][col_name]
                return self._get_gene_background(value)
                
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        """获取表头数据"""
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if section < len(self.display_columns):
                    return self.display_columns[section]
            elif orientation == Qt.Orientation.Vertical:
                return str(section + 1)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        return None

    def flags(self, index):
        """设置单元格标志"""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def update_data(self, df: pd.DataFrame):
        """更新数据"""
        # 确保后代近交系数列存在且不含有NaN
        if '后代近交系数' in df.columns:
            # 将nan值替换为"0.00%"
            df['后代近交系数'] = df['后代近交系数'].fillna("0.00%")
            
            # 确保是字符串格式
            df['后代近交系数'] = df['后代近交系数'].astype(str)
            
            # 如果不是百分比格式，进行格式化
            def format_percentage(value):
                if '%' not in value:
                    try:
                        return f"{float(value):.2%}"
                    except (ValueError, TypeError):
                        return "0.00%"
                return value
                
            df['后代近交系数'] = df['后代近交系数'].apply(format_percentage)
            
            # 打印检查后代近交系数格式
            print("检查后代近交系数格式:")
            unique_values = df['后代近交系数'].unique()
            print(f"唯一值: {unique_values[:10]}")
            
        # 按近交系数排序
        if '近交系数' in df.columns:
            # 将百分比格式的字符串转为数值进行排序
            df['近交系数_value'] = df['近交系数'].apply(lambda x: float(x.strip('%')) / 100 if isinstance(x, str) and '%' in x else 0.0)
            df = df.sort_values(by='近交系数_value', ascending=False)
            df = df.drop(columns=['近交系数_value'])
            
        # 确保"后代近交系数"列在"近交系数"列后面
        if '后代近交系数' in df.columns and '近交系数' in df.columns:
            # 获取所有列名
            columns = list(df.columns)
            
            # 如果列已经存在，需要先移除
            if '后代近交系数' in columns:
                columns.remove('后代近交系数')
                
            # 确定近交系数列的位置
            if '近交系数' in columns:
                inbreeding_idx = columns.index('近交系数')
                # 在近交系数列后面插入后代近交系数列
                columns.insert(inbreeding_idx + 1, '后代近交系数')
            else:
                # 如果没有近交系数列，就添加到母牛号和父号后面
                columns.append('后代近交系数')
                
            # 确保不重复
            columns = [col for i, col in enumerate(columns) if col not in columns[:i]]
            
            try:
                # 重新排序dataframe
                df = df[columns]
            except KeyError as e:
                print(f"列排序错误: {e}")
                print(f"现有列: {df.columns.tolist()}")
                print(f"尝试排序的列: {columns}")
        
        # 设置要显示的列
        # 确保在模型中始终包含关键列，顺序清晰
        display_columns = []
        
        # 先添加基本信息列
        for col in ['母牛号', '父号', '配种公牛号']:
            if col in df.columns:
                display_columns.append(col)
                
        # 添加后代近交系数列
        if '后代近交系数' in df.columns:
            display_columns.append('后代近交系数')
            
        # 添加所有隐性基因列
        for gene in self.defect_genes:
            if gene in df.columns:
                display_columns.append(gene)
                
        # 设置显示列
        print(f"显示列: {display_columns}")
        self.display_columns = display_columns
        
        # 更新数据
        self.beginResetModel()
        self.df = df
        self.endResetModel()

    def _format_gene_value(self, value):
        """格式化基因值显示"""
        if value == 'C':
            return "携带者(C)"
        elif value == 'F':
            return "正常(F)"
        elif value == 'NO safe':
            return "不安全"
        elif value == 'safe':
            return "安全"
        elif value == 'missing data':
            return "缺数据"
        return str(value)
            
    def _get_gene_background(self, value):
        """获取基因值对应的背景色"""
        colors = {
            'NO safe': QBrush(QColor(255, 200, 200)),  # 浅红色
            'safe': QBrush(QColor(200, 255, 200)),  # 浅绿色
            'missing data': QBrush(QColor(245, 245, 245)),  # 浅灰色
            'missing cow data': QBrush(QColor(255, 255, 200)),  # 浅黄色
            'missing bull data': QBrush(QColor(200, 200, 255))  # 浅蓝色
        }
        return colors.get(value)

    def sort(self, column: int, order: Qt.SortOrder) -> None:
        """实现排序功能"""
        try:
            self.layoutAboutToBeChanged.emit()
            
            # 获取列名
            if 0 <= column < len(self.display_columns):
                column_name = self.display_columns[column]
                
                # 如果是近交系数或后代近交系数列，需要特殊处理
                if column_name in ['近交系数', '后代近交系数']:
                    # 移除百分号并转换为浮点数进行排序
                    self.df[f'{column_name}_sort'] = self.df[column_name].str.rstrip('%').astype(float)
                    self.df = self.df.sort_values(
                        by=f'{column_name}_sort',
                        ascending=(order == Qt.SortOrder.AscendingOrder)
                    )
                    # 删除临时排序列
                    self.df = self.df.drop(columns=[f'{column_name}_sort'])
                else:
                    # 其他列正常排序
                    self.df = self.df.sort_values(
                        by=column_name,
                        ascending=(order == Qt.SortOrder.AscendingOrder)
                    )
                
                # 保存当前排序状态
                self.sort_column = column
                self.sort_order = order
            
            self.layoutChanged.emit()
        except Exception as e:
            print(f"排序时发生错误: {e}")


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
            # 获取异常类型列的索引
            type_index = list(self.column_names.keys()).index('异常类型')
            status_index = list(self.column_names.keys()).index('状态')
            
            abnormal_type = self.df.iloc[index.row(), type_index]
            
            # 根据异常类型设置不同的背景色
            if abnormal_type == '近交系数过高':
                # 为近交系数过高的行设置橙色背景
                return QBrush(QColor(255, 165, 0))  # 橙色
            elif index.column() == status_index:
                # 对于其他类型的异常，如果状态为NO safe，则显示红色
                value = self.df.iloc[index.row(), status_index]
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