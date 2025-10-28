"""
Sheet 8构建器: 已用公牛性状汇总分析
v1.2.1版本 - 多维度公牛使用汇总分析

包含3个汇总表：
1. 表1：按年份+冻精类型汇总（宏观趋势）
2. 表2：总体汇总（按公牛，所有年份）
3. 表3：按年份+公牛汇总（详细分析）
"""

from .base_builder import BaseSheetBuilder
from openpyxl.utils import get_column_letter
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class Sheet8Builder(BaseSheetBuilder):
    """
    Sheet 8: 已用公牛性状汇总分析

    包含3个汇总表：
    1. 按年份和冻精类型汇总 - 宏观趋势分析
    2. 总体汇总（按公牛）- 所有年份数据
    3. 按年份和公牛汇总 - 详细分析
    """

    def build(self, data: dict):
        """
        构建Sheet 8: 已用公牛性状汇总分析

        Args:
            data: 包含已用公牛汇总数据（来自bull_usage_collector）
                - year_type_summary: 表1 - 按年份+类型汇总
                - overall_summary: 表2 - 总体汇总（按公牛）
                - year_bull_summary: 表3 - 按年份+公牛汇总
                - trait_columns: 性状列名列表
                - all_years: 所有年份列表
        """
        try:
            logger.info("开始构建Sheet 8: 已用公牛性状汇总分析")

            # 创建Sheet
            self._create_sheet("已用公牛性状汇总")
            logger.info("✓ Sheet创建成功")

            # 获取数据
            year_type_summary = data.get('year_type_summary')
            overall_summary = data.get('overall_summary')
            year_bull_summary = data.get('year_bull_summary')
            trait_columns = data.get('trait_columns', [])
            all_years = data.get('all_years', [])

            if not trait_columns:
                logger.warning("性状列为空，只显示使用次数")

            logger.info(f"✓ 数据准备完成：{len(trait_columns)} 个性状，{len(all_years)} 个年份")

            current_row = 1

            # ========== 表1：按年份+冻精类型汇总 ==========
            current_row = self._build_table1_year_type_summary(
                current_row, year_type_summary, trait_columns
            )
            current_row += 3  # 空3行

            # ========== 表2：总体汇总（按公牛） ==========
            current_row = self._build_table2_overall_summary(
                current_row, overall_summary, trait_columns
            )
            current_row += 3  # 空3行

            # ========== 表3：按年份+公牛汇总 ==========
            current_row = self._build_table3_year_bull_summary(
                current_row, year_bull_summary, trait_columns
            )

            # === 设置列宽 ===
            max_cols = len(trait_columns) + 4  # 年份+编号+类型+使用次数+性状
            for col_idx in range(1, max_cols + 1):
                col_letter = get_column_letter(col_idx)
                self.ws.column_dimensions[col_letter].width = 12

            # === 冻结首行 ===
            self._freeze_panes('A3')  # 冻结前两行（标题+表头）

            logger.info(f"✓ Sheet 8构建完成：3个汇总表，{len(trait_columns)} 个性状")

        except Exception as e:
            logger.error(f"构建Sheet 8失败: {e}", exc_info=True)
            raise

    def _build_table1_year_type_summary(self, start_row: int, summary_df: pd.DataFrame,
                                       trait_columns: list) -> int:
        """
        构建表1：按年份+冻精类型汇总（宏观趋势）

        Returns:
            下一个可用行号
        """
        current_row = start_row

        # 标题
        cell = self.ws.cell(row=current_row, column=1, value="表1：按年份和冻精类型汇总")
        self.style_manager.apply_title_style(cell)
        current_row += 1

        if summary_df is None or summary_df.empty:
            cell = self.ws.cell(row=current_row, column=1, value="暂无数据")
            return current_row + 1

        # 表头
        headers = ['使用年份', '冻精类型', '使用次数'] + trait_columns
        self._write_header(current_row, headers, start_col=1)
        current_row += 1

        # 数据行
        for idx, row in summary_df.iterrows():
            values = [
                row.get('使用年份', ''),
                row.get('冻精类型', ''),
                row.get('使用次数', 0)
            ]
            for trait in trait_columns:
                val = row.get(trait)
                values.append(val if pd.notna(val) else '-')

            self._write_data_row(current_row, values, start_col=1, alignment='center')
            current_row += 1

        # 汇总行
        total_count = summary_df['使用次数'].sum()
        total_row = ['合计', '-', total_count]

        for trait in trait_columns:
            if pd.api.types.is_numeric_dtype(summary_df[trait]):
                valid_data = summary_df[[trait, '使用次数']].dropna(subset=[trait])
                if len(valid_data) > 0:
                    weighted_avg = (valid_data[trait] * valid_data['使用次数']).sum() / valid_data['使用次数'].sum()
                    total_row.append(weighted_avg)
                else:
                    total_row.append('-')
            else:
                total_row.append('-')

        self._write_total_row(current_row, total_row, start_col=1)
        current_row += 1

        logger.info(f"  ✓ 表1构建完成：{len(summary_df)} 行数据")
        return current_row

    def _build_table2_overall_summary(self, start_row: int, summary_df: pd.DataFrame,
                                     trait_columns: list) -> int:
        """
        构建表2：总体汇总（按公牛，所有年份）

        Returns:
            下一个可用行号
        """
        current_row = start_row

        # 标题
        cell = self.ws.cell(row=current_row, column=1, value="表2：总体汇总（按公牛）")
        self.style_manager.apply_title_style(cell)
        current_row += 1

        if summary_df is None or summary_df.empty:
            cell = self.ws.cell(row=current_row, column=1, value="暂无数据")
            return current_row + 1

        # 表头
        headers = ['冻精编号', '使用次数'] + trait_columns
        self._write_header(current_row, headers, start_col=1)
        current_row += 1

        # 数据行
        for idx, row in summary_df.iterrows():
            values = [
                row.get('冻精编号', ''),
                row.get('使用次数', 0)
            ]
            for trait in trait_columns:
                val = row.get(trait)
                values.append(val if pd.notna(val) else '-')

            self._write_data_row(current_row, values, start_col=1, alignment='center')
            current_row += 1

        # 汇总行
        total_count = summary_df['使用次数'].sum()
        total_row = ['合计', total_count]

        for trait in trait_columns:
            if pd.api.types.is_numeric_dtype(summary_df[trait]):
                valid_data = summary_df[[trait, '使用次数']].dropna(subset=[trait])
                if len(valid_data) > 0:
                    weighted_avg = (valid_data[trait] * valid_data['使用次数']).sum() / valid_data['使用次数'].sum()
                    total_row.append(weighted_avg)
                else:
                    total_row.append('-')
            else:
                total_row.append('-')

        self._write_total_row(current_row, total_row, start_col=1)
        current_row += 1

        logger.info(f"  ✓ 表2构建完成：{len(summary_df)} 个公牛")
        return current_row

    def _build_table3_year_bull_summary(self, start_row: int, summary_df: pd.DataFrame,
                                       trait_columns: list) -> int:
        """
        构建表3：按年份+公牛汇总

        Returns:
            下一个可用行号
        """
        current_row = start_row

        # 标题
        cell = self.ws.cell(row=current_row, column=1, value="表3：按年份和公牛汇总")
        self.style_manager.apply_title_style(cell)
        current_row += 1

        if summary_df is None or summary_df.empty:
            cell = self.ws.cell(row=current_row, column=1, value="暂无数据")
            return current_row + 1

        # 表头
        headers = ['使用年份', '冻精编号', '冻精类型', '使用次数'] + trait_columns
        self._write_header(current_row, headers, start_col=1)
        current_row += 1

        # 数据行
        for idx, row in summary_df.iterrows():
            values = [
                row.get('使用年份', ''),
                row.get('冻精编号', ''),
                row.get('冻精类型', ''),
                row.get('使用次数', 0)
            ]
            for trait in trait_columns:
                val = row.get(trait)
                values.append(val if pd.notna(val) else '-')

            self._write_data_row(current_row, values, start_col=1, alignment='center')
            current_row += 1

        # 汇总行
        total_count = summary_df['使用次数'].sum()
        total_row = ['合计', '-', '-', total_count]

        for trait in trait_columns:
            if pd.api.types.is_numeric_dtype(summary_df[trait]):
                valid_data = summary_df[[trait, '使用次数']].dropna(subset=[trait])
                if len(valid_data) > 0:
                    weighted_avg = (valid_data[trait] * valid_data['使用次数']).sum() / valid_data['使用次数'].sum()
                    total_row.append(weighted_avg)
                else:
                    total_row.append('-')
            else:
                total_row.append('-')

        self._write_total_row(current_row, total_row, start_col=1)
        current_row += 1

        logger.info(f"  ✓ 表3构建完成：{len(summary_df)} 行数据")
        return current_row
