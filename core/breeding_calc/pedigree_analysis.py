"""
系谱识别情况分析模块
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Optional, Tuple
from sqlalchemy import create_engine, text

from core.data.update_manager import LOCAL_DB_PATH

logger = logging.getLogger(__name__)

class PedigreeAnalysis:
    """系谱识别情况分析"""
    
    def __init__(self):
        self.db_engine = None
        self.bull_library_naab_dict = {}
        self.bull_library_reg_dict = {}
        
    def init_db_connection(self) -> bool:
        """初始化数据库连接"""
        try:
            self.db_engine = create_engine(f'sqlite:///{LOCAL_DB_PATH}')
            return True
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return False
            
    def load_bull_library(self):
        """加载公牛库数据"""
        if not self.db_engine:
            self.init_db_connection()
            
        try:
            with self.db_engine.connect() as conn:
                # 读取所有公牛数据
                result = conn.execute(text("SELECT * FROM bull_library"))
                
                for row in result:
                    data = dict(row._mapping)
                    # 存储NAAB号索引
                    if data.get('BULL NAAB'):
                        self.bull_library_naab_dict[data['BULL NAAB']] = data
                    # 存储REG号索引
                    if data.get('BULL REG'):
                        self.bull_library_reg_dict[data['BULL REG']] = data
                        
            logger.info(f"加载公牛库完成: NAAB {len(self.bull_library_naab_dict)}头, REG {len(self.bull_library_reg_dict)}头")
            
        except Exception as e:
            logger.error(f"加载公牛库失败: {e}")
            
    def check_bull_exists(self, bull_id: str) -> bool:
        """检查公牛是否存在于数据库中"""
        if pd.isna(bull_id) or bull_id == '':
            return False
            
        bull_id = str(bull_id).strip()
        
        # 检查NAAB或REG
        return bull_id in self.bull_library_naab_dict or bull_id in self.bull_library_reg_dict
        
    def analyze_pedigree_completeness(self, cow_df: pd.DataFrame, project_path: Path) -> pd.DataFrame:
        """分析系谱完整性"""
        
        # 加载公牛库
        self.load_bull_library()
        
        # 复制数据避免修改原始数据
        df = cow_df.copy()
        
        # 添加出生年份
        if 'birth_date' in df.columns:
            df['birth_year'] = pd.to_datetime(df['birth_date'], errors='coerce').dt.year
        else:
            df['birth_year'] = pd.NA
            
        # 添加识别状态列
        df['sire_identified'] = df['sire'].apply(
            lambda x: '已识别' if self.check_bull_exists(x) else '未识别'
        )
        df['mgs_identified'] = df['mgs'].apply(
            lambda x: '已识别' if self.check_bull_exists(x) else '未识别'
        )
        df['mmgs_identified'] = df['mmgs'].apply(
            lambda x: '已识别' if self.check_bull_exists(x) else '未识别'
        )
        
        # 添加性别限制，排除公牛
        df = df[df['sex'] != '公']
        
        # 获取最大出生年份
        max_birth_year = df['birth_year'].max()
        if pd.isna(max_birth_year):
            max_birth_year = pd.Timestamp.now().year
            
        # 创建出生年份分组
        bins = [-float('inf')] + list(range(int(max_birth_year)-4, int(max_birth_year))) + [float('inf')]
        labels = [f'{int(max_birth_year)-4}年及以前'] + [str(year) for year in range(int(max_birth_year)-3, int(max_birth_year)+1)]
        
        df['birth_year_group'] = pd.cut(
            df['birth_year'],
            bins=bins,
            labels=labels
        )
        
        # 创建分析函数
        def analyze_group(group):
            total = len(group)
            sire_identified = (group['sire_identified'] == '已识别').sum()
            mgs_identified = (group['mgs_identified'] == '已识别').sum()
            mmgs_identified = (group['mmgs_identified'] == '已识别').sum()
            
            return pd.Series({
                '头数': total,
                '父号可识别头数': sire_identified,
                '父号识别率': sire_identified / total if total > 0 else 0,
                '外祖父可识别头数': mgs_identified,
                '外祖父识别率': mgs_identified / total if total > 0 else 0,
                '外曾外祖父可识别头数': mmgs_identified,
                '外曾外祖父识别率': mmgs_identified / total if total > 0 else 0,
            })
            
        # 生成分析结果
        results = []
        
        # 按是否在场分组
        for in_herd in df['是否在场'].unique():
            df_in_herd = df[df['是否在场'] == in_herd]
            
            # 按年份分组分析
            year_result = df_in_herd.groupby('birth_year_group').apply(analyze_group).reset_index()
            year_result['是否在场'] = in_herd
            results.append(year_result)
            
            # 添加小计行
            subtotal = df_in_herd.pipe(analyze_group)
            subtotal = pd.DataFrame(subtotal).T.reset_index(drop=True)
            subtotal['birth_year_group'] = '合计'
            subtotal['是否在场'] = in_herd
            results.append(subtotal)
            
            # 添加空行
            empty_row = pd.DataFrame({'是否在场': [''], 'birth_year_group': ['']})
            results.append(empty_row)
            
        # 合并所有结果
        final_result = pd.concat(results, ignore_index=True)
        
        # 重新排序列
        final_result = final_result[[
            '是否在场', 'birth_year_group', '头数', 
            '父号可识别头数', '父号识别率', 
            '外祖父可识别头数', '外祖父识别率', 
            '外曾外祖父可识别头数', '外曾外祖父识别率'
        ]]
        
        # 格式化百分比列
        percentage_columns = ['父号识别率', '外祖父识别率', '外曾外祖父识别率']
        for col in percentage_columns:
            final_result[col] = final_result[col].apply(lambda x: f"{x:.2%}" if pd.notnull(x) else '')
            
        logger.info("系谱识别情况分析完成")
        return final_result