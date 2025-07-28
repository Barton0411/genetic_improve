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
    filename='test_processor.log',
    filemode='w'
)

# 导入需要测试的函数
try:
    from core.data.processor import preprocess_cow_data, process_cow_data_file
    logging.info("成功导入处理函数")
except ImportError as e:
    logging.error(f"导入错误: {e}")
    print(f"导入错误: {e}")
    print("请确保在正确的目录中运行此脚本")
    sys.exit(1)

def progress_callback(progress, message=None):
    """进度回调函数"""
    print(f"进度: {progress}%")
    if message:
        print(f"消息: {message}")

def test_preprocess_cow_data():
    """测试预处理母牛数据的函数"""
    logging.info("开始测试 preprocess_cow_data 函数")
    
    try:
        # 创建一个简单的测试DataFrame
        test_data = {
            '耳号': ['001', '002', '003', '004'],
            '品种': ['HO', 'HO', 'HO', 'HO'],
            '性别': ['母', '母', '公', '母'],
            '父亲号': ['123HO12345', '124HO67890', '125HO11111', '126HO22222'],
            '外祖父': ['127HO33333', '128HO44444', '129HO55555', '130HO66666'],
            '母亲号': ['005', '006', '007', '008'],
            '外曾外祖父': ['131HO77777', '132HO88888', '133HO99999', '134HO00000'],
            '胎次': [1, 2, 0, 3],
            '最近产犊日期': ['2023-01-01', '2023-02-02', '2023-03-03', '2023-04-04'],
            '牛只出生日期': ['2020-01-01', '2019-02-02', '2021-03-03', '2018-04-04'],
            '月龄': [36, 48, 24, 60],
            '本胎次配次': [1, 2, 0, 3],
            '本胎次奶厅高峰产量': [30, 35, 0, 40],
            '305奶量': [8000, 9000, 0, 10000],
            '泌乳天数': [100, 150, 0, 200],
            '繁育状态': ['空怀', '初检孕', '空怀', '复检孕']
        }
        
        df = pd.DataFrame(test_data)
        logging.info(f"测试数据创建成功, 形状: {df.shape}")
        
        # 调用预处理函数
        result_df = preprocess_cow_data(df, progress_callback=progress_callback)
        logging.info(f"预处理完成, 结果形状: {result_df.shape}")
        
        # 打印结果
        print("\n预处理结果预览:")
        print(result_df.head())
        logging.info("测试 preprocess_cow_data 函数成功")
        
        return True
    except Exception as e:
        error_trace = traceback.format_exc()
        logging.error(f"测试 preprocess_cow_data 函数失败: {e}")
        logging.error(error_trace)
        print(f"错误: {e}")
        print("详细错误信息已记录到日志文件中")
        return False

def test_process_cow_data_file(input_file_path, output_dir):
    """测试处理母牛数据文件的函数"""
    logging.info(f"开始测试 process_cow_data_file 函数")
    logging.info(f"输入文件: {input_file_path}")
    logging.info(f"输出目录: {output_dir}")
    
    try:
        # 确保输入文件存在
        input_path = Path(input_file_path)
        if not input_path.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_path}")
        
        # 确保输出目录存在
        project_path = Path(output_dir)
        if not project_path.exists():
            project_path.mkdir(parents=True, exist_ok=True)
            logging.info(f"创建输出目录: {project_path}")
        
        # 创建必要的子目录
        standardized_path = project_path / "standardized_data"
        raw_data_path = project_path / "raw_data"
        standardized_path.mkdir(parents=True, exist_ok=True)
        raw_data_path.mkdir(parents=True, exist_ok=True)
        
        # 复制输入文件到raw_data目录
        target_file = raw_data_path / "cow_data.xlsx"
        try:
            import shutil
            shutil.copy2(input_path, target_file)
            logging.info(f"复制输入文件到: {target_file}")
        except Exception as e:
            logging.error(f"复制文件失败: {e}")
            raise
        
        # 调用处理函数
        result_path = process_cow_data_file(target_file, project_path, progress_callback=progress_callback)
        
        logging.info(f"处理完成, 结果文件: {result_path}")
        print(f"\n处理结果已保存到: {result_path}")
        
        # 打印处理结果
        try:
            result_df = pd.read_excel(result_path)
            print(f"处理后数据形状: {result_df.shape}")
            print("\n处理后数据预览:")
            print(result_df.head())
        except Exception as e:
            logging.error(f"读取结果文件失败: {e}")
            print(f"无法读取结果文件: {e}")
        
        logging.info("测试 process_cow_data_file 函数成功")
        return True
    except Exception as e:
        error_trace = traceback.format_exc()
        logging.error(f"测试 process_cow_data_file 函数失败: {e}")
        logging.error(error_trace)
        print(f"错误: {e}")
        print("详细错误信息已记录到日志文件中")
        return False

if __name__ == "__main__":
    print("测试 processor.py 中的母牛数据处理功能")
    
    # 测试预处理函数
    print("\n=== 测试 preprocess_cow_data 函数 ===")
    test_preprocess_cow_data()
    
    # 测试文件处理函数
    print("\n=== 测试 process_cow_data_file 函数 ===")
    input_file = input("请输入母牛数据Excel文件路径(例如: D:\\projects\\mating\\genetic_projects\\旺生_2025_04_02_14_24\\raw_data\\cow_data.xlsx): ")
    output_dir = input("请输入测试输出目录(例如: D:\\projects\\mating\\genetic_projects\\test_output): ")
    
    if input_file and output_dir:
        test_process_cow_data_file(input_file, output_dir)
    else:
        print("未提供输入文件或输出目录，跳过文件处理测试")
    
    print("\n测试完成! 请查看 test_processor.log 获取详细日志。") 