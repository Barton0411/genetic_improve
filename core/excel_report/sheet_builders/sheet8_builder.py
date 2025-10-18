"""
Sheet 8构建器: 已用公牛性状汇总分析
v1.2版本 - 过去5年已用公牛育种性状汇总及趋势分析
"""

from .base_builder import BaseSheetBuilder
from openpyxl.utils import get_column_letter
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class Sheet8Builder(BaseSheetBuilder):
    """
    Sheet 8: 已用公牛性状汇总分析

    包含内容:
    1. 过去5年已用公牛性状汇总表（按公牛分组）
    2. 各性状进展折线图（TODO）
    3. 性状进展数据表（TODO）
    """

    def build(self, data: dict):
        """
        构建Sheet 8: 已用公牛性状汇总分析

        Args:
            data: 包含已用公牛汇总数据（来自bull_usage_collector）
                - recent_5_years_summary: 过去5年按公牛汇总的性状数据（DataFrame）
                - trait_columns: 性状列名列表
                - current_year: 当前年份
        """
        try:
            logger.info("开始构建Sheet 8: 已用公牛性状汇总分析")

            # 创建Sheet
            self._create_sheet("已用公牛性状汇总")
            logger.info("✓ Sheet创建成功")

            # 获取数据
            summary_df = data.get('recent_5_years_summary')
            trait_columns = data.get('trait_columns', [])
            current_year = data.get('current_year')

            if summary_df is None or summary_df.empty:
                logger.warning("过去5年汇总数据为空，跳过构建")
                cell = self.ws.cell(row=1, column=1, value="暂无数据")
                self.style_manager.apply_title_style(cell)
                return

            logger.info(f"✓ 数据准备完成：{len(summary_df)} 个公牛，{len(trait_columns)} 个性状")

            current_row = 1

            # === 1. 标题 ===
            title_text = f"过去5年已用公牛性状汇总（{current_year-5}-{current_year}）"
            cell = self.ws.cell(row=current_row, column=1, value=title_text)
            self.style_manager.apply_title_style(cell)
            current_row += 1

            # === 2. 构建表头 ===
            headers = ['冻精编号', '使用次数'] + trait_columns

            self._write_header(current_row, headers, start_col=1)
            current_row += 1

            # === 3. 写入数据 ===
            for idx, row in summary_df.iterrows():
                values = []

                # 冻精编号
                naab = row.get('冻精编号', '')
                values.append(naab)

                # 使用次数
                count = row.get('使用次数', 0)
                values.append(count)

                # 各性状值
                for trait in trait_columns:
                    val = row.get(trait)
                    values.append(val if pd.notna(val) else '-')

                self._write_data_row(current_row, values, start_col=1, alignment='center')
                current_row += 1

            # === 4. 添加汇总行（可选） ===
            # 计算总使用次数
            total_count = summary_df['使用次数'].sum()

            # 计算各性状的加权平均（按使用次数加权）
            total_row = ['总计', total_count]

            for trait in trait_columns:
                # 只对数值类型的性状计算加权平均
                if pd.api.types.is_numeric_dtype(summary_df[trait]):
                    # 过滤掉空值
                    valid_data = summary_df[[trait, '使用次数']].dropna(subset=[trait])

                    if len(valid_data) > 0:
                        # 加权平均 = Σ(性状值 × 使用次数) / Σ使用次数
                        weighted_sum = (valid_data[trait] * valid_data['使用次数']).sum()
                        total_weight = valid_data['使用次数'].sum()

                        if total_weight > 0:
                            weighted_avg = weighted_sum / total_weight
                            total_row.append(weighted_avg)
                        else:
                            total_row.append('-')
                    else:
                        total_row.append('-')
                else:
                    # 非数值列，不计算
                    total_row.append('-')

            self._write_total_row(current_row, total_row, start_col=1)
            current_row += 1

            # === 5. 设置列宽 ===
            for col_idx in range(1, len(headers) + 1):
                col_letter = get_column_letter(col_idx)

                if col_idx == 1:  # 冻精编号列
                    self.ws.column_dimensions[col_letter].width = 18
                elif col_idx == 2:  # 使用次数列
                    self.ws.column_dimensions[col_letter].width = 12
                else:  # 性状列
                    self.ws.column_dimensions[col_letter].width = 12

            # === 6. 冻结首行 ===
            self._freeze_panes('A3')  # 冻结前两行（标题+表头）

            logger.info(f"✓ Sheet 8构建完成：{len(summary_df)} 个公牛，{len(trait_columns)} 个性状")

        except Exception as e:
            logger.error(f"构建Sheet 8失败: {e}", exc_info=True)
            raise
