#!/usr/bin/env python3
"""
完整的强制更新测试 - 使用本地API服务
"""

import sys
import logging
from PyQt6.QtWidgets import QApplication

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_with_local_api():
    """使用本地API测试强制更新"""
    print("\n" + "="*80)
    print("🔥 完整强制更新流程测试")
    print("="*80)
    
    try:
        # 创建QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 导入更新管理器
        from core.update.version_manager import VersionManager
        
        # 使用本地测试API服务器
        local_api_url = "http://localhost:8080"
        
        print(f"📡 连接本地测试API: {local_api_url}")
        
        # 创建版本管理器
        manager = VersionManager(local_api_url)
        
        print(f"📌 当前版本: {manager.current_version}")
        print("🔍 检查更新...")
        
        # 检查更新
        has_update, version_info, is_force_update = manager.check_for_updates()
        
        if not has_update:
            print("✅ 当前已是最新版本")
            return False
        
        latest_version = version_info.get('data', {}).get('version', '未知')
        print(f"🆕 发现新版本: {latest_version}")
        print(f"⚠️  强制更新: {'是' if is_force_update else '否'}")
        
        if is_force_update:
            print("🚨 检测到强制更新！将显示强制更新对话框...")
            print("💡 对话框特点:")
            print("   - 无法关闭（X按钮无效）")
            print("   - ESC键无效") 
            print("   - 必须点击'立即更新'")
            print("   - 支持下载进度显示")
            print("   - 自动启动独立更新器")
            
            # 调用强制更新处理
            should_exit = manager.handle_force_update(version_info)
            
            if should_exit:
                print("✅ 强制更新流程已启动，程序将退出")
                return True
            else:
                print("❌ 强制更新流程未完成")
                return False
        else:
            print("ℹ️  这是一个可选更新")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_version_detection_logic():
    """测试版本检测逻辑"""
    print("\n" + "="*80)
    print("🔍 强制更新检测逻辑测试")
    print("="*80)
    
    from core.update.version_manager import VersionManager
    
    manager = VersionManager()
    
    # 测试不同场景的版本信息
    test_scenarios = [
        {
            'name': '正常可选更新',
            'data': {
                'version': '1.0.6',
                'force_update': False,
                'security_update': False,
                'min_supported_version': None
            },
            'expected': False
        },
        {
            'name': '强制更新标志',
            'data': {
                'version': '1.0.6', 
                'force_update': True,
                'security_update': False,
                'min_supported_version': None
            },
            'expected': True
        },
        {
            'name': '安全更新', 
            'data': {
                'version': '1.0.6',
                'force_update': False,
                'security_update': True,
                'min_supported_version': None
            },
            'expected': True
        },
        {
            'name': '版本过低强制更新',
            'data': {
                'version': '1.0.6',
                'force_update': False,
                'security_update': False,
                'min_supported_version': '1.0.6'  # 当前是1.0.5，低于最低要求
            },
            'expected': True
        },
        {
            'name': '多重强制条件',
            'data': {
                'version': '1.0.6',
                'force_update': True,
                'security_update': True,
                'min_supported_version': '1.0.6'
            },
            'expected': True
        }
    ]
    
    print("测试强制更新检测逻辑:")
    all_passed = True
    
    for scenario in test_scenarios:
        version_info = {'data': scenario['data']}
        result = manager._is_force_update_required(version_info)
        expected = scenario['expected']
        
        status = "✅" if result == expected else "❌"
        result_text = "强制" if result else "可选"
        expected_text = "强制" if expected else "可选"
        
        print(f"   {status} {scenario['name']}: {result_text} (预期: {expected_text})")
        
        if result != expected:
            all_passed = False
    
    print(f"\\n🎯 检测逻辑测试: {'全部通过' if all_passed else '存在失败'}")
    return all_passed

def show_test_instructions():
    """显示测试说明"""
    print("🚀 强制更新完整测试")
    print("="*80)
    print()
    print("📋 测试步骤:")
    print("1. 启动本地API服务器（在另一个终端）:")
    print("   python3 local_test_api.py")
    print()
    print("2. 运行此测试脚本:")
    print("   python3 test_force_update_complete.py")
    print()
    print("3. 观察强制更新对话框:")
    print("   - 尝试点击关闭按钮（应该被阻止）")
    print("   - 尝试按ESC键（应该无效）")
    print("   - 点击'立即更新'按钮测试下载流程")
    print()
    print("💡 测试环境:")
    print(f"   当前版本: 1.0.5")
    print(f"   最新版本: 1.0.6 (强制更新)")
    print(f"   本地API: http://localhost:8080")

def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        show_test_instructions()
        return
    
    # 先运行检测逻辑测试
    logic_test_passed = test_version_detection_logic()
    
    if not logic_test_passed:
        print("❌ 基础逻辑测试失败，请先修复问题")
        return
    
    # 检查本地API是否可用
    import requests
    try:
        response = requests.get("http://localhost:8080/api/health", timeout=3)
        if response.status_code == 200:
            print("✅ 本地测试API服务可用")
        else:
            print("❌ 本地API服务响应异常")
            return
    except:
        print("❌ 本地API服务不可用")
        print("💡 请先在另一个终端运行:")
        print("   python3 local_test_api.py")
        return
    
    # 运行完整测试
    print("\\n🎬 开始完整强制更新测试...")
    success = test_with_local_api()
    
    if success:
        print("\\n🎉 强制更新测试成功！")
    else:
        print("\\n😞 强制更新测试未完全成功，请检查日志")

if __name__ == '__main__':
    main()