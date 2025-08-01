"""
PPT生成功能测试脚本

用于测试PPT生成的完整流程
"""

import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# 添加项目路径到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.report.ppt_generator import PPTGenerator
from core.report.data_preparation import DataPreparation

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_test_data(output_folder: Path):
    """创建测试数据文件"""
    logger.info("开始创建测试数据...")
    
    # 1. 创建牛只信息
    n_cows = 200
    cow_df = pd.DataFrame({
        'cow_id': [f'COW{i:04d}' for i in range(1, n_cows + 1)],
        'birth_date': [datetime.now() - timedelta(days=np.random.randint(365, 3650)) for _ in range(n_cows)],
        'lac': np.random.choice([0, 1, 2, 3, 4], n_cows),
        '是否在场': np.random.choice(['是', '否'], n_cows, p=[0.8, 0.2]),
        'sex': ['母'] * n_cows
    })
    cow_df.to_excel(output_folder / '牛只信息.xlsx', index=False)
    logger.info("创建牛只信息完成")
    
    # 2. 创建公牛性状数据
    n_bulls = 50
    bull_traits = pd.DataFrame({
        'NAAB': [f'BULL{i:03d}' for i in range(1, n_bulls + 1)],
        'TPI': np.random.normal(2500, 200, n_bulls),
        'NM$': np.random.normal(600, 150, n_bulls),
        'MILK': np.random.normal(1000, 300, n_bulls),
        'FAT': np.random.normal(50, 15, n_bulls),
        'PROT': np.random.normal(40, 10, n_bulls),
        'SCS': np.random.normal(2.8, 0.3, n_bulls),
        'PL': np.random.normal(5, 2, n_bulls),
        'DPR': np.random.normal(0, 2, n_bulls)
    })
    bull_traits.to_excel(output_folder / '公牛性状数据.xlsx', index=False)
    logger.info("创建公牛性状数据完成")
    
    # 3. 创建系谱信息
    table_c = cow_df.copy()
    table_c['sire_id'] = [f'SIRE{np.random.randint(1, 30):03d}' if np.random.random() > 0.1 else '' for _ in range(n_cows)]
    table_c['dam_id'] = [f'DAM{np.random.randint(1, 100):04d}' if np.random.random() > 0.05 else '' for _ in range(n_cows)]
    table_c['birth_year'] = table_c['birth_date'].dt.year
    table_c['sire_identified'] = ['已识别' if sid else '未识别' for sid in table_c['sire_id']]
    table_c['mgs_identified'] = np.random.choice(['已识别', '未识别'], n_cows, p=[0.7, 0.3])
    table_c['mmgs_identified'] = np.random.choice(['已识别', '未识别'], n_cows, p=[0.5, 0.5])
    table_c.to_excel(output_folder / '系谱信息.xlsx', index=False)
    logger.info("创建系谱信息完成")
    
    # 4. 创建母牛性状数据
    cow_traits = pd.DataFrame({
        'ID': cow_df['cow_id'],
        'TPI': np.random.normal(2400, 250, n_cows),
        'NM$': np.random.normal(500, 200, n_cows),
        'MILK': np.random.normal(800, 400, n_cows),
        'FAT': np.random.normal(45, 20, n_cows),
        'PROT': np.random.normal(35, 15, n_cows),
        'SCS': np.random.normal(2.9, 0.4, n_cows),
        'PL': np.random.normal(4, 2.5, n_cows),
        'DPR': np.random.normal(-0.5, 2.5, n_cows)
    })
    cow_traits.to_excel(output_folder / '母牛性状数据.xlsx', index=False)
    logger.info("创建母牛性状数据完成")
    
    # 5. 创建配种记录
    n_breedings = 500
    breeding_df = pd.DataFrame({
        'cow_id': np.random.choice(cow_df['cow_id'], n_breedings),
        '配种日期': [datetime.now() - timedelta(days=np.random.randint(1, 730)) for _ in range(n_breedings)],
        'BULL NAAB': np.random.choice(bull_traits['NAAB'], n_breedings),
        '冻精类型': np.random.choice(['普通冻精', '性控冻精'], n_breedings, p=[0.6, 0.4])
    })
    breeding_df.to_excel(output_folder / '配种记录.xlsx', index=False)
    logger.info("创建配种记录完成")
    
    # 6. 创建育种指数得分
    breeding_index_scores = pd.DataFrame({
        'cow_id': cow_df['cow_id'],
        '育种指数得分': np.random.normal(100, 15, n_cows)
    })
    breeding_index_scores.to_excel(output_folder / '育种指数得分.xlsx', index=False)
    logger.info("创建育种指数得分完成")
    
    # 7. 创建合并的母牛性状数据
    merged_cow_traits = cow_df.merge(cow_traits, left_on='cow_id', right_on='ID', how='left')
    merged_cow_traits['育种指数得分'] = breeding_index_scores['育种指数得分']
    merged_cow_traits.to_excel(output_folder / '母牛关键性状合并.xlsx', index=False)
    logger.info("创建合并的母牛性状数据完成")
    
    # 8. 创建选中性状列表
    selected_traits = ['TPI', 'NM$', 'MILK', 'FAT', 'PROT', 'SCS', 'PL', 'DPR']
    with open(output_folder / 'selected_traits_key_traits.txt', 'w', encoding='utf-8') as f:
        for trait in selected_traits:
            f.write(trait + '\n')
    logger.info("创建选中性状列表完成")
    

