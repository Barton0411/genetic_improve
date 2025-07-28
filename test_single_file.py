import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
import logging
import traceback

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='test_single_file.log',
    filemode='w'
)

def test_single_file(input_file_path):
    """直接测试单个Excel文件的读取和基本处理"""
    logging.info(f"开始测试文件: {input_file_path}")
    
    try:
        # 确保输入文件存在
        input_path = Path(input_file_path)
        if not input_path.exists():
            error_msg = f"输入文件不存在: {input_path}"
            logging.error(error_msg)
            print(error_msg)
            return False
        
        print(f"开始读取文件: {input_path}")
        
        # 尝试直接用pandas读取文件
        try:
            # 第一阶段：初步读取文件，不做任何转换
            df = pd.read_excel(input_path)
            logging.info(f"成功读取文件, 原始数据形状: {df.shape}")
            print(f"成功读取文件, 原始数据形状: {df.shape}")
            
            # 显示前几行数据和列名
            print("\n列名:")
            print(df.columns.tolist())
            print("\n数据预览:")
            print(df.head(3))
            
            # 检查数据类型
            print("\n数据类型:")
            print(df.dtypes)
            
            # 检查是否有空值
            print("\n空值统计:")
            print(df.isnull().sum())
            
            # 第二阶段：进行基本的数据转换，检查是否出错
            print("\n开始进行基本数据处理...")
            
            # 尝试转换数值列
            numeric_columns = ['胎次', '月龄', '本胎次配次', '本胎次奶厅高峰产量', '305奶量', '泌乳天数']
            for column in numeric_columns:
                if column in df.columns:
                    try:
                        # 转换为数值类型，无效值转为NaN
                        df[column] = pd.to_numeric(df[column], errors='coerce')
                        print(f"成功转换数值列: {column}")
                    except Exception as e:
                        print(f"转换数值列 {column} 时出错: {e}")
            
            # 尝试转换日期列
            date_columns = ['最近产犊日期', '牛只出生日期']
            for column in date_columns:
                if column in df.columns:
                    try:
                        df[column] = pd.to_datetime(df[column], errors='coerce')
                        print(f"成功转换日期列: {column}")
                    except Exception as e:
                        print(f"转换日期列 {column} 时出错: {e}")
            
            # 尝试处理ID列
            id_columns = ['耳号', '父亲号', '外祖父', '母亲号', '外曾外祖父']
            for column in id_columns:
                if column in df.columns:
                    try:
                        # 将列转换为字符串类型
                        df[column] = df[column].astype(str)
                        # 去除空格、小数点并清理
                        df[column] = df[column].str.replace(' ', '').str.replace('.', '').str.strip()
                        print(f"成功处理ID列: {column}")
                    except Exception as e:
                        print(f"处理ID列 {column} 时出错: {e}")
            
            # 检查处理后的数据状态
            print("\n处理后数据状态:")
            print(f"数据形状: {df.shape}")
            print("\n处理后数据预览:")
            print(df.head(3))
            
            logging.info("测试成功完成")
            print("\n基本测试成功完成，未发现明显错误")
            return True
            
        except Exception as e:
            error_trace = traceback.format_exc()
            logging.error(f"读取文件时出错: {e}")
            logging.error(error_trace)
            print(f"读取文件时出错: {e}")
            print(error_trace)
            return False
            
    except Exception as e:
        error_trace = traceback.format_exc()
        logging.error(f"处理过程中发生错误: {e}")
        logging.error(error_trace)
        print(f"处理过程中发生错误: {e}")
        print(error_trace)
        return False

if __name__ == "__main__":
    print("单文件测试工具 - 检查Excel文件是否能正确读取和处理")
    
    if len(sys.argv) > 1:
        # 从命令行参数获取文件路径
        input_file = sys.argv[1]
    else:
        # 手动输入文件路径
        input_file = input("请输入要测试的母牛数据Excel文件路径: ")
    
    if input_file:
        test_single_file(input_file)
    else:
        print("未提供输入文件，退出测试")
    
    print("\n测试完成! 请查看 test_single_file.log 获取详细日志。") 