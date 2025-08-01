#!/usr/bin/env python3
"""
迁移测试文件，从旧版本的matcher迁移到新版本
"""

import os
import re
from pathlib import Path

def migrate_file(filepath):
    """迁移单个文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # 替换导入语句
    replacements = [
        # v3 -> cycle_based_matcher
        (r'from core\.matching\.individual_matcher_v3 import IndividualMatcherV3',
         'from core.matching.cycle_based_matcher import CycleBasedMatcher'),
        (r'IndividualMatcherV3', 'CycleBasedMatcher'),
        
        # v2 -> matrix_recommendation_generator
        (r'from core\.matching\.recommendation_generator_v2 import RecommendationGeneratorV2',
         'from core.matching.matrix_recommendation_generator import MatrixRecommendationGenerator'),
        (r'RecommendationGeneratorV2', 'MatrixRecommendationGenerator'),
    ]
    
    for old_pattern, new_pattern in replacements:
        content = re.sub(old_pattern, new_pattern, content)
    
    if content != original_content:
        # 备份原文件
        backup_path = filepath.with_suffix(filepath.suffix + '.bak')
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        
        # 写入新内容
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ 已迁移: {filepath}")
        print(f"   备份保存在: {backup_path}")
        return True
    else:
        print(f"ℹ️  无需迁移: {filepath}")
        return False

def main():
    """主函数"""
    project_root = Path(__file__).parent
    
    # 需要迁移的文件列表
    files_to_migrate = [
        'tests/test_allocation_ratio.py',
        'tests/test_improved_matching.py',
        'test_new_generator.py',
        'test_user_project.py',
        'generate_new_report.py',
    ]
    
    migrated_count = 0
    
    for file_path in files_to_migrate:
        full_path = project_root / file_path
        if full_path.exists():
            if migrate_file(full_path):
                migrated_count += 1
        else:
            print(f"⚠️  文件不存在: {full_path}")
    
    print(f"\n迁移完成！共迁移了 {migrated_count} 个文件")
    
    # 提示可以删除的文件
    print("\n现在可以安全删除以下文件：")
    print("- core/matching/individual_matcher_v3.py")
    print("- core/matching/recommendation_generator_v2.py")

if __name__ == '__main__':
    main()