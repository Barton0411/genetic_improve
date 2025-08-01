"""
数据验证器模块

负责验证PPT生成所需的数据完整性和正确性
"""

import logging
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class DataValidator:
    """数据验证器类"""
    
    def __init__(self):
        """初始化数据验证器"""
        # 定义必需的列
        self.required_columns = {
            'cow_data': ['cow_id', 'birth_date', '是否在场'],
            'bull_traits': ['NAAB'],
            'breeding_records': ['BULL NAAB', '配种日期', '冻精类型'],
            'breeding_index': ['cow_id', '育种指数得分'],
            'pedigree': ['cow_id', 'sire_identified']
        }
        
        # 定义数值范围
        self.value_ranges = {
            'TPI': (0, 5000),
            'NM$': (-1000, 2000),
            'MILK': (-5000, 10000),
            'FAT': (-200, 200),
            'PROT': (-100, 100),
            'SCS': (0, 5),
            'PL': (-10, 10),
            'DPR': (-10, 10),
            '育种指数得分': (0, 3000),
            'lac': (0, 20)
        }
        
        # 定义有效值列表
        self.valid_values = {
            '是否在场': ['是', '否', 'Y', 'N', 'Yes', 'No', True, False, 1, 0],
            '冻精类型': ['常规', '性控', '肉牛', '性控X', '性控Y'],
            'sex': ['公', '母', 'M', 'F', 'Male', 'Female'],
            'sire_identified': ['已识别', '未识别', True, False, 1, 0]
        }
    
    def validate_dataframe(self, df: pd.DataFrame, data_type: str) -> Tuple[bool, List[str]]:
        """
        验证数据框的完整性和正确性
        
        Args:
            df: 要验证的数据框
            data_type: 数据类型（cow_data, bull_traits等）
            
        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []
        
        if df is None:
            errors.append(f"{data_type}数据为空")
            return False, errors
            
        if df.empty:
            errors.append(f"{data_type}数据框为空")
            return False, errors
            
        # 1. 检查必需列
        if data_type in self.required_columns:
            missing_cols = []
            for col in self.required_columns[data_type]:
                if col not in df.columns:
                    missing_cols.append(col)
                    
            if missing_cols:
                errors.append(f"{data_type}缺少必需列: {', '.join(missing_cols)}")
                
        # 2. 检查数据类型
        errors.extend(self._check_data_types(df, data_type))
        
        # 3. 检查数值范围
        errors.extend(self._check_value_ranges(df))
        
        # 4. 检查有效值
        errors.extend(self._check_valid_values(df))
        
        # 5. 检查特定数据类型的规则
        if data_type == 'cow_data':
            errors.extend(self._validate_cow_data(df))
        elif data_type == 'breeding_records':
            errors.extend(self._validate_breeding_records(df))
        elif data_type == 'bull_traits':
            errors.extend(self._validate_bull_traits(df))
            
        return len(errors) == 0, errors
    
    def _check_data_types(self, df: pd.DataFrame, data_type: str) -> List[str]:
        """检查数据类型"""
        errors = []
        
        # 检查日期列
        date_columns = ['birth_date', '配种日期', 'Date', 'date']
        for col in date_columns:
            if col in df.columns:
                try:
                    # 尝试转换为日期
                    pd.to_datetime(df[col])
                except Exception as e:
                    errors.append(f"列{col}包含无效的日期值")
                    
        # 检查数值列
        numeric_columns = ['TPI', 'NM$', 'MILK', 'FAT', 'PROT', 'SCS', 'PL', 'DPR', 
                          '育种指数得分', 'lac']
        for col in numeric_columns:
            if col in df.columns:
                try:
                    pd.to_numeric(df[col])
                except Exception:
                    errors.append(f"列{col}包含非数值数据")
                    
        return errors
    
    def _check_value_ranges(self, df: pd.DataFrame) -> List[str]:
        """检查数值范围"""
        errors = []
        
        for col, (min_val, max_val) in self.value_ranges.items():
            if col in df.columns:
                try:
                    numeric_data = pd.to_numeric(df[col], errors='coerce')
                    out_of_range = numeric_data[(numeric_data < min_val) | (numeric_data > max_val)]
                    
                    if len(out_of_range) > 0:
                        errors.append(
                            f"列{col}有{len(out_of_range)}个值超出范围[{min_val}, {max_val}]"
                        )
                except Exception:
                    pass
                    
        return errors
    
    def _check_valid_values(self, df: pd.DataFrame) -> List[str]:
        """检查有效值"""
        errors = []
        
        for col, valid_vals in self.valid_values.items():
            if col in df.columns:
                invalid_vals = df[~df[col].isin(valid_vals)][col].unique()
                if len(invalid_vals) > 0:
                    errors.append(
                        f"列{col}包含无效值: {', '.join(map(str, invalid_vals[:5]))}"
                        f"{'...' if len(invalid_vals) > 5 else ''}"
                    )
                    
        return errors
    
    def _validate_cow_data(self, df: pd.DataFrame) -> List[str]:
        """验证母牛数据特定规则"""
        errors = []
        
        # 检查cow_id唯一性
        if 'cow_id' in df.columns:
            duplicates = df[df.duplicated(subset=['cow_id'], keep=False)]
            if len(duplicates) > 0:
                errors.append(f"发现{len(duplicates)}个重复的cow_id")
                
        # 检查出生日期合理性
        if 'birth_date' in df.columns:
            try:
                birth_dates = pd.to_datetime(df['birth_date'])
                future_dates = birth_dates[birth_dates > pd.Timestamp.now()]
                if len(future_dates) > 0:
                    errors.append(f"发现{len(future_dates)}个未来的出生日期")
                    
                very_old = birth_dates[birth_dates < pd.Timestamp('1990-01-01')]
                if len(very_old) > 0:
                    errors.append(f"发现{len(very_old)}个过早的出生日期（1990年之前）")
            except Exception:
                pass
                
        return errors
    
    def _validate_breeding_records(self, df: pd.DataFrame) -> List[str]:
        """验证配种记录特定规则"""
        errors = []
        
        # 检查配种日期合理性
        if '配种日期' in df.columns:
            try:
                breed_dates = pd.to_datetime(df['配种日期'])
                future_dates = breed_dates[breed_dates > pd.Timestamp.now()]
                if len(future_dates) > 0:
                    errors.append(f"发现{len(future_dates)}个未来的配种日期")
            except Exception:
                pass
                
        # 检查BULL NAAB格式
        if 'BULL NAAB' in df.columns:
            invalid_naab = df[df['BULL NAAB'].astype(str).str.len() < 3]['BULL NAAB']
            if len(invalid_naab) > 0:
                errors.append(f"发现{len(invalid_naab)}个无效的BULL NAAB编号")
                
        return errors
    
    def _validate_bull_traits(self, df: pd.DataFrame) -> List[str]:
        """验证公牛性状数据特定规则"""
        errors = []
        
        # 检查NAAB唯一性
        if 'NAAB' in df.columns:
            duplicates = df[df.duplicated(subset=['NAAB'], keep=False)]
            if len(duplicates) > 0:
                errors.append(f"发现{len(duplicates)}个重复的NAAB编号")
                
        return errors
    
    def validate_file_exists(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """
        验证文件是否存在
        
        Args:
            file_path: 文件路径
            
        Returns:
            (是否存在, 错误信息)
        """
        if not file_path.exists():
            return False, f"文件不存在: {file_path}"
            
        if not file_path.is_file():
            return False, f"路径不是文件: {file_path}"
            
        if file_path.stat().st_size == 0:
            return False, f"文件为空: {file_path}"
            
        return True, None
    
    def validate_all_required_files(self, output_folder: Path) -> Tuple[bool, List[str]]:
        """
        验证所有必需的文件是否存在
        
        Args:
            output_folder: 输出文件夹路径
            
        Returns:
            (是否全部存在, 缺失文件列表)
        """
        required_files = {
            '母牛数据': ['processed_cow_data.xlsx', '牛只信息.xlsx', 'cow_data.xlsx'],
            '公牛数据': ['processed_bull_data.xlsx', '公牛性状数据.xlsx', 'bull_data.xlsx'],
            '育种指数': ['processed_index_cow_index_scores.xlsx', '育种指数得分.xlsx'],
            '配种记录': ['配种记录.xlsx', 'breeding_records.xlsx']
        }
        
        missing_files = []
        
        for data_type, possible_files in required_files.items():
            found = False
            for filename in possible_files:
                if (output_folder / filename).exists():
                    found = True
                    break
                    
            if not found:
                missing_files.append(f"{data_type}: {', '.join(possible_files)}")
                
        return len(missing_files) == 0, missing_files
    
    def generate_validation_report(self, validation_results: Dict[str, Tuple[bool, List[str]]]) -> str:
        """
        生成验证报告
        
        Args:
            validation_results: 验证结果字典 {数据类型: (是否有效, 错误列表)}
            
        Returns:
            验证报告文本
        """
        report_lines = ["=== PPT数据验证报告 ===\n"]
        
        total_errors = 0
        for data_type, (is_valid, errors) in validation_results.items():
            report_lines.append(f"\n【{data_type}】")
            if is_valid:
                report_lines.append("✓ 数据验证通过")
            else:
                report_lines.append(f"✗ 发现{len(errors)}个问题:")
                for error in errors:
                    report_lines.append(f"  - {error}")
                total_errors += len(errors)
                
        report_lines.append(f"\n总计: 发现{total_errors}个数据问题")
        
        if total_errors == 0:
            report_lines.append("\n所有数据验证通过，可以生成PPT报告。")
        else:
            report_lines.append("\n请修正上述问题后再生成PPT报告。")
            
        return "\n".join(report_lines)