"""
Part 3: 系谱分析构建器
"""

import logging
from typing import Dict, List, Optional

import pandas as pd
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_FILL

from ..base_builder import BaseSlideBuilder

logger = logging.getLogger(__name__)


class Part3PedigreeBuilder(BaseSlideBuilder):
    """Part 3: 系谱分析构建器"""

    SECTION_SLIDE_INDEX = 6  # Slide 7 (0-based)
    SUMMARY_SLIDE_INDEX = 7  # Slide 8 (0-based)

    def __init__(self, prs, chart_creator, farm_name: str):
        super().__init__(prs, chart_creator)
        self.farm_name = farm_name

    def build(self, data: Dict, versions: Optional[List[str]] = None):
        """
        构建 Part 3: 系谱分析（填充模板中的第 7-8 页）
        """
        logger.info("=" * 60)
        logger.info("开始构建Part 3: 系谱分析")
        logger.info("=" * 60)

        # 章节页（Slide 7）模板已就绪，这里暂不做动态修改
        self._fill_summary_slide(data)
        logger.info("✓ Part 3 模板页更新完成")

    # ------------------------------------------------------------------ #
    def _find_table(self, slide, name: str):
        for shape in slide.shapes:
            if shape.name == name and getattr(shape, "has_table", False):
                return shape.table
        return None

    @staticmethod
    def _delete_row(table, row_idx: int):
        """
        从导出的 PPT 中物理删除一行（不影响模板文件）。

        python-pptx 没有公开的删除行 API，这里通过底层 XML 删除 <tr> 节点。
        """
        try:
            row = table.rows[row_idx]
        except IndexError:
            return
        tbl = table._tbl  # 底层 <a:tbl>
        tr = row._tr      # 底层 <a:tr>
        tbl.remove(tr)

    # ------------------------------------------------------------------ #
    def _fill_summary_slide(self, data: Dict):
        """填充 Slide 8 - 系谱识别率可视化分析"""
        try:
            slide = self.prs.slides[self.SUMMARY_SLIDE_INDEX]
        except IndexError:
            logger.warning("模板缺少Part3汇总页（Slide 8）")
            return

        df = data.get("pedigree_analysis")
        if df is None or df.empty:
            logger.warning("pedigree_analysis 数据为空，跳过 Slide 8 填充")
            return

        # Excel中该区域的结构示例（列共 8 列）:
        # 0: 出生年份, 1: 总头数, 2: 可识别父号牛数, 3: 可识别父号占比,
        # 4: 可识别外祖父牛数, 5: 可识别外祖父占比, 6: 可识别外曾外祖父牛数, 7: 可识别外曾外祖父占比

        # 找到“出生年份”表头行
        header_row_idx = None
        for i in range(len(df)):
            if str(df.iloc[i, 0]).strip() == "出生年份":
                header_row_idx = i
                break
        if header_row_idx is None:
            logger.warning("未在系谱识别分析中找到“出生年份”表头，跳过填充")
            return

        # 从表头下一行开始，收集到“合计”行为止（包含“合计”），中间空行跳过
        rows = []
        for i in range(header_row_idx + 1, len(df)):
            first_cell = df.iloc[i, 0]
            if pd.isna(first_cell):
                # 空行直接跳过，避免被截断
                continue

            text = str(first_cell).strip()
            row_values = [
                df.iloc[i, j] if j < df.shape[1] else "" for j in range(8)
            ]
            rows.append([str(v) if not pd.isna(v) else "" for v in row_values])

            if text == "合计":
                break

        if not rows:
            logger.warning("未能从系谱识别分析中解析出任何汇总行")
            return

        # 将数据写入模板中的“表格 2”
        table = self._find_table(slide, "表格 2")
        if not table:
            logger.warning("未找到系谱汇总表（表格 2）")
            return

        # 1) 识别模板中的“合计”行：优先查找首列文本包含“合计”的行
        total_template_rows = len(table.rows)
        total_row_idx = None
        for r in range(1, total_template_rows):
            cell_text = table.cell(r, 0).text_frame.text.strip()
            if "合计" in cell_text:
                total_row_idx = r
                break
        if total_row_idx is None:
            # 找不到就退回用最后一行作为“合计”
            total_row_idx = total_template_rows - 1

        # 2) 根据模板结构计算可容纳的年份行行数
        year_slots = max(total_row_idx - 1, 0)

        # rows 中最后一行应为“合计”，其余为年份行
        if rows[-1][0] == "" or "合计" not in rows[-1][0]:
            logger.warning("Excel 最后一行不是“合计”，按顺序最后一行作为合计处理")
        year_rows = rows[:-1]
        total_row = rows[-1]

        # 如果年份行多于模板可容纳的行数，只保留最近的若干年
        if len(year_rows) > year_slots:
            logger.warning(
                "年份行数(%s)超过模板年份行数(%s)，仅保留最近 %s 年",
                len(year_rows),
                year_slots,
                year_slots,
            )
            year_rows = year_rows[-year_slots:]

        # 3) 写入年份行，从第 1 行到 total_row_idx-1
        for slot in range(year_slots):
            row_idx = 1 + slot
            if slot < len(year_rows):
                # 有对应年份数据
                row_values = year_rows[slot]
                for col_idx in range(len(table.columns)):
                    value = row_values[col_idx] if col_idx < len(row_values) else ""
                    self._set_cell_text(table.cell(row_idx, col_idx), value)

        # 4) 写入合计行到模板中的“合计”行（保持该行的浅蓝底样式）
        for col_idx in range(len(table.columns)):
            value = total_row[col_idx] if col_idx < len(total_row) else ""
            self._set_cell_text(table.cell(total_row_idx, col_idx), value)

        # 5) 删除“多余的模板行”，让导出的 PPT 在结构上也只保留
        #    （header + 实际年份行 + 合计行）这些需要的行。
        desired_year_rows = len(year_rows)
        data_start = 1
        current_total_rows = len(table.rows)
        rows_to_keep = {0, total_row_idx}
        # 保留前 N 个年份行（如果模板年份槽比实际年份多，多出的会被删除）
        for i in range(desired_year_rows):
            rows_to_keep.add(data_start + i)
        rows_to_delete = [
            r
            for r in range(1, current_total_rows)
            if r not in rows_to_keep
        ]
        # 从下往上删除，避免索引错位
        for r in sorted(rows_to_delete, reverse=True):
            self._delete_row(table, r)
        total_template_rows = len(table.rows)

        # 6) 根据“占比<80%标粉色”的规则设置底色（包括合计行）
        # 占比列索引：可识别父号占比(3)、可识别外祖父占比(5)、可识别外曾外祖父占比(7)
        percent_columns = [3, 5, 7]

        # 尝试从模板中找一个已有的粉色单元格作为颜色来源
        pink_rgb = None
        try:
            for r in range(1, total_template_rows):
                for c in range(len(table.columns)):
                    cell = table.cell(r, c)
                    fill = cell.fill
                    if fill.type == MSO_FILL.SOLID and fill.fore_color.rgb is not None:
                        # 找到第一个有填充色的正文单元格，作为粉色模板
                        pink_rgb = fill.fore_color.rgb
                        break
                if pink_rgb is not None:
                    break
        except Exception:
            pink_rgb = None

        if pink_rgb is None:
            # 兜底使用一个柔和的粉色
            pink_rgb = RGBColor(255, 230, 230)

        # 从第 1 行到最后一行（包括合计行），对占比列应用 <80% 标粉色规则
        for r in range(1, total_template_rows):
            for c in percent_columns:
                if c >= len(table.columns):
                    continue
                cell = table.cell(r, c)
                text = cell.text_frame.text.strip()
                if not text:
                    continue
                # 去掉百分号并解析数值
                clean = text.replace("%", "").replace("％", "").strip()
                try:
                    value = float(clean)
                except ValueError:
                    continue

                if value < 80.0:
                    # 小于80%标记为粉色
                    fill = cell.fill
                    fill.solid()
                    fill.fore_color.rgb = pink_rgb

    # ------------------------------------------------------------------ #
    @staticmethod
    def _set_cell_text(cell, text: str):
        """只更新单元格文字，保持模板样式"""
        tf = cell.text_frame
        if not tf.paragraphs:
            para = tf.add_paragraph()
        else:
            para = tf.paragraphs[0]
        if para.runs:
            run = para.runs[0]
        else:
            run = para.add_run()
        run.text = text
        # 清理其它 run/段落中的旧文本
        for extra_run in para.runs[1:]:
            extra_run.text = ""
        for extra_para in tf.paragraphs[1:]:
            for extra_run in extra_para.runs:
                extra_run.text = ""
