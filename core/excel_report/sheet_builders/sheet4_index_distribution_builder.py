"""
Sheet 4-1构建器: 母牛指数分布分析
"""

from .base_builder import BaseSheetBuilder
from openpyxl.chart import BarChart, PieChart, LineChart, Reference
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image
import pandas as pd
import numpy as np
import logging
import tempfile

logger = logging.getLogger(__name__)


class Sheet4IndexDistributionBuilder(BaseSheetBuilder):
    """Sheet 4-1: 母牛指数分布分析"""

    def build(self, data: dict):
        """
        构建Sheet 4-1

        Args:
            data: {
                'distribution_present': 在群母牛指数分布DataFrame,
                'distribution_all': 全部母牛指数分布DataFrame,
                'detail_df': 明细数据DataFrame（用于正态分布图）
            }
        """
        try:
            # 创建Sheet
            self._create_sheet("母牛指数分布分析")
            logger.info("构建Sheet 4-1: 母牛指数分布分析")

            present_df = data.get('distribution_present')
            all_df = data.get('distribution_all')
            detail_df = data.get('detail_df')

            if present_df is None or present_df.empty:
                logger.warning("Sheet 4-1: 在群母牛指数分布数据为空，跳过构建")
                return

            current_row = 1

            # === 1. 上方：分布统计表（在群母牛和全部母牛并排，间隔2列） ===
            # 在群母牛表（从A列开始）
            cell = self.ws.cell(row=current_row, column=1, value="在群母牛指数分布")
            self.style_manager.apply_title_style(cell)
            current_row += 1

            # 写入在群母牛表头和数据
            headers_present = list(present_df.columns)
            self._write_header(current_row, headers_present, start_col=1)
            current_row += 1

            for idx, row in present_df.iterrows():
                values = list(row)
                self._write_data_row(current_row, values, start_col=1, alignment='center')
                current_row += 1

            # 全部母牛表（间隔6列）
            if all_df is not None and not all_df.empty:
                right_start_col = len(headers_present) + 1 + 6  # 左表列数 + 1 + 空6列

                current_row_right = 1
                cell = self.ws.cell(row=current_row_right, column=right_start_col, value="全部母牛指数分布")
                self.style_manager.apply_title_style(cell)
                current_row_right += 1

                # 写入全部母牛表头和数据
                headers_all = list(all_df.columns)
                self._write_header(current_row_right, headers_all, start_col=right_start_col)
                current_row_right += 1

                for idx, row in all_df.iterrows():
                    values = list(row)
                    self._write_data_row(current_row_right, values, start_col=right_start_col, alignment='center')
                    current_row_right += 1

            # === 2. 下方：图表区域（垂直排列：饼图、柱状图、正态分布图） ===
            chart_start_row = max(current_row, current_row_right if 'current_row_right' in locals() else current_row) + 2

            # 图表大小
            chart_width = 15  # 15cm宽
            chart_height = 10  # 10cm高
            chart_row_span = 20  # 每个图表占20行
            row_gap = 2  # 图表纵向间隔2行

            # === 在群母牛图表（左侧） ===
            current_chart_row = chart_start_row
            left_data_col = 1  # 在群母牛数据从第1列开始

            # 饼图（数据在第1-3列，第2行是标题，第3行是表头，第4行开始是数据）
            self._create_pie_chart(present_df, "在群母牛指数分布占比",
                                  current_chart_row, 1, chart_height, chart_width, left_data_col)
            current_chart_row += chart_row_span + row_gap

            # 柱状图
            self._create_bar_chart(present_df, "在群母牛指数分布柱状图",
                                  current_chart_row, 1, chart_height, chart_width, left_data_col)
            current_chart_row += chart_row_span + row_gap

            # 正态分布图（使用明细数据）
            if detail_df is not None and not detail_df.empty:
                # 筛选在群母牛数据
                present_detail_df = detail_df[detail_df['是否在场'] == '是'].copy()
                self._create_normal_distribution_chart(present_detail_df, 'index_score', "在群母牛指数正态分布",
                                                       current_chart_row, 1, chart_height, chart_width, 52)
            else:
                logger.warning("明细数据不存在，跳过在群母牛正态分布图")

            # === 全部母牛图表（右侧） ===
            if all_df is not None and not all_df.empty:
                current_chart_row = chart_start_row
                right_chart_col = 1 + 7 + 2  # 左侧图表起始列(1) + 图表占用(7列) + 间隔(2列)
                right_data_col = right_start_col  # 全部母牛数据的起始列

                # 饼图
                self._create_pie_chart(all_df, "全部母牛指数分布占比",
                                      current_chart_row, right_chart_col, chart_height, chart_width, right_data_col)
                current_chart_row += chart_row_span + row_gap

                # 柱状图
                self._create_bar_chart(all_df, "全部母牛指数分布柱状图",
                                      current_chart_row, right_chart_col, chart_height, chart_width, right_data_col)
                current_chart_row += chart_row_span + row_gap

                # 正态分布图（使用明细数据）
                if detail_df is not None and not detail_df.empty:
                    # 全部母牛数据（只筛选母牛）
                    all_detail_df = detail_df[detail_df['sex'] == '母'].copy()
                    self._create_normal_distribution_chart(all_detail_df, 'index_score', "全部母牛指数正态分布",
                                                           current_chart_row, right_chart_col, chart_height, chart_width, 56)
                else:
                    logger.warning("明细数据不存在，跳过全部母牛正态分布图")

            # 设置列宽
            for col in range(1, 40):
                self.ws.column_dimensions[get_column_letter(col)].width = 12

            # 冻结首行
            self._freeze_panes('A2')

            logger.info(f"✓ Sheet 4-1构建完成")

        except Exception as e:
            logger.error(f"构建Sheet 4-1失败: {e}", exc_info=True)
            raise

    def _create_bar_chart(self, df, title, chart_row, chart_col, height_cm, width_cm, data_col):
        """创建柱状图"""
        try:
            chart = BarChart()
            chart.type = "col"
            chart.title = title
            chart.style = 10
            chart.y_axis.title = "头数"
            chart.x_axis.title = "分布区间"

            # 数据范围（第2行是表头，第3行开始是数据）
            # data_col是数据起始列，data_col+1是头数列
            data = Reference(self.ws, min_col=data_col + 1, min_row=2, max_row=2 + len(df))
            cats = Reference(self.ws, min_col=data_col, min_row=3, max_row=2 + len(df))

            chart.add_data(data, titles_from_data=True)
            chart.set_categories(cats)

            # 设置图表大小
            chart.width = width_cm
            chart.height = height_cm

            anchor_cell = f"{get_column_letter(chart_col)}{chart_row}"
            self.ws.add_chart(chart, anchor_cell)

        except Exception as e:
            logger.error(f"创建柱状图失败: {e}")

    def _create_pie_chart(self, df, title, chart_row, chart_col, height_cm, width_cm, data_col):
        """创建饼图"""
        try:
            chart = PieChart()
            chart.title = title
            chart.style = 10

            # 数据范围（第2行是表头，第3行开始是数据）
            # data_col是数据起始列，data_col+1是头数列
            data = Reference(self.ws, min_col=data_col + 1, min_row=2, max_row=2 + len(df))
            cats = Reference(self.ws, min_col=data_col, min_row=3, max_row=2 + len(df))

            chart.add_data(data, titles_from_data=True)
            chart.set_categories(cats)

            # 设置图表大小
            chart.width = width_cm
            chart.height = height_cm

            anchor_cell = f"{get_column_letter(chart_col)}{chart_row}"
            self.ws.add_chart(chart, anchor_cell)

        except Exception as e:
            logger.error(f"创建饼图失败: {e}")

    def _create_normal_distribution_chart(self, detail_df, score_column, title, chart_row, chart_col, height_cm, width_cm, data_start_col=52):
        """
        创建正态分布曲线图（基于明细数据）

        Args:
            detail_df: 明细数据DataFrame
            score_column: 分数列名（如'index_score'）
            title: 图表标题
            chart_row: 图表起始行
            chart_col: 图表起始列
            height_cm: 图表高度
            width_cm: 图表宽度
            data_start_col: 数据写入起始列（默认52，即AZ列）
        """
        try:
            import numpy as np
            from scipy import stats

            # 获取有效数据
            valid_data = detail_df[score_column].dropna()

            if len(valid_data) == 0:
                logger.warning(f"没有有效的{score_column}数据，跳过正态分布图")
                return

            # 计算统计量
            mu = valid_data.mean()
            sigma = valid_data.std()
            n = len(valid_data)
            min_val = valid_data.min()
            max_val = valid_data.max()
            median = valid_data.median()
            q1 = valid_data.quantile(0.25)
            q3 = valid_data.quantile(0.75)
            cv = (sigma / mu * 100) if mu != 0 else 0

            # 计算直方图数据（分成20个区间）
            counts, bin_edges = np.histogram(valid_data, bins=20)
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

            # 拟合正态分布
            # 生成正态分布曲线数据点
            x_range = np.linspace(valid_data.min(), valid_data.max(), 100)
            normal_curve = stats.norm.pdf(x_range, mu, sigma) * len(valid_data) * (bin_edges[1] - bin_edges[0])

            # 在当前工作表中写入图表数据（放在远离表格的位置）
            data_start_row = chart_row
            # data_start_col使用参数传入的值

            # 写入X轴数据（区间中心点，显示为整数）
            for i, x_val in enumerate(x_range):
                self.ws.cell(row=data_start_row + i + 1, column=data_start_col, value=int(round(x_val)))

            # 写入Y轴数据（正态分布曲线值）
            for i, y_val in enumerate(normal_curve):
                self.ws.cell(row=data_start_row + i + 1, column=data_start_col + 1, value=round(y_val, 2))

            # 创建折线图（Excel图表）
            chart = LineChart()
            chart.title = title
            chart.style = 13
            chart.y_axis.title = "频数"
            chart.x_axis.title = "指数值"

            # 数据范围
            data = Reference(self.ws, min_col=data_start_col + 1, min_row=data_start_row + 1,
                           max_row=data_start_row + len(x_range))
            cats = Reference(self.ws, min_col=data_start_col, min_row=data_start_row + 1,
                           max_row=data_start_row + len(x_range))

            chart.add_data(data, titles_from_data=False)
            chart.set_categories(cats)

            # 设置图表大小
            chart.width = width_cm
            chart.height = height_cm

            anchor_cell = f"{get_column_letter(chart_col)}{chart_row}"
            self.ws.add_chart(chart, anchor_cell)

            # === 在Excel图表下方添加统计指标表格 ===
            stats_start_row = chart_row + 20 + 2  # Excel图表下方2行
            stats_col = chart_col

            # 统计指标标题
            title_cell = self.ws.cell(row=stats_start_row, column=stats_col, value="统计指标")
            self.style_manager.apply_title_style(title_cell)
            stats_start_row += 1

            # 统计指标数据（两列布局）
            stats_items = [
                ("样本量(N)", f"{n}头"),
                ("均值(μ)", f"{mu:.2f}"),
                ("标准差(σ)", f"{sigma:.2f}"),
                ("变异系数(CV)", f"{cv:.2f}%"),
                ("最小值", f"{min_val:.2f}"),
                ("最大值", f"{max_val:.2f}"),
                ("中位数", f"{median:.2f}"),
                ("下四分位数(Q1)", f"{q1:.2f}"),
                ("上四分位数(Q3)", f"{q3:.2f}"),
            ]

            for label, value in stats_items:
                # 指标名称
                label_cell = self.ws.cell(row=stats_start_row, column=stats_col, value=label)
                self.style_manager.apply_data_style(label_cell, alignment='left')

                # 指标值
                value_cell = self.ws.cell(row=stats_start_row, column=stats_col + 1, value=value)
                self.style_manager.apply_data_style(value_cell, alignment='center')

                stats_start_row += 1

            # === 在统计指标表格下方嵌入matplotlib生成的高质量正态分布图 ===
            try:
                matplotlib_row = stats_start_row + 1  # 统计表格下方1行
                self._create_matplotlib_distribution(valid_data, title, mu, sigma,
                                                    matplotlib_row, chart_col, score_column)
            except Exception as e:
                logger.warning(f"创建matplotlib分布图失败: {e}")

        except ImportError:
            logger.warning("scipy未安装，使用简化的分布图")
            # 如果scipy不可用，创建简单的频率分布图
            self._create_simple_distribution_chart(detail_df, score_column, title,
                                                   chart_row, chart_col, height_cm, width_cm)
        except Exception as e:
            logger.error(f"创建正态分布图失败: {e}")

    def _create_matplotlib_distribution(self, valid_data, title, mu, sigma, chart_row, chart_col, score_column):
        """使用matplotlib创建高质量的正态分布图并嵌入Excel"""
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            from scipy import stats
            from matplotlib.ticker import MaxNLocator

            # 设置中文字体
            matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
            matplotlib.rcParams['axes.unicode_minus'] = False

            # 创建图表
            fig, ax = plt.subplots(figsize=(8, 6), dpi=150)

            # 绘制直方图（频率密度）
            n, bins, patches = ax.hist(valid_data, bins=30, density=True,
                                       alpha=0.6, color='#4472C4',
                                       edgecolor='white', linewidth=0.5,
                                       label='实际分布')

            # 绘制正态分布曲线
            x_range = np.linspace(valid_data.min(), valid_data.max(), 200)
            normal_curve = stats.norm.pdf(x_range, mu, sigma)
            ax.plot(x_range, normal_curve, 'r-', linewidth=2.5,
                   label=f'正态分布曲线\n(μ={mu:.2f}, σ={sigma:.2f})')

            # 添加均值线
            ax.axvline(mu, color='red', linestyle='--', linewidth=1.5,
                      alpha=0.7, label=f'均值: {mu:.2f}')

            # 添加±1σ、±2σ标记
            ax.axvline(mu - sigma, color='orange', linestyle=':', linewidth=1.2,
                      alpha=0.6, label=f'μ±σ')
            ax.axvline(mu + sigma, color='orange', linestyle=':', linewidth=1.2, alpha=0.6)
            ax.axvline(mu - 2*sigma, color='green', linestyle=':', linewidth=1,
                      alpha=0.5, label=f'μ±2σ')
            ax.axvline(mu + 2*sigma, color='green', linestyle=':', linewidth=1, alpha=0.5)

            # 设置X轴刻度为整数
            ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=10))

            # 设置标题和标签
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.set_xlabel('指数值', fontsize=11)
            ax.set_ylabel('频率密度', fontsize=11)
            ax.legend(loc='upper right', fontsize=9)
            ax.grid(True, alpha=0.3, linestyle='--')

            # 添加统计信息文本框
            median = valid_data.median()
            q1 = valid_data.quantile(0.25)
            q3 = valid_data.quantile(0.75)
            cv = (sigma / mu * 100) if mu != 0 else 0

            stats_text = (
                f'样本量: {len(valid_data)}头\n'
                f'均值: {mu:.2f}\n'
                f'标准差: {sigma:.2f}\n'
                f'变异系数: {cv:.2f}%\n'
                f'中位数: {median:.2f}\n'
                f'Q1-Q3: {q1:.2f} - {q3:.2f}'
            )

            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
                   fontsize=9, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

            plt.tight_layout()

            # 保存为临时文件
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            plt.savefig(temp_file.name, dpi=150, bbox_inches='tight',
                       facecolor='white', edgecolor='none')
            plt.close(fig)

            # 插入图片到Excel
            img = Image(temp_file.name)
            # 设置图片大小为原来的0.65倍：9.75cm×6.5cm
            img.width = int(15 * 0.65 * 150 / 2.54)  # 9.75cm宽 ≈ 576像素
            img.height = int(10 * 0.65 * 150 / 2.54)  # 6.5cm高 ≈ 384像素

            anchor_cell = f"{get_column_letter(chart_col)}{chart_row}"
            self.ws.add_image(img, anchor_cell)

            # 注意：临时文件会在Excel保存后自动清理，这里不删除
            logger.info(f"✓ matplotlib正态分布图已嵌入: {title}")

        except ImportError as e:
            logger.warning(f"matplotlib未安装，跳过高质量分布图: {e}")
        except Exception as e:
            logger.error(f"创建matplotlib分布图失败: {e}", exc_info=True)

    def _create_simple_distribution_chart(self, detail_df, score_column, title, chart_row, chart_col, height_cm, width_cm):
        """创建简化的频率分布图（当scipy不可用时）"""
        try:
            import numpy as np

            # 获取有效数据
            valid_data = detail_df[score_column].dropna()

            if len(valid_data) == 0:
                logger.warning(f"没有有效的{score_column}数据")
                return

            # 计算直方图数据
            counts, bin_edges = np.histogram(valid_data, bins=20)
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

            # 在工作表中写入数据
            data_start_row = chart_row
            data_start_col = 52  # AZ列

            for i, (x_val, y_val) in enumerate(zip(bin_centers, counts)):
                self.ws.cell(row=data_start_row + i + 1, column=data_start_col, value=int(round(x_val)))
                self.ws.cell(row=data_start_row + i + 1, column=data_start_col + 1, value=int(y_val))

            # 创建折线图
            chart = LineChart()
            chart.title = title
            chart.style = 13
            chart.y_axis.title = "频数"
            chart.x_axis.title = "指数值"

            data = Reference(self.ws, min_col=data_start_col + 1, min_row=data_start_row + 1,
                           max_row=data_start_row + len(bin_centers))
            cats = Reference(self.ws, min_col=data_start_col, min_row=data_start_row + 1,
                           max_row=data_start_row + len(bin_centers))

            chart.add_data(data, titles_from_data=False)
            chart.set_categories(cats)

            chart.width = width_cm
            chart.height = height_cm

            anchor_cell = f"{get_column_letter(chart_col)}{chart_row}"
            self.ws.add_chart(chart, anchor_cell)

        except Exception as e:
            logger.error(f"创建简化分布图失败: {e}")
