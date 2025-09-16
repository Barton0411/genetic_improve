#!/usr/bin/env python3
"""
上传安装包到阿里云OSS
需要先安装: pip install oss2
"""

import os
import sys
import hashlib
import json
from pathlib import Path
from datetime import datetime

try:
    import oss2
except ImportError:
    print("❌ 请先安装OSS SDK: pip install oss2")
    sys.exit(1)

# OSS配置
OSS_ENDPOINT = 'oss-cn-beijing.aliyuncs.com'
OSS_BUCKET_NAME = 'genetic-improve'

def get_file_size_mb(file_path):
    """获取文件大小（MB）"""
    size_bytes = os.path.getsize(file_path)
    return f"{size_bytes / (1024 * 1024):.1f}MB"

def calculate_sha256(file_path):
    """计算文件SHA256值"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()

def upload_files_to_oss(version, files_dict, access_key_id, access_key_secret):
    """
    上传文件到OSS
    
    Args:
        version: 版本号，如 '1.0.5'
        files_dict: 文件字典 {'win_exe': 'path/to/file.exe', ...}
        access_key_id: OSS访问密钥ID
        access_key_secret: OSS访问密钥Secret
    """
    
    # 创建OSS认证和客户端
    auth = oss2.Auth(access_key_id, access_key_secret)
    bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)
    
    print(f"📦 开始上传版本 {version} 的文件到OSS...")
    
    uploaded_files = {}
    
    for file_type, local_path in files_dict.items():
        if not os.path.exists(local_path):
            print(f"⚠️  文件不存在: {local_path}")
            continue
            
        # 构建OSS路径
        filename = os.path.basename(local_path)
        oss_key = f"releases/v{version}/{filename}"
        
        print(f"\n📤 上传 {filename}...")
        print(f"   本地路径: {local_path}")
        print(f"   OSS路径: {oss_key}")
        print(f"   文件大小: {get_file_size_mb(local_path)}")
        
        try:
            # 上传文件
            with open(local_path, 'rb') as fileobj:
                result = bucket.put_object(oss_key, fileobj)
            
            if result.status == 200:
                print(f"   ✅ 上传成功!")
                
                # 计算文件信息
                file_size = get_file_size_mb(local_path)
                file_checksum = calculate_sha256(local_path)
                file_url = f"https://{OSS_BUCKET_NAME}.{OSS_ENDPOINT}/{oss_key}"
                
                uploaded_files[file_type] = {
                    "url": file_url,
                    "size": file_size,
                    "checksum": f"sha256:{file_checksum}",
                    "filename": filename
                }
                
                print(f"   URL: {file_url}")
            else:
                print(f"   ❌ 上传失败: HTTP {result.status}")
                
        except Exception as e:
            print(f"   ❌ 上传失败: {e}")
    
    return uploaded_files

def create_version_json(version, uploaded_files, changes=None):
    """创建版本信息JSON"""
    
    if changes is None:
        changes = [
            "修复Mac应用图标显示问题",
            "优化Windows构建完整性", 
            "更新应用名称为伊利奶牛选配"
        ]
    
    version_info = {
        "version": version,
        "release_date": datetime.now().strftime("%Y-%m-%d"),
        "changes": changes,
        "downloads": {}
    }
    
    # 映射文件类型到下载分类
    type_mapping = {
        "win_exe": "windows_installer",
        "win_zip": "windows_portable", 
        "mac_dmg": "macos"
    }
    
    for file_type, file_info in uploaded_files.items():
        download_type = type_mapping.get(file_type, file_type)
        version_info["downloads"][download_type] = file_info
    
    return version_info

def upload_version_json(version_info, access_key_id, access_key_secret):
    """上传版本信息JSON到OSS"""
    
    auth = oss2.Auth(access_key_id, access_key_secret)
    bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)
    
    # 转换为JSON字符串
    json_content = json.dumps(version_info, indent=2, ensure_ascii=False)
    
    # 上传到latest/version.json
    oss_key = "releases/latest/version.json"
    
    print(f"\n📝 上传版本信息文件...")
    print(f"   OSS路径: {oss_key}")
    
    try:
        result = bucket.put_object(oss_key, json_content)
        if result.status == 200:
            print(f"   ✅ 版本信息上传成功!")
            print(f"   URL: https://{OSS_BUCKET_NAME}.{OSS_ENDPOINT}/{oss_key}")
            return True
        else:
            print(f"   ❌ 上传失败: HTTP {result.status}")
            return False
    except Exception as e:
        print(f"   ❌ 上传失败: {e}")
        return False

def main():
    print("🚀 阿里云OSS安装包上传工具")
    print("=" * 50)
    
    # 检查环境变量
    access_key_id = os.environ.get('OSS_ACCESS_KEY_ID')
    access_key_secret = os.environ.get('OSS_ACCESS_KEY_SECRET')
    
    if not access_key_id or not access_key_secret:
        print("❌ 请设置环境变量:")
        print("   export OSS_ACCESS_KEY_ID='your_access_key_id'")
        print("   export OSS_ACCESS_KEY_SECRET='your_access_key_secret'")
        return
    
    # 版本号
    version = input("请输入版本号 (如 1.0.5): ").strip()
    if not version:
        print("❌ 版本号不能为空")
        return
    
    # 文件路径
    print("\n请提供安装包文件路径:")
    files_dict = {}
    
    win_exe = input("Windows安装版 (.exe) 路径: ").strip()
    if win_exe and os.path.exists(win_exe):
        files_dict['win_exe'] = win_exe
    
    win_zip = input("Windows便携版 (.zip) 路径: ").strip()
    if win_zip and os.path.exists(win_zip):
        files_dict['win_zip'] = win_zip
        
    mac_dmg = input("macOS安装包 (.dmg) 路径: ").strip()
    if mac_dmg and os.path.exists(mac_dmg):
        files_dict['mac_dmg'] = mac_dmg
    
    if not files_dict:
        print("❌ 没有找到有效的安装包文件")
        return
    
    # 确认上传
    print(f"\n📋 准备上传到OSS:")
    print(f"   Bucket: {OSS_BUCKET_NAME}")
    print(f"   版本: v{version}")
    print(f"   文件数量: {len(files_dict)}")
    
    confirm = input("\n确认上传? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ 取消上传")
        return
    
    # 执行上传
    uploaded_files = upload_files_to_oss(version, files_dict, access_key_id, access_key_secret)
    
    if uploaded_files:
        # 创建并上传版本信息
        version_info = create_version_json(version, uploaded_files)
        upload_version_json(version_info, access_key_id, access_key_secret)
        
        print(f"\n✅ 上传完成! 总共上传了 {len(uploaded_files)} 个文件")
        print("\n📋 版本信息:")
        print(json.dumps(version_info, indent=2, ensure_ascii=False))
        
        print(f"\n🌐 访问URL:")
        print(f"   版本信息: https://{OSS_BUCKET_NAME}.{OSS_ENDPOINT}/releases/latest/version.json")
        for file_type, file_info in uploaded_files.items():
            print(f"   {file_info['filename']}: {file_info['url']}")
    else:
        print("❌ 没有文件上传成功")

if __name__ == "__main__":
    main()