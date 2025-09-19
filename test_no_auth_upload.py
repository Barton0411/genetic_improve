#!/usr/bin/env python3
"""测试无认证的缺失公牛上传"""

import datetime
import requests

# 准备测试数据
test_data = {
    'bulls': [
        {
            'bull': 'TEST_BULL_NO_AUTH',
            'source': 'test_no_auth',
            'time': datetime.datetime.now().isoformat(),
            'user': 'test_user'
        }
    ]
}

# 设置环境变量以禁用代理
import os
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

# 发送请求（无需认证头）
print("发送请求到: http://39.96.189.27/api/data/missing_bulls")
print(f"数据: {test_data}")

try:
    # 创建session并禁用代理
    session = requests.Session()
    session.trust_env = False

    response = session.post(
        'http://39.96.189.27/api/data/missing_bulls',
        json=test_data,
        timeout=15
    )

    print(f"\nHTTP状态码: {response.status_code}")
    print(f"响应内容: {response.text}")

    if response.status_code == 200:
        result = response.json()
        if result.get('success'):
            print("\n✓ 上传成功! 无需认证")
        else:
            print(f"\n✗ 上传失败: {result.get('message')}")
    else:
        print(f"\n✗ HTTP错误: {response.status_code}")

except Exception as e:
    print(f"\n错误: {e}")
    import traceback
    traceback.print_exc()