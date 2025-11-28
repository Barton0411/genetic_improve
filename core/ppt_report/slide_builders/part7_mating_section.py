"""
Part 7: 选配推荐方案章节页构建器（页172）
"""

import logging
from typing import Dict

from ..base_builder import BaseSlideBuilder

logger = logging.getLogger(__name__)


class Part7MatingSectionBuilder(BaseSlideBuilder):
    """Part 7: 选配推荐方案章节页构建器（页172）"""

    def __init__(self, prs, chart_creator, farm_name: str):
        super().__init__(prs, chart_creator)
        self.farm_name = farm_name

    def build(self, data: Dict):
        """
        构建 Part 7: 选配推荐方案章节页（页172）

        章节页通常保持模板静态内容，这里只做验证性检查

        Args:
            data: 数据字典（本页面不需要使用）
        """
        logger.info("=" * 60)
        logger.info("开始构建Part 7: 选配推荐方案章节页（页172）")
        logger.info("=" * 60)

        # 使用动态查找定位页面（从索引50开始，避免找到目录页）
        target_slides = self.find_slides_by_text("选配推荐方案", start_index=50)

        if not target_slides:
            logger.warning("未找到选配推荐方案章节页，跳过")
            return

        slide_index = target_slides[0]
        logger.info(f"✓ 定位到第{slide_index + 1}页（选配推荐方案章节页）")

        # 章节页通常使用模板静态内容，不需要动态填充
        # 如果将来需要动态更新标题或副标题，可以在这里添加代码

        logger.info("✓ Part 7 选配推荐方案章节页验证完成（保持模板静态内容）")
