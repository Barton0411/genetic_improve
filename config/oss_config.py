# config/oss_config.py
# 阿里云OSS对象存储配置

import os
from pathlib import Path

# OSS基本配置
OSS_ENDPOINT = 'oss-cn-beijing.aliyuncs.com'  # 华北2(北京)
OSS_BUCKET_NAME = 'genetic-improve'  # Bucket名称
OSS_REGION = 'cn-beijing'

# OSS访问凭证 - 从环境变量读取（安全考虑）
OSS_ACCESS_KEY_ID = os.environ.get('OSS_ACCESS_KEY_ID', '')
OSS_ACCESS_KEY_SECRET = os.environ.get('OSS_ACCESS_KEY_SECRET', '')

# OSS目录结构配置
OSS_RELEASES_PREFIX = 'releases/'  # 版本发布文件目录前缀

# 支持的文件类型
SUPPORTED_FILE_TYPES = {
    'win_exe': 'GeneticImprove_v{version}_win.exe',
    'win_zip': 'GeneticImprove_v{version}_win.zip', 
    'mac_dmg': 'GeneticImprove_v{version}_mac.dmg'
}

# OSS URL配置
OSS_CUSTOM_DOMAIN = None  # 自定义域名（可选）
OSS_BASE_URL = f'https://{OSS_BUCKET_NAME}.{OSS_ENDPOINT}'

def get_oss_file_url(version: str, file_type: str) -> str:
    """
    获取OSS文件的访问URL
    
    Args:
        version: 版本号，如 '1.0.5'
        file_type: 文件类型，如 'win_exe', 'win_zip', 'mac_dmg'
    
    Returns:
        OSS文件的完整URL
    """
    if file_type not in SUPPORTED_FILE_TYPES:
        raise ValueError(f"Unsupported file type: {file_type}")
    
    filename = SUPPORTED_FILE_TYPES[file_type].format(version=version)
    file_path = f"{OSS_RELEASES_PREFIX}v{version}/{filename}"
    
    if OSS_CUSTOM_DOMAIN:
        return f"https://{OSS_CUSTOM_DOMAIN}/{file_path}"
    else:
        return f"{OSS_BASE_URL}/{file_path}"

def get_oss_file_key(version: str, file_type: str) -> str:
    """
    获取OSS中的文件Key（路径）
    
    Args:
        version: 版本号
        file_type: 文件类型
    
    Returns:
        OSS中的文件Key
    """
    if file_type not in SUPPORTED_FILE_TYPES:
        raise ValueError(f"Unsupported file type: {file_type}")
    
    filename = SUPPORTED_FILE_TYPES[file_type].format(version=version)
    return f"{OSS_RELEASES_PREFIX}v{version}/{filename}"

# 示例配置验证
def validate_oss_config():
    """验证OSS配置是否完整"""
    errors = []
    
    if not OSS_ACCESS_KEY_ID:
        errors.append("OSS_ACCESS_KEY_ID environment variable not set")
    
    if not OSS_ACCESS_KEY_SECRET:
        errors.append("OSS_ACCESS_KEY_SECRET environment variable not set")
    
    if not OSS_BUCKET_NAME:
        errors.append("OSS_BUCKET_NAME not configured")
    
    return errors

if __name__ == "__main__":
    # 测试配置
    print("OSS配置测试:")
    print(f"Endpoint: {OSS_ENDPOINT}")
    print(f"Bucket: {OSS_BUCKET_NAME}")
    print(f"Base URL: {OSS_BASE_URL}")
    
    # 测试URL生成
    test_version = "1.0.5"
    for file_type in SUPPORTED_FILE_TYPES:
        url = get_oss_file_url(test_version, file_type)
        key = get_oss_file_key(test_version, file_type)
        print(f"{file_type}: {url}")
        print(f"  Key: {key}")
    
    # 验证配置
    errors = validate_oss_config()
    if errors:
        print("\n配置错误:")
        for error in errors:
            print(f"- {error}")
    else:
        print("\n✅ OSS配置验证通过")