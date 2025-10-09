"""
文件检查器
检查生成报告所需的数据文件是否存在
"""

from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class FileChecker:
    """文件检查器"""

    # 必需文件列表
    REQUIRED_FILES = [
        "系谱识别分析结果.xlsx",
        "关键育种性状分析结果.xlsx",
    ]

    # 可选文件列表
    OPTIONAL_FILES = [
        "processed_index_cow_index_scores.xlsx",
        "已配公牛育种性状分析结果.xlsx",
        "已配公牛_近交系数及隐性基因分析结果.xlsx",
        "备选公牛排名_按NM$.xlsx",
        "备选公牛排名_按TPI.xlsx",
        "备选公牛_近交系数及隐性基因分析结果.xlsx",
        "个体选配报告.xlsx",
    ]

    def __init__(self, analysis_folder: Path):
        """
        初始化文件检查器

        Args:
            analysis_folder: 分析结果文件夹路径
        """
        self.analysis_folder = Path(analysis_folder)

    def check_required_files(self) -> list:
        """
        检查必需文件是否存在

        Returns:
            缺失文件列表
        """
        missing_files = []

        for filename in self.REQUIRED_FILES:
            file_path = self.analysis_folder / filename
            if not file_path.exists():
                logger.warning(f"缺少必需文件: {filename}")
                missing_files.append(filename)

        return missing_files

    def check_optional_files(self) -> dict:
        """
        检查可选文件是否存在

        Returns:
            {'filename': bool} 字典，表示每个文件是否存在
        """
        result = {}

        for filename in self.OPTIONAL_FILES:
            file_path = self.analysis_folder / filename
            result[filename] = file_path.exists()
            if not result[filename]:
                logger.info(f"可选文件不存在: {filename}")

        return result

    def get_file_path(self, filename: str) -> Path:
        """
        获取文件完整路径

        Args:
            filename: 文件名

        Returns:
            Path对象
        """
        return self.analysis_folder / filename
