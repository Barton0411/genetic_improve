"""
数据适配器模块

处理不同数据源的列名映射和数据格式转换
"""

import pandas as pd
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


class DataAdapter:
    """数据适配器类，处理列名映射和数据格式转换"""
    
    # 列名映射配置
    COLUMN_MAPPINGS = {
        'cow_id': ['cow_id', 'ID', 'Cow_ID', 'CowID', '牛号', '牛只编号'],
        'birth_date': ['birth_date', 'Birth_Date', 'BirthDate', '出生日期', 'birth_dt'],
        'lac': ['lac', 'LAC', 'Lactation', '胎次', 'lactation'],
        '是否在场': ['是否在场', 'InHerd', 'in_herd', '在场状态', 'status'],
        'sex': ['sex', 'Sex', 'Gender', '性别'],
        'sire_id': ['sire_id', 'Sire_ID', 'SireID', '父号', 'sire'],
        'dam_id': ['dam_id', 'Dam_ID', 'DamID', '母号', 'dam'],
        'NAAB': ['NAAB', 'Bull_NAAB', 'BullNAAB', '公牛号', 'bull_id', 'Bull_ID'],
        '配种日期': ['配种日期', 'breeding_date', 'Breeding_Date', 'breed_dt'],
        '冻精类型': ['冻精类型', 'semen_type', 'Semen_Type', 'SemenType'],
        '育种指数得分': ['育种指数得分', 'breeding_index', 'Index_Score', 'TPI_score'],
        # 性状列映射
        'TPI': ['TPI', 'tpi', 'Tpi'],
        'NM$': ['NM$', 'NM', 'net_merit', 'NetMerit'],
        'MILK': ['MILK', 'Milk', 'milk'],
        'FAT': ['FAT', 'Fat', 'fat'],
        'PROT': ['PROT', 'Prot', 'prot', 'Protein'],
        'SCS': ['SCS', 'scs', 'Scs'],
        'PL': ['PL', 'pl', 'Pl'],
        'DPR': ['DPR', 'dpr', 'Dpr']
    }
    
    @classmethod
    def standardize_columns(cls, df: pd.DataFrame, required_columns: Optional[List[str]] = None) -> pd.DataFrame:
        """
        标准化数据框的列名
        
        Args:
            df: 原始数据框
            required_columns: 需要的列名列表（标准名称）
            
        Returns:
            列名标准化后的数据框
        """
        if df is None or df.empty:
            return df
            
        # 复制数据框以避免修改原始数据
        result_df = df.copy()
        
        # 创建反向映射（从实际列名到标准列名）
        column_renames = {}
        
        for standard_name, variations in cls.COLUMN_MAPPINGS.items():
            for col in df.columns:
                if col in variations:
                    column_renames[col] = standard_name
                    break
                    
        # 重命名列
        if column_renames:
            result_df = result_df.rename(columns=column_renames)
            logger.info(f"列名映射: {column_renames}")
            
        # 检查必需的列
        if required_columns:
            missing_columns = []
            for col in required_columns:
                if col not in result_df.columns:
                    missing_columns.append(col)
                    
            if missing_columns:
                logger.warning(f"缺少必需的列: {missing_columns}")
                
        return result_df
    
    @classmethod
    def find_id_column(cls, df: pd.DataFrame) -> Optional[str]:
        """
        查找数据框中的ID列
        
        Args:
            df: 数据框
            
        Returns:
            找到的ID列名，如果没找到返回None
        """
        id_variations = cls.COLUMN_MAPPINGS.get('cow_id', [])
        
        for col in df.columns:
            if col in id_variations:
                return col
                
        return None
    
    @classmethod
    def merge_with_id_mapping(cls, df1: pd.DataFrame, df2: pd.DataFrame, 
                            left_id: Optional[str] = None, 
                            right_id: Optional[str] = None) -> pd.DataFrame:
        """
        使用ID列映射合并两个数据框
        
        Args:
            df1: 左侧数据框
            df2: 右侧数据框
            left_id: 左侧ID列名（如果为None，自动查找）
            right_id: 右侧ID列名（如果为None，自动查找）
            
        Returns:
            合并后的数据框
        """
        # 查找ID列
        if left_id is None:
            left_id = cls.find_id_column(df1)
            if left_id is None:
                raise ValueError("无法在左侧数据框中找到ID列")
                
        if right_id is None:
            right_id = cls.find_id_column(df2)
            if right_id is None:
                raise ValueError("无法在右侧数据框中找到ID列")
                
        logger.info(f"合并数据: 左侧ID列={left_id}, 右侧ID列={right_id}")
        
        # 执行合并
        return pd.merge(df1, df2, left_on=left_id, right_on=right_id, how='inner')
    
    @classmethod
    def convert_date_columns(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        转换日期列为标准格式
        
        Args:
            df: 数据框
            
        Returns:
            日期列转换后的数据框
        """
        date_columns = ['birth_date', '配种日期']
        
        for col in date_columns:
            if col in df.columns:
                try:
                    df[col] = pd.to_datetime(df[col])
                    logger.info(f"转换日期列: {col}")
                except Exception as e:
                    logger.warning(f"转换日期列失败 {col}: {str(e)}")
                    
        return df
    
    @classmethod
    def add_missing_columns(cls, df: pd.DataFrame, column_defaults: Dict[str, any]) -> pd.DataFrame:
        """
        添加缺失的列并设置默认值
        
        Args:
            df: 数据框
            column_defaults: 列名和默认值的字典
            
        Returns:
            添加缺失列后的数据框
        """
        for col, default_value in column_defaults.items():
            if col not in df.columns:
                df[col] = default_value
                logger.info(f"添加缺失列: {col} = {default_value}")
                
        return df