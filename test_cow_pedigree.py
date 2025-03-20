#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试母牛系谱库的构建和合并功能
"""

import logging
import sys
from pathlib import Path
import pandas as pd

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('cow_pedigree_test.log')
    ]
)

# 导入系谱库管理器
from core.inbreeding.pedigree_database import PedigreeDatabase
from core.data.update_manager import LOCAL_DB_PATH, PEDIGREE_CACHE_PATH

def create_test_cow_data(output_path: Path):
    """创建测试用的母牛数据"""
    # 创建测试数据
    data = {
        'cow_id': ['Cow001', 'Cow002', 'Cow003', 'Cow004', 'Cow005'],
        'sire': ['Bull001', '001HO12345', 'Bull003', 'Bull004', ''],
        'dam': ['Cow006', 'Cow007', '', 'Cow008', 'Cow009'],
        'mgs': ['Bull005', 'Bull006', '', 'Bull007', 'Bull008'],
        'mgd': ['Cow010', '', '', 'Cow011', ''],
        'mmgs': ['Bull009', '', '', 'Bull010', '']
    }
    
    # 创建DataFrame
    df = pd.DataFrame(data)
    
    # 确保目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 保存为Excel文件
    df.to_excel(output_path, index=False)
    logging.info(f"测试母牛数据已保存到: {output_path}")
    
    return output_path

def progress_callback(value, message):
    """进度回调函数"""
    if isinstance(value, int):
        progress = f"{value}%"
    else:
        progress = "进行中"
    logging.info(f"进度: {progress} - {message}")
    return True

def test_cow_pedigree_building():
    """测试母牛系谱库的构建和合并功能"""
    # 步骤1: 创建测试数据
    test_data_dir = Path("test_data")
    test_data_dir.mkdir(exist_ok=True)
    cow_data_path = test_data_dir / "test_cow_data.xlsx"
    create_test_cow_data(cow_data_path)
    
    # 步骤2: 初始化系谱库管理器
    pedigree_db = PedigreeDatabase(LOCAL_DB_PATH, PEDIGREE_CACHE_PATH)
    
    # 步骤3: 加载现有系谱库
    pedigree = pedigree_db.load_pedigree()
    initial_count = len(pedigree)
    logging.info(f"初始系谱库中有{initial_count}个节点")
    
    # 步骤4: 构建母牛系谱库并合并
    pedigree_db.build_cow_pedigree(
        cow_data_path=cow_data_path,
        progress_callback=progress_callback,
        export_temp_file=True,
        export_merged_file=True
    )
    
    # 步骤5: 检查结果
    final_count = len(pedigree_db.pedigree)
    logging.info(f"合并后系谱库中有{final_count}个节点，新增{final_count - initial_count}个节点")
    
    # 检查生成的文件
    temp_file = cow_data_path.parent / "temp_cow_pedigree.txt"
    merged_file = cow_data_path.parent / "merged_pedigree.txt"
    
    if temp_file.exists():
        logging.info(f"临时母牛系谱文件已生成: {temp_file}")
        with open(temp_file, 'r') as f:
            lines = f.readlines()
            logging.info(f"临时母牛系谱文件内容预览 (前5行):")
            for i, line in enumerate(lines[:5]):
                logging.info(f"  {line.strip()}")
    
    if merged_file.exists():
        logging.info(f"合并系谱文件已生成: {merged_file}")
        with open(merged_file, 'r') as f:
            lines = f.readlines()
            logging.info(f"合并系谱文件内容预览 (前5行):")
            for i, line in enumerate(lines[:5]):
                logging.info(f"  {line.strip()}")
    
    return pedigree_db

if __name__ == "__main__":
    logging.info("开始测试母牛系谱库的构建和合并功能")
    try:
        pedigree_db = test_cow_pedigree_building()
        logging.info("测试完成")
    except Exception as e:
        logging.error(f"测试过程中发生错误: {e}")
        raise 