"""
对比牧场管理模块
用于管理对比牧场的配置和历史数据
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
import shutil

logger = logging.getLogger(__name__)


class BenchmarkManager:
    """对比牧场管理器"""

    def __init__(self, app_data_dir: Path = None):
        """
        初始化对比牧场管理器

        Args:
            app_data_dir: 应用数据目录，默认使用用户主目录下的.genetic_improve
        """
        if app_data_dir is None:
            import os
            if os.name == 'nt':  # Windows
                app_data_dir = Path(os.environ.get('APPDATA', os.path.expanduser('~'))) / 'GeneticImprove'
            else:  # Mac/Linux
                app_data_dir = Path.home() / '.genetic_improve'

        self.app_data_dir = Path(app_data_dir)
        self.benchmark_dir = self.app_data_dir / 'benchmark_farms'
        self.config_file = self.benchmark_dir / 'benchmark_config.json'

        # 确保目录存在
        self.benchmark_dir.mkdir(parents=True, exist_ok=True)

        # 加载配置
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """
        加载对比牧场配置

        Returns:
            配置字典
        """
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载对比牧场配置失败: {e}")
                return self._get_default_config()
        else:
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """
        获取默认配置

        Returns:
            默认配置字典
        """
        return {
            'farms': [],  # 对比牧场列表
            'last_updated': datetime.now().isoformat()
        }

    def _save_config(self):
        """保存配置到文件"""
        try:
            self.config['last_updated'] = datetime.now().isoformat()
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logger.info("对比牧场配置已保存")
        except Exception as e:
            logger.error(f"保存对比牧场配置失败: {e}")
            raise

    def add_farm(self, farm_name: str, description: str = "", excel_file_path: Path = None) -> bool:
        """
        添加对比牧场

        Args:
            farm_name: 牧场名称
            description: 牧场描述
            excel_file_path: Excel文件路径（关键育种性状分析结果.xlsx）

        Returns:
            是否成功
        """
        try:
            # 检查牧场名称是否已存在
            if any(farm['name'] == farm_name for farm in self.config['farms']):
                logger.warning(f"牧场名称已存在: {farm_name}")
                return False

            # 如果提供了Excel文件，解析数据
            data_summary = None
            if excel_file_path:
                from .excel_parser import TraitsExcelParser

                parser = TraitsExcelParser(excel_file_path)

                # 验证文件
                is_valid, error_msg = parser.validate()
                if not is_valid:
                    logger.error(f"Excel文件验证失败: {error_msg}")
                    return False

                # 解析数据
                data_summary = parser.parse()
                if not data_summary:
                    logger.error("解析Excel文件失败")
                    return False

            # 生成唯一ID
            farm_id = f"farm_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # 创建牧场数据目录
            farm_data_dir = self.benchmark_dir / farm_id
            farm_data_dir.mkdir(parents=True, exist_ok=True)

            # 复制Excel文件到数据目录
            if excel_file_path:
                dest_file = farm_data_dir / '关键育种性状分析结果.xlsx'
                shutil.copy2(excel_file_path, dest_file)
                logger.info(f"已复制Excel文件到 {dest_file}")

            # 添加到配置
            farm_info = {
                'id': farm_id,
                'name': farm_name,
                'description': description,
                'data_file': '关键育种性状分析结果.xlsx',
                'data_dir': str(farm_data_dir),
                'added_date': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'data_summary': data_summary  # 保存解析后的数据摘要
            }

            self.config['farms'].append(farm_info)
            self._save_config()

            logger.info(f"✓ 对比牧场已添加: {farm_name}")
            return True

        except Exception as e:
            logger.error(f"添加对比牧场失败: {e}", exc_info=True)
            return False

    def update_farm(self, farm_id: str, name: str = None, description: str = None,
                   excel_file_path: Path = None) -> bool:
        """
        更新对比牧场信息

        Args:
            farm_id: 牧场ID
            name: 新名称（可选）
            description: 新描述（可选）
            excel_file_path: 新的Excel文件路径（可选，会更新数据）

        Returns:
            是否成功
        """
        try:
            # 查找牧场
            farm = self.get_farm_by_id(farm_id)
            if not farm:
                logger.error(f"未找到牧场: {farm_id}")
                return False

            # 更新信息
            if name is not None:
                # 检查新名称是否与其他牧场冲突
                if any(f['name'] == name and f['id'] != farm_id for f in self.config['farms']):
                    logger.warning(f"牧场名称已存在: {name}")
                    return False
                farm['name'] = name

            if description is not None:
                farm['description'] = description

            # 更新数据文件
            if excel_file_path:
                from .excel_parser import TraitsExcelParser

                parser = TraitsExcelParser(excel_file_path)

                # 验证文件
                is_valid, error_msg = parser.validate()
                if not is_valid:
                    logger.error(f"Excel文件验证失败: {error_msg}")
                    return False

                # 解析数据
                data_summary = parser.parse()
                if not data_summary:
                    logger.error("解析Excel文件失败")
                    return False

                # 复制新文件
                farm_data_dir = Path(farm['data_dir'])
                dest_file = farm_data_dir / '关键育种性状分析结果.xlsx'

                # 删除旧文件
                if dest_file.exists():
                    dest_file.unlink()

                shutil.copy2(excel_file_path, dest_file)
                logger.info(f"已更新Excel文件到 {dest_file}")

                # 更新数据摘要
                farm['data_summary'] = data_summary

            farm['last_updated'] = datetime.now().isoformat()
            self._save_config()

            logger.info(f"✓ 对比牧场已更新: {farm['name']}")
            return True

        except Exception as e:
            logger.error(f"更新对比牧场失败: {e}", exc_info=True)
            return False

    def delete_farm(self, farm_id: str) -> bool:
        """
        删除对比牧场

        Args:
            farm_id: 牧场ID

        Returns:
            是否成功
        """
        try:
            # 查找牧场
            farm = self.get_farm_by_id(farm_id)
            if not farm:
                logger.error(f"未找到牧场: {farm_id}")
                return False

            # 删除数据目录
            farm_data_dir = Path(farm['data_dir'])
            if farm_data_dir.exists():
                shutil.rmtree(farm_data_dir)
                logger.info(f"已删除牧场数据目录: {farm_data_dir}")

            # 从配置中移除
            self.config['farms'] = [f for f in self.config['farms'] if f['id'] != farm_id]
            self._save_config()

            logger.info(f"✓ 对比牧场已删除: {farm['name']}")
            return True

        except Exception as e:
            logger.error(f"删除对比牧场失败: {e}", exc_info=True)
            return False

    def get_all_farms(self) -> List[Dict]:
        """
        获取所有对比牧场列表

        Returns:
            牧场信息列表
        """
        return self.config['farms']

    def get_farm_by_id(self, farm_id: str) -> Optional[Dict]:
        """
        根据ID获取牧场信息

        Args:
            farm_id: 牧场ID

        Returns:
            牧场信息字典，如果不存在返回None
        """
        for farm in self.config['farms']:
            if farm['id'] == farm_id:
                return farm
        return None

    def get_farm_by_name(self, farm_name: str) -> Optional[Dict]:
        """
        根据名称获取牧场信息

        Args:
            farm_name: 牧场名称

        Returns:
            牧场信息字典，如果不存在返回None
        """
        for farm in self.config['farms']:
            if farm['name'] == farm_name:
                return farm
        return None

    def get_farm_data_path(self, farm_id: str) -> Optional[Path]:
        """
        获取牧场数据目录路径

        Args:
            farm_id: 牧场ID

        Returns:
            数据目录路径，如果不存在返回None
        """
        farm = self.get_farm_by_id(farm_id)
        if farm:
            return Path(farm['data_dir'])
        return None

    def get_farm_analysis_path(self, farm_id: str) -> Optional[Path]:
        """
        获取牧场analysis_results目录路径

        Args:
            farm_id: 牧场ID

        Returns:
            analysis_results目录路径，如果不存在返回None
        """
        data_path = self.get_farm_data_path(farm_id)
        if data_path:
            analysis_path = data_path / 'analysis_results'
            if analysis_path.exists():
                return analysis_path
        return None

    def save_selected_comparisons(self, comparisons: List[Dict]):
        """
        保存用户选择的对比数据

        Args:
            comparisons: 对比列表，格式：
                [
                    {'farm_id': 'xxx', 'year_row': '在群母牛总计', 'color': '#FF0000'},
                    ...
                ]
        """
        # 先重新加载配置，确保不覆盖其他更改
        self.config = self._load_config()
        self.config['selected_comparisons'] = comparisons
        self._save_config()
        logger.info(f"已保存 {len(comparisons)} 个对比选择")

    def get_selected_comparisons(self) -> List[Dict]:
        """
        获取用户选择的对比数据

        Returns:
            对比列表
        """
        return self.config.get('selected_comparisons', [])

    def get_comparison_data(self, farm_id: str, sheet_type: str, year_row: str) -> Optional[Dict]:
        """
        获取指定牧场指定年份的对比数据

        Args:
            farm_id: 牧场ID
            sheet_type: sheet类型 ('present_summary' 或 'all_summary')
            year_row: 年份行名称（如"在群母牛总计"、"2024年"等）

        Returns:
            数据字典，包含所有性状的值
        """
        farm = self.get_farm_by_id(farm_id)
        if not farm or 'data_summary' not in farm:
            return None

        data_summary = farm['data_summary']
        if not data_summary or sheet_type not in data_summary:
            return None

        sheet_data = data_summary[sheet_type]
        if 'data' not in sheet_data:
            return None

        # 获取指定年份的数据
        return sheet_data['data'].get(year_row)

    def get_farm_latest_year(self, farm_id: str) -> Optional[int]:
        """
        获取牧场的最后出生年份

        Args:
            farm_id: 牧场ID

        Returns:
            最后出生年份，如果不存在返回None
        """
        farm = self.get_farm_by_id(farm_id)
        if not farm or 'data_summary' not in farm:
            return None

        data_summary = farm['data_summary']
        if not data_summary or 'present_summary' not in data_summary:
            return None

        return data_summary['present_summary'].get('latest_year')

    # === 外部参考数据管理 ===

    def add_reference_data(self, name: str, description: str, excel_file_path: Path) -> bool:
        """
        添加外部参考数据（如行业数据、参测牛数据等）

        Args:
            name: 参考数据名称（如"参测牛数据2024"）
            description: 描述
            excel_file_path: Excel文件路径

        Returns:
            是否成功
        """
        try:
            from .reference_data_manager import ReferenceDataParser

            parser = ReferenceDataParser(excel_file_path)

            # 验证文件
            is_valid, error_msg = parser.validate()
            if not is_valid:
                logger.error(f"外部参考数据验证失败: {error_msg}")
                return False

            # 解析数据
            data = parser.parse()
            if not data:
                logger.error("解析外部参考数据失败")
                return False

            # 生成唯一ID
            ref_id = f"ref_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # 创建数据目录
            ref_data_dir = self.benchmark_dir / ref_id
            ref_data_dir.mkdir(parents=True, exist_ok=True)

            # 复制Excel文件
            dest_file = ref_data_dir / 'reference_data.xlsx'
            shutil.copy2(excel_file_path, dest_file)
            logger.info(f"已复制外部参考数据文件到 {dest_file}")

            # 添加到配置（使用与牧场相同的结构，便于统一处理）
            ref_info = {
                'id': ref_id,
                'name': name,
                'description': description,
                'type': 'reference',  # 标记为外部参考数据
                'data_file': 'reference_data.xlsx',
                'data_dir': str(ref_data_dir),
                'added_date': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'data_summary': {
                    'present_summary': data,  # 外部参考数据只有一份
                    'all_summary': data  # 使用相同数据
                }
            }

            # 初始化引用数据列表（如果不存在）
            if 'reference_data' not in self.config:
                self.config['reference_data'] = []

            self.config['reference_data'].append(ref_info)
            self._save_config()

            logger.info(f"✓ 外部参考数据已添加: {name}")
            return True

        except Exception as e:
            logger.error(f"添加外部参考数据失败: {e}", exc_info=True)
            return False

    def get_all_reference_data(self) -> List[Dict]:
        """
        获取所有外部参考数据

        Returns:
            参考数据列表
        """
        return self.config.get('reference_data', [])

    def get_reference_by_id(self, ref_id: str) -> Optional[Dict]:
        """
        根据ID获取外部参考数据

        Args:
            ref_id: 参考数据ID

        Returns:
            参考数据字典，如果不存在返回None
        """
        for ref in self.config.get('reference_data', []):
            if ref['id'] == ref_id:
                return ref
        return None

    def delete_reference_data(self, ref_id: str) -> bool:
        """
        删除外部参考数据

        Args:
            ref_id: 参考数据ID

        Returns:
            是否成功
        """
        try:
            ref = self.get_reference_by_id(ref_id)
            if not ref:
                logger.error(f"未找到外部参考数据: {ref_id}")
                return False

            # 删除数据目录
            ref_data_dir = Path(ref['data_dir'])
            if ref_data_dir.exists():
                shutil.rmtree(ref_data_dir)
                logger.info(f"已删除参考数据目录: {ref_data_dir}")

            # 从配置中移除
            if 'reference_data' not in self.config:
                self.config['reference_data'] = []

            self.config['reference_data'] = [r for r in self.config['reference_data'] if r['id'] != ref_id]
            self._save_config()

            logger.info(f"✓ 外部参考数据已删除: {ref['name']}")
            return True

        except Exception as e:
            logger.error(f"删除外部参考数据失败: {e}", exc_info=True)
            return False

    def get_all_comparison_sources(self) -> Dict[str, List[Dict]]:
        """
        获取所有对比数据源（包括对比牧场和外部参考数据）

        Returns:
            {
                'farms': [...],  # 对比牧场列表
                'references': [...]  # 外部参考数据列表
            }
        """
        return {
            'farms': self.get_all_farms(),
            'references': self.get_all_reference_data()
        }
