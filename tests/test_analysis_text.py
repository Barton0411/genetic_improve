"""
测试分析文本生成功能

验证PPT分析文本自动生成功能
"""

import sys
from pathlib import Path
import pandas as pd
import logging

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.report.analysis_text_generator import AnalysisTextGenerator

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_analysis_text():
    """测试分析文本生成"""
    
    # 创建测试数据
    # 1. 系谱数据
    pedigree_data = pd.DataFrame({
        'cow_id': [f'CN{i:04d}' for i in range(1, 101)],
        'sire_identified': ['已识别'] * 85 + ['未识别'] * 15,
        'mgs_identified': ['已识别'] * 65 + ['未识别'] * 35,
        'mmgs_identified': ['已识别'] * 45 + ['未识别'] * 55
    })
    
    # 2. 母牛性状数据
    import numpy as np
    np.random.seed(42)
    
    cow_data = pd.DataFrame({
        'cow_id': [f'CN{i:04d}' for i in range(1, 201)],
        'birth_date': pd.date_range(start='2019-01-01', periods=200, freq='7D'),
        '是否在场': ['是'] * 180 + ['否'] * 20,
        'TPI': np.random.normal(2500, 300, 200),
        'NM$': np.random.normal(500, 100, 200),
        'MILK': np.random.normal(1000, 200, 200)
    })
    
    # 3. 育种指数数据
    index_data = pd.DataFrame({
        'cow_id': [f'CN{i:04d}' for i in range(1, 151)],
        '育种指数得分': np.random.normal(1500, 200, 150)
    })
    
    # 4. 配种记录数据
    breeding_data = pd.DataFrame({
        'BULL NAAB': ['7HO13250'] * 50 + ['7HO14522'] * 30 + ['14HO07770'] * 20 + 
                     ['200HO10123'] * 15 + ['7HO15421'] * 10,
        '冻精类型': ['常规'] * 75 + ['性控'] * 40 + ['肉牛'] * 10,
        '配种日期': pd.date_range(start='2024-01-01', periods=125, freq='3D')
    })
    
    # 5. 公牛性状数据
    bull_traits = pd.DataFrame({
        'NAAB': ['7HO13250', '7HO14522', '14HO07770', '200HO10123', '7HO15421'],
        'TPI': [2800, 2750, 2650, 2600, 2550],
        'NM$': [700, 650, 600, 550, 500]
    })
    
    # 创建文本生成器
    trait_translations = {
        'TPI': '综合性能指数',
        'NM$': '终生净效益值',
        'MILK': '产奶量'
    }
    
    text_generator = AnalysisTextGenerator(trait_translations)
    
    # 测试各种文本生成
    logger.info("\n=== 测试系谱分析文本生成 ===")
    pedigree_texts = text_generator.generate_pedigree_analysis_text(pedigree_data)
    for key, text in pedigree_texts.items():
        logger.info(f"{key}: {text}")
    
    logger.info("\n=== 测试遗传评估文本生成 ===")
    genetic_texts = text_generator.generate_genetic_evaluation_text(
        cow_data, ['TPI', 'NM$', 'MILK']
    )
    for key, text in genetic_texts.items():
        logger.info(f"{key}: {text}")
    
    logger.info("\n=== 测试育种指数文本生成 ===")
    index_texts = text_generator.generate_breeding_index_text(index_data)
    for key, text in index_texts.items():
        logger.info(f"{key}: {text}")
    
    logger.info("\n=== 测试公牛使用分析文本生成 ===")
    bull_texts = text_generator.generate_bull_usage_text(breeding_data, bull_traits)
    for key, text in bull_texts.items():
        logger.info(f"{key}: {text}")
    
    logger.info("\n=== 测试性状进展文本生成 ===")
    cow_data['birth_year'] = cow_data['birth_date'].dt.year
    progress_text = text_generator.generate_trait_progress_text(cow_data, 'TPI')
    logger.info(f"TPI进展: {progress_text}")
    
    return True


def main():
    """主函数"""
    try:
        success = test_analysis_text()
        if success:
            logger.info("\n分析文本生成测试成功！")
        else:
            logger.error("\n分析文本生成测试失败！")
    except Exception as e:
        logger.error(f"\n测试过程中出错: {str(e)}", exc_info=True)


if __name__ == "__main__":
    main()