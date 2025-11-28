"""
Part 7: 项目总结建议构建器

- 页174：章节页（"07 项目总结建议"）- 保持模板静态内容
- 页175：总结内容页 - 填充总结和建议（待完善）
"""

import logging
from typing import Dict, List

from ..base_builder import BaseSlideBuilder

logger = logging.getLogger(__name__)


class Part7SummaryBuilder(BaseSlideBuilder):
    """Part 7: 项目总结建议构建器"""

    def __init__(self, prs, chart_creator, farm_name: str):
        super().__init__(prs, chart_creator)
        self.farm_name = farm_name

    def build(self, data: Dict):
        """
        构建 Part 7: 项目总结建议

        - 页174：章节页，保持模板静态内容
        - 页175：总结内容页，填充总结和建议

        Args:
            data: 包含所有部分数据的字典
        """
        logger.info("=" * 60)
        logger.info("开始构建Part 7: 项目总结建议")
        logger.info("=" * 60)

        # 1. 定位章节页（页174）- 只验证，不修改
        section_slides = self.find_slides_by_text("项目总结建议", start_index=50)
        if section_slides:
            section_index = section_slides[0]
            logger.info(f"✓ 定位到第{section_index + 1}页（项目总结建议章节页）- 保持模板静态内容")
        else:
            logger.warning("未找到项目总结建议章节页")
            return

        # 2. 定位总结内容页（页175）- 章节页的下一页
        content_index = section_index + 1
        if content_index >= len(self.prs.slides):
            logger.warning("未找到总结内容页（超出页面范围）")
            return

        content_slide = self.prs.slides[content_index]
        logger.info(f"✓ 定位到第{content_index + 1}页（总结内容页）")

        # 3. 填充总结内容（暂时跳过，等待后续完善）
        # TODO: 根据需求填充总结内容
        logger.info("✓ 总结内容页暂时保持模板占位内容，待后续完善")

        logger.info("✓ Part 7 项目总结建议构建完成")

    # ------------------------------------------------------------------ #
    # 核心生成方法
    # ------------------------------------------------------------------ #

    def _generate_summary_points(self, data: Dict) -> List[str]:
        """
        生成总结要点（基于各个Part的数据）

        Returns:
            总结要点列表（3-5条）
        """
        points = []

        # Part 2: 牧场概况
        farm_info = data.get('farm_info_dict', {})
        if farm_info:
            total_count = farm_info.get('total_count', 0)
            lactating_count = farm_info.get('lactating_count', 0)
            heifer_count = farm_info.get('heifer_count', 0)
            points.append(
                f"牧场在群牛总数{total_count}头，其中成母牛{lactating_count}头，"
                f"后备牛{heifer_count}头，牛群结构合理。"
            )

        # Part 3: 系谱识别（如果有数据）
        pedigree_data = data.get('pedigree_analysis')
        if pedigree_data is not None and not pedigree_data.empty:
            # 可以添加系谱识别率的总结
            points.append("牧场系谱档案建设良好，为精准选配提供了数据基础。")

        # Part 4: 遗传评估（如果有数据）
        genetics_data = data.get('genetic_progress')
        if genetics_data is not None and not genetics_data.empty:
            points.append("牛群关键性状年均进展稳定，育种方向明确。")

        # Part 5: 配种记录（如果有数据）
        breeding_data = data.get('breeding_records')
        if breeding_data is not None and not breeding_data.empty:
            points.append("配种记录完整，公牛使用规范，为遗传改良奠定基础。")

        # Part 7: 选配推荐
        mating_summary = data.get('mating_summary')
        if mating_summary:
            basic_stats = mating_summary.get('basic_stats', {})
            total_cows = basic_stats.get('total_cows', 0)
            has_sexed = basic_stats.get('has_sexed', 0)
            has_regular = basic_stats.get('has_regular', 0)
            if total_cows > 0:
                coverage_rate = ((has_sexed + has_regular) / total_cows) * 100
                points.append(
                    f"本期为{total_cows}头应配母牛提供选配推荐，"
                    f"推荐覆盖率{coverage_rate:.1f}%，智能选配系统运行良好。"
                )

        # 如果points少于3条，添加通用总结
        if len(points) < 3:
            points.append(f"{self.farm_name}育种工作稳步推进，数据质量不断提升。")

        return points[:5]  # 最多返回5条

    def _generate_suggestions(self, data: Dict) -> List[str]:
        """
        生成改进建议（基于各个Part的数据分析）

        Returns:
            改进建议列表（3-5条）
        """
        suggestions = []

        # 基于系谱识别率的建议
        pedigree_data = data.get('pedigree_analysis')
        if pedigree_data is not None and not pedigree_data.empty:
            # 这里可以添加基于系谱识别率的建议
            # 例如：如果识别率低于80%，建议补充系谱信息
            suggestions.append("建议持续完善系谱档案，提高系谱识别率，为精准选配提供更好支持。")

        # 基于选配推荐的建议
        mating_summary = data.get('mating_summary')
        if mating_summary:
            basic_stats = mating_summary.get('basic_stats', {})
            no_recommendation = basic_stats.get('no_recommendation', 0)
            if no_recommendation > 0:
                suggestions.append(
                    f"建议对{no_recommendation}头暂无推荐方案的母牛进行人工审核，"
                    "补充完善相关数据后重新生成推荐。"
                )

        # 通用建议
        suggestions.append("建议定期更新备选公牛库，引入优秀种公牛，提升遗传进展速度。")
        suggestions.append("建议加强性控冻精使用，优化性别比例，提高母犊生产效率。")
        suggestions.append("建议建立选配效果跟踪机制，定期评估选配方案的实施效果。")

        return suggestions[:5]  # 最多返回5条

    # ------------------------------------------------------------------ #
    # 页面更新方法
    # ------------------------------------------------------------------ #

    def _update_summary_section(self, slide, summary_points: List[str]):
        """
        更新总结部分

        查找包含"总结"关键字的文本框，填充总结要点
        """
        summary_box = None

        # 查找总结文本框
        for shape in slide.shapes:
            if shape.has_text_frame:
                # 检查形状名称或文本内容
                if "总结" in shape.name or ("总结" in shape.text and len(shape.text) < 50):
                    summary_box = shape
                    break

        if not summary_box:
            logger.warning("未找到总结文本框，跳过总结部分更新")
            return

        # 生成总结文本
        summary_text = "【项目总结】\n\n" + "\n\n".join([f"{i+1}. {point}" for i, point in enumerate(summary_points)])

        # 更新文本
        self._set_shape_text(summary_box, summary_text)
        logger.info(f"✓ 总结部分更新完成（{len(summary_points)}条要点）")

    def _update_suggestions_section(self, slide, suggestions: List[str]):
        """
        更新建议部分

        查找包含"建议"关键字的文本框，填充改进建议
        """
        suggestions_box = None

        # 查找建议文本框
        for shape in slide.shapes:
            if shape.has_text_frame:
                # 检查形状名称或文本内容
                if "建议" in shape.name or ("建议" in shape.text and len(shape.text) < 50):
                    suggestions_box = shape
                    break

        if not suggestions_box:
            logger.warning("未找到建议文本框，跳过建议部分更新")
            return

        # 生成建议文本
        suggestions_text = "【改进建议】\n\n" + "\n\n".join([f"{i+1}. {sug}" for i, sug in enumerate(suggestions)])

        # 更新文本
        self._set_shape_text(suggestions_box, suggestions_text)
        logger.info(f"✓ 建议部分更新完成（{len(suggestions)}条建议）")

    # ------------------------------------------------------------------ #
    # 辅助方法
    # ------------------------------------------------------------------ #

    @staticmethod
    def _set_shape_text(shape, text: str):
        """设置形状文本，保持模板样式"""
        if not shape.has_text_frame:
            return
        tf = shape.text_frame
        tf.clear()  # 清空所有内容

        # 添加新文本
        para = tf.add_paragraph()
        run = para.add_run()
        run.text = text
