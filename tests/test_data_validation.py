"""
测试数据验证功能

验证PPT生成的数据验证和错误处理功能
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import logging

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.report.data_validator import DataValidator

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_test_data():
    """创建测试数据（包含一些错误）"""
    
    # 1. 创建有问题的母牛数据
    cow_data = pd.DataFrame({
        'cow_id': ['CN0001', 'CN0002', 'CN0001', 'CN0004'],  # 有重复
        'birth_date': ['2020-01-01', '2025-12-31', '2019-05-15', '1985-01-01'],  # 有未来日期和过早日期
        '是否在场': ['是', '否', '在场', '是'],  # 有无效值
        'lac': [1, 2, 25, -1],  # 有超出范围的值
        'TPI': [2500, 6000, 2300, 'N/A']  # 有非数值
    })
    
    # 2. 创建有问题的公牛数据
    bull_data = pd.DataFrame({
        'NAAB': ['7HO13250', '7HO13250', '7HO14522', 'XX'],  # 有重复和无效值
        'TPI': [2800, 2750, -1000, 2600],
        'NM$': [700, 3000, 600, 500]  # 有超出范围的值
    })
    
    # 3. 创建有问题的配种记录
    breeding_data = pd.DataFrame({
        'BULL NAAB': ['7HO13250', '', '7HO14522', 'X'],  # 有空值和无效值
        '配种日期': ['2024-01-01', '2025-12-31', '2024-03-15', '2024-04-01'],  # 有未来日期
        '冻精类型': ['常规', '性控', '未知类型', '肉牛']  # 有无效值
    })
    
    # 4. 创建有问题的育种指数
    index_data = pd.DataFrame({
        'cow_id': ['CN0001', 'CN0002', 'CN0003'],
        '育种指数得分': [1500, 5000, -100]  # 有超出范围的值
    })
    
    # 5. 创建正常的数据用于对比
    normal_cow_data = pd.DataFrame({
        'cow_id': [f'CN{i:04d}' for i in range(1, 51)],
        'birth_date': pd.date_range(start='2020-01-01', periods=50, freq='7D'),
        '是否在场': ['是'] * 45 + ['否'] * 5,
        'lac': np.random.randint(0, 8, 50),
        'TPI': np.random.normal(2500, 300, 50)
    })
    
    return {
        'cow_data_bad': cow_data,
        'bull_data_bad': bull_data,
        'breeding_data_bad': breeding_data,
        'index_data_bad': index_data,
        'cow_data_good': normal_cow_data
    }


def test_validation():
    """测试数据验证功能"""
    
    # 创建验证器
    validator = DataValidator()
    
    # 创建测试数据
    test_data = create_test_data()
    
    logger.info("=== 测试有问题的数据验证 ===")
    
    # 1. 验证有问题的母牛数据
    logger.info("\n验证母牛数据（含错误）...")
    is_valid, errors = validator.validate_dataframe(test_data['cow_data_bad'], 'cow_data')
    logger.info(f"验证结果: {'通过' if is_valid else '失败'}")
    for error in errors:
        logger.info(f"  - {error}")
    
    # 2. 验证有问题的公牛数据
    logger.info("\n验证公牛数据（含错误）...")
    is_valid, errors = validator.validate_dataframe(test_data['bull_data_bad'], 'bull_traits')
    logger.info(f"验证结果: {'通过' if is_valid else '失败'}")
    for error in errors:
        logger.info(f"  - {error}")
    
    # 3. 验证有问题的配种记录
    logger.info("\n验证配种记录（含错误）...")
    is_valid, errors = validator.validate_dataframe(test_data['breeding_data_bad'], 'breeding_records')
    logger.info(f"验证结果: {'通过' if is_valid else '失败'}")
    for error in errors:
        logger.info(f"  - {error}")
    
    # 4. 验证有问题的育种指数
    logger.info("\n验证育种指数（含错误）...")
    is_valid, errors = validator.validate_dataframe(test_data['index_data_bad'], 'breeding_index')
    logger.info(f"验证结果: {'通过' if is_valid else '失败'}")
    for error in errors:
        logger.info(f"  - {error}")
    
    # 5. 验证正常的数据
    logger.info("\n=== 测试正常数据验证 ===")
    logger.info("\n验证正常母牛数据...")
    is_valid, errors = validator.validate_dataframe(test_data['cow_data_good'], 'cow_data')
    logger.info(f"验证结果: {'通过' if is_valid else '失败'}")
    if errors:
        for error in errors:
            logger.info(f"  - {error}")
    
    # 6. 测试验证报告生成
    logger.info("\n=== 生成验证报告 ===")
    validation_results = {
        '母牛数据（错误）': validator.validate_dataframe(test_data['cow_data_bad'], 'cow_data'),
        '公牛数据（错误）': validator.validate_dataframe(test_data['bull_data_bad'], 'bull_traits'),
        '配种记录（错误）': validator.validate_dataframe(test_data['breeding_data_bad'], 'breeding_records'),
        '育种指数（错误）': validator.validate_dataframe(test_data['index_data_bad'], 'breeding_index'),
        '母牛数据（正常）': validator.validate_dataframe(test_data['cow_data_good'], 'cow_data')
    }
    
    report = validator.generate_validation_report(validation_results)
    logger.info("\n" + report)
    
    # 7. 测试文件验证
    logger.info("\n=== 测试文件验证 ===")
    test_file = Path("test_file.xlsx")
    is_valid, error = validator.validate_file_exists(test_file)
    logger.info(f"不存在的文件验证: {error}")
    
    # 创建一个空文件测试
    test_file.touch()
    is_valid, error = validator.validate_file_exists(test_file)
    logger.info(f"空文件验证: {error}")
    test_file.unlink()  # 删除测试文件
    
    return True


def main():
    """主函数"""
    try:
        success = test_validation()
        if success:
            logger.info("\n数据验证测试成功！")
        else:
            logger.error("\n数据验证测试失败！")
    except Exception as e:
        logger.error(f"\n测试过程中出错: {str(e)}", exc_info=True)


if __name__ == "__main__":
    main()