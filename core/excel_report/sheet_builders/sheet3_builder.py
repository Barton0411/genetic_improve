"""
Sheet 3构建器: 育种性状分析
协调3个子Sheet的生成
"""

from .base_builder import BaseSheetBuilder
from .sheet3_yearly_summary_builder import Sheet3YearlySummaryBuilder
from .sheet3_nm_distribution_builder import Sheet3NMDistributionBuilder
from .sheet3_tpi_distribution_builder import Sheet3TPIDistributionBuilder
from .sheet3_detail_builder import Sheet3DetailBuilder
import logging

logger = logging.getLogger(__name__)


class Sheet3Builder(BaseSheetBuilder):
    """Sheet 3: 育种性状分析（协调器）"""

    def build(self, data: dict):
        """
        构建Sheet 3的所有子Sheet

        Args:
            data: {
                'present_summary': 在群母牛年份汇总DataFrame,
                'all_summary': 全部母牛年份汇总DataFrame,
                'nm_distribution_present': 在群母牛NM$分布DataFrame,
                'nm_distribution_all': 全部母牛NM$分布DataFrame,
                'tpi_distribution_present': 在群母牛TPI分布DataFrame,
                'tpi_distribution_all': 全部母牛TPI分布DataFrame,
                'comparison_data': 对比数据字典 {'farms': [...], 'references': [...]},
                'detail_df': 育种性状明细DataFrame
            }
        """
        try:
            logger.info("开始构建Sheet 3: 育种性状分析")

            # 检查数据是否存在
            if not data:
                logger.warning("Sheet 3数据为空，跳过构建")
                return

            # 构建Sheet 3-1: 年份汇总与性状进展
            try:
                logger.info("  构建Sheet 3-1: 年份汇总与性状进展")
                sheet3_1 = Sheet3YearlySummaryBuilder(self.wb, self.style_manager, self.chart_builder)
                sheet3_1.build({
                    'present_summary': data.get('present_summary'),
                    'all_summary': data.get('all_summary'),
                    'comparison_data': data.get('comparison_data', {'farms': [], 'references': []})
                })
                logger.info("  ✓ Sheet 3-1构建完成")
            except Exception as e:
                logger.error(f"  ✗ Sheet 3-1构建失败: {e}", exc_info=True)
                # 继续构建其他sheet

            # 构建Sheet 3-2: NM$分布分析
            logger.info("  构建Sheet 3-2: NM$分布分析")
            sheet3_2 = Sheet3NMDistributionBuilder(self.wb, self.style_manager, self.chart_builder)
            sheet3_2.build({
                'distribution_present': data.get('nm_distribution_present'),
                'distribution_all': data.get('nm_distribution_all'),
                'detail_df': data.get('detail_df')  # 传递明细数据用于正态分布图
            })

            # 构建Sheet 3-3: TPI分布分析
            logger.info("  构建Sheet 3-3: TPI分布分析")
            sheet3_3 = Sheet3TPIDistributionBuilder(self.wb, self.style_manager, self.chart_builder)
            sheet3_3.build({
                'distribution_present': data.get('tpi_distribution_present'),
                'distribution_all': data.get('tpi_distribution_all'),
                'detail_df': data.get('detail_df')  # 传递明细数据用于正态分布图
            })

            # 构建Sheet 3-4: 育种性状明细
            logger.info("  构建Sheet 3-4: 育种性状明细")
            sheet3_4 = Sheet3DetailBuilder(self.wb, self.style_manager, self.chart_builder)
            sheet3_4.build({
                'detail_df': data.get('detail_df')
            })

            logger.info("✓ Sheet 3所有子Sheet构建完成")

        except Exception as e:
            logger.error(f"构建Sheet 3失败: {e}", exc_info=True)
            raise
