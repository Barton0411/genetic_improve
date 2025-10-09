"""
Sheet 4构建器: 母牛指数分析
协调2个子Sheet的生成
"""

from .base_builder import BaseSheetBuilder
from .sheet4_index_distribution_builder import Sheet4IndexDistributionBuilder
from .sheet4_detail_builder import Sheet4DetailBuilder
import logging

logger = logging.getLogger(__name__)


class Sheet4Builder(BaseSheetBuilder):
    """Sheet 4: 母牛指数分析（协调器）"""

    def build(self, data: dict):
        """
        构建Sheet 4的所有子Sheet

        Args:
            data: {
                'distribution_present': 在群母牛指数分布DataFrame,
                'distribution_all': 全部母牛指数分布DataFrame,
                'detail_df': 母牛指数明细DataFrame
            }
        """
        try:
            logger.info("开始构建Sheet 4: 母牛指数分析")

            # 检查数据是否存在
            if not data:
                logger.warning("Sheet 4数据为空，跳过构建")
                return

            # 构建Sheet 4-1: 母牛指数分布分析
            logger.info("  构建Sheet 4-1: 母牛指数分布分析")
            sheet4_1 = Sheet4IndexDistributionBuilder(self.wb, self.style_manager, self.chart_builder)
            sheet4_1.build({
                'distribution_present': data.get('distribution_present'),
                'distribution_all': data.get('distribution_all'),
                'detail_df': data.get('detail_df')
            })

            # 构建Sheet 4-2: 母牛指数排名明细
            logger.info("  构建Sheet 4-2: 母牛指数排名明细")
            sheet4_2 = Sheet4DetailBuilder(self.wb, self.style_manager, self.chart_builder)
            sheet4_2.build({
                'detail_df': data.get('detail_df')
            })

            logger.info("✓ Sheet 4所有子Sheet构建完成")

        except Exception as e:
            logger.error(f"构建Sheet 4失败: {e}", exc_info=True)
            raise
