"""
数据准备模块

负责在生成PPT前准备所有必要的数据文件
"""

import os
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PyQt6.QtWidgets import QMessageBox, QProgressDialog
from PyQt6.QtCore import Qt

from .data_generator import DataGenerator

logger = logging.getLogger(__name__)


class DataPreparation:
    """PPT数据准备类"""
    
    def __init__(self, output_folder: str):
        """
        初始化数据准备类
        
        Args:
            output_folder: 输出文件夹路径
        """
        self.output_folder = Path(output_folder)
        self.required_files = {
            'ranking': '结果-指数排名结果.xlsx',
            'cow_traits': '结果-母牛关键性状指数.xlsx',
            'pedigree_analysis': '结果-系谱识别情况分析.xlsx',
            'traits_annual': '结果-牛群关键性状年度变化.xlsx',
            'nm_distribution': '在群牛只净利润值分布.xlsx',
            'semen_trend': '结果-冻精使用趋势图.xlsx'
        }
        
        self.required_images = {
            'nm_normal': 'NM$_年份正态分布.png',
            'index_normal': '育种指数得分_年份正态分布.png'
        }
        
        self.traits_progress_folder = '结果-牛群关键性状进展图'
        
        # 初始化数据生成器
        self.data_generator = DataGenerator(output_folder)
        
    def check_all_files(self) -> Tuple[bool, List[str]]:
        """
        检查所有必需的文件是否存在
        
        Returns:
            (是否所有文件都存在, 缺失文件列表)
        """
        missing_files = []
        
        # 检查Excel文件
        for key, filename in self.required_files.items():
            filepath = self.output_folder / filename
            if not filepath.exists():
                missing_files.append(filename)
                
        # 检查图片文件
        for key, filename in self.required_images.items():
            filepath = self.output_folder / filename
            if not filepath.exists():
                missing_files.append(filename)
                
        # 检查进展图文件夹
        progress_folder = self.output_folder / self.traits_progress_folder
        if not progress_folder.exists():
            missing_files.append(self.traits_progress_folder)
            
        return len(missing_files) == 0, missing_files
    
    def prepare_all_data(self, parent_widget=None, 
                        cow_df: Optional[pd.DataFrame] = None,
                        bull_traits: Optional[pd.DataFrame] = None,
                        selected_traits: Optional[List[str]] = None,
                        table_c: Optional[pd.DataFrame] = None,
                        merged_cow_traits: Optional[pd.DataFrame] = None,
                        breeding_df: Optional[pd.DataFrame] = None,
                        cow_traits: Optional[pd.DataFrame] = None,
                        breeding_index_scores: Optional[pd.DataFrame] = None) -> bool:
        """
        准备所有PPT所需的数据
        
        Args:
            parent_widget: 父窗口部件（用于显示进度）
            cow_df: 母牛数据
            bull_traits: 公牛性状数据
            selected_traits: 选中的性状列表
            table_c: 包含系谱信息的表格（用于系谱分析）
            merged_cow_traits: 合并的母牛性状数据
            
        Returns:
            是否成功准备所有数据
        """
        try:
            # 创建进度对话框
            if parent_widget:
                progress = QProgressDialog("正在准备PPT数据...", "取消", 0, 100, parent_widget)
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.show()
            
            # 如果没有提供选中的性状，尝试从文件读取
            if selected_traits is None:
                selected_traits = self.get_selected_traits()
                if not selected_traits:
                    # 使用默认的关键性状
                    selected_traits = ['TPI', 'NM$', 'MILK', 'FAT', 'PROT', 'SCS', 'PL', 'DPR']
            
            # 1. 生成指数排名结果
            if not (self.output_folder / self.required_files['ranking']).exists():
                logger.info("生成指数排名结果...")
                if parent_widget:
                    progress.setValue(15)
                    progress.setLabelText("正在生成指数排名结果...")
                    
                if cow_df is not None and breeding_index_scores is not None:
                    success = self.data_generator.generate_index_ranking(
                        cow_df, breeding_index_scores, selected_traits
                    )
                    if not success:
                        logger.error("生成指数排名结果失败")
                else:
                    logger.warning("缺少cow_df或breeding_index_scores数据，无法生成指数排名")
                
            # 2. 生成母牛关键性状指数
            if not (self.output_folder / self.required_files['cow_traits']).exists():
                logger.info("生成母牛关键性状指数...")
                if parent_widget:
                    progress.setValue(30)
                    progress.setLabelText("正在生成母牛关键性状指数...")
                    
                if cow_df is not None and cow_traits is not None:
                    success = self.data_generator.generate_cow_key_traits(
                        cow_df, cow_traits, selected_traits
                    )
                    if not success:
                        logger.error("生成母牛关键性状指数失败")
                else:
                    logger.warning("缺少cow_df或cow_traits数据，无法生成母牛关键性状指数")
                
            # 3. 生成系谱识别情况分析
            if not (self.output_folder / self.required_files['pedigree_analysis']).exists():
                logger.info("生成系谱识别情况分析...")
                if parent_widget:
                    progress.setValue(45)
                    progress.setLabelText("正在生成系谱识别情况分析...")
                    
                if table_c is not None and cow_df is not None:
                    success = self.data_generator.generate_pedigree_identification_analysis(
                        table_c, cow_df
                    )
                    if not success:
                        logger.error("生成系谱识别情况分析失败")
                else:
                    logger.warning("缺少table_c数据，无法生成系谱识别情况分析")
                    
            # 4. 生成关键性状年度变化
            if not (self.output_folder / self.required_files['traits_annual']).exists():
                logger.info("生成关键性状年度变化...")
                if parent_widget:
                    progress.setValue(60)
                    progress.setLabelText("正在生成关键性状年度变化...")
                    
                if merged_cow_traits is not None:
                    success = self.data_generator.generate_key_traits_annual_change(
                        merged_cow_traits, selected_traits
                    )
                    if not success:
                        logger.error("生成关键性状年度变化失败")
                else:
                    logger.warning("缺少merged_cow_traits数据，无法生成关键性状年度变化")
                    
            # 5. 生成NM$分布
            if not (self.output_folder / self.required_files['nm_distribution']).exists():
                logger.info("生成NM$分布...")
                if parent_widget:
                    progress.setValue(75)
                    progress.setLabelText("正在生成NM$分布...")
                    
                if merged_cow_traits is not None and 'NM$' in merged_cow_traits.columns:
                    success = self.data_generator.generate_nm_distribution_charts(merged_cow_traits)
                    if not success:
                        logger.error("生成NM$分布失败")
                else:
                    logger.warning("缺少NM$数据，无法生成分布图")
                    
            # 6. 生成五等份分布表
            nm_quintile_file = self.output_folder / "NM$_5等份分布表.xlsx"
            if not nm_quintile_file.exists():
                logger.info("生成NM$五等份分布...")
                if parent_widget:
                    progress.setValue(85)
                    progress.setLabelText("正在生成五等份分布表...")
                    
                if merged_cow_traits is not None and 'NM$' in merged_cow_traits.columns:
                    success = self.data_generator.generate_quintile_distribution(
                        merged_cow_traits, 'NM$', 'NM$'
                    )
                    if not success:
                        logger.error("生成NM$五等份分布失败")
                        
            # 7. 生成正态分布图
            if not (self.output_folder / self.required_images['nm_normal']).exists():
                logger.info("生成NM$正态分布图...")
                if parent_widget:
                    progress.setValue(90)
                    progress.setLabelText("正在生成正态分布图...")
                    
                if merged_cow_traits is not None and 'NM$' in merged_cow_traits.columns:
                    success = self.data_generator.generate_normal_distribution_charts(
                        merged_cow_traits, 'NM$', 'NM$'
                    )
                    if not success:
                        logger.error("生成NM$正态分布图失败")
                else:
                    logger.warning("缺少NM$数据，无法生成正态分布图")
                    
            # 7.2 生成育种指数正态分布图
            if not (self.output_folder / self.required_images['index_normal']).exists():
                logger.info("生成育种指数正态分布图...")
                if parent_widget:
                    progress.setValue(92)
                    progress.setLabelText("正在生成育种指数正态分布图...")
                    
                if merged_cow_traits is not None and '育种指数得分' in merged_cow_traits.columns:
                    success = self.data_generator.generate_normal_distribution_charts(
                        merged_cow_traits, '育种指数得分', '育种指数得分'
                    )
                    if not success:
                        logger.error("生成育种指数正态分布图失败")
                else:
                    logger.warning("缺少育种指数得分数据，无法生成正态分布图")
                
            # 8. 生成性状进展图
            progress_folder = self.output_folder / self.traits_progress_folder
            if not progress_folder.exists():
                logger.info("生成性状进展图...")
                if parent_widget:
                    progress.setValue(95)
                    progress.setLabelText("正在生成性状进展图...")
                progress_folder.mkdir(exist_ok=True)
                
                if merged_cow_traits is not None:
                    success = self.data_generator.generate_traits_progress_charts(
                        merged_cow_traits, selected_traits
                    )
                    if not success:
                        logger.error("生成性状进展图失败")
                else:
                    logger.warning("缺少merged_cow_traits数据，无法生成性状进展图")
                    
            # 9. 生成冻精使用趋势图数据
            if not (self.output_folder / self.required_files['semen_trend']).exists():
                logger.info("生成冻精使用趋势图数据...")
                if parent_widget:
                    progress.setValue(98)
                    progress.setLabelText("正在生成冻精使用趋势图数据...")
                    
                if breeding_df is not None and bull_traits is not None:
                    success = self.data_generator.generate_semen_usage_trend(
                        breeding_df, bull_traits, selected_traits
                    )
                    if not success:
                        logger.error("生成冻精使用趋势图数据失败")
                else:
                    logger.warning("缺少breeding_df或bull_traits数据，无法生成冻精使用趋势图")
                    
            if parent_widget:
                progress.setValue(100)
                progress.close()
                
            return True
            
        except Exception as e:
            logger.error(f"准备PPT数据时出错: {str(e)}")
            if parent_widget:
                if 'progress' in locals():
                    progress.close()
                QMessageBox.critical(parent_widget, "错误", f"准备数据时出错：{str(e)}")
            return False
    
    def get_selected_traits(self) -> List[str]:
        """
        获取选中的性状列表
        
        Returns:
            选中的性状列表
        """
        traits_file = self.output_folder / "selected_traits_key_traits.txt"
        if traits_file.exists():
            with open(traits_file, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        return []
    
    def validate_data_files(self) -> Dict[str, bool]:
        """
        验证数据文件的有效性
        
        Returns:
            文件验证结果字典
        """
        validation_results = {}
        
        for key, filename in self.required_files.items():
            filepath = self.output_folder / filename
            if filepath.exists():
                try:
                    # 尝试读取文件验证格式
                    df = pd.read_excel(filepath, nrows=5)
                    validation_results[filename] = True
                except Exception as e:
                    logger.error(f"验证文件 {filename} 失败: {str(e)}")
                    validation_results[filename] = False
            else:
                validation_results[filename] = False
                
        return validation_results