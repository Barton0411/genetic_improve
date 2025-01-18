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
        
        if not bull_ids:
            return bull_genes, missing_bulls
            
        try:
            # 为每个ID创建占位符
            placeholders = ', '.join('?' * len(bull_ids))
            query = text(f"""
                SELECT `BULL NAAB`, `BULL REG`, 
                    HH1, HH2, HH3, HH4, HH5, HH6, 
                    BLAD, Chondrodysplasia, Citrullinemia, 
                    DUMPS, `Factor XI`, CVM, Brachyspina, 
                    Mulefoot, `Cholesterol deficiency`, MW
                FROM bull_library 
                WHERE `BULL NAAB` IN ({placeholders}) 
                OR `BULL REG` IN ({placeholders})
            """)
            
            print("要查询的公牛号:", bull_ids)
            # 每个ID都需要出现两次（一次用于NAAB，一次用于REG）
            params = list(bull_ids) * 2
            
            # 执行查询
            with self.db_engine.connect() as conn:
                result = conn.execute(query, params).fetchall()
                print(f"查询到的记录数: {len(result)}")
                
                # 打印前几条记录
                if result:
                    print("前3条记录示例:")
                    for row in result[:3]:
                        print(dict(row))
                
                # 处理查询结果
                found_bulls = set()
                for row in result:
                    row_dict = dict(row)  # 转换为普通字典
                    naab = row_dict['BULL NAAB']
                    reg = row_dict['BULL REG']
                    
                    # 提取基因信息
                    gene_data = {}
                    for gene in self.defect_genes:
                        value = row_dict.get(gene)
                        if pd.isna(value):
                            gene_data[gene] = 'missing data'
                        else:
                            value = str(value).strip().upper()
                            if value == 'C':
                                gene_data[gene] = 'C'
                            elif value == 'F':
                                gene_data[gene] = 'F'
                            else:
                                gene_data[gene] = 'missing data'
                    
                    # 添加到结果字典
                    if naab:
                        bull_genes[str(naab)] = gene_data
                        found_bulls.add(str(naab))
                    if reg:
                        bull_genes[str(reg)] = gene_data
                        found_bulls.add(str(reg))
                
                # 打印查询结果信息
                print(f"找到基因信息的公牛数量: {len(found_bulls)}")
                missing_bulls = list(bull_ids - found_bulls)
                print(f"未找到基因信息的公牛数量: {len(missing_bulls)}")
                if missing_bulls:
                    print("部分未找到的公牛号:", missing_bulls[:5])
                
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

    def analyze_mated_pairs(self, project_path: Path) -> List[Dict]:
        """分析已配公牛对"""
        try:
            # 读取配对数据
            bull_file = project_path / "standardized_data" / "processed_bull_data.xlsx"
            df = pd.read_excel(bull_file)
            
            # 收集需要查询的公牛号
            bull_ids = set()
            bull_ids.update(df['父号'].dropna().astype(str).unique())
            bull_ids.update(df['已配冻精号'].dropna().astype(str).unique())
            bull_ids = {bull for bull in bull_ids if bull and str(bull).strip()}
            
            # 查询基因信息
            bull_genes, missing_bulls = self.query_bull_genes(bull_ids)
            
            # 如果有缺失公牛，记录到云端
            if missing_bulls:
                self.process_missing_bulls(missing_bulls, "已配公牛隐性基因筛查")
                
            # 分析每个配对
            results = []
            for _, row in df.iterrows():
                cow_id = str(row['母牛号'])
                sire_id = str(row['父号']) if pd.notna(row['父号']) else ''
                bull_id = str(row['已配冻精号']) if pd.notna(row['已配冻精号']) else ''
                
                # 获取基因信息
                sire_genes = bull_genes.get(sire_id, {gene: 'missing data' for gene in self.defect_genes})
                bull_genes_data = bull_genes.get(bull_id, {gene: 'missing data' for gene in self.defect_genes})
                
                # 分析安全性
                gene_results = self.analyze_gene_safety(sire_genes, bull_genes_data)
                
                # 记录结果
                results.append({
                    '母牛号': cow_id,
                    '父号': sire_id,
                    '配种公牛号': bull_id,
                    **gene_results
                })
                
            return results
                
        except Exception as e:
            logging.error(f"分析已配公牛对时发生错误: {e}")
            return []

    def analyze_candidate_pairs(self, project_path: Path, bull_genes: Dict[str, str]) -> List[Dict]:
        """分析备选公牛对"""
        results = []
        try:
            # 读取母牛数据和备选公牛数据
            cow_df = pd.read_excel(project_path / "standardized_data" / "processed_cow_data.xlsx")
            bull_df = pd.read_excel(project_path / "standardized_data" / "processed_bull_data.xlsx")
            
            # 只分析在群的母牛
            cow_df = cow_df[cow_df['是否在场'] == '是']
            
            # 分析每对组合
            for _, cow_row in cow_df.iterrows():
                cow_id = cow_row['cow_id']
                sire_id = str(cow_row['sire']) if pd.notna(cow_row['sire']) else ''
                
                # 获取母牛基因信息（通过父号）
                cow_genes = bull_genes.get(sire_id, {gene: 'missing data' for gene in self.defect_genes})
                
                # 分析与每个备选公牛的组合
                for _, bull_row in bull_df.iterrows():
                    bull_id = str(bull_row['bull_id'])
                    candidate_genes = bull_genes.get(bull_id, {gene: 'missing data' for gene in self.defect_genes})
                    
                    # 分析安全性
                    gene_results = self.analyze_gene_safety(cow_genes, candidate_genes)
                    
                    # 记录结果
                    result = {
                        '母牛号': cow_id,
                        '父号': sire_id,
                        '备选公牛号': bull_id,
                        **gene_results
                    }
                    results.append(result)
                    
            return results
            
        except Exception as e:
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

    def start_analysis(self, analysis_type: str):
        """开始基因分析
        
        Args:
            analysis_type: 分析类型 ('mated' 或 'candidate')
        """
        try:
            # 1. 获取项目路径
            project_path = self.get_project_path()
            if not project_path:
                return
                
            # 2. 初始化数据库连接
            if not self.init_db_connection():
                QMessageBox.critical(self, "错误", "无法连接到数据库")
                return
            
            # 3. 创建进度对话框
            progress = QProgressDialog(
                "正在进行隐性基因分析...", 
                "取消", 0, 100, self
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setWindowTitle("处理中")
            progress.setValue(0)
            
            # 4. 收集需要查询的公牛号
            progress.setLabelText("收集公牛信息...")
            required_bulls = self.collect_required_bulls(analysis_type, project_path)
            if not required_bulls:
                QMessageBox.warning(self, "警告", "未找到需要分析的公牛")
                return
            
            # 5. 查询基因信息
            progress.setValue(20)
            progress.setLabelText("查询基因信息...")
            bull_genes, missing_bulls = self.query_bull_genes(required_bulls)
            
            # 6. 处理缺失公牛
            if missing_bulls:
                progress.setValue(30)
                progress.setLabelText("处理缺失公牛记录...")
                self.process_missing_bulls(missing_bulls, analysis_type)
            
            # 7. 分析配对
            progress.setValue(40)
            progress.setLabelText("分析基因配对...")
            if analysis_type == 'mated':
                results = self.analyze_mated_pairs(project_path, bull_genes)
            else:
                results = self.analyze_candidate_pairs(project_path, bull_genes)
            
            if not results:
                QMessageBox.warning(self, "警告", "没有可分析的配对")
                return
            
            # 8. 收集异常信息
            progress.setValue(70)
            progress.setLabelText("整理分析结果...")
            abnormal_df, stats_df = self.collect_abnormal_pairs(results)
            
            # 9. 更新显示
            progress.setValue(80)
            progress.setLabelText("更新显示...")
            self.detail_model.update_data(pd.DataFrame(results))
            self.abnormal_model.update_data(abnormal_df)
            self.stats_model.update_data(stats_df)
            
            # 10. 保存结果
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