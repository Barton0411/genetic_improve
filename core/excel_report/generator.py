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
    """Excel综合报告生成器 v1.1"""

    def __init__(self, project_folder: Path, service_staff: str = None):
        """
        初始化生成器

        Args:
            project_folder: 项目文件夹路径
            service_staff: 牧场服务人员（工号 姓名）
        """
        self.project_folder = Path(project_folder)
        self.analysis_folder = self.project_folder / "analysis_results"
        self.service_staff = service_staff

        # 初始化workbook
        self.wb = Workbook()
        self.wb.remove(self.wb.active)  # 删除默认sheet

        # 导入样式管理器和图表构建器
        from .formatters import StyleManager, ChartBuilder
        self.style_manager = StyleManager()
        self.chart_builder = ChartBuilder()

    def generate(self) -> tuple[bool, str]:
        """
        生成Excel综合报告（完整版）

        Returns:
            (成功标志, 文件路径或错误消息)
        """
        try:
            logger.info("=" * 60)
            logger.info("开始生成Excel综合报告 v1.1")
            logger.info("=" * 60)

            # 1. 检查数据文件
            logger.info("Step 1: 检查必需文件...")
            from .utils import FileChecker
            checker = FileChecker(self.analysis_folder)
            missing_files = checker.check_required_files()
            if missing_files:
                error_msg = f"缺少必要文件：{', '.join(missing_files)}"
                logger.error(error_msg)
                return False, error_msg

            logger.info("✓ 必需文件检查通过")

            # 检查可选文件
            optional_files = checker.check_optional_files()
            logger.info("可选文件状态:")
            for filename, exists in optional_files.items():
                status = "✓" if exists else "✗"
                logger.info(f"  {status} {filename}")

            # 2. 收集所有数据
            logger.info("\nStep 2: 收集数据...")
            data = self._collect_all_data()
            logger.info("✓ 数据收集完成")

            # 3. 生成各个Sheet
            logger.info("\nStep 3: 生成Sheet...")

            logger.info("  [1/10] 生成Sheet 1: 牧场基础信息")
            self._build_sheet1(data['farm_info'])

            logger.info("  [2/10] 生成Sheet 1A: 牧场牛群原始数据")
            self._build_sheet1a(data['farm_info'])

            logger.info("  [3/10] 生成Sheet 2: 系谱识别分析")
            self._build_sheet2(data['pedigree'])

            logger.info("  [3A/10] 生成Sheet 2明细: 全群母牛系谱识别明细")
            self._build_sheet2_detail(data['pedigree'])

            logger.info("  [4/10] 生成Sheet 3: 育种性状分析")
            self._build_sheet3(data['traits'])

            logger.info("  [5/10] 生成Sheet 4: 母牛指数分析")
            self._build_sheet4(data['cow_index'])

            logger.info("  [6/10] 生成Sheet 5: 隐性基因分析")
            self._build_sheet5(data['genes'])

            logger.info("  [7/10] 生成Sheet 6: 近交系数分析")
            self._build_sheet6(data['inbreeding'])

            logger.info("  [8/10] 生成Sheet 7: 备选公牛排名")
            self._build_sheet7(data['bull_ranking'])

            logger.info("  [9/10] 生成Sheet 7A: 备选公牛预测分析")
            self._build_sheet7a(data['bull_prediction'])

            if data.get('mating'):
                logger.info("  [10/10] 生成Sheet 8: 选配推荐结果")
                self._build_sheet8(data['mating'])
            else:
                logger.info("  [10/10] Sheet 8: 无选配数据，跳过")

            logger.info("✓ 所有Sheet生成完成")

            # 4. 保存文件
            logger.info("\nStep 4: 保存文件...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"育种分析综合报告_{timestamp}.xlsx"

            # 保存到reports文件夹
            reports_folder = self.project_folder / "reports"
            reports_folder.mkdir(parents=True, exist_ok=True)
            output_path = reports_folder / filename

            self.wb.save(output_path)
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
        收集所有需要的数据

        Returns:
            数据字典
        """
        from .data_collectors import (
            collect_farm_info,
            collect_pedigree_data,
            collect_traits_data,
            collect_cow_index_data,
            collect_bull_usage_data,
            collect_gene_data,
            collect_inbreeding_data,
            collect_bull_ranking_data,
            collect_bull_prediction_data,
            collect_mating_data
        )

        return {
            'farm_info': collect_farm_info(self.project_folder, self.service_staff),
            'pedigree': collect_pedigree_data(self.analysis_folder),
            'traits': collect_traits_data(self.analysis_folder, self.project_folder),
            'cow_index': collect_cow_index_data(self.analysis_folder, self.project_folder),
            'bull_usage': collect_bull_usage_data(self.analysis_folder),
            'genes': collect_gene_data(self.analysis_folder),
            'inbreeding': collect_inbreeding_data(self.analysis_folder),
            'bull_ranking': collect_bull_ranking_data(self.analysis_folder),
            'bull_prediction': collect_bull_prediction_data(self.analysis_folder),
            'mating': collect_mating_data(self.analysis_folder)
        }

    def _build_sheet1(self, data: dict):
        """构建Sheet 1: 牧场基础信息"""
        from .sheet_builders import Sheet1Builder
        builder = Sheet1Builder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)

    def _build_sheet1a(self, data: dict):
        """构建Sheet 1A: 牧场牛群原始数据"""
        from .sheet_builders import Sheet1ABuilder
        builder = Sheet1ABuilder(self.wb, self.style_manager, self.chart_builder)
        # 传递原始母牛数据文件路径
        builder.build({
            'raw_file_path': data.get('raw_cow_data')
        })

    def _build_sheet2(self, data: dict):
        """构建Sheet 2: 系谱识别分析"""
        from .sheet_builders import Sheet2Builder
        builder = Sheet2Builder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)

    def _build_sheet2_detail(self, data: dict):
        """构建Sheet 2明细: 全群母牛系谱识别明细"""
        from .sheet_builders import Sheet2DetailBuilder
        builder = Sheet2DetailBuilder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)

    def _build_sheet3(self, data: dict):
        """构建Sheet 3: 育种性状分析"""
        from .sheet_builders import Sheet3Builder
        builder = Sheet3Builder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)

    def _build_sheet4(self, data: dict):
        """构建Sheet 4: 母牛指数分析"""
        from .sheet_builders import Sheet4Builder
        builder = Sheet4Builder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)

    def _build_sheet5(self, data: dict):
        """构建Sheet 5: 隐性基因分析"""
        from .sheet_builders import Sheet5Builder
        builder = Sheet5Builder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)

    def _build_sheet6(self, data: dict):
        """构建Sheet 6: 近交系数分析"""
        from .sheet_builders import Sheet6Builder
        builder = Sheet6Builder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)

    def _build_sheet7(self, data: dict):
        """构建Sheet 7: 备选公牛排名"""
        from .sheet_builders import Sheet7Builder
        builder = Sheet7Builder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)

    def _build_sheet7a(self, data: dict):
        """构建Sheet 7A: 备选公牛预测分析"""
        from .sheet_builders import Sheet7ABuilder
        builder = Sheet7ABuilder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)

    def _build_sheet8(self, data: dict):
        """构建Sheet 8: 个体选配结果"""
        from .sheet_builders import Sheet8Builder
        builder = Sheet8Builder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)
