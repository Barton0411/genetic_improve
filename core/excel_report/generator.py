"""
Excel综合报告生成器
主入口类，协调所有Sheet的生成
"""

from pathlib import Path
from openpyxl import Workbook
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ExcelReportGenerator:
    """Excel综合报告生成器 v1.2"""

    def __init__(self, project_folder: Path, service_staff: str = None, progress_callback=None):
        """
        初始化生成器

        Args:
            project_folder: 项目文件夹路径
            service_staff: 牧场服务人员（工号 姓名）
            progress_callback: 进度回调函数 callback(progress: int, message: str)
        """
        self.project_folder = Path(project_folder)
        self.analysis_folder = self.project_folder / "analysis_results"
        self.service_staff = service_staff
        self.progress_callback = progress_callback

        # 初始化workbook
        self.wb = Workbook()
        self.wb.remove(self.wb.active)  # 删除默认sheet

        # 导入样式管理器和图表构建器
        from .formatters import StyleManager, ChartBuilder
        self.style_manager = StyleManager()
        self.chart_builder = ChartBuilder()

    def _report_progress(self, progress: int, message: str):
        """报告进度"""
        if self.progress_callback:
            self.progress_callback(progress, message)

    def generate(self) -> tuple[bool, str]:
        """
        生成Excel综合报告（完整版）

        Returns:
            (成功标志, 文件路径或错误消息)
        """
        try:
            logger.info("=" * 60)
            logger.info("开始生成Excel综合报告 v1.2")
            logger.info("=" * 60)

            # 1. 检查数据文件 (0-5%)
            self._report_progress(0, "正在检查必需文件...")
            logger.info("Step 1: 检查必需文件...")
            from .utils import FileChecker
            checker = FileChecker(self.analysis_folder)
            missing_files = checker.check_required_files()
            if missing_files:
                error_msg = f"缺少必要文件：{', '.join(missing_files)}"
                logger.error(error_msg)
                return False, error_msg

            self._report_progress(5, "✓ 文件检查通过")
            logger.info("✓ 必需文件检查通过")

            # 检查可选文件
            optional_files = checker.check_optional_files()
            logger.info("可选文件状态:")
            for filename, exists in optional_files.items():
                status = "✓" if exists else "✗"
                logger.info(f"  {status} {filename}")

            # 2. 收集所有数据 (5-15%)
            self._report_progress(5, "正在收集数据...")
            logger.info("\nStep 2: 收集数据...")
            data = self._collect_all_data()
            self._report_progress(14, "✓ 数据收集完成")
            logger.info("✓ 数据收集完成")

            # 3. 生成各个Sheet (15-95%)
            self._report_progress(15, "开始生成报告...")
            logger.info("\nStep 3: 生成Sheet...")

            # Sheet 1: 牧场基础信息
            self._report_progress(16, "[1/17] 生成Sheet 1...")
            logger.info("  [1/17] 生成Sheet 1: 牧场基础信息")
            self._build_sheet1(data['farm_info'])
            self._report_progress(18, "✓ Sheet 1 完成")

            # Sheet 2: 牧场牛群原始数据
            self._report_progress(18, "[2/17] 生成Sheet 2...")
            logger.info("  [2/17] 生成Sheet 2: 牧场牛群原始数据")
            self._build_sheet1a(data['farm_info'])
            self._report_progress(25, "✓ Sheet 2 完成")

            # Sheet 3: 系谱识别分析
            self._report_progress(26, "[3/17] 生成Sheet 3...")
            logger.info("  [3/17] 生成Sheet 3: 系谱识别分析")
            self._build_sheet2(data['pedigree'])
            self._report_progress(30, "✓ Sheet 3 完成")

            # Sheet 4: 全群母牛系谱识别明细
            self._report_progress(31, "[4/17] 生成Sheet 4...")
            logger.info("  [4/17] 生成Sheet 4: 全群母牛系谱识别明细")
            self._build_sheet2_detail(data['pedigree'])
            self._report_progress(36, "✓ Sheet 4 完成")

            # Sheets 5-8: 育种性状分析（4个子表）
            self._report_progress(37, "[5-8/17] 生成Sheet 5-8...")
            logger.info("  [5-8/17] 生成Sheet 5-8: 育种性状分析")
            self._build_sheet3(data['traits'])
            self._report_progress(43, "✓ Sheet 5-8 完成")

            # Sheets 9-10: 母牛指数分析（2个子表）
            self._report_progress(44, "[9-10/17] 生成Sheet 9-10...")
            logger.info("  [9-10/17] 生成Sheet 9-10: 母牛指数分析")
            self._build_sheet4(data['cow_index'])
            self._report_progress(50, "✓ Sheet 9-10 完成")

            # Sheet 11: 配种记录-隐性基因分析
            self._report_progress(51, "[11/17] 生成Sheet 11...")
            logger.info("  [11/17] 生成Sheet 11: 配种记录-隐性基因分析")
            self._build_sheet5(data.get('breeding_genes', {}))
            self._report_progress(55, "✓ Sheet 11 完成")

            # Sheet 12: 配种记录-近交系数分析
            self._report_progress(56, "[12/17] 生成Sheet 12...")
            logger.info("  [12/17] 生成Sheet 12: 配种记录-近交系数分析")
            self._build_sheet6(data.get('breeding_inbreeding', {}))
            self._report_progress(60, "✓ Sheet 12 完成")

            # Sheet 13: 配种记录明细
            self._report_progress(61, "[13/17] 生成Sheet 13...")
            logger.info("  [13/17] 生成Sheet 13: 配种记录明细")
            self._build_sheet7(data.get('breeding_details', {}))
            self._report_progress(65, "✓ Sheet 13 完成")

            # Sheet 14: 已用公牛性状汇总分析
            self._report_progress(66, "[14/17] 生成Sheet 14...")
            logger.info("  [14/17] 生成Sheet 14: 已用公牛性状汇总分析")
            self._build_sheet8(data.get('used_bulls_summary', {}))
            self._report_progress(70, "✓ Sheet 14 完成")

            # Sheet 15: 已用公牛性状明细
            self._report_progress(71, "[15/17] 生成Sheet 15...")
            logger.info("  [15/17] 生成Sheet 15: 已用公牛性状明细")
            self._build_sheet9(data.get('used_bulls_detail', {}))
            self._report_progress(75, "✓ Sheet 15 完成")

            # Sheet 16: 备选公牛排名
            self._report_progress(76, "[16/17] 生成Sheet 16...")
            logger.info("  [16/17] 生成Sheet 16: 备选公牛排名")
            self._build_sheet10(data.get('bull_ranking', {}))
            self._report_progress(80, "✓ Sheet 16 完成")

            # Sheet 17: 选配推荐结果
            if data.get('mating'):
                self._report_progress(81, "[17/17] 生成Sheet 17...")
                logger.info("  [17/17] 生成Sheet 17: 选配推荐结果")
                self._build_sheet11(data['mating'])
                self._report_progress(85, "✓ Sheet 17 完成")
            else:
                self._report_progress(81, "[17/17] 跳过Sheet 17...")
                logger.info("  [17/17] Sheet 17: 无选配数据，跳过")
                self._report_progress(85, "✓ 跳过Sheet 17")

            self._report_progress(86, "✓ 所有Sheet生成完成")
            logger.info("✓ 所有Sheet生成完成")

            # 4. 保存文件 (86-100%)
            self._report_progress(87, "正在准备保存文件...")
            logger.info("\nStep 4: 保存文件...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"育种分析综合报告_{timestamp}.xlsx"

            # 保存到reports文件夹
            reports_folder = self.project_folder / "reports"
            reports_folder.mkdir(parents=True, exist_ok=True)
            output_path = reports_folder / filename

            self._report_progress(90, "正在写入Excel文件...")
            self.wb.save(output_path)
            self._report_progress(98, "正在完成...")
            self._report_progress(100, "✓ 报告生成完成!")
            logger.info(f"✓ Excel报告已保存: {output_path}")

            logger.info("=" * 60)
            logger.info("报告生成成功!")
            logger.info("=" * 60)

            return True, str(output_path)

        except Exception as e:
            logger.error(f"✗ 生成Excel报告失败: {e}", exc_info=True)
            return False, str(e)

    def _collect_all_data(self) -> dict:
        """
        收集所有需要的数据 (v1.2)

        Returns:
            数据字典
        """
        from .data_collectors import (
            collect_farm_info,
            collect_pedigree_data,
            collect_traits_data,
            collect_cow_index_data,
            collect_bull_ranking_data,
            collect_mating_data
        )

        # v1.2数据收集器
        from .data_collectors import (
            collect_breeding_genes_data,
            collect_breeding_inbreeding_data,
            collect_breeding_detail_data
        )

        # Sheet 5: 配种记录-隐性基因分析（已实现）
        self._report_progress(6, "收集配种基因数据...")
        breeding_genes = collect_breeding_genes_data(self.analysis_folder)

        # Sheet 6: 配种记录-近交系数分析（已实现）
        self._report_progress(7, "收集近交系数数据...")
        breeding_inbreeding = collect_breeding_inbreeding_data(self.analysis_folder)

        # Sheet 7: 配种记录明细（已实现）
        self._report_progress(8, "收集配种明细数据...")
        breeding_details = collect_breeding_detail_data(self.analysis_folder)

        # Sheet 8: 已用公牛性状汇总分析（v1.2.2新版 - 动态性状+折线图）
        self._report_progress(9, "收集已用公牛汇总...")
        from .data_collectors import collect_used_bulls_summary_data
        used_bulls_summary = collect_used_bulls_summary_data(self.analysis_folder)

        # Sheet 9: 已用公牛性状明细（v1.2.2新版 - 按年份展示公牛明细）
        self._report_progress(10, "收集已用公牛明细...")
        from .data_collectors import collect_used_bulls_detail_data
        used_bulls_detail = collect_used_bulls_detail_data(self.analysis_folder)

        # Sheets 1-4数据收集
        self._report_progress(11, "收集牧场基础信息...")
        farm_info = collect_farm_info(self.project_folder, self.service_staff)

        self._report_progress(12, "收集系谱识别数据...")
        pedigree = collect_pedigree_data(self.analysis_folder)

        self._report_progress(12, "收集育种性状数据...")
        traits = collect_traits_data(self.analysis_folder, self.project_folder)

        self._report_progress(13, "收集母牛指数数据...")
        cow_index = collect_cow_index_data(self.analysis_folder, self.project_folder)

        # Sheets 10-11数据收集
        self._report_progress(13, "收集备选公牛数据...")
        bull_ranking = collect_bull_ranking_data(self.analysis_folder)

        self._report_progress(14, "收集选配推荐数据...")
        mating = collect_mating_data(self.analysis_folder)

        return {
            # Sheets 1-4: 牧场和牛群分析（已完成）
            'farm_info': farm_info,
            'pedigree': pedigree,
            'traits': traits,
            'cow_index': cow_index,

            # Sheets 5-7: 配种记录分析（v1.2新增）
            'breeding_genes': breeding_genes,
            'breeding_inbreeding': breeding_inbreeding,
            'breeding_details': breeding_details,

            # Sheets 8-9: 已用公牛分析（v1.2新增）
            'used_bulls_summary': used_bulls_summary,
            'used_bulls_detail': used_bulls_detail,

            # Sheets 10-11: 备选公牛和选配结果
            'bull_ranking': bull_ranking,
            'mating': mating
        }

    def _build_sheet1(self, data: dict):
        """构建Sheet 1: 牧场基础信息"""
        from .sheet_builders import Sheet1Builder
        builder = Sheet1Builder(self.wb, self.style_manager, self.chart_builder, self.progress_callback)
        builder.build(data)

    def _build_sheet1a(self, data: dict):
        """构建Sheet 1A: 牧场牛群原始数据"""
        from .sheet_builders import Sheet1ABuilder
        builder = Sheet1ABuilder(self.wb, self.style_manager, self.chart_builder, self.progress_callback)
        # 传递原始母牛数据文件路径
        builder.build({
            'raw_file_path': data.get('raw_cow_data')
        })

    def _build_sheet2(self, data: dict):
        """构建Sheet 2: 系谱识别分析"""
        from .sheet_builders import Sheet2Builder
        builder = Sheet2Builder(self.wb, self.style_manager, self.chart_builder, self.progress_callback)
        builder.build(data)

    def _build_sheet2_detail(self, data: dict):
        """构建Sheet 2明细: 全群母牛系谱识别明细"""
        from .sheet_builders import Sheet2DetailBuilder
        builder = Sheet2DetailBuilder(self.wb, self.style_manager, self.chart_builder, self.progress_callback)
        builder.build(data)

    def _build_sheet3(self, data: dict):
        """构建Sheet 3: 育种性状分析"""
        from .sheet_builders import Sheet3Builder
        builder = Sheet3Builder(self.wb, self.style_manager, self.chart_builder, self.progress_callback)
        builder.build(data)

    def _build_sheet4(self, data: dict):
        """构建Sheet 4: 母牛指数分析"""
        from .sheet_builders import Sheet4Builder
        builder = Sheet4Builder(self.wb, self.style_manager, self.chart_builder, self.progress_callback)
        builder.build(data)

    def _build_sheet5(self, data: dict):
        """构建Sheet 5: 配种记录-隐性基因分析"""
        from .sheet_builders import Sheet5Builder
        builder = Sheet5Builder(self.wb, self.style_manager, self.chart_builder, self.progress_callback)
        builder.build(data)

    def _build_sheet6(self, data: dict):
        """构建Sheet 6: 配种记录-近交系数分析"""
        from .sheet_builders import Sheet6Builder
        builder = Sheet6Builder(self.wb, self.style_manager, self.chart_builder, self.progress_callback)
        builder.build(data)

    def _build_sheet7(self, data: dict):
        """构建Sheet 7: 配种记录-隐性基因/近交系数明细"""
        from .sheet_builders import Sheet7Builder
        builder = Sheet7Builder(self.wb, self.style_manager, self.chart_builder, self.progress_callback)
        builder.build(data)

    def _build_sheet8(self, data: dict):
        """构建Sheet 8: 已用公牛性状汇总分析"""
        from .sheet_builders import Sheet8Builder
        builder = Sheet8Builder(self.wb, self.style_manager, self.chart_builder, self.progress_callback)
        builder.build(data)

    def _build_sheet9(self, data: dict):
        """构建Sheet 9: 已用公牛性状明细"""
        from .sheet_builders import Sheet9Builder
        builder = Sheet9Builder(self.wb, self.style_manager, self.chart_builder, self.progress_callback)
        builder.build(data)

    def _build_sheet10(self, data: dict):
        """构建Sheet 10: 备选公牛排名"""
        from .sheet_builders import Sheet10Builder
        builder = Sheet10Builder(self.wb, self.style_manager, self.chart_builder, self.progress_callback)
        builder.build(data)

    def _build_sheet11(self, data: dict):
        """构建Sheet 11: 选配推荐结果"""
        from .sheet_builders import Sheet11Builder
        builder = Sheet11Builder(self.wb, self.style_manager, self.chart_builder, self.progress_callback)
        builder.build(data)
