"""
Sheet 9构建器: 配种事件明细
v1.2.1版本 - 按年份分组的配种事件明细记录

每次配种一行，包含：耳号、配种日期、冻精编号、冻精类型、各性状
"""

from .base_builder import BaseSheetBuilder
from openpyxl.utils import get_column_letter
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class Sheet9Builder(BaseSheetBuilder):
    """
    Sheet 9: 配种事件明细

    显示所有配种事件的详细记录：
    - 按年份分组显示
    - 每次配种一行（耳号、配种日期、冻精编号、冻精类型、各性状）
    - 包括未识别公牛的配种记录（性状显示"-"）
    """

    def build(self, data: dict):
        """
        构建Sheet 9: 配种事件明细

        Args:
            data: 包含配种明细数据（来自bull_usage_collector）
                - breeding_detail: 配种事件明细DataFrame
                - trait_columns: 性状列名列表
                - all_years: 所有年份列表
        """
        try:
            logger.info("开始构建Sheet 9: 配种事件明细")

            # 创建Sheet
            self._create_sheet("配种事件明细")
            logger.info("✓ Sheet创建成功")

            # 获取数据
            breeding_detail = data.get('breeding_detail')
            trait_columns = data.get('trait_columns', [])
            all_years = data.get('all_years', [])

            if breeding_detail is None or breeding_detail.empty:
                logger.warning("配种明细数据为空，跳过构建")
                cell = self.ws.cell(row=1, column=1, value="暂无配种记录")
                self.style_manager.apply_title_style(cell)
                return

            logger.info(f"✓ 数据准备完成：{len(breeding_detail)} 条配种记录，{len(all_years)} 个年份")

            current_row = 1

            # 按年份分组构建明细表
            if all_years and '配种年份' in breeding_detail.columns:
                for year in all_years:
                    year_data = breeding_detail[breeding_detail['配种年份'] == year]

                    if not year_data.empty:
                        current_row = self._build_year_detail_table(
                            current_row, year, year_data, trait_columns
                        )
                        current_row += 3  # 年份之间空3行
            else:
                # 如果没有年份信息，直接显示所有数据
                current_row = self._build_year_detail_table(
                    current_row, "全部", breeding_detail, trait_columns
                )

            # === 设置列宽 ===
            max_cols = len(trait_columns) + 5  # 耳号+日期+编号+类型+年份+性状
            for col_idx in range(1, max_cols + 1):
                col_letter = get_column_letter(col_idx)
                if col_idx == 1:  # 耳号
                    self.ws.column_dimensions[col_letter].width = 15
                elif col_idx == 2:  # 配种日期
                    self.ws.column_dimensions[col_letter].width = 12
                elif col_idx == 3:  # 冻精编号
                    self.ws.column_dimensions[col_letter].width = 15
                else:
                    self.ws.column_dimensions[col_letter].width = 12

            # === 冻结首行 ===
            self._freeze_panes('A3')

            logger.info(f"✓ Sheet 9构建完成：{len(breeding_detail)} 条配种记录")

        except Exception as e:
            logger.error(f"构建Sheet 9失败: {e}", exc_info=True)
            raise

    def _build_year_detail_table(self, start_row: int, year: str,
                                  year_data: pd.DataFrame, trait_columns: list) -> int:
        """
        构建单个年份的配种明细表

        Args:
            start_row: 起始行号
            year: 年份（或"全部"）
            year_data: 该年份的配种数据
            trait_columns: 性状列名列表

        Returns:
            下一个可用行号
        """
        current_row = start_row

        # 标题
        title_text = f"{year}年配种明细" if str(year).isdigit() else "配种明细"
        cell = self.ws.cell(row=current_row, column=1, value=title_text)
        self.style_manager.apply_title_style(cell)
        current_row += 1

        # 表头
        headers = ['耳号', '配种日期', '冻精编号', '冻精类型'] + trait_columns
        if '配种年份' in year_data.columns:
            headers.insert(4, '配种年份')  # 如果有年份列，插入到冻精类型之后

        self._write_header(current_row, headers, start_col=1)
        current_row += 1

        # 数据行
        for idx, row in year_data.iterrows():
            values = [
                row.get('耳号', ''),
                row.get('配种日期', ''),
                row.get('冻精编号', ''),
                row.get('冻精类型', '')
            ]

            if '配种年份' in year_data.columns:
                values.append(row.get('配种年份', ''))

            # 添加性状值
            for trait in trait_columns:
                val = row.get(trait)
                values.append(val if pd.notna(val) else '-')

            self._write_data_row(current_row, values, start_col=1, alignment='center')
            current_row += 1

        # 汇总行
        total_count = len(year_data)
        total_cols = 4 if '配种年份' not in year_data.columns else 5
        total_row = ['合计', f"{total_count}条记录"] + ['-'] * (total_cols - 2)

        # 计算性状平均值（如果有）
        for trait in trait_columns:
            if trait in year_data.columns and pd.api.types.is_numeric_dtype(year_data[trait]):
                valid_values = year_data[trait].dropna()
                if len(valid_values) > 0:
                    total_row.append(valid_values.mean())
                else:
                    total_row.append('-')
            else:
                total_row.append('-')

        self._write_total_row(current_row, total_row, start_col=1)
        current_row += 1

        logger.info(f"  ✓ {year}年明细表构建完成：{total_count} 条记录")
        return current_row
