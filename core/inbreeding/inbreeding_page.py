from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QTableView, QFrame, QSplitter, QMessageBox, QApplication,
    QProgressDialog, QMainWindow, QDialog, QTabWidget, QComboBox, QListWidget, QTextEdit, QHeaderView, QMenu
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QStandardItemModel, QStandardItem
import pandas as pd
import logging
from pathlib import Path
from sqlalchemy import create_engine, text
import datetime
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from typing import List, Dict, Tuple, Set, Optional
import math

from .models import InbreedingDetailModel, AbnormalDetailModel, StatisticsModel
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
            # 配置中文字体支持
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'Heiti TC', 'Arial Unicode MS']
            plt.rcParams['axes.unicode_minus'] = False  # 正确显示负号
            
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
            node_height = 2.8   # 进一步增加方框高度
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
                
                # 在方框中显示REG号（字号为NAAB的2/3）
                reg_fontsize = 6 if gen <= 2 else 5
                ax.text(
                    x, y - node_height/4,  # 增加垂直间距
                    display_text,
                    family='SimHei',
                    ha='center',
                    va='center',
                    fontsize=reg_fontsize,
                    color=text_color,
                    zorder=3
                )
                
                # 在方框中显示NAAB号（加粗显示）
                if naab and node_id not in ["预期后代", "父亲未知", "母亲未知"]:
                    naab_fontsize = 9 if gen <= 2 else 7.5
                    ax.text(
                        x, y + node_height/4,  # 增加垂直间距
                        naab_text,
                        family='SimHei',
                        ha='center',
                        va='center',
                        fontsize=naab_fontsize,
                        fontweight='bold',
                        color=text_color,
                        zorder=3
                    )
            
            # 设置图表属性
            ax.set_title("血缘关系图 (6代)", fontproperties='SimHei')
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
                """鼠标滚轮缩放事件处理"""
                # 获取当前缩放比例
                cur_xlim = ax.get_xlim()
                cur_ylim = ax.get_ylim()
                cur_xrange = (cur_xlim[1] - cur_xlim[0]) * 0.5
                cur_yrange = (cur_ylim[1] - cur_ylim[0]) * 0.5
                xdata = event.xdata  # 获取鼠标x坐标
                ydata = event.ydata  # 获取鼠标y坐标
                
                if xdata is None or ydata is None:
                    return
                
                if event.button == 'up':  # 放大
                    # 缩放比例因子
                    scale_factor = 0.7  # 更快的缩放速度
                else:  # 缩小
                    # 缩放比例因子
                    scale_factor = 1.4  # 更快的缩放速度
                
                # 设置新的缩放范围
                ax.set_xlim([xdata - cur_xrange * scale_factor,
                           xdata + cur_xrange * scale_factor])
                ax.set_ylim([ydata - cur_yrange * scale_factor,
                           ydata + cur_yrange * scale_factor])
                
                # 重新绘制图表
                self.canvas.draw()
            
            # 添加滚轮事件
            self.canvas.mpl_connect('scroll_event', on_scroll)
            
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
            
            def on_motion(event):
                """鼠标移动事件处理"""
                if self.pan_enabled and self.pan_start_xy is not None:
                    # 计算移动距离
                    if event.xdata is None or event.ydata is None or self.pan_start_xy[0] is None or self.pan_start_xy[1] is None:
                        return
                        
                    dx = event.xdata - self.pan_start_xy[0]
                    dy = event.ydata - self.pan_start_xy[1]
                    
                    # 更新坐标轴范围
                    ax.set_xlim(ax.get_xlim() - dx)
                    ax.set_ylim(ax.get_ylim() - dy)
                    
                    # 更新起始点
                    self.pan_start_xy = (event.xdata, event.ydata)
                    
                    # 重新绘制图表
                    self.canvas.draw()
            
            # 添加鼠标事件监听
            self.canvas.mpl_connect('button_press_event', on_press)
            self.canvas.mpl_connect('button_release_event', on_release)
            self.canvas.mpl_connect('motion_notify_event', on_motion)
            
            # 创建图例
            legend_elements = [
                plt.Rectangle((0, 0), 1, 1, facecolor='lightgreen', edgecolor='green', label='预期后代'),
                plt.Rectangle((0, 0), 1, 1, facecolor='#444444', edgecolor='#333333', label='父系'),
                plt.Rectangle((0, 0), 1, 1, facecolor='white', edgecolor='gray', label='母系')
            ]
            
            # 添加共同祖先颜色到图例
            for i, (ancestor, color) in enumerate(common_ancestor_colors.items()):
                if i < 4:  # 最多显示4个共同祖先在图例中
                    display_name = ancestor
                    if len(ancestor) > 12:  # 增加显示长度
                        # 保留末尾部分的REG号，这通常是最有识别度的部分
                        display_name = "..." + ancestor[-10:]
                    legend_elements.append(
                        plt.Rectangle((0, 0), 1, 1, facecolor=color, edgecolor='green', label=f'共同祖先: {display_name}')
                    )
            
            # 添加图例到图表右上角
            ax.legend(handles=legend_elements, loc='upper right', fontsize='x-small')
            
            # 更新后代近交系数标签（如果存在）
            if hasattr(self, 'offspring_label'):
                offspring_inbreeding = self.offspring_details.get('system', 0.0) if self.offspring_details else 0.0
                self.offspring_label.setText(f"潜在后代近交系数: {offspring_inbreeding:.2%}")
            
        except Exception as e:
            logging.error(f"绘制血缘关系图时出错: {str(e)}")
            ax.text(0.5, 0.5, f"绘制血缘关系图时出错: {str(e)}", 
                   horizontalalignment='center', verticalalignment='center')
            
        self.canvas.draw()

    def on_canvas_click(self, event):
        """画布点击事件处理"""
        if event.dblclick:  # 检测双击事件
            # 创建并显示最大化图像对话框
            max_dialog = MaximizedPedigreeDialog(self, self.cow_id, self.sire_id, self.bull_id, 
                                               self.offspring_details)
            max_dialog.exec()

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
        
        layout = QVBoxLayout(self)
        
        # 创建新的图形和画布
        self.figure = Figure(figsize=(12, 10))  # 设置合适的画布大小
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        # 添加关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.on_close)
        layout.addWidget(close_button)
        
        # 启用互动功能
        self.canvas.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self.canvas.setMouseTracking(True)
        
        # 连接事件处理函数
        self.canvas.mpl_connect('scroll_event', self.on_scroll)
        self.canvas.mpl_connect('button_press_event', self.on_press)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        
        # 添加右键菜单
        self.canvas.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self.show_context_menu)
        
        # 平移和缩放状态
        self.pan_enabled = False
        self.pan_start_xy = None
        self.current_scale = 1.0
        self.zoom_factor = 1.2
        self.min_zoom = 0.1
        self.max_zoom = 5.0
        
        # 绘制完整的6代系谱图
        self.draw_pedigree()
    
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
        
        # 获取保存的文件名
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存血缘关系图", "", 
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
                
    def draw_pedigree(self):
        """绘制完整的6代系谱图 - 采用固定画布大小和均匀分布节点"""
        # 创建新的图形和画布
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        try:
            # 配置中文字体支持
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'Heiti TC', 'Arial Unicode MS']
            plt.rcParams['axes.unicode_minus'] = False  # 正确显示负号
            
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
            node_width = 10.0   # 保持适当节点宽度
            node_height = 2.8   # 固定节点高度
            min_v_spacing = 1.2  # 最小垂直间距
            h_spacing = 15.0    # 水平间距
            
            # 计算画布总高度 - 根据第6代节点数(64)
            total_nodes_last_gen = 2 ** 6  # 64个节点
            canvas_height = (node_height + min_v_spacing) * total_nodes_last_gen
            
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
                    edges.append((parent_x + node_width/2, parent_y, x - node_width/2, y))
            
            # 绘制边（连接线）
            for start_x, start_y, end_x, end_y in edges:
                ax.plot([start_x, end_x], [start_y, end_y], color='green', linewidth=1.0, zorder=1)
            
            # 绘制节点（方框）
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
                naab = naab_dict.get(animal_id, "")
                
                # 显示ID和NAAB号
                display_text = str(animal_id)
                naab_text = str(naab) if naab else ""
                
                # 使用固定字体大小，根据文本长度控制
                reg_fontsize = min(8, 8 * 8 / max(len(display_text), 8))  # REG号字体大小上限8
                naab_fontsize = min(10, 10 * 8 / max(len(naab_text), 8))  # NAAB号字体大小上限10
                
                # 在方框中显示REG号
                ax.text(
                    x, y - node_height/4,  # 设置垂直位置
                    display_text,
                    family='SimHei',
                    ha='center',
                    va='center',
                    fontsize=reg_fontsize,
                    color=text_color,
                    zorder=3
                )
                
                # 在方框中显示NAAB号（加粗显示）
                if naab and animal_id not in ["预期后代", "父亲未知", "母亲未知"]:
                    ax.text(
                        x, y + node_height/4,  # 设置垂直位置
                        naab_text,
                        family='SimHei',
                        ha='center',
                        va='center',
                        fontsize=naab_fontsize,
                        fontweight='bold',
                        color=text_color,
                        zorder=3
                    )
            
            # 设置图表属性
            ax.set_title("血缘关系图 (6代完整视图)", fontsize=18, fontfamily='SimHei')
            ax.axis('off')  # 隐藏坐标轴
            
            # 自动调整布局，适应所有节点
            # 确保有足够的边距
            x_margin = node_width
            y_margin = node_height * 2
            
            ax.set_xlim(-x_margin, 6 * h_spacing + node_width + x_margin)
            ax.set_ylim(-canvas_height/2 - y_margin, canvas_height/2 + y_margin)
            
            # 创建图例
            legend_elements = [
                plt.Rectangle((0, 0), 1, 1, facecolor='lightgreen', edgecolor='green', label='预期后代'),
                plt.Rectangle((0, 0), 1, 1, facecolor='#444444', edgecolor='#333333', label='父系'),
                plt.Rectangle((0, 0), 1, 1, facecolor='white', edgecolor='gray', label='母系')
            ]
            
            # 添加共同祖先颜色到图例
            for i, (ancestor, color) in enumerate(common_ancestor_colors.items()):
                if i < 4:  # 最多显示4个共同祖先在图例中
                    display_name = ancestor
                    if len(display_name) > 15:  # 增加显示长度
                        # 保留末尾部分的REG号，这通常是最有识别度的部分
                        display_name = "..." + display_name[-12:]
                    legend_elements.append(
                        plt.Rectangle((0, 0), 1, 1, facecolor=color, edgecolor='red', label=f'共同祖先: {display_name}')
                    )
            
            # 添加图例到图表右上角
            legend = ax.legend(handles=legend_elements, loc='upper right', fontsize='medium')
            
        except Exception as e:
            logging.error(f"绘制完整血缘关系图时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            ax.text(0.5, 0.5, f"绘制血缘关系图时出错: {str(e)}", 
                   horizontalalignment='center', verticalalignment='center')
        
        # 绘制
        self.canvas.draw()
    
    def on_scroll(self, event):
        """滚轮缩放事件处理 - 简单的整体缩放，保持固定字体大小"""
        ax = self.figure.get_axes()[0]
        
        # 获取当前视图范围
        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()
        
        # 获取鼠标位置
        xdata = event.xdata
        ydata = event.ydata
        
        if xdata is None or ydata is None:
            return
            
        # 计算缩放
        if event.button == 'up':
            scale_factor = 1.0 / self.zoom_factor
            self.current_scale *= self.zoom_factor
        else:
            scale_factor = self.zoom_factor
            self.current_scale /= self.zoom_factor
        
        # 限制缩放范围
        if self.current_scale < self.min_zoom:
            scale_factor = self.min_zoom / (self.current_scale * self.zoom_factor)
            self.current_scale = self.min_zoom
        elif self.current_scale > self.max_zoom:
            scale_factor = self.max_zoom / (self.current_scale / self.zoom_factor)
            self.current_scale = self.max_zoom
        
        # 更新视图范围
        new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
        new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor
        
        ax.set_xlim([xdata - new_width * (xdata - cur_xlim[0]) / (cur_xlim[1] - cur_xlim[0]),
                     xdata + new_width * (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])])
        ax.set_ylim([ydata - new_height * (ydata - cur_ylim[0]) / (cur_ylim[1] - cur_ylim[0]),
                     ydata + new_height * (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])])
        
        # 重新绘制图表，不调整字体大小
        self.canvas.draw_idle()
    
    def on_press(self, event):
        """鼠标按下事件处理"""
        if event.button == 1:
            self.pan_enabled = True
            self.pan_start_xy = (event.xdata, event.ydata)
            self.canvas.setCursor(Qt.CursorShape.ClosedHandCursor)
    
    def on_release(self, event):
        """鼠标释放事件处理"""
        if event.button == 1:
            self.pan_enabled = False
            self.pan_start_xy = None
            self.canvas.setCursor(Qt.CursorShape.ArrowCursor)
    
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
            self.canvas.draw_idle()
    
    def on_close(self):
        """关闭对话框时的处理"""
        self.accept()
        # 重新绘制父窗口的3代系谱图
        self.parent_widget.draw_pedigree(max_generations=3)

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
        
        # 表格视图
        self.detail_table = QTableView()
        self.detail_model = InbreedingDetailModel()
        self.detail_table.setModel(self.detail_model)
        
        # 设置表格属性以显示所有列
        self.detail_table.horizontalHeader().setStretchLastSection(True)  # 最后一列填充剩余空间
        self.detail_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)  # 自动调整列宽
        
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
        try:
            # 读取配对数据
            breeding_file = project_path / "standardized_data" / "processed_breeding_data.xlsx"
            print(f"开始分析已配公牛对，从{breeding_file}读取数据")
            df = pd.read_excel(breeding_file)
            print(f"读取到{len(df)}条配对记录")
            
            # 获取系谱库实例用于ID转换
            from core.data.update_manager import get_pedigree_db
            pedigree_db = get_pedigree_db()
            
            # 分析每个配对
            results = []
            print("开始分析每个配对...")
            for i, row in enumerate(df.iterrows()):
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
                if original_bull_id != bull_id and original_bull_id:
                    print(f"  冻精编号转换: {original_bull_id} -> {bull_id}")
                
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
            return results
                
        except Exception as e:
            print(f"分析已配公牛对时发生错误: {e}")
            logging.error(f"分析已配公牛对时发生错误: {e}")
            return []

    def analyze_candidate_pairs(self, project_path: Path, bull_genes: Dict[str, str]) -> List[Dict]:
        """分析备选公牛对"""
        results = []
        try:
            # 读取母牛数据和备选公牛数据
            cow_file = project_path / "standardized_data" / "processed_cow_data.xlsx"
            bull_file = project_path / "standardized_data" / "processed_bull_data.xlsx"
            print(f"开始分析备选公牛对，从{cow_file}和{bull_file}读取数据")
            
            cow_df = pd.read_excel(cow_file)
            bull_df = pd.read_excel(bull_file)
            print(f"读取到{len(cow_df)}条母牛记录和{len(bull_df)}条备选公牛记录")
            
            # 获取系谱库实例用于ID转换
            from core.data.update_manager import get_pedigree_db
            pedigree_db = get_pedigree_db()
            
            # 只分析在群的母牛
            cow_df = cow_df[cow_df['是否在场'] == '是']
            print(f"过滤后在群的母牛数量: {len(cow_df)}")
            
            # 分析每对组合
            print("开始分析每对母牛和备选公牛的组合...")
            cow_count = 0
            pair_count = 0
            for _, cow_row in cow_df.iterrows():
                cow_count += 1
                if cow_count <= 5 or cow_count % 50 == 0:  # 只打印前5头牛和每50头牛，避免日志过长
                    print(f"分析第{cow_count}头母牛")
                
                cow_id = str(cow_row['cow_id'])
                
                # 标准化父号
                original_sire_id = str(cow_row['sire']) if pd.notna(cow_row['sire']) else ''
                sire_id = pedigree_db.standardize_animal_id(original_sire_id, 'bull')
                
                if original_sire_id != sire_id and original_sire_id:
                    print(f"  父号转换: {original_sire_id} -> {sire_id}")
                
                # 获取母牛基因信息（通过父号）
                cow_genes = bull_genes.get(sire_id, {gene: 'missing data' for gene in self.defect_genes})
                
                # 分析与每个备选公牛的组合
                for _, bull_row in bull_df.iterrows():
                    pair_count += 1
                    if pair_count <= 5 or pair_count % 1000 == 0:  # 只打印前5对和每1000对，避免日志过长
                        print(f"  分析第{pair_count}对组合: 母牛{cow_id} - 公牛{bull_row['bull_id']}")
                    
                    # 标准化备选公牛ID
                    original_bull_id = str(bull_row['bull_id'])
                    bull_id = pedigree_db.standardize_animal_id(original_bull_id, 'bull')
                    
                    if original_bull_id != bull_id and original_bull_id:
                        print(f"  备选公牛号转换: {original_bull_id} -> {bull_id}")
                    
                    candidate_genes = bull_genes.get(bull_id, {gene: 'missing data' for gene in self.defect_genes})
                    
                    # 分析安全性
                    gene_results = self.analyze_gene_safety(cow_genes, candidate_genes)
                    
                    # 计算近交系数（临时使用随机值，后续会替换为真实计算）
                    inbreeding_coef = 0.0  # 默认值，后续会替换为真实计算
                    
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
            return results
            
        except Exception as e:
            print(f"分析备选公牛对时发生错误: {e}")
            logging.error(f"分析备选公牛对时发生错误: {e}")
            return []

    def collect_abnormal_pairs(self, results: List[Dict]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """收集异常配对和统计信息"""
        abnormal_records = []
        gene_stats = {gene: 0 for gene in self.defect_genes}
        
        for result in results:
            for gene in self.defect_genes:
                if result[gene] == 'NO safe':
                    abnormal_records.append({
                        '母牛号': result['母牛号'],
                        '父号': result['父号'],
                        '公牛号': result.get('配种公牛号', result.get('备选公牛号')),
                        '异常类型': gene,
                        '状态': 'NO safe'
                    })
                    gene_stats[gene] += 1
        
        # 创建异常记录DataFrame
        abnormal_df = pd.DataFrame(abnormal_records)
        
        # 创建统计信息DataFrame
        stats_df = pd.DataFrame([
            {'异常类型': gene, '数量': count}
            for gene, count in gene_stats.items()
            if count > 0
        ])
        
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
            calculator = PathInbreedingCalculator(max_generations=6)
            
            # 统计计数器
            total_count = len(results)
            success_count = 0
            zero_count = 0
            high_inbreeding_count = 0  # 近交系数 > 0.0625 (6.25%)
            offspring_count = 0  # 统计计算后代近交系数的次数
            print(f"需要计算 {total_count} 个配对的近交系数")
            
            # 开始计算
            for i, result in enumerate(results):
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
                        
                        # 输出高后代近交系数警告
                        if offspring_inbreeding > 0.0625:  # 6.25%
                            print(f"⚠️ 高后代近交警告! {bull_id} 和 {cow_id} 的潜在后代近交系数: {offspring_inbreeding:.2%}")
                        
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
                    except Exception as e:
                        print(f"[ERROR] 计算后代近交系数时出错: {str(e)}")
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
            print("============================\n")
                
            return results
            
        except Exception as e:
            logging.error(f"计算近交系数时出错: {str(e)}")
            print(f"⚠️ 计算近交系数时出错: {str(e)}")
            return results
            
    def start_analysis(self, analysis_type: str):
        """开始分析"""
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
        progress = QProgressDialog("正在分析基因数据...", "取消", 0, 100, self)
        progress.setWindowTitle("分析中")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        QApplication.processEvents()
        
        try:
            # 获取系谱库实例并构建包含母牛数据的完整系谱库
            from core.data.update_manager import get_pedigree_db
            from pathlib import Path
            
            # 更新进度
            progress.setValue(5)
            progress.setLabelText("获取系谱库...")
            QApplication.processEvents()
            
            # 获取系谱库实例
            pedigree_db = get_pedigree_db()
            
            # 获取母牛数据文件路径
            cow_file = project_path / "standardized_data" / "processed_cow_data.xlsx"
            
            # 更新进度
            progress.setValue(10)
            progress.setLabelText("构建母牛系谱库...")
            QApplication.processEvents()
            
            # 构建母牛系谱库并合并
            def update_progress(value, message):
                if isinstance(value, int):
                    # 将系谱库构建进度(0-100)映射到总进度的10-25区间
                    mapped_value = 10 + int(value * 0.15)
                    progress.setValue(mapped_value)
                progress.setLabelText(message)
                QApplication.processEvents()
                return not progress.wasCanceled()
            
            # 检查母牛数据文件是否存在
            if not cow_file.exists():
                print(f"母牛数据文件不存在: {cow_file}")
                QMessageBox.warning(self, "错误", f"母牛数据文件不存在: {cow_file}\n请确保已上传并处理母牛数据。")
                progress.close()
                return
                
            # 构建母牛系谱库
            print("开始构建母牛系谱库...")
            pedigree_db.build_cow_pedigree(cow_file, update_progress)
            print("母牛系谱库构建完成")
                
            # 收集所需的公牛号
            print("开始收集所需的公牛号...")
            required_bulls = self.collect_required_bulls(analysis_type, project_path)
            print(f"收集到{len(required_bulls)}个公牛号")
            progress.setValue(30)
            QApplication.processEvents()
            
            if progress.wasCanceled():
                print("用户取消了分析")
                return
                
            # 查询公牛基因信息
            print("开始查询公牛基因信息...")
            bull_genes, missing_bulls = self.query_bull_genes(required_bulls)
            print(f"查询到{len(bull_genes)}个公牛的基因信息，有{len(missing_bulls)}个公牛未找到")
            progress.setValue(40)
            QApplication.processEvents()
            
            if progress.wasCanceled():
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
                
            progress.setValue(70)
            QApplication.processEvents()
            
            if progress.wasCanceled():
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
                
            progress.setValue(90)
            QApplication.processEvents()
            
            if progress.wasCanceled():
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
            progress.setValue(100)
            print(f"{analysis_type}分析完成")
            QMessageBox.information(self, "完成", f"基因分析完成，共分析{len(results)}对配对。")
            
        except Exception as e:
            print(f"执行{analysis_type}分析时发生错误: {e}")
            logging.error(f"执行隐性基因分析时发生错误: {e}")
            QMessageBox.critical(self, "错误", f"分析过程中发生错误: {str(e)}")
            
        finally:
            progress.close()
            if self.db_engine:
                self.db_engine.dispose()