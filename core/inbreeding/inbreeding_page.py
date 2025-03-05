from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QTableView, QFrame, QSplitter, QMessageBox, QApplication,
    QProgressDialog, QMainWindow, QDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush
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

from .models import InbreedingDetailModel, AbnormalDetailModel, StatisticsModel
from core.data.update_manager import (
    CLOUD_DB_HOST, CLOUD_DB_PORT, CLOUD_DB_USER, 
    CLOUD_DB_PASSWORD, CLOUD_DB_NAME, LOCAL_DB_PATH
)

class PedigreeDialog(QDialog):
    """血缘关系图对话框"""
    def __init__(self, cow_id, sire_id, bull_id, parent=None):
        super().__init__(parent)
        self.cow_id = cow_id
        self.sire_id = sire_id
        self.bull_id = bull_id
        self.parent_widget = parent
        self.setup_ui()
        
    def setup_ui(self):
        """初始化UI"""
        self.setWindowTitle(f"血缘关系图 - 母牛: {self.cow_id}")
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # 添加标题标签
        title_label = QLabel(f"母牛: {self.cow_id} - 父号: {self.sire_id} - 配种公牛: {self.bull_id}")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # 添加近交系数显示
        self.inbreeding_label = QLabel("近交系数: 计算中...")
        self.inbreeding_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.inbreeding_label)
        
        # 创建图形画布
        self.figure = Figure(figsize=(8, 6))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        # 添加关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        
        # 绘制血缘关系图
        self.draw_pedigree()
        
    def get_project_path(self):
        """获取项目路径"""
        if hasattr(self.parent_widget, 'get_project_path'):
            return self.parent_widget.get_project_path()
        return None
        
    def draw_pedigree(self):
        """绘制血缘关系图"""
        # 这里是临时的示例图，后续会替换为真实的血缘关系图
        ax = self.figure.add_subplot(111)
        
        try:
            # 尝试使用InbreedingCalculator生成真实的血缘关系图
            project_path = self.get_project_path()
            if project_path:
                # 这里将来会使用真实的InbreedingCalculator
                # 现在先使用示例图
                pass
                
            # 创建有向图
            G = nx.DiGraph()
            
            # 添加节点
            G.add_node(self.cow_id, pos=(0, 0), node_type="cow")
            G.add_node(self.sire_id, pos=(-1, 1), node_type="bull")
            G.add_node("母亲", pos=(1, 1), node_type="cow")
            G.add_node(self.bull_id, pos=(0, 2), node_type="bull")
            G.add_node("后代", pos=(0, -1), node_type="cow")
            
            # 添加边
            G.add_edge(self.sire_id, self.cow_id)
            G.add_edge("母亲", self.cow_id)
            G.add_edge(self.bull_id, "后代")
            G.add_edge(self.cow_id, "后代")
            
            # 获取节点位置
            pos = nx.get_node_attributes(G, 'pos')
            
            # 绘制节点
            nx.draw_networkx_nodes(G, pos, 
                                nodelist=[n for n, d in G.nodes(data=True) if d.get('node_type') == 'bull'],
                                node_color='skyblue', 
                                node_size=2000, 
                                ax=ax)
            nx.draw_networkx_nodes(G, pos, 
                                nodelist=[n for n, d in G.nodes(data=True) if d.get('node_type') == 'cow'],
                                node_color='pink', 
                                node_size=2000, 
                                ax=ax)
            
            # 绘制边和标签
            nx.draw_networkx_edges(G, pos, arrows=True, ax=ax)
            nx.draw_networkx_labels(G, pos, ax=ax)
            
            ax.set_title("血缘关系图")
            ax.axis('off')
            
            # 更新近交系数标签
            inbreeding_coef = 0.0625  # 示例值，后续会替换为真实计算
            self.inbreeding_label.setText(f"近交系数: {inbreeding_coef:.2%}")
            
        except Exception as e:
            logging.error(f"绘制血缘关系图时出错: {str(e)}")
            ax.text(0.5, 0.5, f"绘制血缘关系图时出错: {str(e)}", 
                   horizontalalignment='center', verticalalignment='center')
            
        self.canvas.draw()

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
        left_layout.addWidget(QLabel("母牛-公牛配对明细表"))
        self.detail_table = QTableView()
        self.detail_model = InbreedingDetailModel()
        self.detail_table.setModel(self.detail_model)
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
        """收集需要查询的公牛号
        
        Args:
            analysis_type: 分析类型 ('mated' 或 'candidate')
            project_path: 项目路径
            
        Returns:
            需要查询的公牛号集合
        """
        required_bulls = set()
        try:
            # 获取母牛父号
            cow_file = project_path / "standardized_data" / "processed_cow_data.xlsx"
            cow_df = pd.read_excel(cow_file)
            if analysis_type == 'candidate':
                # 备选公牛分析只考虑在群的母牛
                cow_df = cow_df[cow_df['是否在场'] == '是']
            required_bulls.update(cow_df['sire'].dropna().astype(str).unique())
            
            # 获取公牛号
            if analysis_type == 'mated':
                # 从配种记录获取已配公牛
                breeding_file = project_path / "standardized_data" / "processed_breeding_data.xlsx"
                breeding_df = pd.read_excel(breeding_file)
                required_bulls.update(breeding_df['冻精编号'].dropna().astype(str).unique())
            else:
                # 从备选公牛文件获取公牛号
                bull_file = project_path / "standardized_data" / "processed_bull_data.xlsx"
                bull_df = pd.read_excel(bull_file)
                required_bulls.update(bull_df['bull_id'].dropna().astype(str).unique())
                
            # 移除空字符串
            required_bulls = {bull for bull in required_bulls if bull and bull.strip()}
            return required_bulls
            
        except Exception as e:
            logging.error(f"收集公牛号时发生错误: {e}")
            return set()

    def query_bull_genes(self, bull_ids: Set[str]) -> Tuple[Dict, List[str]]:
        """查询公牛基因信息"""
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
        sire_id = self.detail_model.df.iloc[row].get('父号', '')
        
        # 获取公牛号（可能是配种公牛号或备选公牛号）
        bull_id = self.detail_model.df.iloc[row].get('配种公牛号', 
                  self.detail_model.df.iloc[row].get('备选公牛号', ''))
        
        # 显示血缘关系图对话框
        dialog = PedigreeDialog(cow_id, sire_id, bull_id, self)
        dialog.exec()

    def analyze_mated_pairs(self, project_path: Path, bull_genes: Dict[str, str]) -> List[Dict]:
        """分析已配公牛对"""
        try:
            # 读取配对数据
            breeding_file = project_path / "standardized_data" / "processed_breeding_data.xlsx"
            print(f"开始分析已配公牛对，从{breeding_file}读取数据")
            df = pd.read_excel(breeding_file)
            print(f"读取到{len(df)}条配对记录")
            
            # 分析每个配对
            results = []
            print("开始分析每个配对...")
            for i, row in enumerate(df.iterrows()):
                if i < 5 or i % 100 == 0:  # 只打印前5行和每100行，避免日志过长
                    print(f"分析第{i+1}条配对记录")
                _, row = row  # 解包iterrows返回的元组
                cow_id = str(row['耳号'])
                sire_id = str(row['父号']) if pd.notna(row['父号']) else ''
                bull_id = str(row['冻精编号']) if pd.notna(row['冻精编号']) else ''
                
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
                    '配种公牛号': bull_id,
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
                sire_id = str(cow_row['sire']) if pd.notna(cow_row['sire']) else ''
                
                # 获取母牛基因信息（通过父号）
                cow_genes = bull_genes.get(sire_id, {gene: 'missing data' for gene in self.defect_genes})
                
                # 分析与每个备选公牛的组合
                for _, bull_row in bull_df.iterrows():
                    pair_count += 1
                    if pair_count <= 5 or pair_count % 1000 == 0:  # 只打印前5对和每1000对，避免日志过长
                        print(f"  分析第{pair_count}对组合: 母牛{cow_id} - 公牛{bull_row['bull_id']}")
                    
                    bull_id = str(bull_row['bull_id'])
                    candidate_genes = bull_genes.get(bull_id, {gene: 'missing data' for gene in self.defect_genes})
                    
                    # 分析安全性
                    gene_results = self.analyze_gene_safety(cow_genes, candidate_genes)
                    
                    # 计算近交系数（临时使用随机值，后续会替换为真实计算）
                    inbreeding_coef = 0.0  # 默认值，后续会替换为真实计算
                    
                    # 记录结果
                    result_dict = {
                        '母牛号': cow_id,
                        '父号': sire_id,
                        '备选公牛号': bull_id,
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
            # 使用InbreedingCalculator计算近交系数
            from core.inbreeding.inbreeding_calculator import InbreedingCalculator
            
            # 初始化计算器
            db_path = Path("local_bull_library.db")
            cow_data_path = project_path / "standardized_data" / "processed_cow_data.xlsx"
            calculator = InbreedingCalculator(db_path, cow_data_path)
            
            for result in results:
                cow_id = result['母牛号']
                # 计算近交系数
                inbreeding_coef, status, method = calculator.calculate_inbreeding_coefficient(cow_id)
                result['近交系数'] = f"{inbreeding_coef:.2%}"
                # 可选：添加计算状态和方法信息
                result['计算状态'] = status
                result['计算方法'] = method
                
            return results
            
        except Exception as e:
            logging.error(f"计算近交系数时出错: {str(e)}")
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
            # 收集所需的公牛号
            print("开始收集所需的公牛号...")
            required_bulls = self.collect_required_bulls(analysis_type, project_path)
            print(f"收集到{len(required_bulls)}个公牛号")
            progress.setValue(10)
            QApplication.processEvents()
            
            if progress.wasCanceled():
                print("用户取消了分析")
                return
                
            # 查询公牛基因信息
            print("开始查询公牛基因信息...")
            bull_genes, missing_bulls = self.query_bull_genes(required_bulls)
            print(f"查询到{len(bull_genes)}个公牛的基因信息，有{len(missing_bulls)}个公牛未找到")
            progress.setValue(30)
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
            progress.setValue(90)
            QApplication.processEvents()
            
            if progress.wasCanceled():
                print("用户取消了分析")
                return
                
            # 收集异常配对
            print("收集异常配对...")
            abnormal_df, stats_df = self.collect_abnormal_pairs(results)
            
            # 更新表格数据
            print("更新表格数据...")
            self.detail_model.update_data(pd.DataFrame(results))
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