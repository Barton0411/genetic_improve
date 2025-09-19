#!/usr/bin/env python3
"""简单测试缺失公牛上传"""

import datetime
import requests
from pathlib import Path
import sys

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from auth.token_manager import get_token_manager

# 获取保存的令牌
token_manager = get_token_manager()
token = token_manager.get_token()

if not token:
    print("未找到令牌，请先登录")
    sys.exit(1)

print(f"找到令牌: {token[:20]}...")

# 准备测试数据
test_data = {
    'bulls': [
        {
            'bull': 'TEST_BULL_123',
            'source': 'test_simple',
            'time': datetime.datetime.now().isoformat(),
            'user': 'test_user'
        }
    ]
}

# 准备请求头
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

# 禁用代理
proxies = {'http': None, 'https': None}

# 发送请求
print("\n发送请求到: http://39.96.189.27/api/data/missing_bulls")
print(f"数据: {test_data}")

try:
    response = requests.post(
        'http://39.96.189.27/api/data/missing_bulls',
        json=test_data,
        headers=headers,
        proxies=proxies,
        timeout=15
    )

    print(f"\nHTTP状态码: {response.status_code}")
    print(f"响应内容: {response.text}")

    if response.status_code == 200:
        result = response.json()
        if result.get('success'):
            print("\n✓ 上传成功!")
        else:
            print(f"\n✗ 上传失败: {result.get('message')}")
    else:
        print(f"\n✗ HTTP错误: {response.status_code}")

except Exception as e:
    print(f"\n错误: {e}")
    import traceback
    traceback.print_exc()