"""
Sheet 3-1构建器: 年份汇总与性状进展
"""

from .base_builder import BaseSheetBuilder
from openpyxl.chart import LineChart, Reference
from openpyxl.utils import get_column_letter
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class Sheet3YearlySummaryBuilder(BaseSheetBuilder):
    """Sheet 3-1: 年份汇总与性状进展"""

    def build(self, data: dict):
        """
        构建Sheet 3-1

        Args:
            data: {
                'present_summary': 在群母牛年份汇总DataFrame,
                'all_summary': 全部母牛年份汇总DataFrame,
                'comparison_farms': 对比牧场数据列表（可选）
            }
        """
        try:
            # 创建Sheet
            self._create_sheet("年份汇总与性状进展")
            logger.info("构建Sheet 3-1: 年份汇总与性状进展")

            present_df = data.get('present_summary')
            all_df = data.get('all_summary')
            comparison_farms = data.get('comparison_farms', [])

            if present_df is None or present_df.empty:
                logger.warning("Sheet 3-1: 在群母牛数据为空，跳过构建")
                return

            current_row = 1

            # === 1. 左侧：在群母牛年份汇总表 ===
            cell = self.ws.cell(row=current_row, column=1, value="在群母牛年份汇总")
            self.style_manager.apply_title_style(cell)
            current_row += 1

            # 写入表头
            headers_present = list(present_df.columns)
            self._write_header(current_row, headers_present, start_col=1)
            current_row += 1

            # 写入数据
            for idx, row in present_df.iterrows():
                values = list(row)
                # 如果是总计行，使用合计行样式
                if '总计' in str(values[0]):
                    self._write_total_row(current_row, values, start_col=1)
                else:
                    self._write_data_row(current_row, values, start_col=1, alignment='center')
                current_row += 1

            # 添加对比牧场数据（如果有）
            if comparison_farms:
                for farm in comparison_farms:
                    farm_row = [farm.get('name', '对比牧场'), farm.get('count', ''),
                               farm.get('NM$', ''), farm.get('TPI', '')]
                    # 补齐其他列
                    while len(farm_row) < len(headers_present):
                        farm_row.append('')
                    self._write_data_row(current_row, farm_row, start_col=1, alignment='center')
                    current_row += 1

            # === 2. 右侧：全部母牛年份汇总表（间隔6列） ===
            if all_df is not None and not all_df.empty:
                right_start_col = len(headers_present) + 1 + 6  # 左表列数 + 1 + 空6列

                current_row_right = 1
                cell = self.ws.cell(row=current_row_right, column=right_start_col, value="全部母牛年份汇总")
                self.style_manager.apply_title_style(cell)
                current_row_right += 1

                # 写入表头
                headers_all = list(all_df.columns)
                self._write_header(current_row_right, headers_all, start_col=right_start_col)
                current_row_right += 1

                # 写入数据
                for idx, row in all_df.iterrows():
                    values = list(row)
                    if '总计' in str(values[0]):
                        self._write_total_row(current_row_right, values, start_col=right_start_col)
                    else:
                        self._write_data_row(current_row_right, values, start_col=right_start_col, alignment='center')
                    current_row_right += 1

                # 添加对比牧场数据（如果有）
                if comparison_farms:
                    for farm in comparison_farms:
                        farm_row = [farm.get('name', '对比牧场'), farm.get('count', ''),
                                   farm.get('NM$', ''), farm.get('TPI', '')]
                        while len(farm_row) < len(headers_all):
                            farm_row.append('')
                        self._write_data_row(current_row_right, farm_row, start_col=right_start_col, alignment='center')
                        current_row_right += 1

            # === 3. 下方：性状进展折线图（3个一排） ===
            chart_start_row = max(current_row, current_row_right if 'current_row_right' in locals() else current_row) + 2

            # 获取需要绘制折线图的性状（所有"平均"开头的列）
            trait_columns = [col for col in headers_present if col.startswith('平均')]

            # 每排3个图表
            charts_per_row = 3
            # 图表间隔设置（不影响图表实际显示尺寸）
            col_gap = 2  # 图表横向间隔2列
            row_gap = 2  # 图表纵向间隔2行

            # 绘制所有性状的折线图
            # 每个图表实际占用空间：横10列 × 竖20行（用于定位）
            chart_col_span = 10
            chart_row_span = 20

            for idx, trait_col in enumerate(trait_columns):
                row_idx = idx // charts_per_row
                col_idx = idx % charts_per_row

                chart_row = chart_start_row + row_idx * (chart_row_span + row_gap)
                chart_col = 1 + col_idx * (chart_col_span + col_gap)

                # 创建折线图
                trait_name = trait_col.replace('平均', '')
                self._create_trait_trend_chart(
                    present_df, trait_col, trait_name,
                    chart_row, chart_col, chart_row_span, chart_col_span
                )

            # 设置列宽
            for col in range(1, right_start_col + len(headers_all) if 'right_start_col' in locals() else len(headers_present) + 1):
                self.ws.column_dimensions[get_column_letter(col)].width = 12

            # 冻结首行
            self._freeze_panes('A2')

            logger.info(f"✓ Sheet 3-1构建完成")

        except Exception as e:
            logger.error(f"构建Sheet 3-1失败: {e}", exc_info=True)
            raise

    def _create_trait_trend_chart(self, df, trait_col, trait_name, chart_row, chart_col, row_span, col_span):
        """创建性状进展折线图"""
        try:
            # 创建折线图
            chart = LineChart()
            chart.title = f"{trait_name}性状进展"
            chart.style = 13
            chart.y_axis.title = trait_name
            chart.x_axis.title = "出生年份"

            # 过滤出有效数据行（排除总计行和对比牧场行）
            valid_df = df[~df['出生年份'].str.contains('总计|对比', na=False)]

            if len(valid_df) == 0:
                return

            # 数据范围（假设数据从第3行开始）
            data = Reference(self.ws, min_col=df.columns.get_loc(trait_col) + 1,
                           min_row=3, max_row=3 + len(valid_df) - 1)
            cats = Reference(self.ws, min_col=1, min_row=3, max_row=3 + len(valid_df) - 1)

            chart.add_data(data, titles_from_data=False)
            chart.set_categories(cats)

            # 自动调整Y轴范围以覆盖最小值和最大值
            # 获取数据的最小值和最大值
            trait_values = valid_df[trait_col].dropna()
            if len(trait_values) > 0:
                min_val = trait_values.min()
                max_val = trait_values.max()
                # 添加10%的边距使图表更美观
                value_range = max_val - min_val
                if value_range > 0:
                    chart.y_axis.scaling.min = min_val - value_range * 0.1
                    chart.y_axis.scaling.max = max_val + value_range * 0.1

            # 设置图表大小（保持原始尺寸）
            chart.width = 20  # 20cm宽
            chart.height = 10  # 10cm高

            anchor_cell = f"{get_column_letter(chart_col)}{chart_row}"
            self.ws.add_chart(chart, anchor_cell)

        except Exception as e:
            logger.error(f"创建折线图失败 {trait_name}: {e}")
