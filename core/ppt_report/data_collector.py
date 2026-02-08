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

        # 批量读取PPT需要的Sheet（跳过detail_only大表，节省I/O）
        all_sheets = {}
        try:
            import time as _time
            t0 = _time.perf_counter()
            # 只读取非detail_only且header=0的Sheet
            needed_sheets = [
                meta['sheet_name'] for meta in EXCEL_SHEET_MAPPING.values()
                if not meta.get('detail_only', False) and meta.get('header', 0) == 0
            ]
            all_sheets = pd.read_excel(self.excel_path, sheet_name=needed_sheets, header=0)
            t1 = _time.perf_counter()
            logger.info(f"✓ 批量读取Excel完成，读取 {len(all_sheets)}/{len(EXCEL_SHEET_MAPPING)} 个Sheet（跳过明细表），耗时: {t1-t0:.2f}秒")
        except Exception as e:
            logger.error(f"批量读取Excel失败，回退到逐个读取: {e}")

        for key, meta in EXCEL_SHEET_MAPPING.items():
            sheet_name = meta['sheet_name']
            header = meta.get('header', 0)

            if header is None:
                # 需要特殊header参数的Sheet（如farm_info），单独读取
                df = self._read_sheet(sheet_name, header=header)
            elif sheet_name in all_sheets:
                # 从批量读取结果中获取
                df = all_sheets[sheet_name]
                logger.debug("✓ 读取Sheet: %s (%s行, 含表头)", sheet_name, len(df))
            else:
                # 批量读取中未找到，尝试单独读取
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

        # 记录Excel源路径，供后续PPT构建器按需直接读取原始Sheet
        self.data_cache['excel_path'] = self.excel_path
        # 添加 data_collector 引用，供 builder 使用 get_raw_sheet() 缓存方法
        self.data_cache['data_collector'] = self

        # 特殊处理：farm_info需要解析成dict（因为Sheet1是横向布局）
        if 'farm_info' in self.data_cache:
            logger.info("正在解析farm_info横向布局...")
            farm_info_dict = self.get_farm_info()
            self.data_cache['farm_info_dict'] = farm_info_dict
            logger.info(f"✓ farm_info解析完成: {farm_info_dict}")

        # 特殊处理：选配推荐摘要（从Excel汇总区域解析）
        mating_summary = self.get_mating_summary()
        if mating_summary:
            self.data_cache['mating_summary'] = mating_summary
            logger.info(f"✓ mating_summary解析完成: {len(mating_summary.get('group_stats', []))}个分组")

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

    def get_raw_sheet(self, sheet_name: str, header=None) -> Optional[pd.DataFrame]:
        """
        获取原始Sheet数据（带缓存）

        用于需要 header=None 读取的场景，避免 builder 独立调用 pd.read_excel()

        Args:
            sheet_name: Sheet名称
            header: header参数，默认None表示无表头

        Returns:
            DataFrame或None
        """
        # 生成缓存键：sheet名称 + header参数
        cache_key = f"_raw_{sheet_name}_h{header}"

        if cache_key in self.data_cache:
            logger.debug(f"使用缓存: {cache_key}")
            return self.data_cache[cache_key]

        try:
            df = pd.read_excel(self.excel_path, sheet_name=sheet_name, header=header)
            self.data_cache[cache_key] = df
            logger.info(f"✓ 读取原始Sheet '{sheet_name}' (header={header}): {len(df)}行 x {len(df.columns)}列")
            return df
        except Exception as e:
            logger.error(f"✗ 读取原始Sheet '{sheet_name}' 失败: {e}")
            return None

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
        import numpy as np

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

            # P2优化：批量转换为字符串数组，减少重复转换
            str_array = df.fillna("").astype(str).to_numpy()
            n_rows, n_cols = str_array.shape

            def find_keyword_and_value(keyword, check_func=None, value_offsets=[1]):
                """向量化查找关键字并获取相邻单元格的值"""
                for r in range(n_rows):
                    for c in range(n_cols):
                        cell_str = str_array[r, c].strip()
                        if keyword in cell_str:
                            if check_func and not check_func(cell_str):
                                continue
                            for offset in value_offsets:
                                if c + offset < n_cols:
                                    val = str_array[r, c + offset].strip()
                                    if val:
                                        return val
                return None

            def find_exact_and_value(keyword, value_offsets=[1, 2]):
                """查找精确匹配的关键字并获取数值"""
                for r in range(n_rows):
                    for c in range(n_cols):
                        cell_str = str_array[r, c].strip()
                        if cell_str == keyword:
                            for offset in value_offsets:
                                if c + offset < n_cols:
                                    val = str_array[r, c + offset].strip()
                                    if val.replace('.', '').replace(',', '').isdigit():
                                        return val
                return None

            # 基本信息提取
            val = find_keyword_and_value('牧场名称')
            if val:
                info['farm_name'] = val

            val = find_keyword_and_value('报告生成时间') or find_keyword_and_value('报告时间')
            if val:
                info['report_time'] = val

            val = find_keyword_and_value('服务人员')
            if val:
                info['service_staff'] = val

            # 成母牛数量
            val = find_keyword_and_value('成母牛', lambda s: '胎次>0' in s, [1, 2])
            if val and val.replace('.', '').replace(',', '').isdigit():
                info['lactating_count'] = int(float(val.replace(',', '')))

            # 后备牛数量
            val = find_keyword_and_value('后备牛', lambda s: '胎次=0' in s, [1, 2])
            if val and val.replace('.', '').replace(',', '').isdigit():
                info['heifer_count'] = int(float(val.replace(',', '')))

            # 合计（总头数）
            val = find_exact_and_value('合计')
            if val:
                info['total_count'] = int(float(val.replace(',', '')))

            # 平均胎次
            val = find_keyword_and_value('平均胎次')
            if val:
                try:
                    info['avg_lactation'] = float(val.replace(',', ''))
                except:
                    pass

            # 平均泌乳天数
            val = find_keyword_and_value('平均泌乳天数')
            if val:
                try:
                    raw = val.replace('天', '').replace(',', '').strip()
                    info['avg_dim'] = int(float(raw))
                except:
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
        获取选配推荐摘要（从Excel汇总区域读取）

        Returns:
            {
                'basic_stats': {
                    'total_cows': 665,
                    'has_sexed': 255,
                    'has_regular': 665,
                    'no_recommendation': 0
                },
                'group_stats': [
                    {'group': '后备牛已孕牛+非性控', 'total': 52, 'sexed': 0, 'regular': 52},
                    ...
                ]
            }
        """
        df = self.get_data('mating_results')
        if df is None or df.empty:
            return None

        try:
            # 读取基础统计摘要（行1-4, 0-based索引0-3）
            # 行0: 标题
            # 行1: 总母牛数
            # 行2: 有性控推荐
            # 行3: 有常规推荐
            # 行4: 无推荐

            basic_stats = {
                'total_cows': _to_int(df.iloc[1, 1]) or 0,      # 行2列B
                'has_sexed': _to_int(df.iloc[2, 1]) or 0,       # 行3列B
                'has_regular': _to_int(df.iloc[3, 1]) or 0,     # 行4列B
                'no_recommendation': _to_int(df.iloc[4, 1]) or 0  # 行5列B
            }

            logger.info(f"基础统计: 总{basic_stats['total_cows']}头, "
                       f"性控{basic_stats['has_sexed']}, "
                       f"常规{basic_stats['has_regular']}, "
                       f"无推荐{basic_stats['no_recommendation']}")

            # 读取分组统计（行7起）
            # 行6: "按分组统计"标题
            # 行7: 表头 ['分组', '母牛数', '性控推荐数', '常规推荐数']
            # 行8-: 分组数据

            group_stats = []
            header_row = 7  # 0-based索引，对应Excel的行8

            # 从表头下一行开始读取数据
            data_start_row = header_row + 1

            for i in range(data_start_row, min(data_start_row + 20, len(df))):
                group_name = df.iloc[i, 0]
                if pd.isna(group_name) or str(group_name).strip() == '':
                    break  # 遇到空行停止

                group_stats.append({
                    'group': str(group_name).strip(),
                    'total': _to_int(df.iloc[i, 1]) or 0,
                    'sexed': _to_int(df.iloc[i, 2]) or 0,
                    'regular': _to_int(df.iloc[i, 3]) or 0
                })

            logger.info(f"分组统计: 共{len(group_stats)}个分组")

            return {
                'basic_stats': basic_stats,
                'group_stats': group_stats
            }

        except Exception as e:
            logger.error(f"读取选配摘要失败: {e}", exc_info=True)
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
