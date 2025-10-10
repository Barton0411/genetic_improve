"""
对比牧场数据收集器
收集用户勾选的对比牧场和外部参考数据
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional
from core.benchmark import BenchmarkManager

logger = logging.getLogger(__name__)


class BenchmarkDataCollector:
    """对比牧场数据收集器"""

    def __init__(self, project_path: Path):
        """
        初始化收集器

        Args:
            project_path: 项目路径
        """
        self.project_path = project_path
        self.benchmark_manager = BenchmarkManager()

    def collect(self) -> Dict:
        """
        收集对比数据

        Returns:
            {
                'farms': [  # 对比牧场列表（用于表格和折线图）
                    {
                        'id': 'farm_xxx',
                        'name': '测试1',
                        'color': '#ff6b6b',
                        'latest_year': 2024,
                        'present_data': {...},  # 在群母牛总计数据
                        'all_data': {...}  # 全部母牛总计数据
                    }
                ],
                'references': [  # 外部参考数据列表（仅用于折线图）
                    {
                        'id': 'ref_xxx',
                        'name': '基因组检测',
                        'color': '#4ecdc4',
                        'year_data': {  # 年份数据
                            '2021年': {'平均NM$': 850, ...},
                            '2022年': {...},
                        },
                        'traits': ['平均NM$', '平均TPI', ...]
                    }
                ]
            }
        """
        try:
            logger.info("开始收集对比数据...")

            # 获取用户勾选的对比数据
            selected_comparisons = self.benchmark_manager.get_selected_comparisons()

            if not selected_comparisons:
                logger.info("没有勾选任何对比数据")
                return {'farms': [], 'references': []}

            farms = []
            references = []

            # 处理每个勾选的对比数据
            for comp in selected_comparisons:
                # 对比牧场
                if 'farm_id' in comp:
                    farm_data = self._collect_farm_data(comp)
                    if farm_data:
                        farms.append(farm_data)

                # 外部参考数据
                elif 'reference_id' in comp:
                    ref_data = self._collect_reference_data(comp)
                    if ref_data:
                        references.append(ref_data)

            logger.info(f"✓ 收集完成: {len(farms)}个对比牧场, {len(references)}个外部参考数据")

            return {
                'farms': farms,
                'references': references
            }

        except Exception as e:
            logger.error(f"收集对比数据失败: {e}", exc_info=True)
            return {'farms': [], 'references': []}

    def _collect_farm_data(self, comparison: Dict) -> Optional[Dict]:
        """
        收集对比牧场数据

        Args:
            comparison: {'farm_id': 'xxx', 'color': '#xxx'}

        Returns:
            对比牧场数据字典
        """
        try:
            farm_id = comparison['farm_id']
            color = comparison.get('color', '#95a5a6')

            # 从BenchmarkManager获取牧场数据
            farm = self.benchmark_manager.get_farm_by_id(farm_id)
            if not farm:
                logger.warning(f"未找到对比牧场: {farm_id}")
                return None

            # 提取数据摘要
            data_summary = farm.get('data_summary', {})
            present_summary = data_summary.get('present_summary', {})
            all_summary = data_summary.get('all_summary', {})

            # 提取总计行数据（用于表格）
            present_data = self._extract_total_data(present_summary)
            all_data = self._extract_total_data(all_summary)

            return {
                'id': farm_id,
                'name': farm['name'],
                'color': color,
                'latest_year': present_summary.get('latest_year'),
                'present_cow_count': present_summary.get('cow_count', 0),
                'all_cow_count': all_summary.get('cow_count', 0),
                'present_data': present_data,  # 总计数据（用于表格）
                'all_data': all_data,  # 总计数据（用于表格）
                # 年份数据（用于折线图）
                'year_data': present_summary.get('data', {}),  # 年份数据字典
                'year_rows': present_summary.get('year_rows', []),  # 年份列表
                'traits': present_summary.get('traits', [])  # 性状列表
            }

        except Exception as e:
            logger.error(f"收集对比牧场数据失败: {e}", exc_info=True)
            return None

    def _collect_reference_data(self, comparison: Dict) -> Optional[Dict]:
        """
        收集外部参考数据

        Args:
            comparison: {'reference_id': 'xxx', 'color': '#xxx'}

        Returns:
            外部参考数据字典
        """
        try:
            ref_id = comparison['reference_id']
            color = comparison.get('color', '#e67e22')

            # 从BenchmarkManager获取外部参考数据
            reference = self.benchmark_manager.get_reference_by_id(ref_id)
            if not reference:
                logger.warning(f"未找到外部参考数据: {ref_id}")
                return None

            # 提取数据摘要
            data_summary = reference.get('data_summary', {})
            present_summary = data_summary.get('present_summary', {})

            return {
                'id': ref_id,
                'name': reference['name'],
                'color': color,
                'year_data': present_summary.get('data', {}),
                'traits': present_summary.get('traits', []),
                'year_rows': present_summary.get('year_rows', [])
            }

        except Exception as e:
            logger.error(f"收集外部参考数据失败: {e}", exc_info=True)
            return None

    def _extract_total_data(self, summary: Dict) -> Dict:
        """
        从汇总数据中提取总计行数据

        Args:
            summary: {
                'year_rows': ['2021年', '2022年', '总计'],
                'traits': ['平均NM$', '平均TPI', ...],
                'data': {
                    '2021年': {'平均NM$': 850, ...},
                    '总计': {'平均NM$': 900, ...}
                }
            }

        Returns:
            总计行数据: {'平均NM$': 900, '平均TPI': 2600, ...}
        """
        data = summary.get('data', {})

        # 查找总计行
        for year_key in data.keys():
            if '总计' in str(year_key):
                return data[year_key]

        # 如果没有总计行，返回空字典
        logger.warning("未找到总计行数据")
        return {}
