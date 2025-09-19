import sys
sys.path.insert(0, '.')
from api.api_client import APIClient

client = APIClient()
result = client.login("cs", "cs123")
if result.get('success'):
    print("✓ 登录成功!")
    data = result.get('data', {})
    print(f"  用户名: {data.get('username')}")
    print(f"  令牌: {str(data.get('token'))[:20]}...")
else:
    print(f"✗ 登录失败: {result.get('message')}")
