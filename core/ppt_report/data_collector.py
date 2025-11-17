"""
数据收集器 - 从Excel综合报告中提取PPT所需的数据
"""

import logging
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from .utils import find_excel_report, safe_read_excel
from .config import EXCEL_SHEET_MAPPING

logger = logging.getLogger(__name__)


def _to_int(value):
    try:
        if pd.isna(value):
            return None
        return int(float(str(value).strip().replace(',', '')))
    except Exception:
        return None


def _to_float(value):
    try:
        if pd.isna(value):
            return None
        return float(str(value).strip().replace('%', '').replace('天', ''))
    except Exception:
        return None


class DataCollector:
    """从Excel报告收集PPT所需的数据"""

    def __init__(self, excel_report_path: Path):
        """
        初始化数据收集器

        Args:
            excel_report_path: Excel综合报告路径
        """
        self.excel_path = excel_report_path
        self.data_cache = {}

    def collect_all_data(self) -> Dict:
        """
        收集所有需要的数据

        Returns:
            数据字典（混合DataFrame和dict）
        """
        logger.info("开始收集PPT所需数据...")

        total_sheets = len(EXCEL_SHEET_MAPPING)
        for key, meta in EXCEL_SHEET_MAPPING.items():
            sheet_name = meta['sheet_name']
            header = meta.get('header', 0)
            df = self._read_sheet(sheet_name, header=header)
            if df is not None:
                self.data_cache[key] = df
                logger.debug(
                    "✓ 加载Sheet成功: %s (key=%s, 行数=%s, dynamic=%s, detail_only=%s)",
                    sheet_name,
                    key,
                    len(df),
                    meta.get('dynamic', False),
                    meta.get('detail_only', False),
                )
            else:
                level = logging.ERROR if meta.get('required', False) else logging.WARNING
                logger.log(level, "✗ Sheet '%s' 读取失败 (key=%s)", sheet_name, key)

        logger.info("数据收集完成: 成功读取 %s/%s 个Sheet", len(self.data_cache), total_sheets)

        # 特殊处理：farm_info需要解析成dict（因为Sheet1是横向布局）
        if 'farm_info' in self.data_cache:
            logger.info("正在解析farm_info横向布局...")
            farm_info_dict = self.get_farm_info()
            self.data_cache['farm_info_dict'] = farm_info_dict
            logger.info(f"✓ farm_info解析完成: {farm_info_dict}")

        return self.data_cache

    def _read_sheet(self, sheet_name: str, header=0) -> Optional[pd.DataFrame]:
        """
        读取指定Sheet

        Args:
            sheet_name: Sheet名称

        Returns:
            DataFrame或None
        """
        try:
            df = pd.read_excel(self.excel_path, sheet_name=sheet_name, header=header)
            header_text = "无header" if header is None else "含表头"
            logger.info("✓ 读取Sheet: %s (%s行, %s)", sheet_name, len(df), header_text)
            return df
        except Exception as e:
            logger.error(f"✗ 读取Sheet失败 '{sheet_name}': {e}")
            return None

    def get_data(self, key: str) -> Optional[pd.DataFrame]:
        """
        获取缓存的数据

        Args:
            key: 数据键名

        Returns:
            DataFrame或None
        """
        return self.data_cache.get(key)

    def get_farm_info(self) -> Dict[str, any]:
        """
        获取牧场基本信息（从Excel Sheet1横向布局中提取）

        Sheet1布局：
        - A-B列：基本信息（牧场名称、报告生成时间、服务人员）
        - D-F列：成母牛/后备牛分布
        - H-J列：不同胎次分布

        Returns:
            牧场信息字典
        """
        df = self.get_data('farm_info')
        if df is None or df.empty:
            logger.warning("farm_info数据为空")
            return {}

        info = {
            'farm_name': '',
            'report_time': '',
            'report_date': None,
            'service_staff': '',
            'total_count': 0,
            'lactating_count': 0,
            'heifer_count': 0,
            'avg_lactation': 0.0,
            'avg_dim': 0,
            'upload_stats': [],
            'cow_type_distribution': [],
            'parity_distribution': []
        }

        try:
            logger.info(f"开始解析farm_info，DataFrame形状: {df.shape}")
            logger.info(f"列名: {df.columns.tolist()}")

            # Excel Sheet1是横向布局，直接读取时列名可能是Unnamed
            # 遍历所有行和列查找数据
            for row_idx in range(len(df)):
                for col_idx in range(len(df.columns)):
                    cell_value = df.iloc[row_idx, col_idx]

                    if pd.isna(cell_value):
                        continue

                    cell_str = str(cell_value).strip()

                    # 基本信息部分（A-B列，第0-1列）
                    if '牧场名称' in cell_str and col_idx + 1 < len(df.columns):
                        info['farm_name'] = str(df.iloc[row_idx, col_idx + 1]).strip()
                    elif ('报告生成时间' in cell_str or '报告时间' in cell_str) and col_idx + 1 < len(df.columns):
                        info['report_time'] = str(df.iloc[row_idx, col_idx + 1]).strip()
                    elif '服务人员' in cell_str and col_idx + 1 < len(df.columns):
                        info['service_staff'] = str(df.iloc[row_idx, col_idx + 1]).strip()

                    # 成母牛数量
                    elif '成母牛' in cell_str and '胎次>0' in cell_str:
                        # 找到这一行的数量列（下一列或下两列）
                        for offset in [1, 2]:
                            if col_idx + offset < len(df.columns):
                                val = df.iloc[row_idx, col_idx + offset]
                                if pd.notnull(val) and str(val).replace('.', '').isdigit():
                                    info['lactating_count'] = int(float(val))
                                    break

                    # 后备牛数量
                    elif '后备牛' in cell_str and '胎次=0' in cell_str:
                        for offset in [1, 2]:
                            if col_idx + offset < len(df.columns):
                                val = df.iloc[row_idx, col_idx + offset]
                                if pd.notnull(val) and str(val).replace('.', '').isdigit():
                                    info['heifer_count'] = int(float(val))
                                    break

                    # 合计（总头数）
                    elif cell_str == '合计':
                        for offset in [1, 2]:
                            if col_idx + offset < len(df.columns):
                                val = df.iloc[row_idx, col_idx + offset]
                                if pd.notnull(val) and str(val).replace('.', '').isdigit():
                                    info['total_count'] = int(float(val))
                                    break

                    # 平均胎次
                    elif '平均胎次' in cell_str and col_idx + 1 < len(df.columns):
                        val = df.iloc[row_idx, col_idx + 1]
                        if pd.notnull(val):
                            try:
                                info['avg_lactation'] = float(val)
                            except:
                                pass

                    # 平均泌乳天数
                    elif '平均泌乳天数' in cell_str and col_idx + 1 < len(df.columns):
                        val = df.iloc[row_idx, col_idx + 1]
                        if pd.notnull(val):
                            try:
                                # 可能是类似 "123.0天" 的格式
                                raw = str(val).replace('天', '').strip()
                                info['avg_dim'] = int(float(raw))
                            except Exception:
                                pass

            # 尝试解析报告日期
            if info['report_time']:
                try:
                    info['report_date'] = pd.to_datetime(info['report_time'])
                except Exception:
                    info['report_date'] = None

            logger.info(f"提取牧场信息成功: 牧场={info['farm_name']}, "
                       f"总数={info['total_count']}, 成母牛={info['lactating_count']}, "
                       f"后备牛={info['heifer_count']}")

            info['upload_stats'] = self._parse_upload_stats(df)
            info['cow_type_distribution'] = self._parse_cow_type_distribution(df)
            info['parity_distribution'] = self._parse_parity_distribution(df)

        except Exception as e:
            logger.error(f"提取牧场信息失败: {e}", exc_info=True)

        return info

    def get_pedigree_stats(self) -> Optional[pd.DataFrame]:
        """
        获取系谱统计数据

        Returns:
            系谱统计DataFrame
        """
        return self.get_data('pedigree_analysis')

    def get_traits_summary(self) -> Optional[pd.DataFrame]:
        """
        获取育种性状汇总

        Returns:
            性状汇总DataFrame
        """
        return self.get_data('traits_summary')

    def get_traits_yearly(self) -> Optional[pd.DataFrame]:
        """
        获取年度性状趋势

        Returns:
            年度趋势DataFrame
        """
        return self.get_data('traits_yearly')

    def get_tpi_distribution(self) -> Optional[pd.DataFrame]:
        """
        获取TPI分布数据

        Returns:
            TPI分布DataFrame
        """
        return self.get_data('traits_tpi')

    def get_nm_distribution(self) -> Optional[pd.DataFrame]:
        """
        获取NM$分布数据

        Returns:
            NM$分布DataFrame
        """
        return self.get_data('traits_nm')

    def get_cow_index_ranking(self, top_n: int = 20) -> Optional[pd.DataFrame]:
        """
        获取母牛指数排名

        Args:
            top_n: 返回前N名

        Returns:
            排名DataFrame
        """
        df = self.get_data('cow_index_rank')
        if df is not None and not df.empty:
            return df.head(top_n)
        return None

    def get_breeding_genes_stats(self) -> Optional[pd.DataFrame]:
        """
        获取配种基因统计

        Returns:
            配种基因统计DataFrame
        """
        return self.get_data('breeding_genes')

    def get_breeding_inbreeding_stats(self) -> Optional[pd.DataFrame]:
        """
        获取配种近交统计

        Returns:
            配种近交统计DataFrame
        """
        return self.get_data('breeding_inbreeding')

    def get_used_bulls_summary(self) -> Optional[pd.DataFrame]:
        """
        获取已用公牛汇总

        Returns:
            已用公牛汇总DataFrame
        """
        return self.get_data('used_bulls_summary')

    def get_used_bulls_detail(self, top_n: int = 10) -> Optional[pd.DataFrame]:
        """
        获取已用公牛明细（Top N）

        Args:
            top_n: 返回前N名

        Returns:
            已用公牛明细DataFrame
        """
        df = self.get_data('used_bulls_detail')
        if df is not None and not df.empty:
            return df.head(top_n)
        return None

    def get_candidate_bulls_ranking(self, top_n: int = 20) -> Optional[pd.DataFrame]:
        """
        获取备选公牛排名

        Args:
            top_n: 返回前N名

        Returns:
            备选公牛排名DataFrame
        """
        df = self.get_data('candidate_bulls_rank')
        if df is not None and not df.empty:
            return df.head(top_n)
        return None

    def get_candidate_bulls_genes(self) -> Optional[pd.DataFrame]:
        """
        获取备选公牛基因分析

        Returns:
            备选公牛基因DataFrame
        """
        return self.get_data('candidate_bulls_genes')

    def get_candidate_bulls_inbreeding(self) -> Optional[pd.DataFrame]:
        """
        获取备选公牛近交分析

        Returns:
            备选公牛近交DataFrame
        """
        return self.get_data('candidate_bulls_inbreeding')

    def get_mating_summary(self) -> Optional[Dict[str, any]]:
        """
        获取选配推荐摘要

        Returns:
            选配摘要字典
        """
        df = self.get_data('mating_results')
        if df is None or df.empty:
            return None

        try:
            summary = {
                'total_cows': len(df),
                'has_sexed': len(df[df['推荐性控冻精1选'].notna()]),
                'has_regular': len(df[df['推荐常规冻精1选'].notna()]),
                'no_recommendation': len(df[(df['推荐性控冻精1选'].isna()) & (df['推荐常规冻精1选'].isna())]),
            }

            # 按分组统计（如果有分组字段）
            if '分组' in df.columns:
                group_stats = df.groupby('分组').size().to_dict()
                summary['group_stats'] = group_stats

            return summary

        except Exception as e:
            logger.error(f"计算选配摘要失败: {e}")
            return None

    def _parse_upload_stats(self, df: pd.DataFrame):
        stats = []
        header_found = False
        for row_idx in range(len(df)):
            if df.shape[1] <= 11:
                break
            cell = df.iloc[row_idx, 11]
            if isinstance(cell, str) and '数据类型' in cell:
                header_found = True
                continue
            if header_found:
                data_type = df.iloc[row_idx, 11]
                if pd.isna(data_type):
                    break
                count = df.iloc[row_idx, 12] if df.shape[1] > 12 else None
                remark = df.iloc[row_idx, 13] if df.shape[1] > 13 else ''
                stats.append({
                    'type': str(data_type).strip(),
                    'count': _to_int(count) or 0,
                    'remark': '' if pd.isna(remark) else str(remark).strip()
                })
        return stats

    def _parse_cow_type_distribution(self, df: pd.DataFrame):
        distribution = []
        targets = ['成母牛(胎次>0)', '后备牛(胎次=0)', '合计']
        for row_idx in range(len(df)):
            if df.shape[1] <= 5:
                break
            cell = df.iloc[row_idx, 3]
            if isinstance(cell, str) and cell.strip() in targets:
                distribution.append({
                    'type': cell.strip(),
                    'count': _to_int(df.iloc[row_idx, 4]) or 0,
                    'percent': _to_float(df.iloc[row_idx, 5]) or 0.0
                })
        return distribution

    def _parse_parity_distribution(self, df: pd.DataFrame):
        parity = []
        header_found = False
        for row_idx in range(len(df)):
            if df.shape[1] <= 9:
                break
            cell = df.iloc[row_idx, 7]
            if isinstance(cell, str) and '胎次' in cell and not header_found:
                header_found = True
                continue
            if header_found:
                if pd.isna(cell):
                    break
                parity.append({
                    'type': str(cell).strip(),
                    'count': _to_int(df.iloc[row_idx, 8]) or 0,
                    'percent': _to_float(df.iloc[row_idx, 9]) or 0.0
                })
        return parity
