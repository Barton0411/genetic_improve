"""选配前确认对话框"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QGroupBox, QTextEdit, QDialogButtonBox,
    QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import pandas as pd
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class MatingConfirmationDialog(QDialog):
    """选配前确认对话框"""

    def __init__(self, project_path, parent=None):
        super().__init__(parent)
        self.project_path = Path(project_path)
        self.proceed_with_skipped = False  # 是否跳过缺失数据的公牛继续
        self.init_ui()
        self.load_and_analyze_data()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("选配前确认")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("选配前数据检查")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # 缺失数据公牛详情组
        self.missing_group = QGroupBox("⚠️ 发现缺少育种数据的公牛")
        missing_layout = QVBoxLayout()

        self.missing_info_label = QLabel("以下公牛有库存但缺少育种数据：")
        missing_layout.addWidget(self.missing_info_label)

        self.missing_text = QTextEdit()
        self.missing_text.setReadOnly(True)
        self.missing_text.setMaximumHeight(250)
        missing_layout.addWidget(self.missing_text)

        self.missing_group.setLayout(missing_layout)
        self.missing_group.setVisible(False)  # 默认隐藏
        layout.addWidget(self.missing_group)

        # 添加弹性空间
        layout.addStretch()

        # 信息标签（默认显示正常状态）
        self.info_label = QLabel("✓ 所有公牛数据完整，可以开始选配")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_font = QFont()
        info_font.setPointSize(12)
        self.info_label.setFont(info_font)
        layout.addWidget(self.info_label)

        layout.addStretch()

        # 按钮
        button_layout = QHBoxLayout()

        self.continue_button = QPushButton("继续选配（跳过缺失数据的公牛）")
        self.continue_button.setEnabled(False)
        self.continue_button.setVisible(False)  # 默认隐藏
        self.continue_button.clicked.connect(self.on_continue_with_skip)

        self.cancel_button = QPushButton("取消（检查公牛信息）")
        self.cancel_button.setVisible(False)  # 默认隐藏
        self.cancel_button.clicked.connect(self.reject)

        self.proceed_button = QPushButton("开始选配")
        self.proceed_button.setDefault(True)
        self.proceed_button.clicked.connect(self.accept)

        button_layout.addWidget(self.continue_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        button_layout.addWidget(self.proceed_button)

        layout.addLayout(button_layout)

    def load_and_analyze_data(self):
        """加载并分析数据"""
        try:
            # 加载公牛数据
            bull_file = self.project_path / "standardized_data" / "processed_bull_data.xlsx"
            if not bull_file.exists():
                # 如果没有公牛数据文件，直接开始选配
                return

            bull_df = pd.read_excel(bull_file)

            # 统计有库存的公牛
            if '支数' in bull_df.columns:
                bulls_with_inventory = bull_df[bull_df['支数'] > 0].copy()
            else:
                bulls_with_inventory = bull_df.copy()  # 如果没有支数列，假设都有库存

            # 检查缺少育种数据的公牛
            if len(bulls_with_inventory) > 0:
                self.check_missing_bull_data(bulls_with_inventory)

        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            QMessageBox.warning(self, "警告", f"加载数据时出错：{str(e)}")

    def check_missing_bull_data(self, bull_df):
        """检查缺少育种数据的有库存公牛"""
        try:
            missing_bulls = []
            bulls_with_data = set()

            # 检查公牛指数文件 processed_index_bull_scores.xlsx
            bull_index_file = self.project_path / "analysis_results" / "processed_index_bull_scores.xlsx"
            if bull_index_file.exists():
                try:
                    index_df = pd.read_excel(bull_index_file)
                    if 'bull_id' in index_df.columns:
                        # 获取有指数数据的公牛（检查包含 权重_index 的列，特别是 NM$权重_index）
                        index_cols = [col for col in index_df.columns if '权重_index' in col]
                        if not index_cols:
                            # 如果没有权重_index列，尝试其他指数列
                            index_cols = [col for col in index_df.columns if '_index' in col.lower() or 'Index' in col]

                        if index_cols:
                            # 只要有任一指数列不为空就认为有数据
                            has_data_mask = index_df[index_cols].notna().any(axis=1)
                            bulls_with_index = index_df[has_data_mask]['bull_id'].astype(str)
                            bulls_with_data.update(bulls_with_index)
                            logger.info(f"从 {bull_index_file.name} 找到 {len(bulls_with_index)} 头有数据的公牛")
                            logger.info(f"使用的指数列: {index_cols}")
                        else:
                            logger.warning(f"{bull_index_file.name} 中未找到指数列")
                except Exception as e:
                    logger.warning(f"读取公牛指数文件失败: {e}")
            else:
                logger.info(f"公牛指数文件不存在: {bull_index_file}")

            # 然后检查数据库（使用 bull_library 表）
            try:
                from core.data.database_manager import DatabaseManager
                db_manager = DatabaseManager()

                if db_manager and db_manager.get_connection():
                    # 查询数据库中的公牛数据
                    # bull_library 表使用 BULL NAAB 作为公牛ID，NM$ 等作为指数
                    query = """
                    SELECT DISTINCT `BULL NAAB` as bull_id
                    FROM bull_library
                    WHERE `NM$` IS NOT NULL OR `TPI` IS NOT NULL
                    """
                    with db_manager.get_connection() as conn:
                        result = pd.read_sql_query(query, conn)
                        bulls_in_db = result['bull_id'].astype(str)
                        bulls_with_data.update(bulls_in_db)
                        logger.info(f"从数据库找到 {len(bulls_in_db)} 头有数据的公牛")
            except Exception as e:
                logger.info(f"数据库检查跳过: {e}")

            # 记录已找到数据的公牛总数
            logger.info(f"总共找到 {len(bulls_with_data)} 头有数据的公牛")

            # 检查每头有库存的公牛
            for _, row in bull_df.iterrows():
                bull_id = str(row['bull_id'])
                inventory = row.get('支数', 0)

                if inventory > 0:  # 只检查有库存的公牛
                    if bull_id not in bulls_with_data:
                        missing_bulls.append({
                            'bull_id': bull_id,
                            'classification': row.get('classification', '未知'),
                            'inventory': inventory
                        })
                        logger.debug(f"公牛 {bull_id} 有库存 {inventory} 但缺少数据")
                    else:
                        logger.debug(f"公牛 {bull_id} 有库存 {inventory} 且有数据")

            # 显示缺失数据的公牛
            if missing_bulls:
                self.show_missing_bulls(missing_bulls)

        except Exception as e:
            logger.error(f"检查公牛数据失败: {e}")
            # 不影响主流程，只记录错误

    def show_missing_bulls(self, missing_bulls):
        """显示缺少数据的公牛信息"""
        self.missing_group.setVisible(True)

        # 构建显示文本
        text_lines = []
        text_lines.append(f"共有 {len(missing_bulls)} 头公牛有库存但缺少育种数据：\n")

        # 按分类分组显示
        regular_missing = [b for b in missing_bulls if b['classification'] == '常规']
        sexed_missing = [b for b in missing_bulls if b['classification'] == '性控']

        if regular_missing:
            text_lines.append("【常规冻精】")
            for bull in regular_missing[:10]:  # 最多显示10个
                text_lines.append(f"  {bull['bull_id']} (库存: {bull['inventory']}支)")
            if len(regular_missing) > 10:
                text_lines.append(f"  ... 还有 {len(regular_missing)-10} 头")

        if sexed_missing:
            text_lines.append("\n【性控冻精】")
            for bull in sexed_missing[:10]:  # 最多显示10个
                text_lines.append(f"  {bull['bull_id']} (库存: {bull['inventory']}支)")
            if len(sexed_missing) > 10:
                text_lines.append(f"  ... 还有 {len(sexed_missing)-10} 头")

        self.missing_text.setPlainText("\n".join(text_lines))

        # 更新信息标签
        self.info_label.setText(f"⚠️ 发现 {len(missing_bulls)} 头公牛有库存但缺少育种数据")
        self.info_label.setStyleSheet("color: orange;")

        # 显示两个选择按钮
        self.continue_button.setVisible(True)
        self.continue_button.setEnabled(True)
        self.cancel_button.setVisible(True)

        # 隐藏默认的"开始选配"按钮
        self.proceed_button.setVisible(False)

    def on_continue_with_skip(self):
        """用户选择跳过缺失数据的公牛继续"""
        self.proceed_with_skipped = True
        self.accept()

    def get_confirmation_result(self):
        """获取用户的确认结果"""
        return {
            'proceed': self.result() == QDialog.DialogCode.Accepted,
            'skip_missing': self.proceed_with_skipped
        }