#!/usr/bin/env python3
"""
智能更新系统测试 - 测试强制更新功能
"""

import sys
import logging
from PyQt6.QtWidgets import QApplication

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_path_detection():
    """测试路径检测功能"""
    print("\n" + "="*60)
    print("🔍 智能路径检测测试")
    print("="*60)
    
    try:
        from core.update.smart_updater import detect_current_installation
        
        app_info = detect_current_installation()
        
        print(f"📍 检测结果:")
        print(f"   可执行文件: {app_info['executable_path']}")
        print(f"   程序根目录: {app_info['app_root']}")
        print(f"   用户数据目录: {app_info['user_data_dir']}")
        print(f"   操作系统: {app_info['platform']}")
        print(f"   安装类型: {app_info['install_type']}")
        print(f"   安装位置: {app_info['install_location']}")
        if app_info.get('drive_letter'):
            print(f"   驱动器: {app_info['drive_letter']}:")
        print(f"   需要管理员权限: {'是' if app_info['requires_admin'] else '否'}")
        print(f"   目录可写: {'是' if app_info['is_writable'] else '否'}")
        
        return app_info
        
    except Exception as e:
        print(f"❌ 路径检测失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_force_update_cli():
    """测试命令行强制更新"""
    print("\n" + "="*60)
    print("⚠️  命令行强制更新测试")  
    print("="*60)
    
    try:
        from core.update.version_manager import VersionManager
        
        # 模拟强制更新的版本信息
        version_info = {
            'data': {
                'version': '1.0.6',
                'force_update': True,
                'security_update': True,
                'changes': [
                    '重要安全修复：修复数据泄露漏洞',
                    '紧急修复：修复程序崩溃问题',
                    '性能优化：提升系统运行速度',
                    '新增功能：增强数据备份机制'
                ],
                'package_size': 52428800,  # 50MB
                'mac_download_url': 'https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.6/GeneticImprove_v1.0.6_mac.dmg',
                'win_download_url': 'https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.6/GeneticImprove_v1.0.6_win.exe',
                'md5': 'abc123def456'
            }
        }
        
        manager = VersionManager()
        
        # 测试强制更新检测
        force_required = manager._is_force_update_required(version_info)
        print(f"🔍 强制更新检测: {'需要' if force_required else '不需要'}")
        
        if force_required:
            print("⚠️  检测到强制更新，将启动命令行更新流程...")
            
            # 模拟命令行强制更新
            result = manager._handle_force_update_cli(version_info)
            print(f"✅ 命令行更新结果: {'成功' if result else '失败'}")
        
        return True
        
    except Exception as e:
        print(f"❌ 命令行更新测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_force_update_gui():
    """测试GUI强制更新"""
    print("\n" + "="*60)
    print("🖥️  GUI强制更新测试")
    print("="*60)
    
    try:
        # 创建QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        from core.update.smart_updater import detect_current_installation
        from core.update.force_update_dialog import ForceUpdateDialog
        
        # 获取应用信息
        app_info = detect_current_installation()
        
        # 模拟强制更新的版本信息
        version_info = {
            'data': {
                'version': '1.0.6',
                'force_update': True,
                'security_update': True,
                'changes': [
                    '🔒 重要安全修复：修复数据泄露漏洞',
                    '🚨 紧急修复：修复程序崩溃问题', 
                    '⚡ 性能优化：提升系统运行速度',
                    '💾 新增功能：增强数据备份机制',
                    '🛡️ 系统加固：增强防护能力'
                ],
                'package_size': 52428800,  # 50MB
                'mac_download_url': 'https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.6/GeneticImprove_v1.0.6_mac.dmg',
                'win_download_url': 'https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.6/GeneticImprove_v1.0.6_win.exe',
                'md5': 'abc123def456'
            }
        }
        
        print("💡 将显示强制更新对话框...")
        print("   注意：这是一个无法关闭的对话框，模拟真实的强制更新场景")
        print("   您可以点击'立即更新'来测试更新流程")
        
        # 创建强制更新对话框
        dialog = ForceUpdateDialog(version_info, app_info)
        
        # 显示对话框
        result = dialog.exec()
        
        print(f"✅ GUI更新对话框结果: {result}")
        
        return True
        
    except Exception as e:
        print(f"❌ GUI更新测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_version_comparison():
    """测试版本比较功能"""
    print("\n" + "="*60)
    print("📊 版本比较功能测试")
    print("="*60)
    
    try:
        from core.update.version_manager import VersionManager
        
        manager = VersionManager()
        
        test_cases = [
            ("1.0.5", "1.0.6", "1.0.5 < 1.0.6"),
            ("1.0.6", "1.0.5", "1.0.6 > 1.0.5"),
            ("1.0.5", "1.0.5", "1.0.5 = 1.0.5"),
            ("1.0.5", "1.1.0", "1.0.5 < 1.1.0"),
            ("2.0.0", "1.9.9", "2.0.0 > 1.9.9"),
        ]
        
        print("版本比较测试:")
        for v1, v2, expected in test_cases:
            result = manager._compare_versions(v1, v2)
            if result > 0:
                actual = f"{v1} > {v2}"
            elif result < 0:
                actual = f"{v1} < {v2}"
            else:
                actual = f"{v1} = {v2}"
            
            status = "✅" if actual == expected else "❌"
            print(f"   {status} {expected} -> {actual}")
        
        return True
        
    except Exception as e:
        print(f"❌ 版本比较测试失败: {e}")
        return False

def test_update_detection_scenarios():
    """测试不同更新场景的检测"""
    print("\n" + "="*60)
    print("🎯 更新检测场景测试")
    print("="*60)
    
    try:
        from core.update.version_manager import VersionManager
        
        manager = VersionManager()
        
        scenarios = [
            {
                'name': '普通更新',
                'version_info': {
                    'data': {
                        'version': '1.0.6',
                        'force_update': False
                    }
                },
                'expected_force': False
            },
            {
                'name': '强制更新标志',
                'version_info': {
                    'data': {
                        'version': '1.0.6',
                        'force_update': True
                    }
                },
                'expected_force': True
            },
            {
                'name': '安全更新',
                'version_info': {
                    'data': {
                        'version': '1.0.6',
                        'security_update': True
                    }
                },
                'expected_force': True
            },
            {
                'name': '最低版本要求',
                'version_info': {
                    'data': {
                        'version': '1.0.6',
                        'min_supported_version': '1.0.6'
                    }
                },
                'expected_force': True
            }
        ]
        
        print("强制更新检测测试:")
        for scenario in scenarios:
            result = manager._is_force_update_required(scenario['version_info'])
            status = "✅" if result == scenario['expected_force'] else "❌"
            print(f"   {status} {scenario['name']}: {'强制' if result else '可选'}")
        
        return True
        
    except Exception as e:
        print(f"❌ 更新检测测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 智能更新系统全面测试")
    print("="*80)
    
    tests = [
        ("路径检测", test_path_detection),
        ("版本比较", test_version_comparison), 
        ("更新检测场景", test_update_detection_scenarios),
        ("命令行强制更新", test_force_update_cli),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
            results.append((test_name, False))
    
    # 显示测试结果
    print("\n" + "="*80)
    print("📋 测试结果总结")
    print("="*80)
    
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} {test_name}")
    
    # GUI测试需要单独运行
    print("\n💡 要测试GUI强制更新对话框，请运行:")
    print("   python test_smart_update.py --gui")
    
    if "--gui" in sys.argv:
        print("\n🖥️  启动GUI测试...")
        test_force_update_gui()

if __name__ == '__main__':
    main()