"""
测试近交系数数据收集器
"""

from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.excel_report.data_collectors import collect_breeding_inbreeding_data
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_inbreeding_data_collection():
    """测试近交系数数据收集"""
    logger.info("=" * 60)
    logger.info("测试近交系数数据收集")
    logger.info("=" * 60)

    # 使用测试项目路径
    test_project = Path("/Users/bozhenwang/GeneticImprove/去青青_2025_10_08_15_59")
    analysis_folder = test_project / "analysis_results"

    # 收集数据
    data = collect_breeding_inbreeding_data(analysis_folder)

    # 检查数据结构
    logger.info(f"\n数据键: {list(data.keys())}")

    if 'all_years_distribution' in data:
        dist = data['all_years_distribution']
        logger.info(f"\n全部年份分布:")
        logger.info(f"  总配次: {dist['total']}")
        logger.info(f"  区间: {dist['intervals']}")
        logger.info(f"  数量: {dist['counts']}")
        logger.info(f"  占比: {[f'{r*100:.1f}%' for r in dist['ratios']]}")
        logger.info(f"  风险等级: {dist['risk_levels']}")

    if 'recent_12m_distribution' in data:
        dist = data['recent_12m_distribution']
        logger.info(f"\n近12个月分布:")
        logger.info(f"  总配次: {dist['total']}")
        logger.info(f"  数量: {dist['counts']}")
        logger.info(f"  占比: {[f'{r*100:.1f}%' for r in dist['ratios']]}")

    if 'date_range' in data:
        logger.info(f"\n日期范围: {data['date_range']}")

    if 'yearly_trend' in data:
        logger.info(f"\n按年份趋势（共{len(data['yearly_trend'])}年）:")
        for year_data in data['yearly_trend']:
            logger.info(f"  {year_data['year']}: "
                       f"配次{year_data['total_count']}, "
                       f"平均{year_data['avg_inbreeding']*100:.2f}%, "
                       f"高风险{year_data['high_risk_count']}次({year_data['high_risk_ratio']*100:.1f}%)")

    logger.info("\n✓ 数据收集测试通过")
    return data


if __name__ == "__main__":
    try:
        data = test_inbreeding_data_collection()
        sys.exit(0 if data else 1)
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        sys.exit(1)
