"""
Sheet 10构建器: 备选公牛排名
v1.2版本 - 按育种指数排名的备选公牛列表
"""

from .base_builder import BaseSheetBuilder
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class Sheet10Builder(BaseSheetBuilder):
    """
    Sheet 10: 备选公牛排名

    包含内容:
    1. 按育种指数排名表
    2. 包含主要育种性状值
    """

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

            # 构建排名表
            current_row = self._build_ranking_table(current_row, bull_rankings, data)

            logger.info("✓ Sheet 10构建完成")

        except Exception as e:
            logger.error(f"Sheet 10构建失败: {e}", exc_info=True)
            raise

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

        # 表头
        for col_idx, col_name in enumerate(df.columns, 1):
            cell = self.ws.cell(row=current_row, column=col_idx, value=col_name)
            self.style_manager.apply_header_style(cell)

            # 设置列宽
            col_letter = get_column_letter(col_idx)
            if 'bull_id' in col_name:
                self.ws.column_dimensions[col_letter].width = 16
            elif 'semen_type' in col_name:
                self.ws.column_dimensions[col_letter].width = 12
            elif col_name == 'ranking':
                self.ws.column_dimensions[col_letter].width = 10
            elif col_name == '测试_index':
                self.ws.column_dimensions[col_letter].width = 14
            elif col_name == '支数':
                self.ws.column_dimensions[col_letter].width = 10
            else:
                self.ws.column_dimensions[col_letter].width = 12

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

                # 应用格式
                if col_name == 'ranking':
                    # 排名列居中加粗
                    self.style_manager.apply_data_style(cell, alignment='center')
                    cell.font = Font(bold=True, size=11)
                elif col_name in ['支数']:
                    self.style_manager.apply_data_style(cell, alignment='center')
                elif col_name == '测试_index':
                    # 育种指数保留2位小数
                    self.style_manager.apply_data_style(cell, alignment='center')
                    cell.number_format = '0.00'
                elif col_name in ['DPR', 'PROT%']:
                    # 浮点数保留2位小数
                    self.style_manager.apply_data_style(cell, alignment='center')
                    cell.number_format = '0.00'
                elif col_name in ['MILK', 'RFI', 'FAT', 'PROT']:
                    # 整数居中
                    self.style_manager.apply_data_style(cell, alignment='center')
                else:
                    self.style_manager.apply_data_style(cell, alignment='center')

            current_row += 1

        # 冻结首行
        self.ws.freeze_panes = self.ws.cell(row=header_row + 1, column=1)

        logger.info(f"✓ Sheet 10排名表构建完成: {len(df)}头公牛")

        return current_row
