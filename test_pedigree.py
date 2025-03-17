# test_pedigree.py

import sys
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 导入update_manager模块
from core.data.update_manager import check_and_update_database, get_pedigree_db

def test_pedigree_database():
    """测试系谱库的构建和基本功能"""
    try:
        print("开始测试系谱库...")
        
        # 首先检查并更新数据库
        print("检查并更新数据库...")
        check_and_update_database(
            progress_callback=lambda progress, message: print(f"进度: {progress}%, {message}")
        )
        
        # 获取系谱库
        print("\n获取系谱库...")
        pedigree_db = get_pedigree_db()
        
        # 打印系谱库基本信息
        print(f"\n系谱库基本信息:")
        print(f"- 动物总数: {len(pedigree_db.pedigree)}")
        print(f"- 虚拟节点数: {len(pedigree_db.virtual_nodes)}")
        print(f"- NAAB到REG映射数: {len(pedigree_db.naab_to_reg_map)}")
        
        # 提取和打印几个样本
        print("\n系谱样本:")
        sample_count = 0
        for animal_id, info in pedigree_db.pedigree.items():
            if sample_count >= 5:
                break
            if info['type'] == 'bull':  # 只打印公牛样本
                print(f"公牛ID: {animal_id}")
                print(f"  - 父系ID: {info['sire'] or '未知'}")
                print(f"  - 母系ID: {info['dam'] or '未知'}")
                sample_count += 1
        
        # 测试NAAB转REG功能
        print("\n测试NAAB转REG功能:")
        naab_examples = list(pedigree_db.naab_to_reg_map.keys())[:3]  # 取前3个NAAB号作为示例
        for naab in naab_examples:
            reg = pedigree_db.convert_naab_to_reg(naab)
            print(f"NAAB: {naab} -> REG: {reg}")
        
        # 导出系谱文件测试
        output_path = Path('pedigree_sample.txt')
        print(f"\n导出系谱文件到 {output_path}...")
        pedigree_db.export_pedigree_file(output_path)
        
        # 打印前几行
        print("\n导出文件的前5行:")
        with open(output_path, 'r') as f:
            lines = f.readlines()[:5]
            for line in lines:
                print(line.strip())
        
        # 测试系谱重新编号
        print("\n测试系谱重新编号...")
        renumbered_pedigree, old_to_new, new_to_old = pedigree_db.renumber_pedigree()
        print(f"重编号后的系谱包含 {len(renumbered_pedigree)} 个节点")
        print(f"ID映射数量: {len(old_to_new)}")
        
        # 展示一些映射示例
        print("\nID映射示例:")
        sample_count = 0
        for old_id, new_id in list(old_to_new.items())[:5]:
            print(f"原ID: {old_id} -> 新ID: {new_id}")
            sample_count += 1
        
        print("\n系谱库测试完成!")
        
    except Exception as e:
        logging.error(f"测试系谱库时出错: {e}")
        raise

if __name__ == "__main__":
    test_pedigree_database() 