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
        print(f"[ERROR] Cannot import version info: {e}")
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
        
        print(f"[SUCCESS] Changelog generated: {changelog_file}")
        return changelog_file
    except Exception as e:
        print(f"[ERROR] Failed to save changelog: {e}")
        return None

def upload_to_oss(changelog_file, version):
    """上传changelog到OSS（模拟实现）"""
    print(f"[INFO] Simulating OSS upload...")
    print(f"   Source: {changelog_file}")
    print(f"   Target: releases/v{version}/CHANGELOG.txt")
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
# Auto-generate changelog (add to build script)
echo "[BUILD] Generating changelog for version {version}..."
python3 auto_generate_changelog.py

# Upload to OSS (requires OSS CLI configuration)
echo "[BUILD] Uploading changelog to OSS..."
# ossutil cp CHANGELOG_v{version}.txt oss://genetic-improve/releases/v{version}/CHANGELOG.txt

echo "[BUILD] Changelog generation and upload completed"
'''
    
    with open('build_with_changelog.sh', 'w') as f:
        f.write(script_content)
    
    print(f"[INFO] Build script generated: build_with_changelog.sh")

def main():
    """主函数"""
    print("[AUTO-CHANGELOG] Starting changelog generation...")
    print("=" * 50)
    
    # 获取版本信息
    current_version, version_info = get_version_info()
    
    if not current_version or not version_info:
        print("[ERROR] Cannot get version info")
        sys.exit(1)
    
    print(f"Current version: {current_version}")
    print(f"Release date: {version_info.get('date', 'unknown')}")
    print(f"Author: {version_info.get('author', 'unknown')}")
    
    # 生成changelog内容
    content = generate_changelog_content(version_info)
    
    if not content:
        print("[ERROR] No changes found")
        sys.exit(1)
    
    print(f"Changes ({len(version_info.get('changes', []))} items):")
    for i, change in enumerate(version_info.get('changes', []), 1):
        print(f"   {i}. {change}")
    
    # 保存changelog文件
    changelog_file = save_changelog_file(current_version, content)
    
    if not changelog_file:
        sys.exit(1)
    
    # 模拟上传到OSS
    if upload_to_oss(changelog_file, current_version):
        print("[SUCCESS] OSS upload simulation completed")
    
    # 生成构建脚本示例
    generate_build_script(current_version)
    
    print()
    print("[INFO] Next steps:")
    print("1. Upload CHANGELOG.txt to OSS")
    print(f"   Target path: releases/v{current_version}/CHANGELOG.txt") 
    print("2. Or integrate with GitHub Actions")
    print("3. Or add to existing build script")
    
    print()
    print("[INFO] Integration methods:")
    print("- Add changelog generation to package_app.py")
    print("- Call this script in GitHub Actions")
    print("- Execute automatically in release script")

if __name__ == "__main__":
    main()