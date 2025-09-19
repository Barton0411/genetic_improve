import requests

# 测试不使用代理
session = requests.Session()
session.trust_env = False
session.proxies = {'http': None, 'https': None}

try:
    print("测试连接 http://39.96.189.27/api/auth/verify ...")
    response = session.get("http://39.96.189.27/api/auth/verify", timeout=5)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.text[:100]}")
except Exception as e:
    print(f"错误: {e}")
