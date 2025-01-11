from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QTableView, QFrame, QSplitter, QMessageBox, QApplication,
    QProgressDialog, QMainWindow
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush
import pandas as pd
import logging
from pathlib import Path
from sqlalchemy import create_engine, text
import datetime
from typing import List, Dict, Tuple, Set, Optional

from .models import InbreedingDetailModel, AbnormalDetailModel, StatisticsModel
from core.data.update_manager import (
    CLOUD_DB_HOST, CLOUD_DB_PORT, CLOUD_DB_USER, 
    CLOUD_DB_PASSWORD, CLOUD_DB_NAME, LOCAL_DB_PATH
)

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
            
            # 检查数据库文件是否存在
            db_path = Path(LOCAL_DB_PATH)
            print(f"数据库文件路径: {db_path}")
            print(f"数据库文件是否存在: {db_path.exists()}")
            print(f"数据库文件大小: {db_path.stat().st_size if db_path.exists() else 0} bytes")
            
            # 检查父目录是否存在
            print(f"父目录是否存在: {db_path.parent.exists()}")
            print(f"父目录权限: {oct(db_path.parent.stat().st_mode)[-3:] if db_path.parent.exists() else 'N/A'}")
            
            # 尝试创建数据库连接
            connection_string = f'sqlite:///{LOCAL_DB_PATH}'
            print(f"数据库连接字符串: {connection_string}")
            
            self.db_engine = create_engine(connection_string)
            
            # 测试连接并检查表结构
            with self.db_engine.connect() as conn:
                # 检查表是否存在
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
                print("数据库中的表:", [r[0] for r in result])
                
                # 检查bull_library表的结构
                if 'bull_library' in [r[0] for r in result]:
                    result = conn.execute(text("PRAGMA table_info(bull_library)")).fetchall()
                    print("bull_library表结构:", result)
                    
                    # 检查数据量
                    count = conn.execute(text("SELECT COUNT(*) FROM bull_library")).scalar()
                    print(f"bull_library表中的记录数: {count}")
                    
                    # 检查一条示例数据
                    try:
                        sample = conn.execute(text("""
                            SELECT `BULL NAAB`, `BULL REG`, 
                                HH1, HH2, HH3, HH4, HH5, HH6, 
                                BLAD, Chondrodysplasia, Citrullinemia, 
                                DUMPS, `Factor XI`, CVM, Brachyspina, 
                                Mulefoot, `Cholesterol deficiency`, MW
                            FROM bull_library LIMIT 1
                        """)).fetchone()
                        if sample:
                            # 使用zip和列名创建字典
                            columns = ['BULL NAAB', 'BULL REG', 
                                     'HH1', 'HH2', 'HH3', 'HH4', 'HH5', 'HH6',
                                     'BLAD', 'Chondrodysplasia', 'Citrullinemia',
                                     'DUMPS', 'Factor XI', 'CVM', 'Brachyspina',
                                     'Mulefoot', 'Cholesterol deficiency', 'MW']
                            sample_dict = dict(zip(columns, sample))
                            print("示例数据:", sample_dict)
                    except Exception as e:
                        print(f"获取示例数据时出错: {e}")
            
            return True
        except Exception as e:
            logging.error(f"数据库连接失败: {e}")
            print(f"数据库连接失败，错误信息: {str(e)}")
            return False

    def collect_required_bulls(self, analysis_type: str, project_path: Path) -> Set[str]:
        """收集需要查询的公牛号"""
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
            required_bulls = {bull for bull in required_bulls if bull and str(bull).strip()}
            return required_bulls
            
        except Exception as e:
            logging.error(f"收集公牛号时发生错误: {e}")
            return set()

    def query_bull_genes(self, bull_ids: Set[str]) -> Tuple[Dict, List[str]]:
        """查询公牛基因信息"""
        bull_genes = {}
        missing_bulls = []
        
        if not bull_ids:
            return bull_genes, missing_bulls
            
        try:
            # 修改SQL语句，使用OR连接多个条件而不是IN子句
            conditions = []
            params = {}
            for i, bull_id in enumerate(bull_ids):
                naab_key = f'naab_{i}'
                reg_key = f'reg_{i}'
                conditions.append(f"`BULL NAAB` = :{naab_key} OR `BULL REG` = :{reg_key}")
                params[naab_key] = bull_id
                params[reg_key] = bull_id
                
            query = text(f"""
                SELECT `BULL NAAB`, `BULL REG`, 
                    HH1, HH2, HH3, HH4, HH5, HH6, 
                    BLAD, Chondrodysplasia, Citrullinemia, 
                    DUMPS, `Factor XI`, CVM, Brachyspina, 
                    Mulefoot, `Cholesterol deficiency`, MW
                FROM bull_library 
                WHERE {' OR '.join(conditions)}
            """)
            
            print("要查询的公牛号:", bull_ids)
            
            # 定义列名
            columns = ['BULL NAAB', 'BULL REG', 
                      'HH1', 'HH2', 'HH3', 'HH4', 'HH5', 'HH6',
                      'BLAD', 'Chondrodysplasia', 'Citrullinemia',
                      'DUMPS', 'Factor XI', 'CVM', 'Brachyspina',
                      'Mulefoot', 'Cholesterol deficiency', 'MW']
            
            # 执行查询
            with self.db_engine.connect() as conn:
                result = conn.execute(query, params)
                rows = result.fetchall()
                print(f"查询到的记录数: {len(rows)}")
                
                # 处理查询结果
                found_bulls = set()
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    naab = row_dict.get('BULL NAAB')
                    reg = row_dict.get('BULL REG')
                    
                    # 提取基因信息
                    gene_data = {}
                    for gene in self.defect_genes:
                        value = row_dict.get(gene)
                        # 只有明确标记为C的才是携带者，其他都是非携带
                        value = str(value).strip().upper() if value else ''
                        gene_data[gene] = 'C' if value == 'C' else 'F'
                    
                    # 添加到结果字典
                    if naab:
                        bull_genes[str(naab)] = gene_data
                        found_bulls.add(str(naab))
                    if reg:
                        bull_genes[str(reg)] = gene_data
                        found_bulls.add(str(reg))
                
                # 记录未找到的公牛
                missing_bulls = list(bull_ids - found_bulls)
                
                return bull_genes, missing_bulls
                
        except Exception as e:
            logging.error(f"查询公牛基因信息失败: {e}")
            print(f"查询失败，错误信息: {e}")
            print(f"SQL语句: {query}")
            print(f"参数: {params}")
            return {}, list(bull_ids)
 
    def process_missing_bulls(self, missing_bulls: List[str], analysis_type: str) -> None:
        """处理缺失公牛记录"""
        if not missing_bulls:
            return
            
        try:
            # 准备数据
            main_window = self.get_main_window()
            username = main_window.username if main_window else 'unknown'
            missing_df = pd.DataFrame({
                'bull': missing_bulls,
                'source': f'隐性基因筛查_{analysis_type}',
                'time': datetime.datetime.now(),
                'user': username
            })
            
            # 连接云端数据库并上传
            cloud_engine = create_engine(
                f"mysql+pymysql://{CLOUD_DB_USER}:{CLOUD_DB_PASSWORD}"
                f"@{CLOUD_DB_HOST}:{CLOUD_DB_PORT}/{CLOUD_DB_NAME}?charset=utf8mb4"
            )
            missing_df.to_sql('miss_bull', cloud_engine, if_exists='append', index=False)
            
        except Exception as e:
            logging.error(f"处理缺失公牛记录失败: {e}")

    def analyze_gene_safety(self, sire_id: str, bull_id: str, bull_genes: Dict[str, Dict[str, str]]) -> Dict[str, str]:
        """分析基因配对安全性
        
        Args:
            sire_id: 母牛的父号
            bull_id: 配种公牛号或备选公牛号
            bull_genes: 所有公牛的基因信息字典
            
        Returns:
            基因安全性分析结果
        """
        result = {}
        
        # 检查是否能找到相应的公牛
        sire_found = bool(sire_id and sire_id in bull_genes)
        bull_found = bool(bull_id and bull_id in bull_genes)
        
        for gene in self.defect_genes:
            if not sire_id:  # 如果父号为空
                result[gene] = 'missing cow data'
            elif not bull_id:  # 如果公牛号为空
                result[gene] = 'missing bull data'
            elif not sire_found:  # 如果父号在数据库中找不到
                result[gene] = 'missing cow data'
            elif not bull_found:  # 如果公牛号在数据库中找不到
                result[gene] = 'missing bull data'
            else:
                # 获取基因信息
                sire_gene = bull_genes[sire_id][gene]
                bull_gene = bull_genes[bull_id][gene]
                
                # 只有双方都是携带者时才是不安全的
                if sire_gene == 'C' and bull_gene == 'C':
                    result[gene] = 'NO safe'
                else:
                    result[gene] = 'safe'
                
        return result

    def analyze_mated_pairs(self, project_path: Path) -> List[Dict]:
        """分析已配公牛对"""
        try:
            # 读取配对数据
            breeding_file = project_path / "standardized_data" / "processed_breeding_data.xlsx"
            df = pd.read_excel(breeding_file)
            print("配种记录列名:", df.columns.tolist())
            
            # 读取母牛数据以获取父号
            cow_file = project_path / "standardized_data" / "processed_cow_data.xlsx"
            cow_df = pd.read_excel(cow_file)
            print("母牛数据列名:", cow_df.columns.tolist())
            
            # 定义列名映射
            cow_columns_map = {
                'cow_id': '耳号',
                'sire': '父号'
            }
            breeding_columns_map = {
                '耳号': '耳号',
                '父号': '父号',
                '冻精编号': '配种公牛'
            }
            
            # 统一列名
            cow_df = cow_df.rename(columns=cow_columns_map)
            df = df.rename(columns=breeding_columns_map)
            
            # 创建耳号到父号的映射
            cow_to_sire = dict(zip(cow_df['耳号'], cow_df['父号']))
            
            # 收集需要查询的公牛号
            bull_ids = set()
            # 添加所有母牛的父号
            bull_ids.update(cow_df['父号'].dropna().astype(str).unique())
            # 添加所有配种公牛号
            bull_ids.update(df['配种公牛'].dropna().astype(str).unique())
            # 移除空字符串
            bull_ids = {bull for bull in bull_ids if bull and str(bull).strip()}
            
            # 查询基因信息
            bull_genes, missing_bulls = self.query_bull_genes(bull_ids)
            
            # 如果有缺失公牛，记录到云端
            if missing_bulls:
                self.process_missing_bulls(missing_bulls, "已配公牛隐性基因筛查")
                
            # 分析每个配对
            results = []
            for _, row in df.iterrows():
                ear_id = str(row['耳号'])
                bull_id = str(row['配种公牛']) if pd.notna(row['配种公牛']) else ''
                
                # 获取母牛的父号
                sire_id = str(cow_to_sire.get(ear_id, '')) if pd.notna(cow_to_sire.get(ear_id)) else ''
                
                # 分析安全性
                gene_results = self.analyze_gene_safety(sire_id, bull_id, bull_genes)
                
                # 记录结果
                results.append({
                    '耳号': ear_id,
                    '父号': sire_id,
                    '配种公牛': bull_id,
                    **gene_results
                })
                
            return results
                
        except Exception as e:
            logging.error(f"分析已配公牛对时发生错误: {e}")
            print(f"错误详情: {e}")
            return []

    def analyze_candidate_pairs(self, project_path: Path, bull_genes: Dict[str, Dict[str, str]]) -> List[Dict]:
        """分析备选公牛对"""
        results = []
        try:
            # 读取母牛数据和备选公牛数据
            cow_df = pd.read_excel(project_path / "standardized_data" / "processed_cow_data.xlsx")
            bull_df = pd.read_excel(project_path / "standardized_data" / "processed_bull_data.xlsx")
            
            print("母牛数据列名:", cow_df.columns.tolist())
            print("备选公牛数据列名:", bull_df.columns.tolist())
            
            # 定义列名映射
            cow_columns_map = {
                'cow_id': '耳号',
                'sire': '父号'
            }
            bull_columns_map = {
                'bull_id': '配种公牛'
            }
            
            # 统一列名
            cow_df = cow_df.rename(columns=cow_columns_map)
            bull_df = bull_df.rename(columns=bull_columns_map)
            
            # 只分析在群的母牛
            cow_df = cow_df[cow_df['是否在场'] == '是']
            
            # 分析每对组合
            for _, cow_row in cow_df.iterrows():
                ear_id = cow_row['耳号']
                sire_id = str(cow_row['父号']) if pd.notna(cow_row['父号']) else ''
                
                # 分析与每个备选公牛的组合
                for _, bull_row in bull_df.iterrows():
                    bull_id = str(bull_row['配种公牛'])
                    
                    # 分析安全性
                    gene_results = self.analyze_gene_safety(sire_id, bull_id, bull_genes)
                    
                    # 记录结果
                    result = {
                        '耳号': ear_id,
                        '父号': sire_id,
                        '配种公牛': bull_id,
                        **gene_results
                    }
                    results.append(result)
                    
            return results
            
        except Exception as e:
            logging.error(f"分析备选公牛对时发生错误: {e}")
            print(f"错误详情: {e}")
            return []

    def collect_abnormal_pairs(self, results: List[Dict]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """收集异常配对和统计信息"""
        abnormal_records = []
        gene_stats = {gene: 0 for gene in self.defect_genes}
        
        for result in results:
            for gene in self.defect_genes:
                if result[gene] == 'NO safe':
                    abnormal_records.append({
                        '耳号': result['耳号'],
                        '父号': result['父号'],
                        '配种公牛': result['配种公牛'],
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

    def start_analysis(self, analysis_type: str):
        """开始基因分析"""
        try:
            # 获取项目路径
            project_path = self.get_project_path()
            if not project_path:
                return
                
            # 初始化数据库连接
            if not self.init_db_connection():
                QMessageBox.critical(self, "错误", "无法连接到数据库")
                return
            
            # 创建进度对话框
            progress = QProgressDialog(
                "正在进行隐性基因分析...", 
                "取消", 0, 100, self
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setWindowTitle("处理中")
            progress.setValue(0)
            
            # 收集需要查询的公牛号
            progress.setLabelText("收集公牛信息...")
            required_bulls = self.collect_required_bulls(analysis_type, project_path)
            if not required_bulls:
                QMessageBox.warning(self, "警告", "未找到需要分析的公牛")
                return
            
            # 查询基因信息
            progress.setValue(20)
            progress.setLabelText("查询基因信息...")
            bull_genes, missing_bulls = self.query_bull_genes(required_bulls)
            
            # 处理缺失公牛
            if missing_bulls:
                progress.setValue(30)
                progress.setLabelText("处理缺失公牛记录...")
                self.process_missing_bulls(missing_bulls, analysis_type)
            
            # 分析配对
            progress.setValue(40)
            progress.setLabelText("分析基因配对...")
            if analysis_type == 'mated':
                results = self.analyze_mated_pairs(project_path)  # 只传入 project_path
            else:
                results = self.analyze_candidate_pairs(project_path, bull_genes)
            
            if not results:
                QMessageBox.warning(self, "警告", "没有可分析的配对")
                return
            
            # 收集异常信息
            progress.setValue(70)
            progress.setLabelText("整理分析结果...")
            abnormal_df, stats_df = self.collect_abnormal_pairs(results)
            
            # 更新显示
            progress.setValue(80)
            progress.setLabelText("更新显示...")
            self.detail_model.update_data(pd.DataFrame(results))
            self.abnormal_model.update_data(abnormal_df)
            self.stats_model.update_data(stats_df)
            
            # 保存结果
            progress.setValue(90)
            progress.setLabelText("保存结果...")
            output_dir = project_path / "analysis_results"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            type_str = "已配公牛" if analysis_type == 'mated' else "备选公牛"
            pd.DataFrame(results).to_excel(output_dir / f"隐性基因筛查结果_{type_str}.xlsx", index=False)
            abnormal_df.to_excel(output_dir / f"隐性基因筛查异常明细_{type_str}.xlsx", index=False)
            stats_df.to_excel(output_dir / f"隐性基因筛查统计_{type_str}.xlsx", index=False)
            
            progress.setValue(100)
            QMessageBox.information(self, "完成", f"{type_str}隐性基因分析完成！")
            
        except Exception as e:
            logging.error(f"执行隐性基因分析时发生错误: {e}")
            QMessageBox.critical(self, "错误", f"执行过程中发生错误：{str(e)}")
        finally:
            if hasattr(self, 'progress'):
                self.progress.close()
            if self.db_engine:
                self.db_engine.dispose() 