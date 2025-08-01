"""
使用真实项目数据测试PPT生成

测试PPT生成功能是否能正确处理实际项目数据
"""

import sys
from pathlib import Path
import logging

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.report.ppt_generator import PPTGenerator

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_real_project():
    """使用真实项目测试PPT生成"""
    
    # 使用测试项目路径
    project_path = Path("/Users/Shared/Files From d.localized/projects/mating/genetic_projects/测试-基因组检测数据上传_2024_12_25_16_14")
    output_folder = project_path / "analysis_results"
    
    if not output_folder.exists():
        logger.error(f"项目文件夹不存在: {output_folder}")
        return False
        
    logger.info(f"使用项目: {project_path}")
    
    # 创建PPT生成器
    ppt_generator = PPTGenerator(str(output_folder), username="测试用户")
    
    # 设置牧场名称
    ppt_generator.farm_name = "测试牧场"
    
    # 测试数据加载
    logger.info("开始加载数据...")
    data_loaded = ppt_generator.load_source_data()
    
    if data_loaded:
        logger.info("数据加载成功！")
        
        # 检查加载的数据
        if ppt_generator.cow_df is not None:
            logger.info(f"母牛数据: {len(ppt_generator.cow_df)} 条记录")
            logger.info(f"母牛数据列: {list(ppt_generator.cow_df.columns)[:10]}...")
            
        if ppt_generator.bull_traits is not None:
            logger.info(f"公牛数据: {len(ppt_generator.bull_traits)} 条记录")
            logger.info(f"公牛数据列: {list(ppt_generator.bull_traits.columns)[:10]}...")
            
        if ppt_generator.breeding_index_scores is not None:
            logger.info(f"育种指数: {len(ppt_generator.breeding_index_scores)} 条记录")
            logger.info(f"育种指数列: {list(ppt_generator.breeding_index_scores.columns)}")
            
        # 尝试生成PPT
        logger.info("开始生成PPT...")
        try:
            # 准备数据
            data_ready = ppt_generator.prepare_data(parent_widget=None)
            
            if data_ready:
                logger.info("数据准备完成！")
                
                # 创建PPT
                prs = ppt_generator.create_presentation()
                
                # 生成标题页
                ppt_generator.slide_generators['title'].create_title_slide(
                    prs, ppt_generator.farm_name, ppt_generator.username
                )
                logger.info("标题页创建成功")
                
                # 生成目录页
                ppt_generator.slide_generators['toc'].create_toc_slide(prs)
                logger.info("目录页创建成功")
                
                # 保存PPT
                output_path = output_folder / f"{ppt_generator.farm_name}PPT测试.pptx"
                prs.save(str(output_path))
                logger.info(f"PPT保存成功: {output_path}")
                
                return True
            else:
                logger.error("数据准备失败")
                return False
                
        except Exception as e:
            logger.error(f"生成PPT时出错: {str(e)}", exc_info=True)
            return False
            
    else:
        logger.error("数据加载失败")
        
        # 列出实际存在的文件
        logger.info("项目中的文件:")
        for file in output_folder.glob("*.xlsx"):
            logger.info(f"  - {file.name}")
            
        return False


def main():
    """主函数"""
    success = test_real_project()
    
    if success:
        logger.info("测试成功！")
    else:
        logger.error("测试失败！")


if __name__ == "__main__":
    main()