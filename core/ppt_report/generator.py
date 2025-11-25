"""
主PPT生成器 - 基于Excel综合报告
"""

import logging
from pathlib import Path
from typing import Optional, Tuple, Callable
from datetime import datetime

from pptx import Presentation
from pptx.util import Inches

from .utils import find_excel_report
from .data_collector import DataCollector
from .chart_creator import ChartCreator
from .config import *

logger = logging.getLogger(__name__)


class ExcelBasedPPTGenerator:
    """
    基于Excel综合报告的PPT生成器

    与现有PPTGenerator接口兼容，但数据源改为Excel综合报告
    """

    def __init__(self, project_path: Path, farm_name: str = "牧场", reporter_name: str = "用户"):
        """
        初始化PPT生成器

        Args:
            project_path: 项目路径
            farm_name: 牧场名称
            reporter_name: 汇报人姓名
        """
        self.project_path = Path(project_path)
        self.farm_name = farm_name
        self.reporter_name = reporter_name
        self.reports_folder = self.project_path / "reports"
        self.output_folder = self.project_path / "analysis_results"
        self.output_folder.mkdir(parents=True, exist_ok=True)

        # 查找Excel报告
        self.excel_report_path = None

        # 初始化组件（延迟初始化）
        self.data_collector = None
        self.chart_creator = None
        self.prs = None
        self.farm_info = {}
        self.last_output_path: Optional[Path] = None

        logger.info(f"初始化PPT生成器: {farm_name}, 汇报人: {reporter_name}")

    def check_required_files(self) -> Tuple[bool, str]:
        """
        检查必需文件是否存在

        Returns:
            (是否满足条件, 错误信息)
        """
        # 检查Excel综合报告
        self.excel_report_path = find_excel_report(self.reports_folder)

        if self.excel_report_path is None:
            return False, "未找到Excel综合报告，请先生成Excel报告（点击'生成Excel报告'按钮）"

        logger.info(f"找到Excel报告: {self.excel_report_path.name}")
        return True, ""

    def generate_ppt(self, progress_callback: Optional[Callable] = None) -> bool:
        """
        生成PPT报告（主入口）

        Args:
            progress_callback: 进度回调函数 callback(message: str, progress: int)

        Returns:
            是否成功生成
        """
        try:
            logger.info("=" * 60)
            logger.info("开始生成PPT报告 v2.0（基于Excel）")
            logger.info("=" * 60)

            # 1. 初始化组件 (0-5%)
            self._report_progress(progress_callback, "正在初始化...", 0)
            self._initialize_components()
            self._report_progress(progress_callback, "✓ 初始化完成", 5)

            # 2. 收集数据 (5-15%)
            self._report_progress(progress_callback, "正在读取Excel报告数据...", 5)
            data = self.data_collector.collect_all_data()
            self.farm_info = data.get('farm_info_dict', {}) or {}
            self._report_progress(progress_callback, "✓ 数据读取完成", 15)

            # 3. 创建PPT演示文稿 (15-20%)
            self._report_progress(progress_callback, "正在创建PPT...", 15)
            self._create_presentation()
            self._report_progress(progress_callback, "✓ PPT创建完成", 20)

            # 4. 生成各部分幻灯片 (20-90%)
            total_parts = 7
            current_progress = 20
            progress_per_part = 70 / total_parts

            # Part 1: 封面与目录 (20-30%)
            self._report_progress(progress_callback, "[1/7] 生成封面与目录...", current_progress)
            self._build_part1_cover_and_toc()
            current_progress += progress_per_part
            self._report_progress(progress_callback, "✓ Part 1 完成", int(current_progress))

            # Part 2: 牧场概况 (30-40%)
            self._report_progress(progress_callback, "[2/7] 生成牧场概况...", int(current_progress))
            self._build_part2_farm_overview(data)
            current_progress += progress_per_part
            self._report_progress(progress_callback, "✓ Part 2 完成", int(current_progress))

            # Part 3: 系谱分析 (40-50%)
            self._report_progress(progress_callback, "[3/7] 生成系谱分析...", int(current_progress))
            self._build_part3_pedigree(data)
            current_progress += progress_per_part
            self._report_progress(progress_callback, "✓ Part 3 完成", int(current_progress))

            # Part 4: 遗传评估 (50-65%)
            self._report_progress(progress_callback, "[4/7] 生成遗传评估...", int(current_progress))
            self._build_part4_genetics(data)
            current_progress += progress_per_part
            self._report_progress(progress_callback, "✓ Part 4 完成", int(current_progress))

            # Part 5: 配种记录 (65-75%)
            self._report_progress(progress_callback, "[5/7] 生成配种分析...", int(current_progress))
            self._build_part5_breeding(data)
            current_progress += progress_per_part
            self._report_progress(progress_callback, "✓ Part 5 完成", int(current_progress))

            # Part 6: 公牛使用 (75-85%)
            self._report_progress(progress_callback, "[6/7] 生成公牛分析...", int(current_progress))
            self._build_part6_bulls(data)
            current_progress += progress_per_part
            self._report_progress(progress_callback, "✓ Part 6 完成", int(current_progress))

            # Part 7: 选配推荐 (85-90%)
            self._report_progress(progress_callback, "[7/7] 生成选配推荐...", int(current_progress))
            self._build_part7_mating(data)
            current_progress += progress_per_part
            self._report_progress(progress_callback, "✓ Part 7 完成", 90)

            # 5. 保存PPT (90-100%)
            self._report_progress(progress_callback, "正在保存PPT文件...", 90)
            output_path = self._save_presentation()
            self._report_progress(progress_callback, "✓ PPT保存完成", 95)

            # 6. 清理临时文件 (95-100%)
            self._report_progress(progress_callback, "正在清理临时文件...", 95)
            self.chart_creator.cleanup()
            self._report_progress(progress_callback, "✓ 清理完成", 100)

            logger.info("=" * 60)
            logger.info(f"✅ PPT报告生成成功: {output_path}")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"生成PPT失败: {e}", exc_info=True)
            if progress_callback:
                progress_callback(f"❌ 生成失败: {e}", 0)
            return False

    def _initialize_components(self):
        """初始化各组件"""
        # 数据收集器
        self.data_collector = DataCollector(self.excel_report_path)

        # 图表生成器
        self.chart_creator = ChartCreator()

        logger.info("组件初始化完成")

    def _create_presentation(self):
        """创建PPT演示文稿"""
        # 查找模板（从程序根目录）
        program_root = Path(__file__).parent.parent.parent
        preferred_template = program_root / "牧场牧场育种分析报告-模版.pptx"
        fallback_template = program_root / "PPT模版.pptx"

        template_path = preferred_template if preferred_template.exists() else fallback_template

        if template_path.exists():
            self.prs = Presentation(str(template_path))
            logger.info(f"使用PPT模板创建: {template_path}")
        else:
            self.prs = Presentation()
            self.prs.slide_width = Inches(13.33)
            self.prs.slide_height = Inches(7.5)
            logger.warning("未找到模板，使用空白PPT")

    def _save_presentation(self) -> Path:
        """保存PPT文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        farm_name = (self.farm_info.get("farm_name") or self.farm_name or "牧场").strip()
        filename = f"{farm_name}牧场育种分析报告_{timestamp}.pptx"

        # 报告输出到 reports 目录；analysis_results 仅用于中间结果
        self.reports_folder.mkdir(parents=True, exist_ok=True)
        output_path = self.reports_folder / filename

        self.prs.save(str(output_path))
        self.last_output_path = output_path
        logger.info(f"PPT已保存: {output_path}")

        return output_path

    def _report_progress(self, callback: Optional[Callable], message: str, progress: int):
        """报告进度"""
        if callback:
            callback(message, progress)
        logger.info(f"[{progress}%] {message}")

    # ==================== 各部分构建方法（占位） ====================

    def _build_part1_cover_and_toc(self):
        """构建Part 1: 封面与目录"""
        from .slide_builders import Part1CoverBuilder

        # 使用初始化时传入的汇报人姓名
        builder = Part1CoverBuilder(
            self.prs,
            self.chart_creator,
            farm_info=self.farm_info,
            fallback_farm_name=self.farm_name,
            fallback_reporter=self.reporter_name
        )
        builder.build()

    def _build_part2_farm_overview(self, data: dict):
        """构建Part 2: 牧场概况"""
        from .slide_builders import Part2FarmOverviewBuilder

        logger.info("构建Part 2: 牧场概况")
        builder = Part2FarmOverviewBuilder(self.prs, self.chart_creator, self.farm_name)
        builder.build(data)

    def _build_part3_pedigree(self, data: dict):
        """构建Part 3: 系谱分析"""
        from .slide_builders.part3_pedigree import Part3PedigreeBuilder

        logger.info("构建Part 3: 系谱分析")
        builder = Part3PedigreeBuilder(self.prs, self.chart_creator, self.farm_name)
        builder.build(data)

    def _build_part4_genetics(self, data: dict):
        """构建Part 4: 遗传评估"""
        from .slide_builders.part4_genetics import Part4GeneticsBuilder

        logger.info("构建Part 4: 遗传评估")
        builder = Part4GeneticsBuilder(self.prs, self.chart_creator, self.farm_name)
        builder.build(data)

    def _build_part5_breeding(self, data: dict):
        """构建Part 5: 配种记录"""
        logger.info("构建Part 5: 配种记录")
        # TODO: 实现配种记录分析
        pass

    def _build_part6_bulls(self, data: dict):
        """构建Part 6: 公牛使用"""
        logger.info("构建Part 6: 公牛使用")
        # TODO: 实现公牛使用分析
        pass

    def _build_part7_mating(self, data: dict):
        """构建Part 7: 选配推荐"""
        logger.info("构建Part 7: 选配推荐")
        # TODO: 实现选配推荐
        pass
