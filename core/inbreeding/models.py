from PyQt6.QtCore import Qt, QAbstractTableModel
import pandas as pd
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette

class InbreedingDetailModel(QAbstractTableModel):
    """明细表数据模型"""
    def __init__(self):
        super().__init__()
        self.df = pd.DataFrame()  # 初始化一个空的DataFrame
        self.display_columns = []
        self.sort_column = None  # 当前排序的列
        self.sort_order = Qt.SortOrder.AscendingOrder  # 排序顺序
        self._sort_cache = {}  # 排序键缓存
        
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
        
        # 定义状态颜色映射（8种详细状态）
        self.status_colors = {
            '高风险': QBrush(Qt.GlobalColor.red),
            '缺少公牛信息': QBrush(Qt.GlobalColor.gray),
            '缺少母牛父亲信息': QBrush(Qt.GlobalColor.gray),
            '缺少双方信息': QBrush(QColor(128, 128, 128)),  # 深灰色
            '仅公牛携带': QBrush(QColor(255, 165, 0)),  # 橙色
            '仅母牛父亲携带': QBrush(QColor(255, 165, 0)),  # 橙色
            '-': QBrush(Qt.GlobalColor.green)
        }

    def rowCount(self, parent=None):
        return len(self.df)

    def columnCount(self, parent=None):
        return len(self.display_columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """获取单元格数据"""
        if not index.isValid() or not self.df.empty and (index.row() >= len(self.df) or index.column() >= len(self.display_columns)):
            return None

        col_name = self.display_columns[index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            value = self.df.iloc[index.row()][col_name]

            # 格式化基因数据
            if col_name in self.defect_genes or col_name.endswith('(母)') or col_name.endswith('(公)'):
                return self._format_gene_value(value)

            return str(value)

        elif role == Qt.ItemDataRole.BackgroundRole:
            if col_name in self.defect_genes:
                value = self.df.iloc[index.row()][col_name]
                return self._get_gene_background(value)

        elif role == Qt.ItemDataRole.ForegroundRole:
            # 检测是否为深色模式
            app = QApplication.instance()
            is_dark_mode = False
            if app:
                palette = app.palette()
                bg_color = palette.color(QPalette.ColorRole.Window)
                brightness = (bg_color.red() * 299 + bg_color.green() * 587 + bg_color.blue() * 114) / 1000
                is_dark_mode = brightness < 128

            # 深色模式下，隐性基因列使用黑色文字
            if is_dark_mode and col_name in self.defect_genes:
                return QBrush(QColor(0, 0, 0))  # 黑色

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
            print(f"数据类型: {df['后代近交系数'].dtype}")
            # 检查前5行的具体值
            print(f"前5行值: {df['后代近交系数'].head().tolist()}")
            # 检查是否有百分号
            has_percent = df['后代近交系数'].astype(str).str.contains('%').any()
            print(f"是否包含百分号: {has_percent}")
            
        # 按近交系数排序 - 优先使用后代近交系数
        if '后代近交系数' in df.columns:
            # 将百分比格式的字符串转为数值进行排序
            df['后代近交系数_value'] = df['后代近交系数'].apply(lambda x: float(x.strip('%')) / 100 if isinstance(x, str) and '%' in x else 0.0)
            df = df.sort_values(by='后代近交系数_value', ascending=False)  # 降序：从大到小
            df = df.drop(columns=['后代近交系数_value'])
        elif '近交系数' in df.columns:
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
        for col in ['母牛号', '父号', '配种公牛号', '备选公牛号']:
            if col in df.columns:
                display_columns.append(col)

        # 如果有原始公牛号列，也添加（用于对比）
        for col in ['原始备选公牛号', '原始配种公牛号']:
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
        
        # 更新数据并预计算排序键
        self.beginResetModel()
        self.df = df
        self._precompute_sort_keys()
        
        # 为近交系数相关列设置默认降序排序状态
        self._set_default_sort_state()
        
        self.endResetModel()

    def _set_default_sort_state(self):
        """为近交系数相关列设置默认降序排序状态"""
        try:
            # 如果数据包含后代近交系数列，默认按此列降序排序
            if '后代近交系数' in self.df.columns and not self.df.empty:
                # 设置默认排序状态：后代近交系数列，降序
                self.sort_column = self.display_columns.index('后代近交系数') if '后代近交系数' in self.display_columns else -1
                self.sort_order = Qt.SortOrder.DescendingOrder
            # 如果只有近交系数列，按此列降序排序
            elif '近交系数' in self.df.columns and not self.df.empty:
                self.sort_column = self.display_columns.index('近交系数') if '近交系数' in self.display_columns else -1
                self.sort_order = Qt.SortOrder.DescendingOrder
            else:
                self.sort_column = -1
                self.sort_order = Qt.SortOrder.AscendingOrder
        except Exception as e:
            print(f"设置默认排序状态失败: {e}")
            self.sort_column = -1
            self.sort_order = Qt.SortOrder.AscendingOrder

    def _precompute_sort_keys(self):
        """预计算排序键以提高排序性能"""
        self._sort_cache.clear()

        if self.df.empty:
            return

        # 为百分比列预计算排序键
        percentage_columns = ['近交系数', '后代近交系数']
        for col in percentage_columns:
            if col in self.df.columns:
                def parse_percentage(x):
                    """
                    解析百分比值，支持多种格式：
                    - "3.54%" -> 3.54
                    - "0.0354" -> 3.54 (转换为百分比数值)
                    - 3.54 -> 3.54
                    - 0.0354 -> 3.54 (转换为百分比数值)
                    """
                    try:
                        if pd.isna(x) or x == '':
                            return -1.0

                        # 如果是字符串
                        if isinstance(x, str):
                            x_stripped = x.strip()
                            if '%' in x_stripped:
                                # "3.54%" -> 3.54
                                return float(x_stripped.rstrip('%'))
                            else:
                                # "0.0354" -> 3.54
                                val = float(x_stripped)
                                # 如果值小于1，认为是小数形式，需要乘以100
                                if 0 <= val < 1:
                                    return val * 100
                                return val
                        else:
                            # 如果是数字
                            val = float(x)
                            # 如果值小于1，认为是小数形式，需要乘以100
                            if 0 <= val < 1:
                                return val * 100
                            return val
                    except (ValueError, TypeError) as e:
                        print(f"解析百分比失败: {x} ({type(x).__name__}), 错误: {e}")
                        return -1.0

                sort_values = self.df[col].apply(parse_percentage).values
                self._sort_cache[col] = sort_values

                # 增强调试信息
                if col == '后代近交系数':
                    print(f"\n生成排序缓存 - {col}:")
                    print(f"  原始数据类型: {self.df[col].dtype}")
                    print(f"  原始前10个值: {self.df[col].head(10).tolist()}")
                    print(f"  排序键前10个值: {sort_values[:10]}")
                    print(f"  最大值: {sort_values.max():.4f}, 最小值: {sort_values.min():.4f}")
                    print(f"  唯一值数量: {len(set(sort_values))}")
                    # 检查是否有异常值
                    abnormal = [i for i, v in enumerate(sort_values[:20]) if v < 0]
                    if abnormal:
                        print(f"  警告：前20项中发现异常值（-1.0）在索引: {abnormal}")

    def _format_gene_value(self, value):
        """格式化基因值显示"""
        if value == 'C':
            return "携带者(C)"
        elif value == 'F':
            return "正常(F)"
        elif value == '高风险':
            return "高风险"
        elif value == '缺少公牛信息':
            return "缺少公牛信息"
        elif value == '缺少母牛父亲信息':
            return "缺少母牛父亲信息"
        elif value == '缺少双方信息':
            return "缺少双方信息"
        elif value == '仅公牛携带':
            return "仅公牛携带"
        elif value == '仅母牛父亲携带':
            return "仅母牛父亲携带"
        elif value == '-':
            return "-"
        return str(value)
            
    def _get_gene_background(self, value):
        """获取基因值对应的背景色"""
        colors = {
            '高风险': QBrush(QColor(255, 200, 200)),  # 浅红色
            '缺少公牛信息': QBrush(QColor(245, 245, 245)),  # 浅灰色
            '缺少母牛父亲信息': QBrush(QColor(245, 245, 245)),  # 浅灰色
            '缺少双方信息': QBrush(QColor(220, 220, 220)),  # 深浅灰色
            '仅公牛携带': QBrush(QColor(255, 220, 200)),  # 浅橙色
            '仅母牛父亲携带': QBrush(QColor(255, 220, 200)),  # 浅橙色
            '-': QBrush(QColor(200, 255, 200))  # 浅绿色
        }
        return colors.get(value)

    def sort(self, column: int, order: Qt.SortOrder) -> None:
        """实现排序功能 - 高性能优化版本"""
        try:
            if self.df.empty:
                return

            # 移除跳过逻辑，确保每次点击都会执行排序
            # （用户点击列头时期望看到排序效果）

            self.layoutAboutToBeChanged.emit()
            
            # 获取列名
            if 0 <= column < len(self.display_columns):
                column_name = self.display_columns[column]
                
                # 检查该列是否存在于DataFrame中
                if column_name not in self.df.columns:
                    print(f"警告: 列 '{column_name}' 不存在于DataFrame中")
                    self.layoutChanged.emit()
                    return
                
                # 优化：如果是近交系数或后代近交系数列，使用预计算的排序键
                if column_name in ['近交系数', '后代近交系数'] and column_name in self._sort_cache:
                    # 使用预计算的排序键，性能更好
                    try:
                        import numpy as np
                        sort_keys = self._sort_cache[column_name]
                        sorted_indices = np.argsort(sort_keys)

                        # 对于近交系数和后代近交系数，默认降序（从大到小）更有意义
                        if order == Qt.SortOrder.AscendingOrder:
                            # 如果用户明确要求升序，则保持升序
                            pass  # sorted_indices 已经是升序
                        else:
                            # 默认或明确要求降序，则降序
                            sorted_indices = sorted_indices[::-1]

                        self.df = self.df.iloc[sorted_indices].reset_index(drop=True)

                        # 增强调试信息
                        print(f"\n===== 排序调试信息 =====")
                        print(f"列名: '{column_name}'")
                        print(f"排序方向: {'升序 (小→大)' if order == Qt.SortOrder.AscendingOrder else '降序 (大→小)'}")
                        print(f"数据总行数: {len(sort_keys)}")
                        if len(sorted_indices) > 0:
                            print(f"排序键前10项: {sort_keys[sorted_indices[:10]]}")
                            print(f"对应原始值前10项: {self.df[column_name].head(10).tolist()}")
                            print(f"排序键最大值: {sort_keys.max():.4f}, 最小值: {sort_keys.min():.4f}")
                        print(f"=====================\n")
                            
                    except Exception as e:
                        print(f"使用缓存排序失败，回退到普通排序: {e}")
                        # 回退到标准排序
                        # 对于近交系数列，默认降序更有意义
                        default_ascending = False if column_name in ['近交系数', '后代近交系数'] else True
                        actual_ascending = (order == Qt.SortOrder.AscendingOrder) if order != Qt.SortOrder.DescendingOrder else (not default_ascending)
                        
                        self.df = self.df.sort_values(
                            by=column_name,
                            ascending=actual_ascending,
                            na_position='first'
                        ).reset_index(drop=True)
                else:
                    # 对于其他列，使用标准排序，但确保索引重置
                    self.df = self.df.sort_values(
                        by=column_name,
                        ascending=(order == Qt.SortOrder.AscendingOrder),
                        na_position='first'  # 空值排在前面
                    ).reset_index(drop=True)
                
                # 保存当前排序状态
                self.sort_column = column
                self.sort_order = order
            
            self.layoutChanged.emit()
        except Exception as e:
            print(f"排序时发生错误: {e}")
            import traceback
            traceback.print_exc()
            self.layoutChanged.emit()


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