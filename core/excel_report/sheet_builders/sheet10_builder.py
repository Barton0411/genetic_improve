"""
Sheet 10构建器: 备选公牛排名
v1.3版本 - 按育种指数排名的备选公牛列表，带技术标准对比和标红
"""

from .base_builder import BaseSheetBuilder
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import pandas as pd
import logging
from ..config.bull_quality_standards import (
    US_PROGENY_STANDARDS, US_GENOMIC_STANDARDS,
    DEFECT_GENES, QUALITY_STANDARD_TABLE
)

logger = logging.getLogger(__name__)


class Sheet10Builder(BaseSheetBuilder):
    """
    Sheet 10: 备选公牛排名

    包含内容:
    1. 按育种指数排名表
    2. 包含主要育种性状值
    """

    # 中英文表头映射（使用系统标准翻译）
    HEADER_MAP = {
        'ranking': '排名\nRanking',
        'bull_id': '公牛号\nBull ID',
        'semen_type': '精液类型\nSemen Type',
        '测试_index': '育种指数\nBreeding Index',
        '支数': '支数\nDoses',
        'TPI': 'TPI\n育种综合指数',
        'NM$': 'NM$\n净利润值',
        'MILK': 'MILK\n产奶量',
        'FAT': 'FAT\n乳脂量',
        'FAT %': 'FAT%\n乳脂率',
        'PROT': 'PROT\n乳蛋白量',
        'PROT%': 'PROT%\n乳蛋白率',
        'SCS': 'SCS\n体细胞指数',
        'PL': 'PL\n生产寿命',
        'DPR': 'DPR\n女儿怀孕率',
        'PTAT': 'PTAT\n体型综合指数',
        'UDC': 'UDC\n乳房综合指数',
        'FLC': 'FLC\n肢蹄综合指数',
        'RFI': 'RFI\n剩余饲料采食量',
        'FE': 'FE\n饲料效率指数',
        'FS': 'FS\n饲料节约指数',
        'HH1': 'HH1\n(缺陷基因)',
        'HH2': 'HH2\n(缺陷基因)',
        'HH3': 'HH3\n(缺陷基因)',
        'HH4': 'HH4\n(缺陷基因)',
        'HH5': 'HH5\n(缺陷基因)',
        'HH6': 'HH6\n(缺陷基因)',
        'MW': 'MW\n(缺陷基因)'
    }

    def build(self, data: dict):
        """
        构建Sheet 10: 备选公牛排名

        Args:
            data: 包含备选公牛排名数据
                - bull_rankings: 公牛排名DataFrame（按ranking排序）
                - total_bulls: 公牛总数
                - sexed_bulls: 性控公牛数
                - regular_bulls: 常规公牛数
        """
        try:
            logger.info("构建Sheet 10: 备选公牛排名")

            # 检查数据
            if not data or 'bull_rankings' not in data:
                logger.warning("Sheet10: 缺少排名数据，跳过生成")
                return

            # 创建Sheet
            self._create_sheet("备选公牛排名")

            bull_rankings = data.get('bull_rankings')

            if bull_rankings is None or bull_rankings.empty:
                logger.warning("备选公牛排名数据为空，跳过构建")
                return

            current_row = 1

            # 1. 构建技术标准表
            current_row = self._build_quality_standards_table(current_row)
            current_row += 2  # 空2行

            # 2. 构建排名表
            current_row = self._build_ranking_table(current_row, bull_rankings, data)

            logger.info("✓ Sheet 10构建完成")

        except Exception as e:
            logger.error(f"Sheet 10构建失败: {e}", exc_info=True)
            raise

    def _build_quality_standards_table(self, start_row: int) -> int:
        """
        构建优质冻精技术标准表

        Args:
            start_row: 起始行号

        Returns:
            下一个可用行号
        """
        current_row = start_row

        # 标题
        title = "三、优质冻精技术标准"
        title_cell = self.ws.cell(row=current_row, column=1, value=title)
        title_cell.font = Font(size=14, bold=True)
        title_cell.alignment = Alignment(horizontal='left', vertical='center')
        current_row += 1

        # 表头 - 第一行
        headers = ['育种\n指标\n标识', '种\n标类型', 'TPI\n(GTPI)\n综合生产\n指数',
                   'NM$\n净效益\n指数', 'Milk\n奶量育\n种值\n(磅)', 'Prot蛋\n白量育\n种值\n(磅)',
                   'UDC\n乳房\n综合\n指数', 'FE\n饲料\n转化\n指数', 'PL\n生产\n寿命',
                   'DPR女\n儿怀孕\n率', '缺陷基因']

        header_start_row = current_row
        for col_idx, header in enumerate(headers, 1):
            cell = self.ws.cell(row=current_row, column=col_idx, value=header)
            self.style_manager.apply_header_style(cell)
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

            # 设置列宽
            col_letter = get_column_letter(col_idx)
            if col_idx == 1:  # 育种指标标识
                self.ws.column_dimensions[col_letter].width = 8
            elif col_idx == 2:  # 种标类型
                self.ws.column_dimensions[col_letter].width = 8
            elif col_idx == 11:  # 缺陷基因
                self.ws.column_dimensions[col_letter].width = 15
            else:
                self.ws.column_dimensions[col_letter].width = 10

        current_row += 1

        # 数据行1: 美国 - 后裔
        row_data = ['美国', '后裔', '≥2850', '≥300', '≥200', '≥20', '≥0', '≥100', '≥1.5', '≥-2', 'HH1-HH6\nHMW']
        for col_idx, value in enumerate(row_data, 1):
            cell = self.ws.cell(row=current_row, column=col_idx, value=value)
            self.style_manager.apply_data_style(cell, alignment='center')
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

        # 第一行的"美国"单元格需要合并（跨2行）
        self.ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row+1, end_column=1)
        country_cell = self.ws.cell(row=current_row, column=1)
        country_cell.alignment = Alignment(horizontal='center', vertical='center')

        current_row += 1

        # 数据行2: 基因组
        row_data = ['', '基因组', '≥2900', '≥400', '≥300', '≥30', '≥0', '≥100', '≥1.5', '≥-2', 'HH1-HH6\nHMW']
        for col_idx, value in enumerate(row_data[1:], 2):  # 跳过第一列（已合并）
            cell = self.ws.cell(row=current_row, column=col_idx, value=value)
            self.style_manager.apply_data_style(cell, alignment='center')
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

        current_row += 1

        logger.info("✓ 技术标准表构建完成")
        return current_row

    def _check_below_standard(self, trait_name: str, value, use_genomic: bool = False) -> tuple:
        """
        检查性状值是否低于标准

        Args:
            trait_name: 性状名称
            value: 性状值
            use_genomic: 是否使用基因组标准

        Returns:
            (below_progeny, below_genomic): 低于后裔标准, 低于基因组标准
        """
        # 处理NaN值
        if pd.isna(value):
            return (False, False)

        try:
            value = float(value)
        except (ValueError, TypeError):
            return (False, False)

        below_progeny = False
        below_genomic = False

        # 检查后裔标准
        if trait_name in US_PROGENY_STANDARDS:
            standard_value = US_PROGENY_STANDARDS[trait_name]
            below_progeny = value < standard_value

        # 检查基因组标准
        if trait_name in US_GENOMIC_STANDARDS:
            standard_value = US_GENOMIC_STANDARDS[trait_name]
            below_genomic = value < standard_value

        return (below_progeny, below_genomic)

    def _build_ranking_table(self, start_row: int, df: pd.DataFrame, summary: dict) -> int:
        """
        构建备选公牛排名表

        Args:
            start_row: 起始行号
            df: 排名DataFrame
            summary: 统计摘要

        Returns:
            下一个可用行号
        """
        current_row = start_row

        # 标题
        title_cell = self.ws.cell(row=current_row, column=1, value="备选公牛排名")
        title_cell.font = Font(size=14, bold=True, color="FFFFFF")
        title_cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        title_cell.alignment = Alignment(horizontal='center', vertical='center')
        # 合并标题行
        num_cols = len(df.columns)
        self.ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=num_cols)
        current_row += 1

        # 统计信息行
        stats_text = f"总计: {summary.get('total_bulls', 0)}头公牛 (性控: {summary.get('sexed_bulls', 0)}, 常规: {summary.get('regular_bulls', 0)})"
        stats_cell = self.ws.cell(row=current_row, column=1, value=stats_text)
        stats_cell.font = Font(size=11, italic=True)
        stats_cell.alignment = Alignment(horizontal='left', vertical='center')
        self.ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=num_cols)
        current_row += 1

        # 表头 - 使用中英文映射
        for col_idx, col_name in enumerate(df.columns, 1):
            # 获取中英文表头，如果没有映射则使用原列名
            header_text = self.HEADER_MAP.get(col_name, col_name)
            cell = self.ws.cell(row=current_row, column=col_idx, value=header_text)
            self.style_manager.apply_header_style(cell)
            # 设置自动换行以显示多行表头
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

            # 设置列宽
            col_letter = get_column_letter(col_idx)
            if 'bull_id' in col_name:
                self.ws.column_dimensions[col_letter].width = 16
            elif 'semen_type' in col_name:
                self.ws.column_dimensions[col_letter].width = 14
            elif col_name == 'ranking':
                self.ws.column_dimensions[col_letter].width = 12
            elif col_name == '测试_index':
                self.ws.column_dimensions[col_letter].width = 16
            elif col_name == '支数':
                self.ws.column_dimensions[col_letter].width = 10
            elif col_name in DEFECT_GENES:
                self.ws.column_dimensions[col_letter].width = 10
            else:
                self.ws.column_dimensions[col_letter].width = 14

        current_row += 1
        header_row = current_row - 1

        # 数据行
        for _, row_data in df.iterrows():
            for col_idx, col_name in enumerate(df.columns, 1):
                value = row_data[col_name]

                # 处理NaN
                if pd.isna(value):
                    value = ""

                cell = self.ws.cell(row=current_row, column=col_idx, value=value)

                # 默认应用格式
                self.style_manager.apply_data_style(cell, alignment='center')

                # 特殊格式
                if col_name == 'ranking':
                    # 排名列加粗
                    cell.font = Font(bold=True, size=11)
                elif col_name == '测试_index':
                    # 育种指数保留2位小数
                    cell.number_format = '0.00'
                elif col_name in ['DPR', 'PROT%', 'FAT %']:
                    # 浮点数保留2位小数
                    cell.number_format = '0.00'

                # 标色逻辑
                should_red = False
                should_pink = False

                # 1. 检查性状值是否低于标准
                if col_name in US_PROGENY_STANDARDS:
                    below_progeny, below_genomic = self._check_below_standard(col_name, value)
                    if below_progeny:
                        # 低于后裔标准，标红
                        should_red = True
                    elif below_genomic:
                        # 高于后裔但低于基因组，标粉色
                        should_pink = True

                # 2. 检查基因是否携带（C表示携带）
                if col_name in DEFECT_GENES:
                    if value == 'C':
                        should_red = True

                # 应用颜色填充
                if should_red:
                    cell.fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
                    cell.font = Font(color="FFFFFF", bold=True)  # 白色文字，加粗
                elif should_pink:
                    cell.fill = PatternFill(start_color="FFB6C1", end_color="FFB6C1", fill_type="solid")
                    cell.font = Font(color="000000", bold=True)  # 黑色文字，加粗

            current_row += 1

        # 冻结首行
        self.ws.freeze_panes = self.ws.cell(row=header_row + 1, column=1)

        logger.info(f"✓ Sheet 10排名表构建完成: {len(df)}头公牛")

        return current_row
