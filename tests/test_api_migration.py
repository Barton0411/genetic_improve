#!/usr/bin/env python3
"""
API化改造测试脚本
测试新的API认证系统是否正常工作
"""

import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.api_client import APIClient
from auth.auth_service import AuthService
from auth.token_manager import TokenManager

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_api_client():
    """测试API客户端基本功能"""
    print("\n" + "="*50)
    print("测试API客户端")
    print("="*50)

    try:
        # 测试API客户端初始化
        client = APIClient()
        print(f"✅ API客户端初始化成功")
        print(f"   - 基础URL: {client.base_url}")
        print(f"   - 超时时间: {client.timeout}秒")

        # 测试健康检查
        print("\n🔍 测试健康检查...")
        success, message = client.health_check()
        if success:
            print(f"✅ 健康检查成功: {message}")
        else:
            print(f"❌ 健康检查失败: {message}")

        return success

    except Exception as e:
        print(f"❌ API客户端测试失败: {e}")
        return False

def test_token_manager():
    """测试令牌管理器"""
    print("\n" + "="*50)
    print("测试令牌管理器")
    print("="*50)

    try:
        manager = TokenManager()
        print("✅ 令牌管理器初始化成功")

        # 测试令牌保存和获取
        test_token = "test_jwt_token_12345"
        test_user = "test_user"

        print(f"\n💾 测试令牌保存...")
        success = manager.save_token(test_token, test_user)
        if success:
            print("✅ 令牌保存成功")
        else:
            print("❌ 令牌保存失败")
            return False

        print(f"\n📖 测试令牌获取...")
        retrieved_token = manager.get_token()
        if retrieved_token == test_token:
            print("✅ 令牌获取成功")
        else:
            print(f"❌ 令牌获取失败，期望: {test_token}, 实际: {retrieved_token}")
            return False

        print(f"\n🗑️  测试令牌清除...")
        success = manager.clear_token()
        if success and manager.get_token() is None:
            print("✅ 令牌清除成功")
        else:
            print("❌ 令牌清除失败")
            return False

        return True

    except Exception as e:
        print(f"❌ 令牌管理器测试失败: {e}")
        return False

def test_auth_service():
    """测试认证服务"""
    print("\n" + "="*50)
    print("测试认证服务")
    print("="*50)

    try:
        auth = AuthService()
        print("✅ 认证服务初始化成功")

        # 测试服务器健康检查
        print(f"\n🔍 测试服务器健康检查...")
        is_healthy = auth.check_server_health()
        if is_healthy:
            print("✅ 服务器健康检查通过")
        else:
            print("❌ 服务器健康检查失败 - API服务可能未启动")

        # 测试登录状态
        print(f"\n👤 检查当前登录状态...")
        is_logged_in = auth.is_logged_in()
        print(f"   登录状态: {is_logged_in}")

        return True

    except Exception as e:
        print(f"❌ 认证服务测试失败: {e}")
        return False

def test_api_vs_legacy():
    """对比测试：API版本 vs 传统版本"""
    print("\n" + "="*50)
    print("对比测试：API vs 传统数据库连接")
    print("="*50)

    # 检查是否还存在硬编码数据库密码
    try:
        from core.data.update_manager import CLOUD_DB_PASSWORD_RAW
        print(f"⚠️  检测到硬编码数据库密码仍然存在")
        print(f"   位置: core/data/update_manager.py")
        print(f"   密码: {CLOUD_DB_PASSWORD_RAW[:4]}****")
        print(f"   状态: 🚨 需要在部署API后移除")

        legacy_detected = True
    except ImportError:
        print("✅ 硬编码数据库密码已移除")
        legacy_detected = False

    print(f"\n📊 改造状态总结:")
    print(f"   - API客户端: ✅ 已实现")
    print(f"   - 令牌管理: ✅ 已实现")
    print(f"   - 认证服务: ✅ 已升级为API版本")
    print(f"   - 硬编码密码: {'🚨 仍存在' if legacy_detected else '✅ 已移除'}")

    return not legacy_detected

def run_full_test():
    """运行完整测试套件"""
    print("🧪 开始API化改造测试")
    print("="*60)

    test_results = []

    # 运行各项测试
    test_results.append(("API客户端", test_api_client()))
    test_results.append(("令牌管理器", test_token_manager()))
    test_results.append(("认证服务", test_auth_service()))
    test_results.append(("API vs 传统对比", test_api_vs_legacy()))

    # 输出测试结果
    print("\n" + "="*60)
    print("📋 测试结果汇总")
    print("="*60)

    passed = 0
    total = len(test_results)

    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name:20} : {status}")
        if result:
            passed += 1

    print(f"\n📊 测试统计: {passed}/{total} 通过")

    if passed == total:
        print("\n🎉 所有测试通过！API化改造基础架构正常工作")
        print("\n📝 下一步操作:")
        print("   1. 在服务器上部署认证API服务")
        print("   2. 配置Nginx路由")
        print("   3. 测试完整的登录注册流程")
        print("   4. 移除硬编码数据库连接")
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败，请检查相关模块")

    return passed == total

if __name__ == "__main__":
    success = run_full_test()
    sys.exit(0 if success else 1)