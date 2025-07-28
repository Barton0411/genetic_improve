"""
个体选配功能测试脚本
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.matching.individual_matcher import IndividualMatcher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_individual_matcher.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def create_test_data(test_project_path: Path):
    """创建测试数据"""
    logger.info("创建测试数据...")
    
    # 创建目录结构
    (test_project_path / "analysis_results").mkdir(parents=True, exist_ok=True)
    (test_project_path / "standardized_data").mkdir(parents=True, exist_ok=True)
    
    # 创建母牛指数数据
    cow_data = {
        'cow_id': ['COW001', 'COW002', 'COW003', 'COW004', 'COW005', 'COW006'],
        'group': ['后备牛第1周期+非性控', '后备牛第1周期+非性控', '后备牛第3周期+非性控', 
                 '难孕牛', '已孕牛', '成母牛A'],
        'sex': ['母'] * 6,
        '是否在场': ['是'] * 6,
        'lac': [0, 0, 0, 2, 3, 1],
        'age': [420, 450, 480, 800, 1200, 600],
        'sire': ['SIRE001', 'SIRE002', 'SIRE003', 'SIRE004', 'SIRE005', 'SIRE006'],
        'mgs': ['MGS001', 'MGS002', 'MGS003', 'MGS004', 'MGS005', 'MGS006'],
        'dam': ['DAM001', 'DAM002', 'DAM003', 'DAM004', 'DAM005', 'DAM006'],
        'mmgs': ['MMGS001', 'MMGS002', 'MMGS003', 'MMGS004', 'MMGS005', 'MMGS006'],
        'calving_date': pd.to_datetime(['2023-01-01', '2023-02-01', '2023-03-01', 
                                       '2022-06-01', '2021-12-01', '2022-09-01']),
        'birth_date': pd.to_datetime(['2022-01-01', '2022-02-01', '2022-03-01', 
                                     '2020-06-01', '2019-12-01', '2021-09-01']),
        'breed': ['荷斯坦'] * 6,
        'TPI_index': [2800, 2750, 2600, 2900, 2950, 2700]  # 权重指数
    }
    
    cow_df = pd.DataFrame(cow_data)
    cow_file = test_project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
    cow_df.to_excel(cow_file, index=False)
    logger.info(f"创建母牛数据: {cow_file}")
    
    # 创建备选公牛数据
    bull_data = {
        'bull_id': ['BULL001', 'BULL002', 'BULL003', 'BULL004', 'BULL005', 'BULL006'],
        'classification': ['常规', '常规', '性控', '性控', '常规', '性控'],
        '支数': [100, 80, 120, 90, 60, 150]
    }
    
    bull_df = pd.DataFrame(bull_data)
    bull_file = test_project_path / "standardized_data" / "processed_bull_data.xlsx"
    bull_df.to_excel(bull_file, index=False)
    logger.info(f"创建公牛数据: {bull_file}")
    
    # 创建选配报告数据
    report_data = {
        'cow_id': ['COW001', 'COW002', 'COW003', 'COW004', 'COW005', 'COW006'],
        '推荐常规冻精1选': ['BULL001', 'BULL002', 'BULL001', 'BULL005', 'BULL002', 'BULL001'],
        '推荐常规冻精2选': ['BULL002', 'BULL005', 'BULL002', 'BULL001', 'BULL005', 'BULL002'],
        '推荐常规冻精3选': ['BULL005', 'BULL001', 'BULL005', 'BULL002', 'BULL001', 'BULL005'],
        '推荐性控冻精1选': ['BULL003', 'BULL004', 'BULL006', 'BULL003', 'BULL004', 'BULL003'],
        '推荐性控冻精2选': ['BULL004', 'BULL006', 'BULL003', 'BULL006', 'BULL003', 'BULL004'],
        '推荐性控冻精3选': ['BULL006', 'BULL003', 'BULL004', 'BULL004', 'BULL006', 'BULL006'],
        '常规冻精1近交系数': ['2.5%', '1.8%', '2.1%', '3.0%', '2.8%', '2.3%'],
        '常规冻精2近交系数': ['1.9%', '2.2%', '1.7%', '2.4%', '2.1%', '1.8%'],
        '常规冻精3近交系数': ['2.8%', '2.5%', '2.9%', '1.6%', '2.7%', '2.6%'],
        '性控冻精1近交系数': ['2.1%', '2.3%', '1.9%', '2.7%', '2.0%', '2.4%'],
        '性控冻精2近交系数': ['2.6%', '1.7%', '2.8%', '2.2%', '2.5%', '1.9%'],
        '性控冻精3近交系数': ['1.8%', '2.9%', '2.4%', '1.5%', '1.6%', '2.7%'],
        '常规冻精1隐性基因情况': ['Safe', 'Safe', 'Safe', 'Safe', 'Safe', 'Safe'],
        '常规冻精2隐性基因情况': ['Safe', 'Safe', 'Safe', 'Safe', 'Safe', 'Safe'],
        '常规冻精3隐性基因情况': ['Safe', 'Safe', 'Safe', 'Safe', 'Safe', 'Safe'],
        '性控冻精1隐性基因情况': ['Safe', 'Safe', 'Safe', 'Safe', 'Safe', 'Safe'],
        '性控冻精2隐性基因情况': ['Safe', 'Safe', 'Safe', 'Safe', 'Safe', 'Safe'],
        '性控冻精3隐性基因情况': ['Safe', 'Safe', 'Safe', 'Safe', 'Safe', 'Safe']
    }
    
    report_df = pd.DataFrame(report_data)
    report_file = test_project_path / "analysis_results" / "individual_mating_report.xlsx"
    report_df.to_excel(report_file, index=False)
    logger.info(f"创建选配报告: {report_file}")
    
    return True

def test_individual_matcher():
    """测试个体选配功能"""
    logger.info("开始测试个体选配功能...")
    
    # 设置测试项目路径
    test_project_path = Path("test_matching_project")
    test_project_path.mkdir(exist_ok=True)
    
    try:
        # 创建测试数据
        if not create_test_data(test_project_path):
            logger.error("创建测试数据失败")
            return False
        
        # 创建个体选配器
        matcher = IndividualMatcher()
        
        # 加载数据
        logger.info("加载数据...")
        if not matcher.load_data(test_project_path):
            logger.error("数据加载失败")
            return False
        
        # 设置参数
        logger.info("设置选配参数...")
        semen_counts = {
            'BULL001': 100,
            'BULL002': 80,
            'BULL003': 120,
            'BULL004': 90,
            'BULL005': 60,
            'BULL006': 150
        }
        
        matcher.set_parameters(
            semen_counts=semen_counts,
            inbreeding_threshold=0.03125,
            control_defect_genes=True
        )
        
        # 执行选配
        logger.info("执行个体选配...")
        result_df = matcher.perform_matching()
        
        if result_df is None or result_df.empty:
            logger.error("选配结果为空")
            return False
        
        # 保存结果
        output_file = test_project_path / "analysis_results" / "individual_matching_results.xlsx"
        if matcher.save_results(result_df, output_file):
            logger.info(f"选配结果已保存: {output_file}")
        else:
            logger.error("保存结果失败")
            return False
        
        # 验证结果
        logger.info("验证选配结果...")
        logger.info(f"处理母牛数量: {len(result_df)}")
        logger.info(f"结果列数: {len(result_df.columns)}")
        
        # 检查必要的列是否存在
        required_columns = ['cow_id', '性控1选', '性控2选', '性控3选', '常规1选', '常规2选', '常规3选']
        missing_columns = [col for col in required_columns if col not in result_df.columns]
        if missing_columns:
            logger.error(f"缺少必要列: {missing_columns}")
            return False
        
        # 统计分配情况
        allocation_stats = {}
        for col in required_columns[1:]:  # 排除cow_id
            non_null_count = result_df[col].notna().sum()
            allocation_stats[col] = non_null_count
            logger.info(f"{col}: {non_null_count}/{len(result_df)} 头母牛已分配")
        
        # 显示前几行结果
        logger.info("选配结果示例:")
        logger.info("\n" + result_df[required_columns].head().to_string())
        
        logger.info("个体选配测试完成！")
        return True
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    finally:
        # 清理测试数据（可选）
        pass

if __name__ == "__main__":
    success = test_individual_matcher()
    if success:
        print("✅ 个体选配测试通过")
        sys.exit(0)
    else:
        print("❌ 个体选配测试失败")
        sys.exit(1) 