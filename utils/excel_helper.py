# utils/excel_helper.py
"""
Excel文件保存工具函数
确保保存的Excel文件中母牛号等ID字段保持为字符串格式
"""

import pandas as pd
from pathlib import Path
from typing import Union


def save_dataframe_to_excel(
    df: pd.DataFrame,
    output_path: Union[str, Path],
    sheet_name: str = 'Sheet1',
    index: bool = False,
    **kwargs
) -> None:
    """
    保存DataFrame到Excel文件，自动确保ID字段为字符串格式

    Args:
        df: 要保存的DataFrame
        output_path: 输出文件路径
        sheet_name: 工作表名称，默认为'Sheet1'
        index: 是否保存索引，默认False
        **kwargs: 传递给to_excel的其他参数

    功能:
        自动将以下列转换为字符串类型：
        - cow_id (母牛号)
        - 母牛号
        - bull_id (公牛号)
        - 公牛号
        - sire (父号)
        - dam (母号)
        - mgs (外祖父号)
        - mgd (外祖母号)
        - mmgs (外曾祖父号)
    """
    # 创建副本避免修改原始数据
    df_copy = df.copy()

    # 需要转换为字符串的列名列表
    id_columns = [
        'cow_id', '母牛号', '耳号',
        'bull_id', '公牛号', 'NAAB',
        'sire', '父号', '父亲号',
        'dam', '母号', '母亲号',
        'mgs', '外祖父', '外祖父号',
        'mgd', '外祖母', '外祖母号',
        'mmgs', '外曾祖父', '外曾祖父号'
    ]

    # 转换存在的列为字符串类型
    for col in id_columns:
        if col in df_copy.columns:
            # 先将NaN保持为空，其他值转为字符串
            df_copy[col] = df_copy[col].apply(
                lambda x: str(int(x)) if pd.notna(x) and isinstance(x, (int, float)) and x == int(x)
                else (str(x) if pd.notna(x) else x)
            )

    # 保存到Excel
    output_path = Path(output_path)
    df_copy.to_excel(output_path, sheet_name=sheet_name, index=index, **kwargs)


def save_dataframe_with_writer(
    df: pd.DataFrame,
    writer: pd.ExcelWriter,
    sheet_name: str,
    index: bool = False,
    **kwargs
) -> None:
    """
    使用ExcelWriter保存DataFrame，自动确保ID字段为字符串格式

    Args:
        df: 要保存的DataFrame
        writer: ExcelWriter对象
        sheet_name: 工作表名称
        index: 是否保存索引，默认False
        **kwargs: 传递给to_excel的其他参数

    使用示例:
        with pd.ExcelWriter('output.xlsx') as writer:
            save_dataframe_with_writer(df1, writer, 'Sheet1')
            save_dataframe_with_writer(df2, writer, 'Sheet2')
    """
    # 创建副本避免修改原始数据
    df_copy = df.copy()

    # 需要转换为字符串的列名列表
    id_columns = [
        'cow_id', '母牛号', '耳号',
        'bull_id', '公牛号', 'NAAB',
        'sire', '父号', '父亲号',
        'dam', '母号', '母亲号',
        'mgs', '外祖父', '外祖父号',
        'mgd', '外祖母', '外祖母号',
        'mmgs', '外曾祖父', '外曾祖父号'
    ]

    # 转换存在的列为字符串类型
    for col in id_columns:
        if col in df_copy.columns:
            # 先将NaN保持为空，其他值转为字符串
            df_copy[col] = df_copy[col].apply(
                lambda x: str(int(x)) if pd.notna(x) and isinstance(x, (int, float)) and x == int(x)
                else (str(x) if pd.notna(x) else x)
            )

    # 保存到ExcelWriter
    df_copy.to_excel(writer, sheet_name=sheet_name, index=index, **kwargs)
