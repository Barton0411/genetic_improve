#!/usr/bin/env python3
"""测试令牌修复是否成功"""

import sys
from pathlib import Path

# 添加项目路径到系统路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from api.api_client import get_api_client
from auth.token_manager import get_token_manager
import datetime

def test_token_persistence():
    """测试令牌持久化和API调用"""

    print("=" * 50)
    print("测试令牌持久化修复")
    print("=" * 50)

    # 1. 检查是否有保存的令牌
    token_manager = get_token_manager()
    saved_token = token_manager.get_token()

    if saved_token:
        print(f"✓ 找到本地保存的令牌")
        print(f"  令牌前20字符: {saved_token[:20]}...")
    else:
        print("✗ 未找到本地保存的令牌")
        print("  请先通过应用程序登录")
        return False

    # 2. 获取API客户端并检查令牌
    api_client = get_api_client()

    if api_client.token:
        print(f"✓ API客户端成功恢复令牌")
        print(f"  令牌前20字符: {api_client.token[:20]}...")
    else:
        print("✗ API客户端未能恢复令牌")
        return False

    # 3. 测试令牌验证
    print("\n测试令牌验证...")
    success, message = api_client.verify_token()

    if success:
        print(f"✓ 令牌验证成功: {message}")
    else:
        print(f"✗ 令牌验证失败: {message}")
        return False

    # 4. 测试获取用户信息
    print("\n测试获取用户信息...")
    success, user_info, message = api_client.get_profile()

    if success and user_info:
        print(f"✓ 成功获取用户信息:")
        print(f"  用户ID: {user_info.get('user_id')}")
        print(f"  姓名: {user_info.get('name')}")
    else:
        print(f"✗ 获取用户信息失败: {message}")
        return False

    # 5. 测试上传缺失公牛（模拟数据）
    print("\n测试上传缺失公牛...")
    test_bulls_data = [
        {
            'bull': 'TEST_BULL_001',
            'source': 'token_test',
            'time': datetime.datetime.now().isoformat(),
            'user': user_info.get('user_id', 'unknown')
        }
    ]

    success = api_client.upload_missing_bulls(test_bulls_data)

    if success:
        print(f"✓ 成功上传测试缺失公牛记录")
    else:
        print(f"✗ 上传缺失公牛失败")
        return False

    print("\n" + "=" * 50)
    print("所有测试通过！令牌持久化修复成功")
    print("=" * 50)
    return True

if __name__ == "__main__":
    try:
        success = test_token_persistence()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)