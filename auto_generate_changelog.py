#!/usr/bin/env python3
"""
自动生成changelog.txt脚本
从version.py中的VERSION_HISTORY自动生成changelog文件
"""

import os
import sys
from pathlib import Path
from datetime import datetime

def get_version_info():
    """获取版本信息"""
    try:
        from version import get_version, get_version_info
        current_version = get_version()
        version_info = get_version_info()
        return current_version, version_info
    except ImportError as e:
        print(f"❌ 无法导入版本信息: {e}")
        return None, None

def generate_changelog_content(version_info):
    """生成changelog内容"""
    if not version_info:
        return None
    
    changes = version_info.get('changes', [])
    if not changes:
        return None
    
    # 生成changelog内容
    content_lines = []
    
    for change in changes:
        # 确保每行都有emoji或者标记
        if not any(emoji in change for emoji in ['🔥', '⚡', '🛡️', '🎨', '📦', '🔒', '🚀', '💻', '🐛', '✨']):
            change = f"✨ {change}"
        
        content_lines.append(change)
    
    return '\n'.join(content_lines)

def save_changelog_file(version, content, output_dir=None):
    """保存changelog文件"""
    if not output_dir:
        output_dir = Path.cwd()
    else:
        output_dir = Path(output_dir)
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成文件名
    changelog_file = output_dir / f"CHANGELOG_v{version}.txt"
    
    try:
        with open(changelog_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ changelog文件已生成: {changelog_file}")
        return changelog_file
    except Exception as e:
        print(f"❌ 保存changelog失败: {e}")
        return None

def upload_to_oss(changelog_file, version):
    """上传changelog到OSS（模拟实现）"""
    print(f"📤 模拟上传到OSS...")
    print(f"   源文件: {changelog_file}")
    print(f"   目标路径: releases/v{version}/CHANGELOG.txt")
    print(f"   OSS URL: https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v{version}/CHANGELOG.txt")
    
    # 实际实现中，这里会使用OSS SDK上传文件
    # import oss2
    # auth = oss2.Auth('access_key', 'secret_key')  
    # bucket = oss2.Bucket(auth, 'endpoint', 'bucket_name')
    # bucket.put_object_from_file(f'releases/v{version}/CHANGELOG.txt', str(changelog_file))
    
    return True

def generate_build_script(version):
    """生成构建脚本中的changelog生成命令"""
    script_content = f'''
# 自动生成changelog（添加到构建脚本中）
echo "🔄 自动生成版本 {version} 的changelog..."
python3 auto_generate_changelog.py

# 上传到OSS（需要配置OSS CLI）
echo "📤 上传changelog到OSS..."
# ossutil cp CHANGELOG_v{version}.txt oss://genetic-improve/releases/v{version}/CHANGELOG.txt

echo "✅ changelog生成和上传完成"
'''
    
    with open('build_with_changelog.sh', 'w') as f:
        f.write(script_content)
    
    print(f"📜 构建脚本已生成: build_with_changelog.sh")

def main():
    """主函数"""
    print("🔄 自动生成changelog.txt")
    print("=" * 50)
    
    # 获取版本信息
    current_version, version_info = get_version_info()
    
    if not current_version or not version_info:
        print("❌ 无法获取版本信息")
        sys.exit(1)
    
    print(f"📱 当前版本: {current_version}")
    print(f"📅 发布日期: {version_info.get('date', '未知')}")
    print(f"👤 发布者: {version_info.get('author', '未知')}")
    
    # 生成changelog内容
    content = generate_changelog_content(version_info)
    
    if not content:
        print("❌ 没有找到更新内容")
        sys.exit(1)
    
    print(f"📝 更新内容 ({len(version_info.get('changes', []))} 项):")
    for i, change in enumerate(version_info.get('changes', []), 1):
        print(f"   {i}. {change}")
    
    # 保存changelog文件
    changelog_file = save_changelog_file(current_version, content)
    
    if not changelog_file:
        sys.exit(1)
    
    # 模拟上传到OSS
    if upload_to_oss(changelog_file, current_version):
        print("✅ OSS上传模拟成功")
    
    # 生成构建脚本示例
    generate_build_script(current_version)
    
    print()
    print("🎯 下一步操作:")
    print("1. 将生成的CHANGELOG.txt文件上传到OSS")
    print(f"   目标路径: releases/v{current_version}/CHANGELOG.txt") 
    print("2. 或者集成到GitHub Actions自动化流程")
    print("3. 或者添加到现有的构建脚本中")
    
    print()
    print("🚀 集成方式:")
    print("• 在package_app.py中添加changelog生成步骤")
    print("• 在GitHub Actions中调用此脚本")
    print("• 在发布脚本中自动执行")

if __name__ == "__main__":
    main()