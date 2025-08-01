"""
PPT生成功能测试脚本

用于测试新的PPT生成模块
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.report.ppt_generator import PPTGenerator

def test_ppt_generation():
    """测试PPT生成功能"""
    # 创建测试输出目录
    test_output = project_root / "test_output"
    test_output.mkdir(exist_ok=True)
    
    # 创建PPT生成器
    generator = PPTGenerator(str(test_output), "测试用户")
    
    # 检查数据文件
    all_ready, missing_files = generator.data_prep.check_all_files()
    
    print("=== PPT生成测试 ===")
    print(f"输出目录: {test_output}")
    print(f"数据文件检查: {'通过' if all_ready else '未通过'}")
    
    if not all_ready:
        print("\n缺失的文件:")
        for file in missing_files:
            print(f"  - {file}")
        print("\n提示: 需要先运行相关的数据分析功能生成这些文件")
    else:
        print("\n所有必需文件已就绪，可以生成PPT")
        
    # 测试性状翻译
    print("\n=== 性状翻译测试 ===")
    test_traits = ["TPI", "NM$", "MILK", "FAT"]
    for trait in test_traits:
        translated = generator.trait_translations.get(trait, trait)
        print(f"{trait} -> {translated}")
        
    print("\n测试完成！")

if __name__ == "__main__":
    test_ppt_generation()