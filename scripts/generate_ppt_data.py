"""
手动生成PPT所需的数据文件

用于生成PPT报告所需的各种分析文件
"""

import sys
from pathlib import Path
import logging

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.report.data_preparation import DataPreparation
from core.report.ppt_generator import PPTGenerator

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def generate_missing_files(project_path: str):
    """生成缺失的PPT数据文件"""
    
    output_folder = Path(project_path) / "analysis_results"
    
    if not output_folder.exists():
        logger.error(f"项目文件夹不存在: {output_folder}")
        return False
        
    logger.info(f"开始为项目生成PPT数据文件: {project_path}")
    
    # 创建PPT生成器来加载数据
    ppt_generator = PPTGenerator(str(output_folder))
    
    # 加载源数据
    logger.info("加载源数据...")
    data_loaded = ppt_generator.load_source_data()
    
    if not data_loaded:
        logger.error("源数据加载失败")
        return False
        
    # 创建数据准备器
    data_prep = DataPreparation(str(output_folder))
    
    # 准备所有数据
    logger.info("开始准备PPT数据...")
    success = data_prep.prepare_all_data(
        parent_widget=None,
        cow_df=ppt_generator.cow_df,
        bull_traits=ppt_generator.bull_traits,
        selected_traits=ppt_generator.selected_traits,
        table_c=ppt_generator.table_c,
        merged_cow_traits=ppt_generator.merged_cow_traits,
        breeding_df=ppt_generator.breeding_df,
        cow_traits=ppt_generator.cow_traits,
        breeding_index_scores=ppt_generator.breeding_index_scores
    )
    
    if success:
        logger.info("PPT数据文件生成成功！")
        
        # 列出生成的文件
        logger.info("\n已生成的文件：")
        required_files = [
            "结果-指数排名结果.xlsx",
            "结果-母牛关键性状指数.xlsx",
            "结果-系谱识别情况分析.xlsx",
            "结果-牛群关键性状年度变化.xlsx",
            "在群牛只净利润值分布.xlsx",
            "结果-冻精使用趋势图.xlsx",
            "NM$_年份正态分布.png",
            "育种指数得分_年份正态分布.png"
        ]
        
        for filename in required_files:
            file_path = output_folder / filename
            if file_path.exists():
                logger.info(f"  ✅ {filename}")
            else:
                logger.warning(f"  ❌ {filename}")
                
        # 检查性状进展图文件夹
        progress_folder = output_folder / "结果-牛群关键性状进展图"
        if progress_folder.exists():
            chart_count = len(list(progress_folder.glob("*.png")))
            logger.info(f"  ✅ 结果-牛群关键性状进展图/ ({chart_count} 个图表)")
        else:
            logger.warning(f"  ❌ 结果-牛群关键性状进展图/")
            
    else:
        logger.error("PPT数据文件生成失败")
        
    return success


def main():
    """主函数"""
    # 使用指定的项目路径
    project_path = "/Users/Shared/Files From d.localized/projects/mating/genetic_projects/测试-基因组检测数据上传_2024_12_25_16_14"
    
    try:
        success = generate_missing_files(project_path)
        if success:
            logger.info("\n所有PPT数据文件已准备就绪，可以生成PPT报告了！")
        else:
            logger.error("\n数据文件生成失败，请检查错误信息")
    except Exception as e:
        logger.error(f"\n生成过程中出错: {str(e)}", exc_info=True)


if __name__ == "__main__":
    main()