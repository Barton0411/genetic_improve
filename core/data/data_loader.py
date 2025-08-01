"""
数据加载器
统一管理所有数据的加载和预处理
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional, List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DataLoader:
    """统一的数据加载器"""
    
    def __init__(self, base_path: Path, project_name: Optional[str] = None):
        """
        初始化数据加载器
        
        Args:
            base_path: 项目基础路径
            project_name: 项目名称（如果指定，从genetic_projects下加载）
        """
        self.base_path = Path(base_path)
        
        if project_name:
            # 从特定项目加载
            self.project_path = self.base_path / "genetic_projects" / project_name
            self.data_path = self.project_path / "standardized_data"
            self.analysis_path = self.project_path / "analysis_results"
        else:
            # 从默认位置加载
            self.data_path = self.base_path / "data" / "标准化后文件"
            self.analysis_path = self.base_path / "analysis_results"
        
    def load_cow_data(self) -> pd.DataFrame:
        """
        加载母牛基础数据
        
        Returns:
            母牛数据DataFrame
        """
        # 加载标准化后的数据
        cow_file = self.data_path / "processed_cow_data.xlsx"
        if not cow_file.exists():
            logger.error(f"母牛数据文件不存在: {cow_file}")
            return pd.DataFrame()
            
        try:
            cow_df = pd.read_excel(cow_file)
            logger.info(f"成功加载 {len(cow_df)} 头母牛数据")
            
            # 确保关键字段存在
            required_fields = ['cow_id', 'sex', '是否在场', 'lac']
            missing_fields = [f for f in required_fields if f not in cow_df.columns]
            if missing_fields:
                logger.warning(f"母牛数据缺少字段: {missing_fields}")
            
            # 数据类型转换
            if 'cow_id' in cow_df.columns:
                cow_df['cow_id'] = cow_df['cow_id'].astype(str)
            
            # 计算衍生字段
            cow_df = self._calculate_derived_fields(cow_df)
            
            return cow_df
            
        except Exception as e:
            logger.error(f"加载母牛数据失败: {e}")
            return pd.DataFrame()
    
    def load_cow_index_scores(self) -> pd.DataFrame:
        """
        加载母牛指数得分
        
        Returns:
            母牛指数得分DataFrame
        """
        index_file = self.analysis_path / "processed_index_cow_index_scores.xlsx"
        if not index_file.exists():
            logger.warning(f"母牛指数文件不存在: {index_file}")
            return pd.DataFrame()
            
        try:
            index_df = pd.read_excel(index_file)
            if 'cow_id' in index_df.columns:
                index_df['cow_id'] = index_df['cow_id'].astype(str)
            logger.info(f"成功加载 {len(index_df)} 头母牛的指数得分")
            return index_df
        except Exception as e:
            logger.error(f"加载母牛指数失败: {e}")
            return pd.DataFrame()
    
    def load_bull_data(self) -> pd.DataFrame:
        """
        加载公牛数据（包括库存信息）
        
        Returns:
            公牛数据DataFrame
        """
        bull_file = self.data_path / "processed_bull_data.xlsx"
        if not bull_file.exists():
            logger.error(f"公牛数据文件不存在: {bull_file}")
            return pd.DataFrame()
            
        try:
            bull_df = pd.read_excel(bull_file)
            if 'bull_id' in bull_df.columns:
                bull_df['bull_id'] = bull_df['bull_id'].astype(str)
            logger.info(f"成功加载 {len(bull_df)} 头公牛数据")
            
            # 确保必要字段
            if '支数' not in bull_df.columns and 'inventory' in bull_df.columns:
                bull_df['支数'] = bull_df['inventory']
            
            return bull_df
        except Exception as e:
            logger.error(f"加载公牛数据失败: {e}")
            return pd.DataFrame()
    
    def load_bull_index_scores(self) -> pd.DataFrame:
        """
        加载公牛指数得分
        
        Returns:
            公牛指数得分DataFrame
        """
        index_file = self.analysis_path / "processed_index_bull_index_scores.xlsx"
        if not index_file.exists():
            logger.warning(f"公牛指数文件不存在: {index_file}")
            return pd.DataFrame()
            
        try:
            index_df = pd.read_excel(index_file)
            if 'bull_id' in index_df.columns:
                index_df['bull_id'] = index_df['bull_id'].astype(str)
            logger.info(f"成功加载 {len(index_df)} 头公牛的指数得分")
            return index_df
        except Exception as e:
            logger.error(f"加载公牛指数失败: {e}")
            return pd.DataFrame()
    
    def load_inbreeding_data(self) -> pd.DataFrame:
        """
        加载近交系数数据
        
        Returns:
            近交系数DataFrame
        """
        inbreeding_file = self.analysis_path / "inbreeding_final_result.xlsx"
        if not inbreeding_file.exists():
            logger.warning(f"近交系数文件不存在: {inbreeding_file}")
            return pd.DataFrame()
            
        try:
            inbreeding_df = pd.read_excel(inbreeding_file)
            # 确保ID是字符串
            if 'cow_id' in inbreeding_df.columns:
                inbreeding_df['cow_id'] = inbreeding_df['cow_id'].astype(str)
            if 'bull_id' in inbreeding_df.columns:
                inbreeding_df['bull_id'] = inbreeding_df['bull_id'].astype(str)
            logger.info(f"成功加载 {len(inbreeding_df)} 条近交系数记录")
            return inbreeding_df
        except Exception as e:
            logger.error(f"加载近交系数失败: {e}")
            return pd.DataFrame()
    
    def load_defect_genes_data(self) -> pd.DataFrame:
        """
        加载隐性基因数据
        
        Returns:
            隐性基因DataFrame
        """
        defect_file = self.analysis_path / "defect_genes_final_result.xlsx"
        if not defect_file.exists():
            logger.warning(f"隐性基因文件不存在: {defect_file}")
            return pd.DataFrame()
            
        try:
            defect_df = pd.read_excel(defect_file)
            # 确保ID是字符串
            if 'cow_id' in defect_df.columns:
                defect_df['cow_id'] = defect_df['cow_id'].astype(str)
            if 'bull_id' in defect_df.columns:
                defect_df['bull_id'] = defect_df['bull_id'].astype(str)
            logger.info(f"成功加载 {len(defect_df)} 条隐性基因记录")
            return defect_df
        except Exception as e:
            logger.error(f"加载隐性基因失败: {e}")
            return pd.DataFrame()
    
    def load_strategy_table(self) -> pd.DataFrame:
        """
        加载策略表
        
        Returns:
            策略表DataFrame
        """
        strategy_file = self.data_path / "策略表导入模板.xlsx"
        if not strategy_file.exists():
            logger.warning(f"策略表文件不存在: {strategy_file}")
            return pd.DataFrame()
            
        try:
            strategy_df = pd.read_excel(strategy_file)
            logger.info(f"成功加载策略表，包含 {len(strategy_df)} 条策略")
            return strategy_df
        except Exception as e:
            logger.error(f"加载策略表失败: {e}")
            return pd.DataFrame()
    
    def load_all_data(self) -> Dict[str, pd.DataFrame]:
        """
        加载所有数据
        
        Returns:
            包含所有数据的字典
        """
        data = {
            'cow_data': self.load_cow_data(),
            'cow_index': self.load_cow_index_scores(),
            'bull_data': self.load_bull_data(),
            'bull_index': self.load_bull_index_scores(),
            'inbreeding': self.load_inbreeding_data(),
            'defect_genes': self.load_defect_genes_data(),
            'strategy': self.load_strategy_table()
        }
        
        # 合并母牛数据和指数
        if not data['cow_data'].empty and not data['cow_index'].empty:
            data['cow_complete'] = data['cow_data'].merge(
                data['cow_index'][['cow_id', 'Combine Index Score']], 
                on='cow_id', 
                how='left'
            )
        else:
            data['cow_complete'] = data['cow_data']
        
        # 合并公牛数据和指数
        if not data['bull_data'].empty and not data['bull_index'].empty:
            data['bull_complete'] = data['bull_data'].merge(
                data['bull_index'][['bull_id', 'Index Score']], 
                on='bull_id', 
                how='left'
            )
        else:
            data['bull_complete'] = data['bull_data']
        
        return data
    
    def _calculate_derived_fields(self, cow_df: pd.DataFrame) -> pd.DataFrame:
        """
        计算衍生字段
        
        Args:
            cow_df: 母牛数据
            
        Returns:
            添加了衍生字段的DataFrame
        """
        today = datetime.now()
        
        # 计算日龄
        if 'birth_date' in cow_df.columns:
            cow_df['birth_date'] = pd.to_datetime(cow_df['birth_date'], errors='coerce')
            cow_df['日龄'] = (today - cow_df['birth_date']).dt.days
            cow_df['月龄'] = cow_df['日龄'] / 30.5
        
        # 计算DIM（仅对成母牛）
        if 'calving_date' in cow_df.columns:
            cow_df['calving_date'] = pd.to_datetime(cow_df['calving_date'], errors='coerce')
            # 只对已产犊的牛计算DIM
            mask = (cow_df['lac'] > 0) & cow_df['calving_date'].notna()
            cow_df.loc[mask, 'DIM_calc'] = (today - cow_df.loc[mask, 'calving_date']).dt.days
        
        return cow_df
    
    def validate_data(self, data: Dict[str, pd.DataFrame]) -> Dict[str, List[str]]:
        """
        验证数据完整性
        
        Args:
            data: 数据字典
            
        Returns:
            验证结果字典 {数据名: [问题列表]}
        """
        issues = {}
        
        # 验证母牛数据
        if 'cow_complete' in data and not data['cow_complete'].empty:
            cow_issues = []
            cow_df = data['cow_complete']
            
            # 检查必需字段
            required = ['cow_id', 'sex', '是否在场', 'lac']
            missing = [f for f in required if f not in cow_df.columns]
            if missing:
                cow_issues.append(f"缺少必需字段: {missing}")
            
            # 检查在场母牛数量
            if '是否在场' in cow_df.columns and 'sex' in cow_df.columns:
                available_cows = cow_df[(cow_df['是否在场'] == '是') & (cow_df['sex'] == '母')]
                if len(available_cows) == 0:
                    cow_issues.append("没有在场的母牛")
            
            if cow_issues:
                issues['母牛数据'] = cow_issues
        
        # 验证公牛数据
        if 'bull_complete' in data and not data['bull_complete'].empty:
            bull_issues = []
            bull_df = data['bull_complete']
            
            # 检查必需字段
            required = ['bull_id', '支数']
            missing = [f for f in required if f not in bull_df.columns]
            if missing:
                bull_issues.append(f"缺少必需字段: {missing}")
            
            # 检查有库存的公牛
            if '支数' in bull_df.columns:
                available_bulls = bull_df[bull_df['支数'] > 0]
                if len(available_bulls) == 0:
                    bull_issues.append("没有有库存的公牛")
            
            if bull_issues:
                issues['公牛数据'] = bull_issues
        
        return issues