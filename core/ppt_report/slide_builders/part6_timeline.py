"""
Part 6: 配种记录时间线分析构建器
对应PPT模版的"配种记录时间线"页面（两页：全部记录、近一年）
"""

import logging
from typing import Dict, List
from pathlib import Path
from io import BytesIO

from openpyxl import load_workbook
from openpyxl.drawing.image import Image as OpenpyxlImage
from pptx.util import Cm, Pt

from ..base_builder import BaseSlideBuilder
from ..config import FONT_NAME_CN

logger = logging.getLogger(__name__)


class Part6TimelineBuilder(BaseSlideBuilder):
    """Part 6: 配种记录时间线分析构建器"""

    def __init__(self, prs, chart_creator, farm_name: str):
        super().__init__(prs, chart_creator)
        self.farm_name = farm_name

    def build(self, data: Dict):
        """
        构建 Part 6: 配种记录时间线分析

        Args:
            data: 包含 'excel_path' 的数据字典
        """
        logger.info("=" * 60)
        logger.info("开始构建Part 6: 配种记录时间线分析")
        logger.info("=" * 60)

        # 读取Excel文件中的图片
        excel_path = data.get("excel_path")
        if excel_path is None:
            logger.error("excel_path 未找到，跳过配种记录时间线")
            return

        try:
            # 从Excel中提取Image 12和Image 13
            images = self._extract_images_from_excel(excel_path)
            logger.info(f"✓ 从Excel中提取到 {len(images)} 个图片")
        except Exception as e:
            logger.error(f"提取Excel图片失败: {e}")
            return

        if len(images) < 2:
            logger.warning(f"Excel中图片数量不足（需要2个，实际{len(images)}个），跳过配种记录时间线")
            return

        # 查找"配种记录时间线"页面
        logger.info(f"开始查找包含'配种记录时间线'的页面，模板共{len(self.prs.slides)}页")
        target_slides = self.find_slides_by_text("配种记录时间线", start_index=0)

        if len(target_slides) < 2:
            logger.error(f"❌ 未找到足够的配种记录时间线页面（需要2页，实际{len(target_slides)}页），跳过")
            return

        logger.info(f"✓ 找到 {len(target_slides)} 个配种记录时间线页面")

        # 导出图片到临时文件
        temp_dir = Path(self.chart_creator.output_dir)

        # Image 12: 配种记录时间线-全部记录
        image_12_path = self._export_image_to_file(images[0], temp_dir / "timeline_all.png")
        if image_12_path:
            self._add_image_to_slide(target_slides[0], image_12_path, "配种记录时间线-全部记录")
            self._fill_timeline_analysis(target_slides[0], "all")
            logger.info(f"✓ 添加图片到第{target_slides[0] + 1}页: 配种记录时间线-全部记录")

        # Image 13: 配种记录时间线-近一年
        if len(images) > 1:
            image_13_path = self._export_image_to_file(images[1], temp_dir / "timeline_recent.png")
            if image_13_path:
                self._add_image_to_slide(target_slides[1], image_13_path, "配种记录时间线-近一年")
                self._fill_timeline_analysis(target_slides[1], "recent")
                logger.info(f"✓ 添加图片到第{target_slides[1] + 1}页: 配种记录时间线-近一年")

        logger.info("✓ Part 6 配种记录时间线分析完成")

    def _fill_timeline_analysis(self, slide_index: int, timeline_type: str):
        """
        填充时间线分析文本

        Args:
            slide_index: 幻灯片索引
            timeline_type: 时间线类型 ('all' 或 'recent')
        """
        try:
            slide = self.prs.slides[slide_index]

            # 生成分析文本
            if timeline_type == "all":
                analysis = (
                    "分析：配种记录时间线展示了牧场历史配种活动的整体分布情况。"
                    "时间线可直观反映配种的季节性规律和年度变化趋势，"
                    "有助于优化配种计划安排和冻精库存管理。"
                )
            else:  # recent
                analysis = (
                    "分析：近一年配种记录时间线展示了最近12个月的配种活动分布。"
                    "通过分析近期配种密度和时间分布，可以评估当前配种计划执行情况，"
                    "及时调整配种策略以提高繁殖效率。"
                )

            # 查找分析文本框（避免匹配到标题）
            textbox = None
            candidate_textboxes = []

            for shape in slide.shapes:
                if hasattr(shape, "text_frame"):
                    name = shape.name if shape.name else ""
                    shape_text = shape.text if hasattr(shape, "text") else ""

                    # 跳过标题：页面标题通常包含"配种记录时间线"
                    if "配种记录时间线" in shape_text:
                        continue
                    # 跳过图片
                    if "图片" in name or "Picture" in name:
                        continue

                    # 查找文本框
                    if "文本框" in name or "TextBox" in name:
                        candidate_textboxes.append(shape)

            # 按位置（top）排序，选择最靠下的文本框作为分析文本框
            if candidate_textboxes:
                candidate_textboxes.sort(key=lambda s: getattr(s, 'top', 0), reverse=True)
                textbox = candidate_textboxes[0]

            if textbox:
                # 清空文本框并设置新内容
                tf = textbox.text_frame
                tf.clear()
                p = tf.paragraphs[0] if tf.paragraphs else tf.add_paragraph()
                run = p.add_run()
                run.text = analysis

                # 设置字体：微软雅黑15号非加粗
                run.font.name = FONT_NAME_CN
                run.font.size = Pt(15)
                run.font.bold = False

                logger.info(f"✓ 填充时间线分析文本")
            else:
                logger.debug("未找到时间线分析文本框")

        except Exception as e:
            logger.warning(f"填充时间线分析失败: {e}")

    def _extract_images_from_excel(self, excel_path: str) -> List[OpenpyxlImage]:
        """
        从Excel中提取图片（Image 12和Image 13）

        Returns:
            List[OpenpyxlImage]: 图片对象列表
        """
        wb = load_workbook(str(excel_path))
        ws = wb['已用公牛性状汇总']

        images = []

        # 获取工作表中的所有图片
        if hasattr(ws, '_images') and ws._images:
            # 按图片的位置或名称排序（假设Image 12和13是最后两个）
            all_images = list(ws._images)
            logger.info(f"工作表中共有 {len(all_images)} 个图片对象")

            # 通常Excel中的图表和图片是按顺序编号的
            # Image 12和Image 13应该是倒数第2个和倒数第1个
            if len(all_images) >= 2:
                images = all_images[-2:]  # 取最后两个
                logger.debug(f"提取最后两个图片作为时间线图")
            else:
                images = all_images
        else:
            logger.warning("工作表中没有找到图片对象")

        return images

    def _export_image_to_file(self, image: OpenpyxlImage, output_path: Path) -> Path:
        """
        将Excel图片导出为文件

        Args:
            image: openpyxl图片对象
            output_path: 输出文件路径

        Returns:
            Path: 导出的图片文件路径
        """
        try:
            # 获取图片数据
            if hasattr(image, '_data'):
                image_data = image._data()
            elif hasattr(image, 'ref'):
                # 从图片引用中获取数据
                image_data = image.ref
            else:
                logger.warning("无法获取图片数据")
                return None

            # 保存图片
            with open(output_path, 'wb') as f:
                if isinstance(image_data, bytes):
                    f.write(image_data)
                else:
                    f.write(image_data.read())

            logger.debug(f"图片已导出: {output_path.name}")
            return output_path

        except Exception as e:
            logger.warning(f"导出图片失败: {e}")
            return None

    def _add_image_to_slide(self, slide_index: int, image_path: Path, title: str):
        """
        将图片添加到幻灯片（大小：32cm宽 × 10cm高）

        Args:
            slide_index: 幻灯片索引
            image_path: 图片文件路径
            title: 图片标题（用于日志）
        """
        try:
            slide = self.prs.slides[slide_index]

            # 图片大小：32cm宽 × 10cm高（用户要求）
            width = Cm(32)
            height = Cm(10)

            # 居中放置
            # PPT默认尺寸：33.867cm × 19.05cm (13.33" × 7.5")
            prs_width = self.prs.slide_width
            prs_height = self.prs.slide_height

            left = (prs_width - width) // 2
            top = Cm(4)  # 距离顶部4cm

            # 查找并删除现有的图片占位符
            for shape in slide.shapes:
                if hasattr(shape, 'name') and ('图片' in shape.name or 'Picture' in shape.name):
                    sp = shape._element
                    sp.getparent().remove(sp)
                    logger.debug(f"  删除占位符: {shape.name}")
                    break

            # 添加新图片
            slide.shapes.add_picture(
                str(image_path),
                left=left,
                top=top,
                width=width,
                height=height
            )

            logger.debug(f"  图片已添加: {title}, 大小={width.cm:.1f}cm×{height.cm:.1f}cm")

        except Exception as e:
            logger.warning(f"添加图片到幻灯片失败: {e}")
            logger.debug(f"错误详情: {e}", exc_info=True)
