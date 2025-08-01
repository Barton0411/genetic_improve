from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QTableView, QFrame, QSplitter, QMessageBox, QApplication,
    QMainWindow, QDialog, QTabWidget, QComboBox, QListWidget, QListWidgetItem, QTextEdit, QHeaderView, QMenu, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QStandardItemModel, QStandardItem
import pandas as pd
import logging
from pathlib import Path
from sqlalchemy import create_engine, text
import datetime
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib import font_manager
from typing import List, Dict, Tuple, Set, Optional
import math
import time
import platform
import os

# 设置matplotlib中文字体
def setup_chinese_font():
    """设置matplotlib的中文字体支持"""
    system = platform.system()
    
    if system == 'Darwin':  # macOS
        # 尝试多个字体路径
        font_paths = [
            '/Library/Fonts/Arial Unicode.ttf',
            '/System/Library/Fonts/STHeiti Light.ttc',
            '/System/Library/Fonts/STHeiti Medium.ttc',
            '/System/Library/Fonts/Helvetica.ttc'
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    # 添加字体到matplotlib
                    font_manager.fontManager.addfont(font_path)
                    # 获取字体名称
                    font = font_manager.FontProperties(fname=font_path)
                    font_name = font.get_name()
                    # 设置为默认字体
                    plt.rcParams['font.sans-serif'] = [font_name, 'DejaVu Sans']
                    plt.rcParams['axes.unicode_minus'] = False
                    return font_path
                except Exception:
                    continue
                    
    elif system == 'Windows':  # Windows
        # Windows系统的中文字体
        chinese_fonts = [
            'Microsoft YaHei',      # 微软雅黑
            'SimHei',              # 黑体
            'SimSun',              # 宋体
            'Microsoft JhengHei',   # 微软正黑体
            'FangSong',            # 仿宋
            'KaiTi',               # 楷体
            'NSimSun'              # 新宋体
        ]
        
        # 尝试设置中文字体
        for font_name in chinese_fonts:
            try:
                # 检查字体是否存在
                font_list = [f.name for f in font_manager.fontManager.ttflist]
                if font_name in font_list:
                    plt.rcParams['font.sans-serif'] = [font_name, 'DejaVu Sans']
                    plt.rcParams['axes.unicode_minus'] = False
                    import logging
                    logging.info(f"Using Chinese font: {font_name}")
                    return font_name
            except Exception as e:
                import logging
                logging.warning(f"Failed to set font {font_name}: {e}")
                continue
        
        # 如果没有找到合适的中文字体，尝试使用系统字体文件
        windows_font_paths = [
            'C:/Windows/Fonts/msyh.ttc',     # 微软雅黑
            'C:/Windows/Fonts/simhei.ttf',   # 黑体
            'C:/Windows/Fonts/simsun.ttc',   # 宋体
        ]
        
        for font_path in windows_font_paths:
            if os.path.exists(font_path):
                try:
                    font_manager.fontManager.addfont(font_path)
                    font = font_manager.FontProperties(fname=font_path)
                    font_name = font.get_name()
                    plt.rcParams['font.sans-serif'] = [font_name, 'DejaVu Sans']
                    plt.rcParams['axes.unicode_minus'] = False
                    import logging
                    logging.info(f"Using Chinese font from file: {font_path}")
                    return font_name  # 返回字体名称而不是路径
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to load font from {font_path}: {e}")
                    continue
                    
    # 默认设置（如果找不到中文字体）
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    import logging
    logging.warning("No Chinese font found, using default font")
    return None

# 初始化时调用
CHINESE_FONT_PATH = setup_chinese_font()

def get_chinese_font_prop(size=10, weight='normal'):
    """获取中文字体属性，如果没有找到中文字体则返回None"""
    # Windows系统优先使用字体族名称，避免路径问题
    if platform.system() == 'Windows':
        # 使用plt.rcParams中设置的字体
        font_names = plt.rcParams['font.sans-serif']
        if font_names and font_names[0] != 'DejaVu Sans':
            try:
                return font_manager.FontProperties(family=font_names[0], size=size, weight=weight)
            except Exception as e:
                logging.warning(f"Failed to use font family {font_names[0]}: {e}")
    
    # 其他系统或Windows失败时，尝试使用字体文件路径
    if CHINESE_FONT_PATH and isinstance(CHINESE_FONT_PATH, str) and os.path.exists(CHINESE_FONT_PATH):
        try:
            return font_manager.FontProperties(fname=CHINESE_FONT_PATH, size=size, weight=weight)
        except Exception as e:
            logging.warning(f"Failed to use font file {CHINESE_FONT_PATH}: {e}")
    
    return None

from .models import InbreedingDetailModel, AbnormalDetailModel, StatisticsModel
from gui.progress import ProgressDialog
from core.data.update_manager import (
    CLOUD_DB_HOST, CLOUD_DB_PORT, CLOUD_DB_USER, 
    CLOUD_DB_PASSWORD, CLOUD_DB_NAME, LOCAL_DB_PATH, get_pedigree_db
)

class PedigreeDialog(QDialog):
    """血缘关系图对话框"""
    def __init__(self, cow_id, sire_id, bull_id, parent=None, inbreeding_details=None, offspring_details=None):
        super().__init__(parent)
        self.cow_id = cow_id
        self.sire_id = sire_id
        self.bull_id = bull_id
        self.parent_widget = parent
        self.inbreeding_details = inbreeding_details  # 母牛近交详情
        self.offspring_details = offspring_details    # 后代近交详情
        self.setup_ui()
        
    def setup_ui(self):
        """初始化UI"""
        self.setWindowTitle(f"血缘关系图 - 母牛: {self.cow_id}")
        self.resize(1200, 800)  # 增加默认窗口大小
        
        layout = QVBoxLayout(self)
        
        # 添加标题标签
        title_label = QLabel(f"母牛: {self.cow_id} - 父号: {self.sire_id} - 配种公牛: {self.bull_id}")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)
        
        # 上部分 - 近交系数信息
        upper_widget = QWidget()
        upper_layout = QVBoxLayout(upper_widget)
        
        # 添加后代近交系数显示
        offspring_inbreeding = 0.0
        if self.bull_id and self.offspring_details and 'system' in self.offspring_details:
            offspring_inbreeding = self.offspring_details['system']
            self.offspring_label = QLabel(f"潜在后代近交系数: {offspring_inbreeding:.2%}")
            self.offspring_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # 对于高近交系数使用红色警示文本
            if offspring_inbreeding > 0.0625:  # 6.25%
                self.offspring_label.setStyleSheet("font-weight: bold; font-size: 14px; color: red;")
            else:
                self.offspring_label.setStyleSheet("font-weight: bold; font-size: 14px;")
                
            upper_layout.addWidget(self.offspring_label)
            
            # 如果检测到直接血缘关系，显示警告
            if self.bull_id == self.sire_id:
                warning_label = QLabel("⚠️ 警告: 配种公牛与母牛的父亲相同，存在直系血亲关系!")
                warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                warning_label.setStyleSheet("font-weight: bold; font-size: 14px; color: red;")
                upper_layout.addWidget(warning_label)
        
        # 创建图形画布
        self.figure = Figure(figsize=(10, 8))  # 增加画布大小
        self.canvas = FigureCanvas(self.figure)
        upper_layout.addWidget(self.canvas)
        
        # 添加双击事件处理
        self.canvas.mpl_connect('button_press_event', self.on_canvas_click)
        
        splitter.addWidget(upper_widget)
        
        # 下部分 - 近交详情表格
        lower_widget = QWidget()
        lower_layout = QVBoxLayout(lower_widget)
        
        # 创建标签页
        tab_widget = QTabWidget()
        lower_layout.addWidget(tab_widget)
        
        # 潜在后代近交详情标签页
        if self.bull_id and self.offspring_details:
            offspring_tab = QWidget()
            offspring_layout = QVBoxLayout(offspring_tab)
            self.create_inbreeding_details_widget(offspring_layout, self.offspring_details, "潜在后代近交详情")
            tab_widget.addTab(offspring_tab, "潜在后代近交详情")
            
            # 添加计算过程标签页
            calc_tab = QWidget()
            calc_layout = QVBoxLayout(calc_tab)
            self.create_calculation_process_widget(calc_layout, self.offspring_details)
            tab_widget.addTab(calc_tab, "计算过程")
        
        splitter.addWidget(lower_widget)
        
        # 设置分割器比例
        splitter.setStretchFactor(0, 3)  # 上部分占比较大
        splitter.setStretchFactor(1, 2)
        
        # 添加关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        
        # 绘制血缘关系图
        self.draw_pedigree(max_generations=3)  # 默认显示3代
    
    def create_inbreeding_details_widget(self, layout, details, title):
        """创建显示近交详情的组件"""
        if not details or 'common_ancestors' not in details:
            layout.addWidget(QLabel("没有找到近交详情"))
            return
            
        # 标题
        label = QLabel(title)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        
        # 创建显示共同祖先的表格
        table = QTableView()
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["共同祖先", "贡献度", "贡献百分比", "占比"])
        
        # 对共同祖先按贡献排序
        sorted_ancestors = sorted(details['common_ancestors'].items(), key=lambda x: x[1], reverse=True)
        
        total_inbreeding = details.get('system', 0.0)
        
        for i, (ancestor_id, contribution) in enumerate(sorted_ancestors):
            if contribution < 0.001:  # 贡献小于0.1%的祖先不显示
                continue
                
            contribution_percent = contribution * 100
            total_percent = (contribution / total_inbreeding) * 100 if total_inbreeding > 0 else 0
            
            model.setItem(i, 0, QStandardItem(str(ancestor_id)))
            model.setItem(i, 1, QStandardItem(f"{contribution:.4f}"))
            model.setItem(i, 2, QStandardItem(f"{contribution_percent:.2f}%"))
            model.setItem(i, 3, QStandardItem(f"{total_percent:.1f}%"))
        
        table.setModel(model)
        table.horizontalHeader().setStretchLastSection(True)
        table.resizeColumnsToContents()
        layout.addWidget(table)
        
        # 显示路径详情
        if 'paths' in details:
            path_label = QLabel("选择共同祖先查看路径详情:")
            layout.addWidget(path_label)
            
            # 选择共同祖先的下拉框
            ancestor_combo = QComboBox()
            for ancestor_id, contribution in sorted_ancestors:
                if contribution >= 0.001:  # 只显示贡献大于0.1%的祖先
                    contribution_percent = contribution * 100
                    ancestor_combo.addItem(f"{ancestor_id} - {contribution_percent:.2f}%", ancestor_id)
            
            layout.addWidget(ancestor_combo)
            
            # 路径列表
            path_list = QListWidget()
            layout.addWidget(path_list)
            
            # 路径详情文本框
            path_detail = QTextEdit()
            path_detail.setReadOnly(True)
            path_detail.setMaximumHeight(100)
            layout.addWidget(path_detail)
            
            # 连接下拉框选择变化信号
            def on_ancestor_selected(index):
                if index < 0:
                    return
                    
                ancestor_id = ancestor_combo.itemData(index)
                path_list.clear()
                
                if ancestor_id in details['paths']:
                    ancestor_paths = details['paths'][ancestor_id]
                    for i, (path_str, path_contrib) in enumerate(ancestor_paths):
                        path_percent = path_contrib * 100
                        item = QListWidgetItem(f"路径 {i+1}: {path_contrib:.6f} ({path_percent:.4f}%)")
                        item.setData(Qt.ItemDataRole.UserRole, path_str)
                        path_list.addItem(item)
            
            # 连接路径列表选择变化信号
            def on_path_selected():
                items = path_list.selectedItems()
                if not items:
                    return
                    
                path_str = items[0].data(Qt.ItemDataRole.UserRole)
                path_detail.setText(path_str)
            
            ancestor_combo.currentIndexChanged.connect(on_ancestor_selected)
            path_list.itemSelectionChanged.connect(on_path_selected)
            
            # 初始选择第一个祖先
            if ancestor_combo.count() > 0:
                ancestor_combo.setCurrentIndex(0)
    
    def create_calculation_process_widget(self, layout, details):
        """创建显示近交系数计算过程的组件"""
        if not details or 'common_ancestors' not in details:
            layout.addWidget(QLabel("没有找到计算详情"))
            return
            
        # 创建HTML内容显示计算过程
        html_content = self._generate_calculation_html(details)
        
        # 创建文本浏览器显示HTML
        text_browser = QTextEdit()
        text_browser.setHtml(html_content)
        text_browser.setReadOnly(True)
        layout.addWidget(text_browser)
    
    def _generate_calculation_html(self, details):
        """生成近交系数计算过程的HTML内容"""
        html_content = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; padding: 10px; }
                h2 { color: #2c3e50; }
                h3 { color: #34495e; margin-top: 15px; }
                .formula { 
                    background-color: #f0f0f0; 
                    padding: 10px; 
                    margin: 10px 0;
                    font-family: 'Courier New', monospace;
                    border-radius: 5px;
                    border: 1px solid #ddd;
                }
                .ancestor { 
                    background-color: #e8f4f8; 
                    padding: 8px; 
                    margin: 8px 0;
                    border-left: 3px solid #3498db;
                }
                .warning { color: #e74c3c; font-weight: bold; }
                .result { 
                    background-color: #d5f4e6; 
                    padding: 10px; 
                    margin: 15px 0;
                    font-weight: bold;
                    border-radius: 5px;
                }
                table { border-collapse: collapse; width: 100%; margin: 10px 0; }
                th { background-color: #3498db; color: white; padding: 8px; text-align: left; }
                td { border: 1px solid #ddd; padding: 8px; }
                tr:nth-child(even) { background-color: #f2f2f2; }
                .contribution { color: #27ae60; font-weight: bold; }
                .path-info { font-size: 0.9em; color: #666; }
            </style>
        </head>
        <body>
        """
        
        # 添加标题
        html_content += f"<h2>近交系数计算过程</h2>"
        
        # 添加基本信息
        total_inbreeding = details.get('system', 0.0)
        html_content += f"<p><strong>母牛:</strong> {self.cow_id}</p>"
        html_content += f"<p><strong>配种公牛:</strong> {self.bull_id}</p>"
        html_content += f"<div class='result'>计算结果: F = {total_inbreeding:.4f} ({total_inbreeding*100:.2f}%)</div>"
        
        # 添加Wright公式说明
        html_content += """
        <h3>计算公式 (Wright公式)</h3>
        <div class='formula'>
            F = Σ [(1/2)^(n₁+n₂+1) × (1 + F_CA)]<br>
            <br>
            其中：<br>
            - n₁ = 从父亲到共同祖先的世代数<br>
            - n₂ = 从母亲到共同祖先的世代数<br>
            - F_CA = 共同祖先的近交系数（如果有GIB值则使用，否则为0）<br>
            - Σ = 对所有共同祖先求和
        </div>
        """
        
        # 添加计算步骤
        html_content += "<h3>计算步骤</h3>"
        
        if 'common_ancestors' in details and details['common_ancestors']:
            # 创建表格显示每个共同祖先的贡献
            html_content += """
            <table>
                <tr>
                    <th>共同祖先</th>
                    <th>路径长度(n₁+n₂)</th>
                    <th>祖先近交系数(F_CA)</th>
                    <th>计算公式</th>
                    <th>贡献值</th>
                    <th>贡献率</th>
                </tr>
            """
            
            # 对共同祖先按贡献排序
            sorted_ancestors = sorted(details['common_ancestors'].items(), 
                                    key=lambda x: x[1], reverse=True)
            
            for ancestor_id, contribution in sorted_ancestors:
                if contribution < 0.0001:  # 忽略太小的贡献
                    continue
                
                # 获取路径信息（如果有）
                path_info = ""
                ancestor_f = 0.0
                path_lengths = "未知"
                
                if 'paths' in details and ancestor_id in details['paths']:
                    # 从路径信息中提取长度（简化显示）
                    paths = details['paths'][ancestor_id]
                    if paths:
                        # 假设路径格式中包含长度信息
                        path_info = f"<br><span class='path-info'>共{len(paths)}条路径</span>"
                
                # 计算贡献百分比
                contribution_percent = (contribution / total_inbreeding * 100) if total_inbreeding > 0 else 0
                
                # 构建表格行
                html_content += f"""
                <tr>
                    <td>{ancestor_id}{path_info}</td>
                    <td>{path_lengths}</td>
                    <td>{ancestor_f:.4f}</td>
                    <td>(1/2)^(n₁+n₂+1) × (1 + {ancestor_f:.4f})</td>
                    <td class='contribution'>{contribution:.6f}</td>
                    <td>{contribution_percent:.2f}%</td>
                </tr>
                """
            
            html_content += "</table>"
            
            # 添加总结
            html_content += f"""
            <h3>计算总结</h3>
            <p>共找到 <strong>{len(details['common_ancestors'])}</strong> 个共同祖先</p>
            <p>近交系数总和: <strong class='result'>F = {total_inbreeding:.4f} ({total_inbreeding*100:.2f}%)</strong></p>
            """
            
            # 添加解释
            if total_inbreeding > 0.0625:
                html_content += "<p class='warning'>⚠️ 注意：近交系数超过6.25%，建议谨慎考虑此配对</p>"
            elif total_inbreeding > 0.03125:
                html_content += "<p style='color: #f39c12;'>⚠️ 提示：近交系数超过3.125%，需要注意潜在风险</p>"
            else:
                html_content += "<p style='color: #27ae60;'>✓ 近交系数在安全范围内</p>"
                
        else:
            html_content += "<p>未找到共同祖先，近交系数为0</p>"
        
        html_content += """
        </body>
        </html>
        """
        
        return html_content
        
    def get_project_path(self):
        """获取项目路径"""
        if hasattr(self.parent_widget, 'get_project_path'):
            return self.parent_widget.get_project_path()
        return None
        
    def draw_pedigree(self, max_generations=3):
        """绘制血缘关系图 - 横向展开，父亲在上，母亲在下"""
        # 清空现有的图表
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        try:
            # 字体已在文件开头初始化
            plt.rcParams['font.size'] = 14  # 增大默认字体大小
            
            # 在Windows上重新设置字体，避免字体缓存问题
            if platform.system() == 'Windows':
                import matplotlib
                matplotlib.rcParams['font.sans-serif'] = plt.rcParams['font.sans-serif']
                matplotlib.rcParams['axes.unicode_minus'] = False
            
            # 获取系谱库实例
            from core.data.update_manager import get_pedigree_db
            pedigree_db = get_pedigree_db()
            
            # 查询NAAB号码
            naab_dict = self.query_naab_numbers(pedigree_db)
            
            # 初始化共同祖先集合
            common_ancestors = set()
            if self.offspring_details and 'common_ancestors' in self.offspring_details:
                common_ancestors = set(self.offspring_details['common_ancestors'].keys())
            
            # 检查特殊情况：如果配种公牛就是母牛的父亲，添加到共同祖先
            cow_info = pedigree_db.pedigree.get(self.cow_id, {})
            cow_father = cow_info.get('sire', '')
            if self.bull_id and cow_father and self.bull_id == cow_father:
                common_ancestors.add(self.bull_id)
                print(f"检测到直系血亲关系：公牛 {self.bull_id} 是母牛 {self.cow_id} 的父亲，将其添加为共同祖先")
            
            # 节点尺寸和间距
            node_width = 5.0   # 进一步增加方框宽度
            node_height = 3.5   # 增加方框高度
            h_spacing = 6.0    # 增加水平间距
            min_spacing = 0.6   # 增加最小垂直间距
            
            # 计算画布总高度
            last_gen_nodes = 2 ** max_generations
            total_height = (node_height + min_spacing) * last_gen_nodes
            
            # 计算每代节点的间距
            v_spacings = {}
            for gen in range(1, max_generations + 1):
                nodes_in_gen = 2 ** gen
                node_alloc_height = total_height / nodes_in_gen
                v_spacings[gen] = node_alloc_height - node_height
            
            # 节点集合，格式为：{(代数,位置ID): (x坐标,y坐标,节点ID)}
            # 位置ID: 从上到下递增的数字，用于标识同代内的位置顺序
            self.nodes = {}
            
            # 边集合，格式为：[(起点x, 起点y, 终点x, 终点y)]
            edges = []
            
            # 构建节点之间的父子关系字典
            # 用于后续过滤共同祖先，避免标记同一条线上多个祖先
            parent_child_paths = {}  # 存储 (子节点,父/母节点) -> 路径索引
            
            # 记录每个位置节点的祖先路径
            # 格式: {(gen, pos): [ancestor1, ancestor2, ...]}，用于确定共同祖先是否在同一线上
            node_ancestors = {}
            
            # 逐代处理所有节点
            # 初始化第0代 - 预期后代
            self.nodes[(0, 0)] = (0, 0, "预期后代")
            node_ancestors[(0, 0)] = []
            
            # 第1代 - 父亲和母亲
            # 计算第1代的节点分配高度和垂直间距
            gen1_spacing = v_spacings[1]
            half_spacing = gen1_spacing / 2
            
            # 父亲位置（上方）
            self.nodes[(1, 0)] = (h_spacing, half_spacing, self.bull_id)
            node_ancestors[(1, 0)] = [self.bull_id]
            
            # 母亲位置（下方）
            self.nodes[(1, 1)] = (h_spacing, -half_spacing, self.cow_id)
            node_ancestors[(1, 1)] = [self.cow_id]
            
            # 添加从预期后代到父母的连接
            edges.append((node_width/2, 0, h_spacing-node_width/2, half_spacing))    # 到父亲
            parent_child_paths[((0, 0), (1, 0))] = 0  # 添加路径索引
            
            edges.append((node_width/2, 0, h_spacing-node_width/2, -half_spacing))   # 到母亲
            parent_child_paths[((0, 0), (1, 1))] = 1  # 添加路径索引
            
            # 递归构建系谱树
            def build_pedigree(gen, position, animal_id):
                """递归构建系谱树
                Args:
                    gen: 当前代数
                    position: 当前位置ID
                    animal_id: 动物ID
                """
                if gen >= max_generations:
                    return
                
                # 获取当前节点的坐标和祖先列表
                x, y, _ = self.nodes[(gen, position)]
                current_ancestors = node_ancestors.get((gen, position), [])
                
                # 获取祖先信息
                node_info = pedigree_db.pedigree.get(animal_id, {})
                sire_id = node_info.get('sire', f'父亲未知')
                dam_id = node_info.get('dam', f'母亲未知')
                
                # 计算下一代位置
                next_gen = gen + 1
                next_x = x + h_spacing
                
                # 计算实际垂直间距 - 基于下一代的总分配高度
                next_gen_spacing = v_spacings[next_gen]
                
                # 每个节点在该代占据的网格位置
                grid_size = 2 ** (max_generations - next_gen)
                
                # 父亲位置（上方）- 每两个位置就会用掉一个父亲位置
                sire_position = position * 2
                # 计算在全局布局中的位置
                sire_global_pos = sire_position * grid_size
                # 计算y坐标 - 以画布中心为原点，向上为正
                sire_y = (total_height / 2) - (sire_global_pos + grid_size / 2) * (node_height + min_spacing)
                self.nodes[(next_gen, sire_position)] = (next_x, sire_y, sire_id)
                
                # 创建父亲节点的祖先列表 (当前祖先 + 父亲自己)
                sire_ancestors = current_ancestors + [sire_id]
                node_ancestors[(next_gen, sire_position)] = sire_ancestors
                
                # 母亲位置（下方）
                dam_position = position * 2 + 1
                # 计算在全局布局中的位置
                dam_global_pos = dam_position * grid_size
                # 计算y坐标
                dam_y = (total_height / 2) - (dam_global_pos + grid_size / 2) * (node_height + min_spacing)
                self.nodes[(next_gen, dam_position)] = (next_x, dam_y, dam_id)
                
                # 创建母亲节点的祖先列表 (当前祖先 + 母亲自己)
                dam_ancestors = current_ancestors + [dam_id]
                node_ancestors[(next_gen, dam_position)] = dam_ancestors
                
                # 添加连接线
                edges.append((x+node_width/2, y, next_x-node_width/2, sire_y))    # 到父亲
                parent_child_paths[((gen, position), (next_gen, sire_position))] = len(edges) - 1
                
                edges.append((x+node_width/2, y, next_x-node_width/2, dam_y))     # 到母亲
                parent_child_paths[((gen, position), (next_gen, dam_position))] = len(edges) - 1
                
                # 递归处理下一代
                build_pedigree(next_gen, sire_position, sire_id)
                build_pedigree(next_gen, dam_position, dam_id)
            
            # 从第一代递归构建
            build_pedigree(1, 0, self.bull_id)  # 从父亲开始
            build_pedigree(1, 1, self.cow_id)   # 从母亲开始
            
            # 过滤共同祖先，每条血缘路径上只保留最接近的一个
            filtered_common_ancestors = set()
            
            # 保存前3代共同祖先的调试信息
            early_gen_ancestors = []
            for gen in range(1, 4):  # 前3代
                gen_ancestors = []
                for (g, pos), ancestors in node_ancestors.items():
                    if g == gen:
                        # 找出这个节点中的所有共同祖先
                        ca_in_node = [a for a in ancestors if a in common_ancestors]
                        if ca_in_node:
                            gen_ancestors.extend(ca_in_node)
                if gen_ancestors:
                    early_gen_ancestors.append((gen, list(set(gen_ancestors))))
            
            # 打印前3代共同祖先
            print("前3代的共同祖先检查:")
            for gen, ancestors in early_gen_ancestors:
                print(f"  第{gen}代共同祖先: {', '.join(ancestors)}")
            
            # 为每个节点找出血缘路径上最近的共同祖先
            for (gen, pos), ancestors in node_ancestors.items():
                # 找出当前节点祖先路径上的所有共同祖先
                path_common_ancestors = [a for a in ancestors if a in common_ancestors]
                # 记录这个节点上全部找到的共同祖先
                if path_common_ancestors and gen <= 3:  # 前3代显示更多调试信息
                    print(f"节点({gen},{pos})的共同祖先: {', '.join(path_common_ancestors)}")
                
                # 如果有共同祖先，只保留最近的一个
                if path_common_ancestors:
                    # 第1-2代的所有共同祖先都保留，不过滤
                    if gen <= 2:
                        for ca in path_common_ancestors:
                            filtered_common_ancestors.add(ca)
                            print(f"添加第{gen}代共同祖先(不过滤): {ca}")
                    else:
                        # 第3代及以上按照最近祖先进行过滤
                        # 最近的共同祖先是列表中的第一个，因为祖先列表是从近到远
                        nearest_ca = path_common_ancestors[0]
                        filtered_common_ancestors.add(nearest_ca)
                        print(f"添加第{gen}代最近共同祖先: {nearest_ca}")
                        if len(path_common_ancestors) > 1:
                            print(f"  过滤掉了以下更远共同祖先: {', '.join(path_common_ancestors[1:])}")
            
            # 确保公牛和母牛如果是共同祖先，也被包含在过滤后的集合中
            if self.bull_id in common_ancestors:
                filtered_common_ancestors.add(self.bull_id)
                print(f"添加公牛 {self.bull_id} 到过滤后的共同祖先集合")
            
            if self.cow_id in common_ancestors:
                filtered_common_ancestors.add(self.cow_id)
                print(f"添加母牛 {self.cow_id} 到过滤后的共同祖先集合")
            
            # 最终共同祖先列表
            print(f"过滤前共同祖先数量: {len(common_ancestors)}")
            print(f"过滤后共同祖先数量: {len(filtered_common_ancestors)}")
            if len(filtered_common_ancestors) > 0:
                print(f"过滤后共同祖先列表: {', '.join(filtered_common_ancestors)}")
            
            # 为共同祖先分配颜色
            common_ancestor_colors = {}
            color_options = ['#FF9999', '#99FF99', '#9999FF', '#FFFF99', '#FF99FF', '#99FFFF']
            
            for i, ancestor in enumerate(common_ancestors):
                color_idx = i % len(color_options)
                common_ancestor_colors[ancestor] = color_options[color_idx]
            
            # 绘制边（连接线）
            for start_x, start_y, end_x, end_y in edges:
                ax.plot([start_x, end_x], [start_y, end_y], color='green', linewidth=1.0, zorder=1)
            
            # 绘制节点（方框）
            for (gen, pos), (x, y, node_id) in self.nodes.items():
                # 确定方框颜色
                if node_id == "预期后代":
                    facecolor = 'lightgreen'
                    edgecolor = 'green'
                    text_color = 'black'
                elif node_id in filtered_common_ancestors:
                    facecolor = common_ancestor_colors[node_id]
                    edgecolor = 'red'  # 共同祖先使用红色边框
                    text_color = 'black'
                elif pos % 2 == 0:  # 父系（偶数位置）
                    facecolor = '#444444'  # 深灰色
                    edgecolor = '#333333'
                    text_color = 'white'
                else:  # 母系（奇数位置）
                    facecolor = 'white'  # 无底色
                    edgecolor = 'gray'
                    text_color = 'black'
                
                # 绘制方框
                rect = plt.Rectangle(
                    (x - node_width/2, y - node_height/2),
                    node_width, node_height,
                    facecolor=facecolor,
                    edgecolor=edgecolor,
                    linewidth=1.0,
                    zorder=2,
                    alpha=0.9,
                )
                ax.add_patch(rect)
                
                # 获取NAAB号
                naab = naab_dict.get(node_id, "")
                
                # 显示完整的ID和NAAB号
                display_text = str(node_id)
                naab_text = str(naab) if naab else ""
                
                # 设置文本大小
                naab_fontsize = 9 if gen <= 2 else 7.5  # NAAB号字体大小
                reg_fontsize = 6 if gen <= 2 else 5     # REG号字体大小
                
                # 计算文本垂直位置
                # 框高为node_height，框的中心点为y
                # 框的上边界为y+node_height/2，下边界为y-node_height/2
                
                # REG位于下部，从框下边界向上17.5%处，即下边界+0.175*node_height
                reg_y_position = y - node_height/2 + node_height * 0.175
                
                # NAAB位于上部，从框上边界向下32.5%处，即上边界-0.325*node_height
                naab_y_position = y + node_height/2 - node_height * 0.325
                
                # 在方框中显示REG号（下部）
                text_font = get_chinese_font_prop(size=reg_fontsize)
                if text_font:
                    ax.text(
                        x, reg_y_position,  # REG号位置，框的下部
                        display_text,
                        fontproperties=text_font,
                        ha='center',
                        va='center',
                        color=text_color,
                        zorder=3
                    )
                else:
                    ax.text(
                        x, reg_y_position,  # REG号位置，框的下部
                        display_text,
                        ha='center',
                        va='center',
                        fontsize=reg_fontsize,
                        color=text_color,
                        zorder=3
                    )
                
                # 在方框中显示NAAB号（上部）（加粗显示）
                if naab and node_id not in ["预期后代", "父亲未知", "母亲未知"]:
                    naab_font = get_chinese_font_prop(size=naab_fontsize, weight='bold')
                    if naab_font:
                        ax.text(
                            x, naab_y_position,  # NAAB号位置，框的上部
                            naab_text,
                            fontproperties=naab_font,
                            ha='center',
                            va='center',
                            color=text_color,
                            zorder=3
                        )
                    else:
                        ax.text(
                            x, naab_y_position,  # NAAB号位置，框的上部
                            naab_text,
                            ha='center',
                            va='center',
                            fontsize=naab_fontsize,
                            fontweight='bold',
                            color=text_color,
                            zorder=3
                        )
            
            # 设置图表属性
            # 使用系统字体设置标题
            title_font = get_chinese_font_prop(size=18)
            if title_font:
                ax.set_title("血缘关系图 (6代)", fontproperties=title_font)
            else:
                ax.set_title("血缘关系图 (6代)", fontsize=18)
            ax.axis('off')  # 隐藏坐标轴
            
            # 自动调整布局，适应所有节点
            all_xs = [x for (_, _), (x, _, _) in self.nodes.items()]
            all_ys = [y for (_, _), (_, y, _) in self.nodes.items()]
            
            # 确保有足够的边距
            x_margin = 1.0
            y_margin = 3.0
            
            ax.set_xlim(min(all_xs) - node_width/2 - x_margin, max(all_xs) + node_width/2 + x_margin)
            ax.set_ylim(min(all_ys) - node_height/2 - y_margin, max(all_ys) + node_height/2 + y_margin)
            
            # 添加缩放和平移功能
            def on_scroll(event):
                """鼠标滚轮和触控板缩放事件处理"""
                # 获取当前缩放比例
                cur_xlim = ax.get_xlim()
                cur_ylim = ax.get_ylim()
                cur_xrange = (cur_xlim[1] - cur_xlim[0]) * 0.5
                cur_yrange = (cur_ylim[1] - cur_ylim[0]) * 0.5
                xdata = event.xdata  # 获取鼠标x坐标
                ydata = event.ydata  # 获取鼠标y坐标
                
                if xdata is None or ydata is None:
                    return
                
                # 获取滚轮步进值
                steps = event.step
                
                # 检测是否为触控板手势（步进值通常小于1）
                if abs(steps) < 1:
                    # 触控板双指缩放，使用更平滑的缩放
                    if steps > 0:
                        scale_factor = 1 - steps * 0.05  # 放大
                    else:
                        scale_factor = 1 - steps * 0.05  # 缩小
                else:
                    # 传统鼠标滚轮
                    if event.button == 'up':  # 放大
                        scale_factor = 0.8
                    else:  # 缩小
                        scale_factor = 1.25
                
                # 限制缩放范围
                new_xrange = cur_xrange * scale_factor
                new_yrange = cur_yrange * scale_factor
                
                # 防止过度缩放
                if new_xrange < 0.5 or new_xrange > 50:
                    return
                
                # 设置新的缩放范围
                ax.set_xlim([xdata - new_xrange, xdata + new_xrange])
                ax.set_ylim([ydata - new_yrange, ydata + new_yrange])
                
                # 重新绘制图表
                self.canvas.draw_idle()
            
            # 添加滚轮事件
            self.canvas.mpl_connect('scroll_event', lambda event: on_scroll(event))
            
            # 添加鼠标平移功能
            self.pan_enabled = False
            self.pan_start_xy = None
            
            def on_press(event):
                """鼠标按下事件处理"""
                if event.button == 1:  # 左键
                    self.pan_enabled = True
                    self.pan_start_xy = (event.xdata, event.ydata)
            
            def on_release(event):
                """鼠标释放事件处理"""
                if event.button == 1:  # 左键
                    self.pan_enabled = False
                    self.pan_start_xy = None
            
            def on_motion(self, event):
                """鼠标移动事件处理"""
                if self.pan_enabled and self.pan_start_xy is not None:
                    ax = self.figure.get_axes()[0]
                    
                    if event.xdata is None or event.ydata is None:
                        return
                        
                    dx = event.xdata - self.pan_start_xy[0]
                    dy = event.ydata - self.pan_start_xy[1]
                    
                    cur_xlim = ax.get_xlim()
                    cur_ylim = ax.get_ylim()
                    
                    ax.set_xlim([cur_xlim[0] - dx, cur_xlim[1] - dx])
                    ax.set_ylim([cur_ylim[0] - dy, cur_ylim[1] - dy])
                    
                    self.pan_start_xy = (event.xdata, event.ydata)
                    self.canvas.draw()
            
            # 添加鼠标事件监听
            self.canvas.mpl_connect('button_press_event', on_press)
            self.canvas.mpl_connect('button_release_event', on_release)
            self.canvas.mpl_connect('motion_notify_event', lambda event: on_motion(self, event))
            
            # 创建图例
            legend_elements = [
                plt.Rectangle((0, 0), 1, 1, facecolor='lightgreen', edgecolor='green', label='预期后代'),
                plt.Rectangle((0, 0), 1, 1, facecolor='#444444', edgecolor='#333333', label='父系'),
                plt.Rectangle((0, 0), 1, 1, facecolor='white', edgecolor='gray', label='母系')
            ]
            
            # 添加共同祖先颜色到图例
            for i, (ancestor, color) in enumerate(common_ancestor_colors.items()):
                if i < 4:  # 最多显示4个共同祖先在图例中
                    # 获取NAAB号
                    naab = naab_dict.get(ancestor, "")
                    # 显示完整的REG和NAAB号
                    if naab:
                        display_name = f"{ancestor} (NAAB: {naab})"
                    else:
                        display_name = ancestor
                    
                    legend_elements.append(
                        plt.Rectangle((0, 0), 1, 1, facecolor=color, edgecolor='green', label=f'共同祖先: {display_name}')
                    )
            
            # 添加图例到图表右上角 - 使用固定大小，不随缩放变化
            legend_font_size = 9  # 使用固定大小的图例字体
            legend = ax.legend(handles=legend_elements, loc='upper right', prop={'size': legend_font_size})
            
            # 不将图例文本添加到text_elements，这样它们就不会随缩放变化大小
            # 移除这部分代码:
            # for text in legend.get_texts():
            #    self.text_elements.append({
            #        'text_obj': text,
            #        'base_size': self.node_height*2.7,
            #        'type': 'legend'
            #    })
            
            # 连接缩放事件
            # self.cid_xlim = ax.callbacks.connect('xlim_changed', self.on_lim_change)
            # self.cid_ylim = ax.callbacks.connect('ylim_changed', self.on_lim_change)
            
        except Exception as e:
            logging.error(f"绘制血缘关系图时出错: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            
            # 尝试显示错误信息
            try:
                ax.text(0.5, 0.5, f"绘制血缘关系图时出错: {str(e)}", 
                       horizontalalignment='center', verticalalignment='center')
            except:
                pass
                
        # 安全地绘制画布
        try:
            self.canvas.draw()
        except Exception as e:
            logging.error(f"Canvas draw error in PedigreeDialog: {e}")
            # 不显示对话框，因为这只是预览窗口

    def on_canvas_click(self, event):
        """画布点击事件处理"""
        if event.dblclick:  # 检测双击事件
            try:
                # 创建并显示最大化图像对话框
                max_dialog = MaximizedPedigreeDialog(self, self.cow_id, self.sire_id, self.bull_id, 
                                                   self.offspring_details)
                max_dialog.exec()
            except Exception as e:
                logging.error(f"打开血缘关系图详细视图时出错: {e}")
                import traceback
                logging.error(traceback.format_exc())
                QMessageBox.critical(self, "错误", 
                                   f"无法打开血缘关系图详细视图:\n\n{str(e)}\n\n"
                                   f"请查看日志文件获取详细信息。")

    def query_naab_numbers(self, pedigree_db):
        """查询所有相关公牛的NAAB号码"""
        naab_dict = {}
        bull_ids = set()
        
        # 收集所有需要查询的公牛ID
        if self.bull_id and self.bull_id != "父亲未知":
            bull_ids.add(self.bull_id)
        if self.sire_id and self.sire_id != "父亲未知":
            bull_ids.add(self.sire_id)
            
        # 从系谱中收集所有公牛ID
        for animal_id, info in pedigree_db.pedigree.items():
            if info.get('type') == 'bull':
                bull_ids.add(animal_id)
                
        if not bull_ids:
            return naab_dict
            
        try:
            # 初始化数据库连接
            from sqlalchemy import create_engine, text
            from core.data.update_manager import LOCAL_DB_PATH
            
            # 连接数据库
            engine = create_engine(f'sqlite:///{LOCAL_DB_PATH}')
            bull_ids_str = "', '".join(bull_ids)
            
            # 查询NAAB号码
            query = text(f"""
                SELECT `BULL REG`, `BULL NAAB` 
                FROM bull_library 
                WHERE `BULL REG` IN ('{bull_ids_str}')
            """)
            
            # 执行查询
            with engine.connect() as conn:
                result = conn.execute(query).fetchall()
                
                # 处理查询结果
                for row in result:
                    reg = row[0]
                    naab = row[1]
                    if reg and naab:
                        naab_dict[reg] = naab
                        
            # 关闭连接
            engine.dispose()
            
        except Exception as e:
            logging.error(f"查询NAAB号码时出错: {str(e)}")
            
        return naab_dict

    # 添加一个空的on_lim_change方法，以防止报错
    def on_lim_change(self, event=None):
        """防止报错的空方法"""
        pass

# 添加最大化对话框类
class MaximizedPedigreeDialog(QDialog):
    """最大化血缘图对话框"""
    def __init__(self, parent, cow_id, sire_id, bull_id, offspring_details):
        super().__init__(parent)
        self.setWindowTitle("血缘关系图 (6代完整视图)")
        self.setWindowState(Qt.WindowState.WindowMaximized)
        
        # 保存必要的数据
        self.parent_widget = parent
        self.cow_id = cow_id
        self.sire_id = sire_id
        self.bull_id = bull_id
        self.offspring_details = offspring_details
        
        # 血统图属性
        self.base_node_height = 7.0  # 基础节点高度，用于计算字体大小
        
        # 缩放监听相关
        self.text_elements = []  # 存储文本元素引用
        self.base_xlim = None    # 初始x轴范围
        self.base_ylim = None    # 初始y轴范围
        self.last_update_time = 0  # 上次更新时间
        self.update_delay = 50   # 更新延迟(毫秒)
        self.update_pending = False  # 是否有待处理的更新
        
        layout = QVBoxLayout(self)
        
        # 创建新的图形和画布
        self.figure = Figure(figsize=(12, 10))  # 设置合适的画布大小
        self.canvas = FigureCanvas(self.figure)
        
        # 添加简化的功能按钮
        btn_layout = QHBoxLayout()
        
        # 放大按钮
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setToolTip("放大")
        zoom_in_btn.setFixedSize(40, 40)
        zoom_in_btn.setStyleSheet("font-size: 18px; font-weight: bold;")
        zoom_in_btn.clicked.connect(self.zoom_in)
        
        # 缩小按钮
        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setToolTip("缩小")
        zoom_out_btn.setFixedSize(40, 40)
        zoom_out_btn.setStyleSheet("font-size: 18px; font-weight: bold;")
        zoom_out_btn.clicked.connect(self.zoom_out)
        
        # 重置按钮
        reset_btn = QPushButton("⟲")
        reset_btn.setToolTip("重置视图")
        reset_btn.setFixedSize(40, 40)
        reset_btn.setStyleSheet("font-size: 18px;")
        reset_btn.clicked.connect(self.zoom_reset)
        
        # 保存按钮
        save_btn = QPushButton("保存图片")
        save_btn.setToolTip("保存血缘图为图片文件")
        save_btn.clicked.connect(self.save_figure)
        
        # 添加手型拖动按钮（切换模式）
        self.pan_btn = QPushButton("👋")
        self.pan_btn.setToolTip("拖动视图")
        self.pan_btn.setFixedSize(40, 40)
        self.pan_btn.setStyleSheet("font-size: 18px;")
        self.pan_btn.setCheckable(True)
        self.pan_btn.clicked.connect(self.toggle_pan_mode)
        
        btn_layout.addWidget(zoom_in_btn)
        btn_layout.addWidget(zoom_out_btn)
        btn_layout.addWidget(reset_btn)
        btn_layout.addWidget(self.pan_btn)
        btn_layout.addWidget(save_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        layout.addWidget(self.canvas)
        
        # 添加关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.on_close)
        layout.addWidget(close_button)
        
        # 添加右键菜单
        self.canvas.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self.show_context_menu)
        
        # 启用matplotlib的拖拽功能
        self.pan_cid = None  # 保存连接ID用于启用/禁用拖拽
        self.pan_start = None  # 初始化拖拽起始位置
        
        # 绘制完整的6代系谱图
        self.draw_pedigree()
        
        # 连接滚轮事件以支持鼠标滚轮和触控板缩放
        self.canvas.mpl_connect('scroll_event', self.on_scroll)
        
    def toggle_pan_mode(self):
        """切换拖动模式"""
        if self.pan_btn.isChecked():
            # 启用拖动模式
            self.canvas.setCursor(Qt.CursorShape.OpenHandCursor)
            if not self.pan_cid:
                self.pan_cid = self.canvas.mpl_connect('button_press_event', self.on_press)
                self.canvas.mpl_connect('button_release_event', self.on_release)
                self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        else:
            # 禁用拖动模式
            self.canvas.setCursor(Qt.CursorShape.ArrowCursor)
            if self.pan_cid:
                self.canvas.mpl_disconnect(self.pan_cid)
                self.pan_cid = None
    
    def on_press(self, event):
        """鼠标按下事件处理"""
        if event.button == 1:  # 左键
            self.pan_start = (event.xdata, event.ydata)
            self.canvas.setCursor(Qt.CursorShape.ClosedHandCursor)  # 改为抓取状态的手型
    
    def on_release(self, event):
        """鼠标释放事件处理"""
        if event.button == 1:  # 左键
            self.pan_start = None
            if self.pan_btn.isChecked():
                self.canvas.setCursor(Qt.CursorShape.OpenHandCursor)  # 恢复为打开状态的手型
    
    def on_motion(self, event):
        """鼠标移动事件处理"""
        if self.pan_start and event.xdata and event.ydata:
            # 计算移动距离
            dx = self.pan_start[0] - event.xdata
            dy = self.pan_start[1] - event.ydata
            
            # 获取当前视图范围
            ax = self.figure.gca()
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            
            # 移动视图
            ax.set_xlim(xlim[0] + dx, xlim[1] + dx)
            ax.set_ylim(ylim[0] + dy, ylim[1] + dy)
            
            # 更新起始位置
            self.pan_start = (event.xdata, event.ydata)
            
            # 更新画布
            self.canvas.draw_idle()
    
    def show_context_menu(self, pos):
        """显示右键菜单"""
        context_menu = QMenu(self)
        save_action = context_menu.addAction("保存为图片")
        
        action = context_menu.exec(self.canvas.mapToGlobal(pos))
        if action == save_action:
            self.save_figure()
    
    def save_figure(self):
        """保存图形为图片文件"""
        from PyQt6.QtWidgets import QFileDialog
        
        # 设置默认文件名
        default_filename = f"{self.bull_id}+{self.cow_id}_6代血缘图"
        
        # 获取保存的文件名
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存血缘关系图", default_filename, 
            "PNG 图片 (*.png);;JPEG 图片 (*.jpg);;PDF 文档 (*.pdf);;SVG 矢量图 (*.svg)"
        )
        
        if file_path:
            try:
                self.figure.savefig(
                    file_path, 
                    dpi=300,  # 高分辨率
                    bbox_inches='tight',  # 紧凑布局
                    pad_inches=0.1,  # 适当的边距
                    facecolor='white'  # 白色背景
                )
                QMessageBox.information(self, "保存成功", f"血缘关系图已保存至:\n{file_path}")
            except Exception as e:
                QMessageBox.warning(self, "保存失败", f"无法保存图片: {str(e)}")
    
    def zoom_in(self):
        """放大图表"""
        ax = self.figure.gca()
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        
        # 计算新的范围 - 缩小25%
        xrange = (xlim[1] - xlim[0]) * 0.25
        yrange = (ylim[1] - ylim[0]) * 0.25
        
        # 设置新的范围
        ax.set_xlim([xlim[0] + xrange, xlim[1] - xrange])
        ax.set_ylim([ylim[0] + yrange, ylim[1] - yrange])
        
        # 更新画布
        self.canvas.draw_idle()
        
    def zoom_out(self):
        """缩小图表"""
        ax = self.figure.gca()
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        
        # 计算新的范围 - 扩大33%
        xrange = (xlim[1] - xlim[0]) * 0.33
        yrange = (ylim[1] - ylim[0]) * 0.33
        
        # 设置新的范围
        ax.set_xlim([xlim[0] - xrange, xlim[1] + xrange])
        ax.set_ylim([ylim[0] - yrange, ylim[1] + yrange])
        
        # 更新画布
        self.canvas.draw_idle()
        
    def zoom_reset(self):
        """重置缩放"""
        if self.base_xlim and self.base_ylim:
            ax = self.figure.gca()
            ax.set_xlim(self.base_xlim)
            ax.set_ylim(self.base_ylim)
            self.canvas.draw_idle()
    
    def on_scroll(self, event):
        """处理鼠标滚轮和触控板缩放事件"""
        # 获取当前axes
        ax = self.figure.gca()
        
        # 获取当前视图范围
        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()
        
        # 获取鼠标位置
        xdata = event.xdata
        ydata = event.ydata
        
        if xdata is None or ydata is None:
            return
        
        # 计算当前范围
        cur_xrange = (cur_xlim[1] - cur_xlim[0]) * 0.5
        cur_yrange = (cur_ylim[1] - cur_ylim[0]) * 0.5
        
        # 获取滚轮步进值
        steps = event.step
        
        # 检测是否为触控板手势（步进值通常小于1）
        if abs(steps) < 1:
            # 触控板双指缩放，使用更平滑的缩放
            if steps > 0:
                scale_factor = 1 - steps * 0.1  # 放大
            else:
                scale_factor = 1 - steps * 0.1  # 缩小
        else:
            # 传统鼠标滚轮
            if event.button == 'up':  # 放大
                scale_factor = 0.9
            else:  # 缩小
                scale_factor = 1.1
        
        # 限制缩放范围
        new_xrange = cur_xrange * scale_factor
        new_yrange = cur_yrange * scale_factor
        
        # 防止过度缩放
        if new_xrange < 0.5 or new_xrange > 100:
            return
        
        # 以鼠标位置为中心进行缩放
        ax.set_xlim([xdata - new_xrange, xdata + new_xrange])
        ax.set_ylim([ydata - new_yrange, ydata + new_yrange])
        
        # 更新画布
        self.canvas.draw_idle()
    
    def draw_pedigree(self):
        """绘制完整的6代系谱图 - 采用固定画布大小和均匀分布节点"""
        # 创建新的图形和画布
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        # 清空文本元素列表
        self.text_elements = []
        
        try:
            # 字体已在文件开头初始化
            plt.rcParams['font.size'] = 14  # 增大默认字体大小
            
            # 在Windows上重新设置字体，避免字体缓存问题
            if platform.system() == 'Windows':
                import matplotlib
                matplotlib.rcParams['font.sans-serif'] = plt.rcParams['font.sans-serif']
                matplotlib.rcParams['axes.unicode_minus'] = False
            
            # 获取系谱库实例
            from core.data.update_manager import get_pedigree_db
            pedigree_db = get_pedigree_db()
            
            # 查询NAAB号码 - 复用父窗口的查询函数
            naab_dict = self.parent_widget.query_naab_numbers(pedigree_db)
            
            # 初始化共同祖先集合
            common_ancestors = set()
            if self.offspring_details and 'common_ancestors' in self.offspring_details:
                common_ancestors = set(self.offspring_details['common_ancestors'].keys())
            
            # 为共同祖先分配颜色
            common_ancestor_colors = {}
            color_options = ['#FF9999', '#99FF99', '#9999FF', '#FFFF99', '#FF99FF', '#99FFFF']
            
            for i, ancestor in enumerate(common_ancestors):
                color_idx = i % len(color_options)
                common_ancestor_colors[ancestor] = color_options[color_idx]
            
            # 设置节点尺寸和间距
            self.node_width = 0.5   # 节点宽度减半
            self.node_height = self.base_node_height  # 使用基础节点高度
            min_v_spacing = 1.5  # 最小垂直间距
            h_spacing = 1.0    # 减小水平间距，使各代更紧凑
            
            # 计算画布总高度 - 根据第6代节点数(64)
            total_nodes_last_gen = 2 ** 6  # 64个节点
            canvas_height = (self.node_height + min_v_spacing) * total_nodes_last_gen
            
            # 节点集合，格式为：{(代数,位置ID): (x坐标,y坐标,节点ID)}
            nodes = {}
            
            # 边集合，格式为：[(起点x, 起点y, 终点x, 终点y)]
            edges = []
            
            # 计算各代节点位置的函数
            def calculate_node_position(gen, pos, max_gen=6):
                """计算节点位置
                Args:
                    gen: 代数 (0-6)
                    pos: 在该代中的位置索引 (0-2^gen-1)
                    max_gen: 最大代数
                Returns:
                    (x, y): 节点的坐标
                """
                # 计算水平位置 - 从左到右
                x = gen * h_spacing
                
                # 计算垂直位置 - 均匀分布
                nodes_in_gen = 2 ** gen
                position_height = canvas_height / nodes_in_gen
                # 计算中心位置，并考虑到节点索引从0开始
                y = canvas_height/2 - (pos + 0.5) * position_height
                
                return (x, y)
            
            # 初始化系谱数据结构
            # 存储格式: {(gen, pos): animal_id}
            pedigree_structure = {}
            
            # 初始化第0代 - 预期后代
            pedigree_structure[(0, 0)] = "预期后代"
            
            # 第1代 - 父亲和母亲
            pedigree_structure[(1, 0)] = self.bull_id  # 父亲
            pedigree_structure[(1, 1)] = self.cow_id   # 母亲
            
            # 递归构建系谱结构
            def build_pedigree_structure(gen, pos, animal_id):
                """递归构建系谱结构
                Args:
                    gen: 当前代数
                    pos: 在该代中的位置索引
                    animal_id: 动物ID
                """
                if gen >= 6:  # 最多构建到第6代
                    return
                
                # 获取祖先信息
                node_info = pedigree_db.pedigree.get(animal_id, {})
                sire_id = node_info.get('sire', f'父亲未知')
                dam_id = node_info.get('dam', f'母亲未知')
                
                # 计算下一代位置
                next_gen = gen + 1
                sire_pos = pos * 2       # 父亲位置
                dam_pos = pos * 2 + 1    # 母亲位置
                
                # 存储父母ID
                pedigree_structure[(next_gen, sire_pos)] = sire_id
                pedigree_structure[(next_gen, dam_pos)] = dam_id
                
                # 递归处理下一代
                build_pedigree_structure(next_gen, sire_pos, sire_id)
                build_pedigree_structure(next_gen, dam_pos, dam_id)
            
            # 从第一代递归构建
            build_pedigree_structure(1, 0, self.bull_id)  # 从父亲开始
            build_pedigree_structure(1, 1, self.cow_id)   # 从母亲开始
            
            # 计算所有节点位置
            for (gen, pos), animal_id in pedigree_structure.items():
                x, y = calculate_node_position(gen, pos)
                nodes[(gen, pos)] = (x, y, animal_id)
            
            # 计算连接线
            for (gen, pos), (x, y, animal_id) in nodes.items():
                if gen > 0:  # 非根节点
                    # 找到父节点
                    parent_gen = gen - 1
                    parent_pos = pos // 2
                    
                    # 获取父节点坐标
                    parent_x, parent_y, _ = nodes[(parent_gen, parent_pos)]
                    
                    # 添加连接线
                    edges.append((parent_x + self.node_width/2, parent_y, x - self.node_width/2, y))
            
            # 绘制边（连接线）
            for start_x, start_y, end_x, end_y in edges:
                ax.plot([start_x, end_x], [start_y, end_y], color='green', linewidth=1.0, zorder=1)
            
            # 绘制节点（方框）和文字
            self.node_rects = []  # 存储节点矩形
            for (gen, pos), (x, y, animal_id) in nodes.items():
                # 确定方框颜色
                if animal_id == "预期后代":
                    facecolor = 'lightgreen'
                    edgecolor = 'green'
                    text_color = 'black'
                elif animal_id in common_ancestors:
                    facecolor = common_ancestor_colors[animal_id]
                    edgecolor = 'red'  # 共同祖先使用红色边框
                    text_color = 'black'
                elif pos % 2 == 0:  # 父系（偶数位置）
                    facecolor = '#444444'  # 深灰色
                    edgecolor = '#333333'
                    text_color = 'white'
                else:  # 母系（奇数位置）
                    facecolor = 'white'  # 无底色
                    edgecolor = 'gray'
                    text_color = 'black'
                
                # 绘制方框
                rect = plt.Rectangle(
                    (x - self.node_width/2, y - self.node_height/2),
                    self.node_width, self.node_height,
                    facecolor=facecolor,
                    edgecolor=edgecolor,
                    linewidth=1.0,
                    zorder=2,
                    alpha=0.9,
                )
                ax.add_patch(rect)
                self.node_rects.append(rect)
                
                # 获取NAAB号
                naab = naab_dict.get(animal_id, "")
                
                # 显示ID和NAAB号
                display_text = str(animal_id)
                naab_text = str(naab) if naab else ""
                
                # 设置初始文本大小
                self.base_naab_size = self.node_height * 0.55  # NAAB文本大小为节点高度的55%
                self.base_node_text_size = self.node_height * 0.3   # REG文本大小为节点高度的30%
                
                # 计算文本垂直位置
                reg_y_position = y - self.node_height/2 + self.node_height * 0.175
                naab_y_position = y + self.node_height/2 - self.node_height * 0.325
                
                # 在方框中显示REG号（下部）
                text_font = get_chinese_font_prop(size=self.base_node_text_size)
                if text_font:
                    reg_text = ax.text(
                        x, reg_y_position,
                        display_text,
                        fontproperties=text_font,
                        ha='center',
                        va='center',
                        color=text_color,
                        zorder=3
                    )
                else:
                    reg_text = ax.text(
                        x, reg_y_position,
                        display_text,
                        ha='center',
                        va='center',
                        size=self.base_node_text_size,
                        color=text_color,
                        zorder=3
                    )
                self.text_elements.append({
                    'text_obj': reg_text,
                    'base_size': self.base_node_text_size,
                    'type': 'reg'
                })
                
                # 在方框中显示NAAB号（上部）（加粗显示）
                if naab and animal_id not in ["预期后代", "父亲未知", "母亲未知"]:
                    naab_font = get_chinese_font_prop(size=self.base_naab_size, weight='bold')
                    if naab_font:
                        naab_text_obj = ax.text(
                            x, naab_y_position,
                            naab_text,
                            fontproperties=naab_font,
                            ha='center',
                            va='center',
                            color=text_color,
                            zorder=3
                        )
                    else:
                        naab_text_obj = ax.text(
                            x, naab_y_position,
                            naab_text,
                            ha='center',
                            va='center',
                            size=self.base_naab_size,
                            fontweight='bold',
                            color=text_color,
                            zorder=3
                        )
                    self.text_elements.append({
                        'text_obj': naab_text_obj,
                        'base_size': self.base_naab_size,
                        'type': 'naab'
                    })
            
            # 设置图表属性
            title_size = self.node_height * 3
            title_font = get_chinese_font_prop(size=title_size)
            if title_font:
                title_obj = ax.set_title("血缘关系图 (6代完整视图)", fontproperties=title_font)
            else:
                title_obj = ax.set_title("血缘关系图 (6代完整视图)", size=title_size)
            self.text_elements.append({
                'text_obj': title_obj,
                'base_size': title_size,
                'type': 'title'
            })
            
            ax.axis('off')  # 隐藏坐标轴
            
            # 设置视图范围
            x_margin = self.node_width
            y_margin = self.node_height * 2
            
            # 保存初始视图范围
            self.base_xlim = [-x_margin, 6 * h_spacing + self.node_width + x_margin]
            self.base_ylim = [-canvas_height/2 - y_margin, canvas_height/2 + y_margin]
            
            # 设置初始视图范围
            ax.set_xlim(self.base_xlim)
            ax.set_ylim(self.base_ylim)
            
            # 创建图例
            legend_elements = [
                plt.Rectangle((0, 0), 1, 1, facecolor='lightgreen', edgecolor='green', label='预期后代'),
                plt.Rectangle((0, 0), 1, 1, facecolor='#444444', edgecolor='#333333', label='父系'),
                plt.Rectangle((0, 0), 1, 1, facecolor='white', edgecolor='gray', label='母系')
            ]
            
            # 添加共同祖先颜色到图例
            for i, (ancestor, color) in enumerate(common_ancestor_colors.items()):
                if i < 4:  # 最多显示4个共同祖先在图例中
                    # 获取NAAB号
                    naab = naab_dict.get(ancestor, "")
                    # 显示完整的REG和NAAB号
                    if naab:
                        display_name = f"{ancestor} (NAAB: {naab})"
                    else:
                        display_name = ancestor
                    
                    legend_elements.append(
                        plt.Rectangle((0, 0), 1, 1, facecolor=color, edgecolor='green', label=f'共同祖先: {display_name}')
                    )
            
            # 添加图例到图表右上角 - 使用固定大小，不随缩放变化
            legend_font_size = 9  # 使用固定大小的图例字体
            legend = ax.legend(handles=legend_elements, loc='upper right', prop={'size': legend_font_size})
            
            # 连接缩放事件
            self.cid_xlim = ax.callbacks.connect('xlim_changed', self.on_lim_change)
            self.cid_ylim = ax.callbacks.connect('ylim_changed', self.on_lim_change)
            
        except Exception as e:
            logging.error(f"绘制完整血缘关系图时出错: {str(e)}")
            import traceback
            error_details = traceback.format_exc()
            logging.error(error_details)
            
            # 尝试显示错误信息
            try:
                ax.text(0.5, 0.5, f"绘制血缘关系图时出错: {str(e)}", 
                       horizontalalignment='center', verticalalignment='center')
            except:
                pass
            
            # 显示错误对话框
            QMessageBox.critical(self, "绘图错误", 
                               f"绘制血缘关系图时出错:\n\n{str(e)}\n\n"
                               f"请查看日志文件获取详细信息。")
        
        # 绘制
        try:
            self.canvas.draw()
        except Exception as e:
            logging.error(f"Canvas draw error: {e}")
            QMessageBox.critical(self, "绘图错误", 
                               f"显示图形时出错:\n\n{str(e)}")
    
    def on_lim_change(self, event=None):
        """处理坐标轴范围变化事件，用于动态调整文本大小"""
        # 使用节流控制，避免频繁更新
        current_time = int(time.time() * 1000)
        time_since_last_update = current_time - self.last_update_time
        
        if time_since_last_update < self.update_delay and not self.update_pending:
            # 还未到更新时间，设置定时器延迟更新
            self.update_pending = True
            QTimer.singleShot(self.update_delay - time_since_last_update, self.update_text_sizes)
        elif time_since_last_update >= self.update_delay:
            # 已经过了足够的时间，立即更新
            self.update_text_sizes()
    
    def update_text_sizes(self):
        """更新所有文本元素的大小基于当前缩放"""
        # 获取当前视图范围
        ax = self.figure.get_axes()[0]
        current_xlim = ax.get_xlim()
        current_ylim = ax.get_ylim()
        
        # 计算缩放比例 - 使用视图宽度比较
        base_width = self.base_xlim[1] - self.base_xlim[0]
        current_width = current_xlim[1] - current_xlim[0]
        zoom_ratio = base_width / current_width
        
        # 更新文本大小 - 跳过图例文本
        for text_info in self.text_elements:
            text_obj = text_info['text_obj']
            base_size = text_info['base_size']
            
            # 跳过图例文本 (虽然现在已经不添加图例文本了，但为了安全起见)
            if text_info.get('type') == 'legend':
                continue
            
            # 根据缩放比例计算新的文本大小
            new_size = base_size * zoom_ratio
            
            # 应用新的文本大小
            text_obj.set_fontsize(new_size)
        
        # 重新绘制画布 - 只更新文本，不重新计算布局
        self.canvas.draw_idle()
        
        # 更新时间戳和状态
        self.last_update_time = int(time.time() * 1000)
        self.update_pending = False
    
    def on_close(self):
        """关闭对话框"""
        self.close()

class InbreedingPage(QWidget):
    """隐性基因分析页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # 初始化基因列表
        self.defect_genes = [
            "HH1", "HH2", "HH3", "HH4", "HH5", "HH6", 
            "BLAD", "Chondrodysplasia", "Citrullinemia",
            "DUMPS", "Factor XI", "CVM", "Brachyspina",
            "Mulefoot", "Cholesterol deficiency", "MW"
        ]
        self.db_engine = None
        self.progress_dialog = None
        self.setup_ui()

    def setup_ui(self):
        """初始化UI"""
        main_layout = QHBoxLayout(self)
        
        # 左侧明细表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 添加标题和解释标签
        title_label = QLabel("母牛-公牛配对明细表")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        left_layout.addWidget(title_label)
        
        # 添加近交系数解释标签
        explanation_label = QLabel("近交系数 - 母牛自身的近交系数 | 后代近交系数 - 母牛与配种公牛产生的预期后代的近交系数")
        explanation_label.setWordWrap(True)
        explanation_label.setStyleSheet("color: #555; font-size: 12px; margin-bottom: 5px;")
        left_layout.addWidget(explanation_label)
        
        # 添加计算方法说明
        method_frame = QFrame()
        method_frame.setFrameStyle(QFrame.Shape.Box)
        method_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #f0f8ff;
                padding: 5px;
                margin-bottom: 10px;
            }
        """)
        method_layout = QVBoxLayout(method_frame)
        method_layout.setContentsMargins(5, 5, 5, 5)
        
        method_title = QLabel("近交系数计算方法")
        method_title.setStyleSheet("font-weight: bold; font-size: 12px; color: #2c3e50;")
        method_layout.addWidget(method_title)
        
        method_text = QLabel(
            "采用Wright通径法：F = Σ(0.5)^(n+n'+1) × (1+F_A)\n"
            "• n: 父系到共同祖先的代数\n"
            "• n': 母系到共同祖先的代数\n"
            "• F_A: 共同祖先的近交系数\n"
            "• 当有GIB值时直接使用"
        )
        method_text.setWordWrap(True)
        method_text.setStyleSheet("font-size: 11px; color: #444;")
        method_layout.addWidget(method_text)
        
        # 添加详细说明按钮
        detail_btn = QPushButton("查看详细说明")
        detail_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-size: 11px;
                max-width: 100px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        detail_btn.clicked.connect(self.show_calculation_method_detail)
        method_layout.addWidget(detail_btn)
        
        left_layout.addWidget(method_frame)
        
        # 表格视图
        self.detail_table = QTableView()
        self.detail_model = InbreedingDetailModel()
        self.detail_table.setModel(self.detail_model)
        
        # 设置表格属性以显示所有列
        self.detail_table.horizontalHeader().setStretchLastSection(True)  # 最后一列填充剩余空间
        self.detail_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)  # 自动调整列宽
        
        # 启用排序
        self.detail_table.setSortingEnabled(True)  # 启用排序功能
        self.detail_table.horizontalHeader().setSortIndicatorShown(True)  # 显示排序指示器
        self.detail_table.horizontalHeader().setSectionsClickable(True)  # 确保表头可点击
        
        left_layout.addWidget(self.detail_table)
        
        # 连接表格点击事件
        self.detail_table.clicked.connect(self.on_detail_table_clicked)
        
        # 右侧区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 右上异常明细表
        right_layout.addWidget(QLabel("异常配对明细"))
        self.abnormal_table = QTableView()
        self.abnormal_model = AbnormalDetailModel()
        self.abnormal_table.setModel(self.abnormal_model)
        right_layout.addWidget(self.abnormal_table)
        
        # 右中统计表
        right_layout.addWidget(QLabel("异常统计"))
        self.stats_table = QTableView()
        self.stats_model = StatisticsModel()
        self.stats_table.setModel(self.stats_model)
        right_layout.addWidget(self.stats_table)
        
        # 右下按钮区域
        button_layout = QHBoxLayout()
        self.mated_bull_btn = QPushButton("已配公牛分析")
        self.candidate_bull_btn = QPushButton("备选公牛分析")
        
        for btn in [self.mated_bull_btn, self.candidate_bull_btn]:
            btn.setStyleSheet("""
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
            """)
            button_layout.addWidget(btn)
        
        right_layout.addLayout(button_layout)
        
        # 添加导出按钮
        export_btn = QPushButton("导出分析结果")
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 120px;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #219a52;
            }
        """)
        export_btn.clicked.connect(self.export_results)
        right_layout.addWidget(export_btn)
        
        # 添加到分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)  # 左侧占比更大
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)
        
        # 连接信号
        self.mated_bull_btn.clicked.connect(lambda: self.start_analysis("mated"))
        self.candidate_bull_btn.clicked.connect(lambda: self.start_analysis("candidate"))

    def get_project_path(self) -> Optional[Path]:
        """获取当前项目路径"""
        main_window = self.get_main_window()
        if not main_window or not main_window.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return None
        return main_window.selected_project_path

    def get_main_window(self) -> Optional[QMainWindow]:
        """获取主窗口实例"""
        parent = self.parent()
        while parent:
            if isinstance(parent, QMainWindow):
                return parent
            parent = parent.parent()
        return None

    def init_db_connection(self) -> bool:
        """初始化数据库连接"""
        try:
            if self.db_engine:
                self.db_engine.dispose()
            self.db_engine = create_engine(f'sqlite:///{LOCAL_DB_PATH}')
            # 测试连接
            with self.db_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logging.error(f"数据库连接失败: {e}")
            return False

    def collect_required_bulls(self, analysis_type: str, project_path: Path) -> Set[str]:
        """收集需要查询的公牛号并转换为标准REG格式
        
        Args:
            analysis_type: 分析类型 ('mated' 或 'candidate')
            project_path: 项目路径
            
        Returns:
            需要查询的公牛号集合 (已转换为REG格式)
        """
        required_bulls_original = set()
        required_bulls_standardized = set()
        try:
            # 获取系谱库实例用于ID转换
            from core.data.update_manager import get_pedigree_db
            pedigree_db = get_pedigree_db()
            
            # 获取母牛父号
            cow_file = project_path / "standardized_data" / "processed_cow_data.xlsx"
            cow_df = pd.read_excel(cow_file)
            if analysis_type == 'candidate':
                # 备选公牛分析只考虑在群的母牛
                cow_df = cow_df[cow_df['是否在场'] == '是']
                
            # 收集并标准化母牛父号
            sire_ids = cow_df['sire'].dropna().astype(str).unique()
            for sire_id in sire_ids:
                if sire_id and sire_id.strip():
                    required_bulls_original.add(sire_id)
                    standardized_id = pedigree_db.standardize_animal_id(sire_id, 'bull')
                    if standardized_id:
                        required_bulls_standardized.add(standardized_id)
                    if sire_id != standardized_id:
                        print(f"父号转换: {sire_id} -> {standardized_id}")
            
            # 获取公牛号
            if analysis_type == 'mated':
                # 从配种记录获取已配公牛
                breeding_file = project_path / "standardized_data" / "processed_breeding_data.xlsx"
                breeding_df = pd.read_excel(breeding_file)
                bull_ids = breeding_df['冻精编号'].dropna().astype(str).unique()
                for bull_id in bull_ids:
                    if bull_id and bull_id.strip():
                        required_bulls_original.add(bull_id)
                        standardized_id = pedigree_db.standardize_animal_id(bull_id, 'bull')
                        if standardized_id:
                            required_bulls_standardized.add(standardized_id)
                        if bull_id != standardized_id:
                            print(f"配种公牛号转换: {bull_id} -> {standardized_id}")
            else:
                # 从备选公牛文件获取公牛号
                bull_file = project_path / "standardized_data" / "processed_bull_data.xlsx"
                bull_df = pd.read_excel(bull_file)
                bull_ids = bull_df['bull_id'].dropna().astype(str).unique()
                for bull_id in bull_ids:
                    if bull_id and bull_id.strip():
                        required_bulls_original.add(bull_id)
                        standardized_id = pedigree_db.standardize_animal_id(bull_id, 'bull')
                        if standardized_id:
                            required_bulls_standardized.add(standardized_id)
                        if bull_id != standardized_id:
                            print(f"备选公牛号转换: {bull_id} -> {standardized_id}")
                
            # 打印标准化结果
            original_count = len(required_bulls_original)
            standardized_count = len(required_bulls_standardized)
            print(f"收集到{original_count}个原始公牛ID，标准化后得到{standardized_count}个REG格式ID")
            if original_count > standardized_count:
                print(f"有{original_count - standardized_count}个ID转换为空或重复")
                
            # 移除空字符串
            required_bulls_standardized = {bull for bull in required_bulls_standardized if bull and bull.strip()}
            return required_bulls_standardized
            
        except Exception as e:
            logging.error(f"收集公牛号时发生错误: {e}")
            return required_bulls_standardized

    def query_bull_genes(self, bull_ids: Set[str]) -> Tuple[Dict, List[str]]:
        """查询公牛基因信息
        
        Args:
            bull_ids: 已标准化为REG格式的公牛ID集合
            
        Returns:
            Tuple[Dict, List[str]]: 公牛基因信息字典和未找到基因信息的公牛列表
        """
        bull_genes = {}
        missing_bulls = []
        
        print(f"开始查询公牛基因信息，共有{len(bull_ids)}个公牛ID")
        if not bull_ids:
            print("没有公牛ID需要查询")
            return bull_genes, missing_bulls
            
        try:
            # 过滤掉空值和NaN
            valid_bull_ids = {bid for bid in bull_ids if bid and not pd.isna(bid) and bid.strip()}
            print(f"过滤后有效的公牛ID数量: {len(valid_bull_ids)}")
            if not valid_bull_ids:
                print("没有有效的公牛ID")
                return bull_genes, list(bull_ids)
                
            # 使用字符串拼接构建SQL查询
            # 注意：这种方式可能存在SQL注入风险，但在这种特定场景下风险较低
            bull_ids_str = "', '".join(valid_bull_ids)
            
            query = text(f"""
                SELECT `BULL NAAB`, `BULL REG`, 
                    HH1, HH2, HH3, HH4, HH5, HH6, 
                    BLAD, Chondrodysplasia, Citrullinemia, 
                    DUMPS, `Factor XI`, CVM, Brachyspina, 
                    Mulefoot, `Cholesterol deficiency`, MW
                FROM bull_library 
                WHERE `BULL NAAB` IN ('{bull_ids_str}') 
                OR `BULL REG` IN ('{bull_ids_str}')
            """)
            
            logging.info(f"要查询的公牛号: {valid_bull_ids}")
            print(f"SQL查询: {query}")
            
            # 执行查询
            with self.db_engine.connect() as conn:
                print("开始执行SQL查询...")
                # 不需要传递参数，因为已经在SQL中直接包含了值
                result = conn.execute(query).fetchall()
                print(f"查询完成，获取到{len(result)}条记录")
                logging.info(f"查询到的记录数: {len(result)}")
                
                # 处理查询结果
                found_bulls = set()
                print("开始处理查询结果...")
                for i, row in enumerate(result):
                    if i < 5:  # 只打印前5行，避免日志过长
                        print(f"处理第{i+1}行数据")
                    # 使用_mapping属性访问行数据
                    row_dict = dict(row._mapping)
                    naab = row_dict.get('BULL NAAB')
                    reg = row_dict.get('BULL REG')
                    
                    # 提取基因信息
                    gene_data = {}
                    for gene in self.defect_genes:
                        value = row_dict.get(gene)
                        if pd.isna(value):
                            # 数据库中的NULL值表示不携带该基因
                            gene_data[gene] = 'F'
                        else:
                            value = str(value).strip().upper()
                            if value == 'C':
                                gene_data[gene] = 'C'
                            elif value == 'F':
                                gene_data[gene] = 'F'
                            else:
                                gene_data[gene] = value
                    
                    # 添加到结果字典
                    if naab:
                        bull_genes[str(naab)] = gene_data
                        found_bulls.add(str(naab))
                    if reg:
                        bull_genes[str(reg)] = gene_data
                        found_bulls.add(str(reg))
                
                # 记录未找到的公牛
                missing_bulls = list(valid_bull_ids - found_bulls)
                print(f"处理完成，找到{len(found_bulls)}个公牛的基因信息，有{len(missing_bulls)}个公牛未找到")
                logging.info(f"找到基因信息的公牛数量: {len(found_bulls)}")
                logging.info(f"未找到基因信息的公牛数量: {len(missing_bulls)}")
                
                return bull_genes, missing_bulls
                
        except Exception as e:
            print(f"查询公牛基因信息时发生错误: {e}")
            logging.error(f"查询公牛基因信息失败: {e}")
            logging.error(f"SQL语句: {query}")
            return {}, list(bull_ids)

    def process_missing_bulls(self, missing_bulls: List[str], analysis_type: str) -> None:
        """处理缺失公牛记录"""
        if not missing_bulls:
            return
            
        try:
            # 准备数据
            print(f"处理{len(missing_bulls)}个缺失的公牛记录...")
            if len(missing_bulls) > 10:
                print(f"前10个缺失的公牛号: {missing_bulls[:10]}")
            else:
                print(f"缺失的公牛号: {missing_bulls}")
                
            main_window = self.get_main_window()
            username = main_window.username if main_window else 'unknown'
            missing_df = pd.DataFrame({
                'bull': missing_bulls,
                'source': f'隐性基因筛查_{analysis_type}',
                'time': datetime.datetime.now(),
                'user': username
            })
            
            # 连接云端数据库并上传
            print("尝试连接云端数据库上传缺失公牛记录...")
            cloud_engine = create_engine(
                f"mysql+pymysql://{CLOUD_DB_USER}:{CLOUD_DB_PASSWORD}"
                f"@{CLOUD_DB_HOST}:{CLOUD_DB_PORT}/{CLOUD_DB_NAME}?charset=utf8mb4"
            )
            missing_df.to_sql('miss_bull', cloud_engine, if_exists='append', index=False)
            print(f"成功上传{len(missing_bulls)}个缺失公牛记录到云端数据库")
            
            # 提示用户
            print("警告：在本地数据库中未找到公牛基因信息，所有隐性基因将显示为missing_data")
            print("请确保本地数据库已更新，或者联系管理员添加这些公牛的基因信息")
            logging.warning(f"在本地数据库中未找到{len(missing_bulls)}个公牛的基因信息，所有隐性基因将显示为missing_data")
            
            # 显示消息框提醒用户
            QMessageBox.warning(
                self, 
                "公牛基因信息缺失", 
                f"在本地数据库中未找到{len(missing_bulls)}个公牛的基因信息，\n"
                f"这些公牛的隐性基因信息将显示为missing_data。\n\n"
                f"请确保本地数据库已更新，或者联系管理员添加这些公牛的基因信息。"
            )
            
        except Exception as e:
            logging.error(f"处理缺失公牛记录失败: {e}")

    def analyze_gene_safety(self, cow_genes: Dict[str, str], bull_genes: Dict[str, str]) -> Dict[str, str]:
        """分析基因配对安全性"""
        result = {}
        for gene in self.defect_genes:
            cow_gene = cow_genes.get(gene, 'missing data')
            bull_gene = bull_genes.get(gene, 'missing data')
            
            if cow_gene == 'C' and bull_gene == 'C':
                # 双方都是携带者
                result[gene] = 'NO safe'
            elif cow_gene == 'F' and bull_gene == 'F':
                # 双方都是正常
                result[gene] = 'safe'
            elif (cow_gene == 'F' and bull_gene == 'C') or (cow_gene == 'C' and bull_gene == 'F'):
                # 一方携带一方正常
                result[gene] = 'safe'
            elif cow_gene == 'missing data' and bull_gene == 'missing data':
                # 双方都缺数据
                result[gene] = 'missing data'
            elif cow_gene == 'missing data':
                # 母方缺数据
                result[gene] = 'missing cow data'
            elif bull_gene == 'missing data':
                # 公方缺数据
                result[gene] = 'missing bull data'
            else:
                # 其他情况
                result[gene] = 'unknown'
                
        return result

    def on_detail_table_clicked(self, index):
        """处理明细表点击事件"""
        if not index.isValid():
            return
            
        # 获取选中行的数据
        row = index.row()
        cow_id = self.detail_model.df.iloc[row].get('母牛号', '')
        
        # 获取标准化后的父号
        sire_id = self.detail_model.df.iloc[row].get('父号', '')  # 已标准化的REG格式
        
        # 获取标准化后的公牛号（可能是配种公牛号或备选公牛号）
        bull_id = self.detail_model.df.iloc[row].get('配种公牛号', 
                  self.detail_model.df.iloc[row].get('备选公牛号', ''))  # 已标准化的REG格式
        
        # 获取近交详情
        inbreeding_details = self.detail_model.df.iloc[row].get('近交详情')
        offspring_details = self.detail_model.df.iloc[row].get('后代近交详情')
        
        # 显示血缘关系图对话框
        dialog = PedigreeDialog(cow_id, sire_id, bull_id, self, inbreeding_details, offspring_details)
        dialog.exec()

    def analyze_mated_pairs(self, project_path: Path, bull_genes: Dict[str, str]) -> List[Dict]:
        """分析已配公牛对"""
        results = []
        try:
            # 读取配对数据
            breeding_file = project_path / "standardized_data" / "processed_breeding_data.xlsx"
            print(f"开始分析已配公牛对，从{breeding_file}读取数据")
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_info(f"读取配种记录文件: {breeding_file.name}")
            
            df = pd.read_excel(breeding_file)
            print(f"读取到{len(df)}条配对记录")
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_info(f"成功读取 {len(df)} 条配种记录")
            
            # 获取系谱库实例用于ID转换
            from core.data.update_manager import get_pedigree_db
            pedigree_db = get_pedigree_db()
            
            # 分析每个配对
            results = []
            print("开始分析每个配对...")
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_info("开始逐个分析配种记录...")
            
            total_count = len(df)
            
            # 更新进度
            self.update_progress(40, f"分析配对记录 (0/{total_count})")
            
            for i, row in enumerate(df.iterrows()):
                # 检查是否取消
                if hasattr(self, 'progress_dialog') and self.progress_dialog.cancelled:
                    print("用户取消了分析，正在退出...")
                    return results  # 提前返回已处理的结果
                
                # 每10条记录更新一次进度
                if i % 10 == 0:
                    progress = int(40 + (i / total_count) * 30)  # 40-70%的进度范围
                    self.update_progress(progress, f"分析配对记录 ({i+1}/{total_count})")
                    if hasattr(self, 'progress_dialog') and self.progress_dialog:
                        self.progress_dialog.update_info(f"正在分析第 {i+1} 条配种记录...")
                
                if i < 5 or i % 100 == 0:  # 只打印前5行和每100行，避免日志过长
                    print(f"分析第{i+1}条配对记录")
                _, row = row  # 解包iterrows返回的元组
                cow_id = str(row['耳号'])
                
                # 标准化父号(转换为REG)
                original_sire_id = str(row['父号']) if pd.notna(row['父号']) else ''
                sire_id = pedigree_db.standardize_animal_id(original_sire_id, 'bull')
                
                # 标准化公牛号(冻精编号转换为REG)
                original_bull_id = str(row['冻精编号']) if pd.notna(row['冻精编号']) else ''
                bull_id = pedigree_db.standardize_animal_id(original_bull_id, 'bull')
                
                # 记录原始ID和标准化ID，用于调试
                if original_sire_id != sire_id and original_sire_id:
                    print(f"  父号转换: {original_sire_id} -> {sire_id}")
                    if hasattr(self, 'progress_dialog') and self.progress_dialog and i < 10:  # 前10条显示转换信息
                        self.progress_dialog.update_info(f"父号转换: {original_sire_id} -> {sire_id}")
                if original_bull_id != bull_id and original_bull_id:
                    print(f"  冻精编号转换: {original_bull_id} -> {bull_id}")
                    if hasattr(self, 'progress_dialog') and self.progress_dialog and i < 10:  # 前10条显示转换信息
                        self.progress_dialog.update_info(f"冻精编号转换: {original_bull_id} -> {bull_id}")
                
                # 获取基因信息
                sire_genes = bull_genes.get(sire_id, {gene: 'missing data' for gene in self.defect_genes})
                bull_genes_data = bull_genes.get(bull_id, {gene: 'missing data' for gene in self.defect_genes})
                
                # 分析安全性
                gene_results = self.analyze_gene_safety(sire_genes, bull_genes_data)
                
                # 计算近交系数（临时使用随机值，后续会替换为真实计算）
                inbreeding_coef = 0.0  # 默认值，后续会替换为真实计算
                
                # 记录结果
                result_dict = {
                    '母牛号': cow_id,
                    '父号': sire_id,
                    '原始父号': original_sire_id if original_sire_id != sire_id else '',
                    '配种公牛号': bull_id,
                    '原始公牛号': original_bull_id if original_bull_id != bull_id else '',
                    '近交系数': f"{inbreeding_coef:.2%}",  # 格式化为百分比
                }
                
                # 添加基因分析结果
                for gene in self.defect_genes:
                    result_dict[gene] = gene_results[gene]
                    result_dict[f"{gene}(母)"] = sire_genes.get(gene, 'missing data')
                    result_dict[f"{gene}(公)"] = bull_genes_data.get(gene, 'missing data')
                
                results.append(result_dict)
            
            print(f"已配公牛对分析完成，共{len(results)}条结果")
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_info(f"已配公牛对分析完成，共 {len(results)} 条结果")
            return results
                
        except Exception as e:
            print(f"分析已配公牛对时发生错误: {e}")
            logging.error(f"分析已配公牛对时发生错误: {e}")
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_info(f"分析出错: {str(e)}")
            return results

    def analyze_candidate_pairs(self, project_path: Path, bull_genes: Dict[str, str]) -> List[Dict]:
        """分析备选公牛对"""
        results = []
        try:
            # 读取母牛数据和备选公牛数据
            cow_file = project_path / "standardized_data" / "processed_cow_data.xlsx"
            bull_file = project_path / "standardized_data" / "processed_bull_data.xlsx"
            print(f"开始分析备选公牛对，从{cow_file}和{bull_file}读取数据")
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_info(f"读取母牛数据文件: {cow_file.name}")
                self.progress_dialog.update_info(f"读取备选公牛数据文件: {bull_file.name}")
            
            cow_df = pd.read_excel(cow_file)
            bull_df = pd.read_excel(bull_file)
            print(f"读取到{len(cow_df)}条母牛记录和{len(bull_df)}条备选公牛记录")
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_info(f"成功读取 {len(cow_df)} 条母牛记录")
                self.progress_dialog.update_info(f"成功读取 {len(bull_df)} 条备选公牛记录")
            
            # 获取系谱库实例用于ID转换
            from core.data.update_manager import get_pedigree_db
            pedigree_db = get_pedigree_db()
            
            # 只分析在群的母牛
            original_cow_count = len(cow_df)
            cow_df = cow_df[cow_df['是否在场'] == '是']
            print(f"过滤后在群的母牛数量: {len(cow_df)}")
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_info(f"过滤在群母牛: {original_cow_count} -> {len(cow_df)} 头")
            
            # 估计总对数
            total_pairs = len(cow_df) * len(bull_df)
            print(f"预计分析的总配对数: {total_pairs}")
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_info(f"预计分析配对组合: {total_pairs} 对")
            
            # 分析每对组合
            print("开始分析每对母牛和备选公牛的组合...")
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_info("开始逐个分析母牛与备选公牛的配对组合...")
            
            cow_count = 0
            pair_count = 0
            
            # 初始进度
            self.update_progress(50, f"分析配对组合 (0/{total_pairs})")
            
            for _, cow_row in cow_df.iterrows():
                # 检查是否取消
                if hasattr(self, 'progress_dialog') and self.progress_dialog.cancelled:
                    print("用户取消了分析，正在退出...")
                    return results  # 提前返回已处理的结果
                
                cow_count += 1
                if cow_count <= 5 or cow_count % 50 == 0:  # 只打印前5头牛和每50头牛，避免日志过长
                    print(f"分析第{cow_count}头母牛")
                    if hasattr(self, 'progress_dialog') and self.progress_dialog:
                        self.progress_dialog.update_info(f"处理第 {cow_count} 头母牛: {cow_row['cow_id']}")
                
                cow_id = str(cow_row['cow_id'])
                
                # 标准化父号
                original_sire_id = str(cow_row['sire']) if pd.notna(cow_row['sire']) else ''
                sire_id = pedigree_db.standardize_animal_id(original_sire_id, 'bull')
                
                if original_sire_id != sire_id and original_sire_id:
                    print(f"  父号转换: {original_sire_id} -> {sire_id}")
                    if hasattr(self, 'progress_dialog') and self.progress_dialog and cow_count <= 5:  # 前5头牛显示转换信息
                        self.progress_dialog.update_info(f"父号转换: {original_sire_id} -> {sire_id}")
                
                # 获取母牛基因信息（通过父号）
                cow_genes = bull_genes.get(sire_id, {gene: 'missing data' for gene in self.defect_genes})
                
                # 分析与每个备选公牛的组合
                for _, bull_row in bull_df.iterrows():
                    # 每10对检查一次是否取消
                    if pair_count % 10 == 0 and hasattr(self, 'progress_dialog') and self.progress_dialog.cancelled:
                        print("用户取消了分析，正在退出...")
                        return results  # 提前返回已处理的结果
                    
                    pair_count += 1
                    
                    # 更新进度条 - 每100对更新一次
                    if pair_count % 100 == 0:
                        progress = int(40 + (pair_count / total_pairs) * 30)  # 40-70%的进度范围
                        self.update_progress(progress, f"分析配对组合 ({pair_count}/{total_pairs})")
                        if hasattr(self, 'progress_dialog') and self.progress_dialog:
                            self.progress_dialog.update_info(f"已分析 {pair_count} 对配对组合...")
                    
                    if pair_count <= 5 or pair_count % 1000 == 0:  # 只打印前5对和每1000对，避免日志过长
                        print(f"  分析第{pair_count}对组合: 母牛{cow_id} - 公牛{bull_row['bull_id']}")
                    
                    # 标准化备选公牛ID
                    original_bull_id = str(bull_row['bull_id'])
                    bull_id = pedigree_db.standardize_animal_id(original_bull_id, 'bull')
                    
                    if original_bull_id != bull_id and original_bull_id:
                        print(f"  备选公牛号转换: {original_bull_id} -> {bull_id}")
                        if hasattr(self, 'progress_dialog') and self.progress_dialog and pair_count <= 5:  # 前5对显示转换信息
                            self.progress_dialog.update_info(f"备选公牛号转换: {original_bull_id} -> {bull_id}")
                    
                    candidate_genes = bull_genes.get(bull_id, {gene: 'missing data' for gene in self.defect_genes})
                    
                    # 分析安全性
                    gene_results = self.analyze_gene_safety(cow_genes, candidate_genes)
                    
                    # 计算近交系数（临时使用随机值，后续会替换为真实计算）
                    inbreeding_coef = 0.0
                    
                    # 记录结果
                    result_dict = {
                        '母牛号': cow_id,
                        '父号': sire_id,
                        '原始父号': original_sire_id if original_sire_id != sire_id else '',
                        '备选公牛号': bull_id,
                        '原始备选公牛号': original_bull_id if original_bull_id != bull_id else '',
                        '近交系数': f"{inbreeding_coef:.2%}",  # 格式化为百分比
                    }
                    
                    # 添加基因分析结果
                    for gene in self.defect_genes:
                        result_dict[gene] = gene_results[gene]
                        result_dict[f"{gene}(母)"] = cow_genes.get(gene, 'missing data')
                        result_dict[f"{gene}(公)"] = candidate_genes.get(gene, 'missing data')
                    
                    results.append(result_dict)
            
            print(f"备选公牛对分析完成，共{len(results)}条结果")
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_info(f"备选公牛对分析完成，共 {len(results)} 条结果")
            return results
            
        except Exception as e:
            print(f"分析备选公牛对时发生错误: {e}")
            logging.error(f"分析备选公牛对时发生错误: {e}")
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_info(f"分析出错: {str(e)}")
            return results

    def collect_abnormal_pairs(self, results: List[Dict]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """收集异常配对和统计信息"""
        abnormal_records = []
        gene_stats = {gene: 0 for gene in self.defect_genes}
        inbreeding_count = 0  # 统计近交系数过高的数量
        
        # 更新进度
        self.update_progress(90, "收集异常配对...")
        
        # 计数器
        count = 0
        total = len(results)
        
        for result in results:
            # 每10条检查一次是否取消
            count += 1
            if count % 10 == 0 and hasattr(self, 'progress_dialog') and self.progress_dialog.cancelled:
                print("用户取消了异常配对收集，正在退出...")
                # 返回当前已收集的结果
                return pd.DataFrame(abnormal_records), pd.DataFrame(stats_records if 'stats_records' in locals() else [])
            
            # 检测隐性基因问题
            for gene in self.defect_genes:
                if result[gene] == 'NO safe':
                    abnormal_records.append({
                        '母牛号': result['母牛号'],
                        '父号': result['父号'],
                        '公牛号': result.get('配种公牛号', result.get('备选公牛号')),
                        '异常类型': gene,
                        '状态': '公牛与母牛父亲共同携带隐性基因'
                    })
                    gene_stats[gene] += 1
            
            # 检测近交系数过高的情况
            if '后代近交系数' in result:
                # 从格式化的百分比字符串中提取数值
                inbreeding_str = result['后代近交系数']
                try:
                    # 去掉百分号并转换为浮点数
                    inbreeding_value = float(inbreeding_str.strip('%')) / 100
                    if inbreeding_value > 0.0625:  # 近交系数 > 6.25%
                        abnormal_records.append({
                            '母牛号': result['母牛号'],
                            '父号': result['父号'],
                            '公牛号': result.get('配种公牛号', result.get('备选公牛号')),
                            '异常类型': '近交系数过高',
                            '状态': f'{inbreeding_value:.2%}'
                        })
                        inbreeding_count += 1
                except (ValueError, TypeError):
                    # 处理无法转换为浮点数的情况
                    pass
        
        # 创建异常记录DataFrame
        abnormal_df = pd.DataFrame(abnormal_records)
        
        # 创建统计信息DataFrame
        stats_records = [
            {'异常类型': gene, '数量': count}
            for gene, count in gene_stats.items()
            if count > 0
        ]
        
        # 添加近交系数过高的统计
        if inbreeding_count > 0:
            stats_records.append({'异常类型': '近交系数过高', '数量': inbreeding_count})
        
        stats_df = pd.DataFrame(stats_records)
        
        return abnormal_df, stats_df

    def calculate_inbreeding_coefficients(self, project_path: Path, results: List[Dict]) -> List[Dict]:
        """计算近交系数并更新结果
        
        Args:
            project_path: 项目路径
            results: 分析结果列表
            
        Returns:
            更新后的结果列表
        """
        try:
            # 使用PathInbreedingCalculator计算近交系数
            from core.inbreeding.path_inbreeding_calculator import PathInbreedingCalculator
            
            # 初始化计算器，设置追溯6代祖先
            print("\n====== 初始化近交系数计算器 ======")
            print(f"使用通径法(Wright's Formula)计算，追溯6代祖先")
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_info("初始化近交系数计算器...")
                self.progress_dialog.update_info("使用通径法(Wright's Formula)计算，追溯6代祖先")
            
            calculator = PathInbreedingCalculator(max_generations=6)
            
            # 统计计数器
            total_count = len(results)
            success_count = 0
            zero_count = 0
            high_inbreeding_count = 0  # 近交系数 > 0.0625 (6.25%)
            offspring_count = 0  # 统计计算后代近交系数的次数
            print(f"需要计算 {total_count} 个配对的近交系数")
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_info(f"需要计算 {total_count} 个配对的近交系数")
            
            # 开始计算
            for i, result in enumerate(results):
                # 检查是否取消
                if hasattr(self, 'progress_dialog') and self.progress_dialog.cancelled:
                    print("用户取消了计算，正在退出...")
                    return results  # 提前返回当前结果
                
                # 更新进度条 - 在计算期间显示进度
                progress = int(70 + (i / total_count) * 20)  # 70-90%的进度范围
                self.update_progress(progress, f"计算近交系数 ({i+1}/{total_count})")
                
                # 每10个更新详细信息
                if i % 10 == 0 or i < 5:
                    if hasattr(self, 'progress_dialog') and self.progress_dialog:
                        self.progress_dialog.update_info(f"正在计算第 {i+1} 个配对的近交系数...")
                
                # 打印进度
                if i % 10 == 0 or i < 5:  # 每10个或前5个打印一次
                    print(f"\n===== 处理第 {i+1}/{total_count} 个配对 =====")
                
                # 获取标准化的ID
                cow_id = result['母牛号']
                sire_id = result['父号']  # 已经标准化的REG格式
                
                # 获取标准化后的配种公牛或备选公牛ID
                bull_id = result.get('配种公牛号', result.get('备选公牛号', ''))  # 已经标准化的REG格式
                
                print(f"母牛ID: {cow_id}, 父号: {sire_id}, 公牛号: {bull_id}")
                
                # 如果有公牛ID，计算潜在后代的近交系数
                if bull_id:
                    offspring_count += 1
                    print(f"\n计算潜在后代近交系数: 公牛={bull_id}, 母牛={cow_id}")
                    
                    # 显示详细计算信息
                    if hasattr(self, 'progress_dialog') and self.progress_dialog and i < 3:  # 前3个显示详细信息
                        self.progress_dialog.update_info(f"计算后代近交系数: 公牛={bull_id}, 母牛={cow_id}")
                    
                    try:
                        offspring_inbreeding, offspring_contributions, offspring_paths = calculator.calculate_potential_offspring_inbreeding(bull_id, cow_id)
                        
                        # 确保近交系数不是nan
                        if math.isnan(offspring_inbreeding):
                            print(f"[WARNING] 后代近交系数为NaN，设置为0.0")
                            offspring_inbreeding = 0.0
                            
                        result['后代近交系数'] = f"{offspring_inbreeding:.2%}"
                        
                        # 检查是否为近亲繁殖情况
                        if bull_id == sire_id:
                            print(f"⚠️ 警告: 配种公牛 {bull_id} 与母牛 {cow_id} 的父亲相同!")
                            if hasattr(self, 'progress_dialog') and self.progress_dialog and i < 5:
                                self.progress_dialog.update_info(f"⚠️ 警告: 近亲繁殖 - 公牛与母牛父亲相同!")
                        
                        # 输出高后代近交系数警告
                        if offspring_inbreeding > 0.0625:  # 6.25%
                            print(f"⚠️ 高后代近交警告! {bull_id} 和 {cow_id} 的潜在后代近交系数: {offspring_inbreeding:.2%}")
                            high_inbreeding_count += 1
                            if hasattr(self, 'progress_dialog') and self.progress_dialog and high_inbreeding_count <= 3:  # 前3个高近交警告显示
                                self.progress_dialog.update_info(f"⚠️ 发现高近交配对: {offspring_inbreeding:.2%}")
                        
                        result['后代近交详情'] = {
                            'system': offspring_inbreeding,
                            'common_ancestors': offspring_contributions,
                            'paths': offspring_paths
                        }
                        
                        # 打印后代近交信息
                        print(f"后代近交系数: {offspring_inbreeding:.2%}")
                        if offspring_contributions:
                            print(f"共同祖先数量: {len(offspring_contributions)}")
                        else:
                            print("没有找到共同祖先")
                            
                        success_count += 1
                        if offspring_inbreeding == 0.0:
                            zero_count += 1
                            
                    except Exception as e:
                        print(f"[ERROR] 计算后代近交系数时出错: {str(e)}")
                        if hasattr(self, 'progress_dialog') and self.progress_dialog and i < 3:
                            self.progress_dialog.update_info(f"计算出错: {str(e)}")
                        # 设置默认值，避免显示为nan
                        result['后代近交系数'] = "0.00%"
                        result['后代近交详情'] = {
                            'system': 0.0,
                            'common_ancestors': {},
                            'paths': {}
                        }
                else:
                    # 如果没有公牛ID，设置后代近交系数为0
                    result['后代近交系数'] = "0.00%"
                    result['后代近交详情'] = {
                        'system': 0.0,
                        'common_ancestors': {},
                        'paths': {}
                    }
            
            # 输出统计信息
            print("\n====== 近交系数计算统计 ======")
            print(f"总共处理: {total_count} 个配对")
            print(f"计算了后代近交系数: {offspring_count} 个 ({offspring_count/total_count*100:.1f}%)")
            print(f"成功计算: {success_count} 个")
            print(f"零近交系数: {zero_count} 个")
            print(f"高近交系数(>6.25%): {high_inbreeding_count} 个")
            print("============================\n")
            
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_info("近交系数计算完成")
                self.progress_dialog.update_info(f"成功计算: {success_count} 个")
                self.progress_dialog.update_info(f"零近交系数: {zero_count} 个")
                self.progress_dialog.update_info(f"高近交系数(>6.25%): {high_inbreeding_count} 个")
                
            return results
            
        except Exception as e:
            logging.error(f"计算近交系数时出错: {str(e)}")
            print(f"⚠️ 计算近交系数时出错: {str(e)}")
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.update_info(f"⚠️ 计算近交系数时出错: {str(e)}")
            return results

    def update_progress(self, value: int, message: str):
        """更新进度对话框
        
        Args:
            value: 进度值(0-100)
            message: 进度消息
        """
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.update_progress(value)
            self.progress_dialog.set_task_info(message)  # 更新任务标题
            self.progress_dialog.update_info(message)    # 更新详细信息区域
            QApplication.processEvents()
    
    def start_analysis(self, analysis_type: str):
        """开始分析
        Args:
            analysis_type: 分析类型，"mated" 表示已配公牛分析，"candidate" 表示备选公牛分析
        """
        # 保存最后的分析类型
        self._last_analysis_type = analysis_type
        print(f"开始执行{analysis_type}分析...")
        
        # 获取项目路径
        project_path = self.get_project_path()
        if not project_path:
            print("未找到项目路径，无法执行分析")
            QMessageBox.warning(self, "错误", "未找到项目路径，请先选择项目。")
            return
        print(f"项目路径: {project_path}")
        
        # 初始化数据库连接
        if not self.init_db_connection():
            print("数据库连接失败，无法执行分析")
            QMessageBox.warning(self, "错误", "无法连接到数据库，请检查数据库文件。")
            return
        print("数据库连接成功")
        
        # 显示进度对话框
        self.progress_dialog = ProgressDialog(self)
        self.progress_dialog.setWindowTitle("分析中")
        self.progress_dialog.set_task_info("基因数据分析")
        self.progress_dialog.show()
        QApplication.processEvents()
        
        try:
            # 获取系谱库实例并构建包含母牛数据的完整系谱库
            from core.data.update_manager import get_pedigree_db
            from pathlib import Path
            
            # 更新进度
            self.update_progress(5, "获取系谱库...")
            QApplication.processEvents()
            
            # 获取系谱库实例
            pedigree_db = get_pedigree_db()
            
            # 获取母牛数据文件路径
            cow_file = project_path / "standardized_data" / "processed_cow_data.xlsx"
            
            # 更新进度
            self.update_progress(10, "构建母牛系谱库...")
            QApplication.processEvents()
            
            # 构建母牛系谱库并合并
            def update_progress(value, message):
                if isinstance(value, int):
                    # 将系谱库构建进度(0-100)映射到总进度的10-25区间
                    mapped_value = 10 + int(value * 0.15)
                    self.update_progress(mapped_value, message)
                self.progress_dialog.set_task_info(message)
                QApplication.processEvents()
                return not self.progress_dialog.cancelled
            
            # 检查母牛数据文件是否存在
            if not cow_file.exists():
                print(f"母牛数据文件不存在: {cow_file}")
                QMessageBox.warning(self, "错误", f"母牛数据文件不存在: {cow_file}\n请确保已上传并处理母牛数据。")
                self.progress_dialog.close()
                return
                
            # 构建母牛系谱库
            print("开始构建母牛系谱库...")
            pedigree_db.build_cow_pedigree(cow_file, update_progress)
            print("母牛系谱库构建完成")
                
            # 收集所需的公牛号
            print("开始收集所需的公牛号...")
            required_bulls = self.collect_required_bulls(analysis_type, project_path)
            print(f"收集到{len(required_bulls)}个公牛号")
            self.update_progress(30, "收集公牛号")
            QApplication.processEvents()
            
            if self.progress_dialog.cancelled:
                print("用户取消了分析")
                return
                
            # 查询公牛基因信息
            print("开始查询公牛基因信息...")
            bull_genes, missing_bulls = self.query_bull_genes(required_bulls)
            print(f"查询到{len(bull_genes)}个公牛的基因信息，有{len(missing_bulls)}个公牛未找到")
            self.update_progress(40, "查询公牛基因信息")
            QApplication.processEvents()
            
            if self.progress_dialog.cancelled:
                print("用户取消了分析")
                return
                
            # 处理缺失的公牛记录
            if missing_bulls:
                print(f"处理{len(missing_bulls)}个缺失的公牛记录...")
                self.process_missing_bulls(missing_bulls, analysis_type)
            
            # 根据分析类型执行不同的分析
            print(f"开始执行{analysis_type}类型的分析...")
            if analysis_type == "mated":
                # 分析已配公牛对
                print("分析已配公牛对...")
                results = self.analyze_mated_pairs(project_path, bull_genes)
            else:
                # 分析备选公牛对
                print("分析备选公牛对...")
                results = self.analyze_candidate_pairs(project_path, bull_genes)
                
            self.update_progress(70, "分析完成")
            QApplication.processEvents()
            
            if self.progress_dialog.cancelled:
                print("用户取消了分析")
                return
                
            # 计算近交系数
            print("计算近交系数...")
            results = self.calculate_inbreeding_coefficients(project_path, results)
            
            # 打印检查后代近交系数
            print("后代近交系数信息检查:")
            for i, result in enumerate(results[:5]):  # 只打印前5条
                print(f"记录 {i+1}: 后代近交系数={result.get('后代近交系数', '未找到')}, "
                     f"后代近交详情存在={bool(result.get('后代近交详情'))}")
                
            self.update_progress(90, "完成分析")
            QApplication.processEvents()
            
            if self.progress_dialog.cancelled:
                print("用户取消了分析")
                return
                
            # 收集异常配对
            print("收集异常配对...")
            abnormal_df, stats_df = self.collect_abnormal_pairs(results)
            
            # 将结果转换为DataFrame并确保后代近交系数列存在
            results_df = pd.DataFrame(results)
            if '后代近交系数' not in results_df.columns and any('后代近交系数' in item for item in results):
                # 如果列名丢失但数据存在，手动添加列
                results_df['后代近交系数'] = [item.get('后代近交系数', '0.00%') for item in results]
                
            # 打印列名检查
            print(f"结果DataFrame列名: {list(results_df.columns)}")
            
            # 更新表格数据
            print("更新表格数据...")
            self.detail_model.update_data(results_df)
            self.abnormal_model.update_data(abnormal_df)
            self.stats_model.update_data(stats_df)
            
            # 完成
            self.progress_dialog.update_progress(100)
            print(f"{analysis_type}分析完成")
            
            # 自动保存分析结果
            self.export_results(auto_save=True)
            
        except Exception as e:
            print(f"执行{analysis_type}分析时发生错误: {e}")
            logging.error(f"执行隐性基因分析时发生错误: {e}")
            QMessageBox.critical(self, "错误", f"分析过程中发生错误: {str(e)}")
            
        finally:
            self.progress_dialog.close()
            if self.db_engine:
                self.db_engine.dispose()

    def show_calculation_method_detail(self):
        """显示近交系数计算方法的详细说明"""
        from PyQt6.QtWidgets import QTextBrowser
        
        # 创建详细说明对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("近交系数计算方法详细说明")
        dialog.resize(800, 600)
        
        layout = QVBoxLayout(dialog)
        
        # 创建文本浏览器
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        
        # 设置详细说明内容
        content = """
        <h2>近交系数计算方法详细说明</h2>
        
        <h3>一、基本原理</h3>
        <p>本系统采用Wright通径法（Wright's Path Method）计算动物的近交系数。</p>
        
        <h3>二、计算公式</h3>
        <p><b>F = Σ(0.5)<sup>(n+n'+1)</sup> × (1+F<sub>A</sub>)</b></p>
        <ul>
            <li><b>F</b>: 被计算个体的近交系数</li>
            <li><b>n</b>: 从父亲到共同祖先的代数</li>
            <li><b>n'</b>: 从母亲到共同祖先的代数</li>
            <li><b>F<sub>A</sub></b>: 共同祖先自身的近交系数</li>
            <li><b>Σ</b>: 对所有共同祖先路径的贡献求和</li>
        </ul>
        
        <h3>三、计算步骤</h3>
        <ol>
            <li><b>系谱构建</b>：追溯个体的父系和母系系谱，默认追溯6代</li>
            <li><b>共同祖先识别</b>：查找父母双方系谱中的共同祖先</li>
            <li><b>路径计算</b>：计算每条路径的贡献值</li>
            <li><b>近交系数调整</b>：考虑共同祖先自身的近交系数</li>
            <li><b>累加求和</b>：将所有路径贡献值累加得到最终结果</li>
        </ol>
        
        <h3>四、特殊情况</h3>
        <ul>
            <li><b>GIB值优先</b>：当动物有基因组近交系数（GIB）时，直接使用GIB值</li>
            <li><b>系谱信息不全</b>：缺失的祖先不参与计算</li>
            <li><b>代数限制</b>：默认追溯6代，可根据需要调整</li>
        </ul>
        
        <h3>五、结果解释</h3>
        <ul>
            <li><b>F < 3.125%</b>：低度近交，一般认为安全</li>
            <li><b>3.125% ≤ F < 6.25%</b>：中度近交，需要注意</li>
            <li><b>F ≥ 6.25%</b>：高度近交，建议避免</li>
        </ul>
        
        <h3>六、计算示例</h3>
        <p>假设母牛与公牛有共同祖先A：</p>
        <ul>
            <li>父系路径长度 n = 2</li>
            <li>母系路径长度 n' = 3</li>
            <li>祖先A的近交系数 F<sub>A</sub> = 0.05</li>
        </ul>
        <p>计算：基础贡献 = (0.5)<sup>6</sup> = 0.015625</p>
        <p>调整后 = 0.015625 × (1 + 0.05) = 0.0164 = 1.64%</p>
        """
        
        text_browser.setHtml(content)
        layout.addWidget(text_browser)
        
        # 添加关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        dialog.exec()
    
    def export_results(self, auto_save=False):
        """导出分析结果到Excel文件
        
        Args:
            auto_save: 是否自动保存到项目文件夹
        """
        try:
            # 检查是否有数据可以导出
            if self.detail_model.df.empty and self.abnormal_model.df.empty and self.stats_model.df.empty:
                if not auto_save:  # 只在手动导出时显示警告
                    QMessageBox.warning(self, "警告", "没有可导出的数据，请先进行分析。")
                return

            # 根据最后点击的按钮来判断分析类型
            if not hasattr(self, '_last_analysis_type'):
                default_filename = "近交系数及隐性基因分析结果.xlsx"
            else:
                if self._last_analysis_type == "mated":
                    default_filename = "已配公牛_近交系数及隐性基因分析结果.xlsx"
                else:
                    default_filename = "备选公牛_近交系数及隐性基因分析结果.xlsx"

            file_path = None
            if auto_save:
                # 自动保存到项目目录下的analysis_results文件夹
                project_path = self.get_project_path()
                if not project_path:
                    return
                    
                # 确保analysis_results文件夹存在
                analysis_dir = project_path / "analysis_results"
                if not analysis_dir.exists():
                    analysis_dir.mkdir(parents=True, exist_ok=True)
                    
                # 添加时间戳到文件名
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{default_filename.split('.')[0]}_{timestamp}.xlsx"
                file_path = str(analysis_dir / filename)
            else:
                # 手动选择保存位置
                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "导出分析结果",
                    default_filename,
                    "Excel Files (*.xlsx)"
                )

            if not file_path:
                return

            # 创建Excel写入器
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # 导出配对明细表
                if not self.detail_model.df.empty:
                    self.detail_model.df.to_excel(writer, sheet_name='配对明细表', index=False)

                # 导出异常明细表
                if not self.abnormal_model.df.empty:
                    self.abnormal_model.df.to_excel(writer, sheet_name='异常明细表', index=False)

                # 导出统计表
                if not self.stats_model.df.empty:
                    self.stats_model.df.to_excel(writer, sheet_name='统计表', index=False)

            if auto_save:
                # 弹出自定义对话框，提供打开文件选项
                self.show_export_success_dialog(file_path)
            else:
                # 显示成功消息
                QMessageBox.information(self, "导出成功", f"分析结果已成功导出到:\n{file_path}")

        except Exception as e:
            logging.error(f"导出分析结果时发生错误: {e}")
            QMessageBox.critical(self, "导出失败", f"导出过程中发生错误:\n{str(e)}")

    def show_export_success_dialog(self, file_path):
        """显示导出成功对话框，提供打开文件选项
        
        Args:
            file_path: 导出文件的路径
        """
        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("分析完成")
        
        # 设置对话框布局
        layout = QVBoxLayout(dialog)
        
        # 添加消息标签
        message = QLabel(f"分析结果已自动保存到:\n{file_path}")
        message.setWordWrap(True)
        layout.addWidget(message)
        
        # 添加按钮
        button_layout = QHBoxLayout()
        open_button = QPushButton("打开")
        cancel_button = QPushButton("取消")
        
        # 设置按钮样式
        open_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        
        button_layout.addWidget(open_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        # 连接信号
        open_button.clicked.connect(lambda: self.open_file(file_path))
        open_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        
        # 显示对话框
        dialog.setMinimumWidth(400)
        dialog.exec()

    def open_file(self, file_path):
        """使用系统默认程序打开文件
        
        Args:
            file_path: 要打开的文件路径
        """
        try:
            import os
            import platform
            
            # 根据操作系统选择打开文件的方法
            system = platform.system()
            if system == 'Windows':
                os.startfile(file_path)
            elif system == 'Darwin':  # macOS
                import subprocess
                subprocess.call(['open', file_path])
            else:  # Linux
                import subprocess
                subprocess.call(['xdg-open', file_path])
                
        except Exception as e:
            logging.error(f"打开文件时发生错误: {e}")
            QMessageBox.warning(self, "打开失败", f"无法打开文件: {str(e)}\n请手动打开文件。")