def test_data_preparation(output_folder: Path):
    """测试数据准备功能"""
    logger.info("开始测试数据准备功能...")
    
    data_prep = DataPreparation(str(output_folder))
    
    # 检查文件
    all_ready, missing_files = data_prep.check_all_files()
    logger.info(f"文件检查结果: 全部就绪={all_ready}")
    if not all_ready:
        logger.info(f"缺失文件: {missing_files}")
    
    # 验证数据文件
    validation_results = data_prep.validate_data_files()
    logger.info("数据文件验证结果:")
    for file, is_valid in validation_results.items():
        logger.info(f"  {file}: {'有效' if is_valid else '无效'}")
    

def test_ppt_generation(output_folder: Path):
    """测试PPT生成功能"""
    logger.info("开始测试PPT生成功能...")
    
    # 创建PPT生成器
    ppt_generator = PPTGenerator(str(output_folder), username="测试用户")
    
    # 测试模板查找
    template = ppt_generator.find_template()
    logger.info(f"找到模板: {template}")
    
    # 测试数据加载
    data_loaded = ppt_generator.load_source_data()
    logger.info(f"数据加载成功: {data_loaded}")
    
    # 测试PPT生成（不使用GUI）
    try:
        # 设置牧场名称
        ppt_generator.farm_name = "测试牧场"
        
        # 准备数据
        data_ready = ppt_generator.prepare_data(parent_widget=None)
        logger.info(f"数据准备完成: {data_ready}")
        
        if data_ready:
            # 创建PPT
            prs = ppt_generator.create_presentation()
            logger.info("PPT创建成功")
            
            # 生成各部分（简化版，不使用进度对话框）
            ppt_generator.slide_generators['title'].create_title_slide(prs, ppt_generator.farm_name, ppt_generator.username)
            logger.info("标题页创建成功")
            
            ppt_generator.slide_generators['toc'].create_toc_slide(prs)
            logger.info("目录页创建成功")
            
            # 保存PPT
            output_path = output_folder / "测试牧场遗传改良项目专项服务报告.pptx"
            prs.save(str(output_path))
            logger.info(f"PPT保存成功: {output_path}")
            
            return True
            
    except Exception as e:
        logger.error(f"PPT生成失败: {str(e)}")
        return False


def main():
    """主测试函数"""
    # 创建测试输出文件夹
    test_folder = Path("test_output")
    test_folder.mkdir(exist_ok=True)
    
    # 创建分析结果文件夹
    analysis_folder = test_folder / "analysis_results"
    analysis_folder.mkdir(exist_ok=True)
    
    logger.info(f"测试文件夹: {analysis_folder.absolute()}")
    
    # 1. 创建测试数据
    create_test_data(analysis_folder)
    
    # 2. 测试数据准备
    test_data_preparation(analysis_folder)
    
    # 3. 测试PPT生成
    success = test_ppt_generation(analysis_folder)
    
    if success:
        logger.info("测试完成！PPT生成成功。")
    else:
        logger.error("测试失败！请检查错误日志。")
    

if __name__ == "__main__":
    main()