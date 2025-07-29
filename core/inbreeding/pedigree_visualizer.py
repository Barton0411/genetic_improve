from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsTextItem, QGraphicsLineItem, QGraphicsRectItem
)
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPen, QBrush, QColor, QPainter, QFont, QTransform, QMouseEvent
import pandas as pd
import platform


class PedigreeTreeView(QGraphicsView):
    def __init__(self, calculator, animal_id):
        super().__init__()
        self.calculator = calculator
        self.animal_id = animal_id
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        
        # 默认启用拖动功能（使用左键）
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 设置抗锯齿
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 设置变换锚点为鼠标位置
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        # 缩放参数
        self.zoom_factor = 1.15
        self.min_zoom = 0.1
        self.max_zoom = 3.0
        
        # 布局参数计算
        self.generations = 6
        self.last_gen_boxes = 2 ** self.generations
        
        # 节点大小和间距（水平布局）
        self.node_width = 180   # 增加宽度以容纳更多信息
        self.node_height = 40
        self.horizontal_spacing = 100  # 代与代之间的间距
        self.vertical_spacing = 60    # 同代中节点之间的间距
        
        # 计算场景大小
        total_width = (self.generations + 1) * (self.node_width + self.horizontal_spacing)
        total_height = self.last_gen_boxes * self.vertical_spacing
        
        # 计算每一代的节点位置
        self.level_positions = self._calculate_level_positions(total_height)
        
        # 设置场景大小
        self.scene.setSceneRect(0, 0, total_width, total_height)
        
        self.common_ancestors = set()
        self.initUI()

    def _calculate_level_positions(self, total_height):
        """计算每一代节点的位置（水平布局）"""
        level_positions = []
        
        for level in range(self.generations + 1):
            nodes_in_level = 2 ** level
            positions = []
            
            # 计算该层的起始位置和节点间距
            level_height = nodes_in_level * self.vertical_spacing
            start_y = (total_height - level_height) / 2
            
            for i in range(nodes_in_level):
                y = start_y + i * self.vertical_spacing
                positions.append(y)
            
            level_positions.append(positions)
        
        return level_positions

    def wheelEvent(self, event):
        """处理鼠标滚轮事件"""
        # 直接处理滚轮事件进行缩放
        # 获取当前缩放比例
        current_zoom = self.transform().m11()
        
        # 计算缩放因子
        if event.angleDelta().y() > 0:
            factor = self.zoom_factor
        else:
            factor = 1 / self.zoom_factor
        
        # 检查是否超出缩放限制
        new_zoom = current_zoom * factor
        if new_zoom < self.min_zoom or new_zoom > self.max_zoom:
            return
        
        # 应用缩放
        self.scale(factor, factor)
        event.accept()  # 标记事件已处理

    def keyPressEvent(self, event):
        """处理键盘按下事件"""
        if event.key() == Qt.Key.Key_Space:
            # 空格键用于重置视图
            self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        elif event.key() == Qt.Key.Key_Plus or event.key() == Qt.Key.Key_Equal:
            # + 键放大
            self.scale(self.zoom_factor, self.zoom_factor)
        elif event.key() == Qt.Key.Key_Minus:
            # - 键缩小
            self.scale(1 / self.zoom_factor, 1 / self.zoom_factor)
        else:
            super().keyPressEvent(event)

    def initUI(self):
        # 计算近交系数
        F, status, calculation_method = self.calculator.calculate_inbreeding_coefficient(self.animal_id)
        self.common_ancestors = self.calculator.common_ancestors
        
        # 构建系谱树
        pedigree_tree = self.calculator.build_complete_pedigree(self.animal_id)
        if pedigree_tree:
            # 从第一代开始绘制
            self.draw_tree(pedigree_tree, 0, 0)
            
            # 自动调整视图
            self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            
            # 添加近交系数和计算过程显示
            self.add_calculation_details(F, calculation_method)

    def draw_tree(self, node, level, index):
        """递归绘制系谱树"""
        if not node or level > self.generations:
            return
            
        # 计算当前节点位置
        x = level * (self.node_width + self.horizontal_spacing)
        y = self.level_positions[level][index]
        
        # 创建当前节点
        node_item = self.create_node_item(node, x, y)
        self.scene.addItem(node_item)
        
        # 计算下一级位置
        next_level = level + 1
        if next_level <= self.generations:
            # 计算父亲和母亲的位置
            next_index = index * 2
            sire_y = self.level_positions[next_level][next_index]
            dam_y = self.level_positions[next_level][next_index + 1]
            
            # 绘制到父亲的连线（上方）
            self.draw_connection_line(
                x + self.node_width,  # 起点x
                y,                    # 起点y（节点中心）
                x + self.node_width + self.horizontal_spacing,  # 终点x
                sire_y,              # 终点y（父亲节点中心）
                True                 # 是父系连线
            )
            
            # 绘制到母亲的连线（下方）
            self.draw_connection_line(
                x + self.node_width,  # 起点x
                y,                    # 起点y（节点中心）
                x + self.node_width + self.horizontal_spacing,  # 终点x
                dam_y,               # 终点y（母亲节点中心）
                False                # 是母系连线
            )
            
            # 递归绘制父亲节点
            if node.get('sire'):
                self.draw_tree(node['sire'], next_level, next_index)
            else:
                # 创建未知父亲节点
                unknown_sire = {
                    'id': 'unknown_bull',
                    'type': 'bull',
                    'gib': None
                }
                self.draw_tree(unknown_sire, next_level, next_index)
            
            # 递归绘制母亲节点
            if node.get('dam'):
                self.draw_tree(node['dam'], next_level, next_index + 1)
            else:
                # 创建未知母亲节点
                unknown_dam = {
                    'id': 'unknown_cow',
                    'type': 'cow',
                    'gib': None
                }
                self.draw_tree(unknown_dam, next_level, next_index + 1)

    def draw_connection_line(self, x1, y1, x2, y2, is_sire_line=True):
        """绘制连接线（使用三段折线）"""
        # 计算水平和垂直距离
        dx = x2 - x1
        dy = y2 - y1
        
        # 设置控制点
        cp1_x = x1 + dx * 0.2  # 第一个控制点
        cp2_x = x1 + dx * 0.8  # 第二个控制点
        
        # 创建折线的四个点
        points = [
            QPointF(x1, y1),                    # 起点
            QPointF(cp1_x, y1),                 # 第一个控制点
            QPointF(cp2_x, y2),                 # 第二个控制点
            QPointF(x2, y2)                     # 终点
        ]
        
        # 设置线条样式
        pen = QPen(QColor("#666666"))
        pen.setWidth(1)
        if is_sire_line:
            pen.setStyle(Qt.PenStyle.SolidLine)
        else:
            pen.setStyle(Qt.PenStyle.DashLine)  # 母系用虚线
        
        # 绘制折线
        for i in range(len(points) - 1):
            line = QGraphicsLineItem(
                points[i].x(), points[i].y(),
                points[i + 1].x(), points[i + 1].y()
            )
            line.setPen(pen)
            self.scene.addItem(line)

    def create_node_item(self, node, x, y):
        """创建节点图形项"""
        rect = QRectF(x, y - self.node_height/2, self.node_width, self.node_height)
        node_item = QGraphicsRectItem(rect)
        
        # 获取公牛信息
        bull_info = None
        is_common = False
        if node.get('type') == 'bull':
            bull_info = self.calculator.get_bull_info(node['id'])
            if bull_info and bull_info.get('bull_reg'):
                # 使用 REG 号判断是否为共同祖先
                is_common = bull_info['bull_reg'] in self.common_ancestors
        else:
            is_common = node['id'] in self.common_ancestors
            
        is_unknown = 'unknown' in str(node['id']).lower()
        
        # 准备文本信息
        text = ""
        if node.get('type') == 'bull' and bull_info:
            bull_id = str(node['id']).strip()
            
            # 判断是 NAAB 还是 REG
            if len(bull_id) < 11:  # NAAB号
                text = f"NAAB: {bull_id}"
                if bull_info.get('bull_reg'):
                    text += f"\nREG: {bull_info['bull_reg']}"
            else:  # REG号
                text = f"REG: {bull_id}"
                naab_info = self.calculator.get_bull_by_reg(bull_id)
                if naab_info and naab_info.get('NAAB'):
                    text += f"\nNAAB: {naab_info['NAAB']}"
            
            # 添加GIB值
            if bull_info.get('GIB') is not None:
                text += f"\nGIB: {bull_info['GIB']}%"
        else:
            text = node['id']
        
        # 设置节点样式
        if is_unknown:
            color = QColor("#E0E0E0")
            node_item.setPen(QPen(Qt.PenStyle.DashLine))
        elif is_common:
            color = QColor("#FFE4E1")
            node_item.setPen(QPen(QColor("#FF4500"), 2))
            text += "\n⚠️共同祖先"
        else:
            if node.get('type') == 'bull':
                color = QColor(173, 216, 230)  # 浅蓝色表示公牛
            else:
                color = QColor(255, 182, 193)  # 浅粉色表示母牛
            node_item.setPen(QPen(Qt.PenStyle.SolidLine))
        
        node_item.setBrush(QBrush(color))
        
        # 添加文本
        text_item = QGraphicsTextItem(text)
        text_item.setDefaultTextColor(QColor("#000000") if not is_unknown else QColor("#666666"))
        # 设置中文字体
        font = QFont()
        # 根据操作系统设置合适的字体
        system = platform.system()
        if system == "Windows":
            font.setFamily("Microsoft YaHei")  # 微软雅黑
        elif system == "Darwin":  # macOS
            font.setFamily("PingFang SC")  # 苹方字体
        else:  # Linux 或其他
            font.setFamily("WenQuanYi Micro Hei")  # 文泉驿微米黑
        
        font.setPointSize(8)
        if is_unknown:
            font.setItalic(True)
        text_item.setFont(font)
        
        # 居中显示文本
        text_rect = text_item.boundingRect()
        text_x = rect.x() + (rect.width() - text_rect.width()) / 2
        text_y = rect.y() + (rect.height() - text_rect.height()) / 2
        text_item.setPos(text_x, text_y)
        
        text_item.setParentItem(node_item)
        return node_item

    def add_calculation_details(self, F, calculation_method):
        """添加近交系数计算过程的详细显示"""
        # 创建背景矩形
        detail_rect = QGraphicsRectItem(10, 10, 400, 200)
        detail_rect.setBrush(QBrush(QColor(255, 255, 255, 230)))
        detail_rect.setPen(QPen(QColor("#666666")))
        self.scene.addItem(detail_rect)
        
        # 添加操作提示
        self._add_operation_hints()
        
        # 添加标题
        title_text = QGraphicsTextItem("近交系数计算过程")
        title_text.setDefaultTextColor(QColor("#333333"))
        font = QFont()
        # 设置中文字体
        system = platform.system()
        if system == "Windows":
            font.setFamily("Microsoft YaHei")
        elif system == "Darwin":  # macOS
            font.setFamily("PingFang SC")
        else:
            font.setFamily("WenQuanYi Micro Hei")
        font.setPointSize(12)
        font.setBold(True)
        title_text.setFont(font)
        title_text.setPos(20, 20)
        self.scene.addItem(title_text)
        
        # 添加总近交系数
        f_text = QGraphicsTextItem(f"总近交系数: {F*100:.2f}%")
        f_text.setDefaultTextColor(QColor("#FF4500"))
        # 创建新的字体对象
        f_font = QFont()
        if system == "Windows":
            f_font.setFamily("Microsoft YaHei")
        elif system == "Darwin":
            f_font.setFamily("PingFang SC")
        else:
            f_font.setFamily("WenQuanYi Micro Hei")
        f_font.setPointSize(12)
        f_font.setBold(True)
        f_text.setFont(f_font)
        f_text.setPos(20, 45)
        self.scene.addItem(f_text)
        
        # 添加计算详情
        if calculation_method == "GIB":
            self._add_gib_calculation_details(F)
        else:
            self._add_pedigree_calculation_details()

    def _add_gib_calculation_details(self, F: float):
        """添加基于GIB的计算详情"""
        animal = self.calculator.get_cow_info(self.animal_id)
        if animal is None or pd.isna(animal['sire']):
            return
            
        sire_info = self.calculator.prepare_bull_id(animal['sire'])
        gib_text = QGraphicsTextItem()
        text = "使用父系GIB值计算:\n"
        
        if sire_info and sire_info.get('gib') is not None:
            text += f"父系GIB: {sire_info['gib']}%\n"
            text += f"近交系数 = GIB/2 = {sire_info['gib']}/2 = {F:.2%}"
        else:
            text += "父系GIB值未知\n"
            text += "近交系数 = 0"
            
        gib_text.setPlainText(text)
        gib_text.setDefaultTextColor(Qt.GlobalColor.blue)
        # 设置字体
        gib_font = QFont()
        system = platform.system()
        if system == "Windows":
            gib_font.setFamily("Microsoft YaHei")
        elif system == "Darwin":
            gib_font.setFamily("PingFang SC")
        else:
            gib_font.setFamily("WenQuanYi Micro Hei")
        gib_font.setPointSize(9)
        gib_text.setFont(gib_font)
        gib_text.setPos(10, 10)  # 位置可以根据需要调整
        self.scene.addItem(gib_text)

    def _add_pedigree_calculation_details(self):
        """添加基于系谱的计算详情"""
        y_pos = 75
        for ancestor_id in self.common_ancestors:
            paths = self.calculator.ancestor_paths.get(ancestor_id, {})
            if paths:
                path1 = paths['path1']
                path2 = paths['path2']
                ancestor_info = self.calculator.get_bull_info(ancestor_id)
                gib = ancestor_info.get('GIB', 0) if ancestor_info else 0
                
                path1_len = len(path1) - 1
                path2_len = len(path2) - 1
                base_contribution = (0.5) ** (path1_len + path2_len)
                final_contribution = base_contribution * (1 + gib/100 if gib else 1)
                
                detail = QGraphicsTextItem(
                    f"共同祖先 {ancestor_id}:\n"
                    f"  父系路径: {' -> '.join(path1)}\n"
                    f"  母系路径: {' -> '.join(path2)}\n"
                    f"  路径长度: {path1_len + path2_len} 代\n"
                    f"  基础贡献: {base_contribution*100:.4f}%\n"
                    f"  GIB调整: {gib:.1f}%\n"
                    f"  最终贡献: {final_contribution*100:.4f}%\n"
                )
                detail.setDefaultTextColor(QColor("#333333"))
                # 设置字体
                detail_font = QFont()
                system = platform.system()
                if system == "Windows":
                    detail_font.setFamily("Microsoft YaHei")
                elif system == "Darwin":
                    detail_font.setFamily("PingFang SC")
                else:
                    detail_font.setFamily("WenQuanYi Micro Hei")
                detail_font.setPointSize(9)
                detail.setFont(detail_font)
                detail.setPos(20, y_pos)
                self.scene.addItem(detail)
                y_pos += 120 
    
    def _add_operation_hints(self):
        """添加操作提示"""
        # 获取场景边界
        scene_rect = self.scene.sceneRect()
        
        # 创建提示背景
        hint_width = 280
        hint_height = 120
        hint_x = scene_rect.width() - hint_width - 20
        hint_y = 20
        
        hint_rect = QGraphicsRectItem(hint_x, hint_y, hint_width, hint_height)
        hint_rect.setBrush(QBrush(QColor(255, 255, 224, 200)))  # 淡黄色背景
        hint_rect.setPen(QPen(QColor("#666666")))
        self.scene.addItem(hint_rect)
        
        # 添加提示标题
        hint_title = QGraphicsTextItem("操作提示")
        hint_title.setDefaultTextColor(QColor("#333333"))
        # 设置字体
        title_font = QFont()
        system = platform.system()
        if system == "Windows":
            title_font.setFamily("Microsoft YaHei")
        elif system == "Darwin":
            title_font.setFamily("PingFang SC")
        else:
            title_font.setFamily("WenQuanYi Micro Hei")
        title_font.setPointSize(10)
        title_font.setBold(True)
        hint_title.setFont(title_font)
        hint_title.setPos(hint_x + 10, hint_y + 5)
        self.scene.addItem(hint_title)
        
        # 添加提示内容
        hint_text = QGraphicsTextItem(
            "• 鼠标左键拖拽：移动视图\n"
            "• 鼠标滚轮：放大/缩小\n"
            "• 空格键：重置视图\n"
            "• +/- 键：放大/缩小"
        )
        hint_text.setDefaultTextColor(QColor("#555555"))
        # 设置字体
        text_font = QFont()
        if system == "Windows":
            text_font.setFamily("Microsoft YaHei")
        elif system == "Darwin":
            text_font.setFamily("PingFang SC")
        else:
            text_font.setFamily("WenQuanYi Micro Hei")
        text_font.setPointSize(9)
        hint_text.setFont(text_font)
        hint_text.setPos(hint_x + 10, hint_y + 30)
        self.scene.addItem(hint_text)