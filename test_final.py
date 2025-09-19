#!/usr/bin/env python3
"""最终测试 - 模拟实际上传场景"""

import datetime
import requests

# 模拟你遇到的缺失公牛
missing_bulls = ['779HO98765', '291HO22269']

# 准备上传数据
bulls_data = []
for bull_id in missing_bulls:
    bulls_data.append({
        'bull': bull_id,
        'source': 'bull_traits_calc',
        'time': datetime.datetime.now().isoformat(),
        'user': 'test_user'
    })

data = {
    'bulls': bulls_data
}

print(f"准备上传缺失公牛: {', '.join(missing_bulls)}")
print("发送请求到: http://39.96.189.27/api/data/missing_bulls")

# 创建session并禁用代理
session = requests.Session()
session.trust_env = False

try:
    response = session.post(
        'http://39.96.189.27/api/data/missing_bulls',
        json=data,
        timeout=15
    )

    print(f"\nHTTP状态码: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        if result.get('success'):
            print(f"✅ 成功上传 {len(missing_bulls)} 条缺失公牛记录到云端")
            print(f"响应: {result.get('message')}")
        else:
            print(f"❌ 上传失败: {result.get('message')}")
    else:
        print(f"❌ HTTP错误: {response.status_code}")
        print(f"响应: {response.text}")

except Exception as e:
    print(f"❌ 错误: {e}")