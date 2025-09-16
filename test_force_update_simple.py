#!/usr/bin/env python3
"""
简单的强制更新测试 - 直接测试对话框
"""

import sys
from PyQt6.QtWidgets import QApplication

def test_force_update_dialog_directly():
    """直接测试强制更新对话框"""
    print("🚀 启动强制更新对话框测试...")
    
    # 创建QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        # 导入所需模块
        from core.update.smart_updater import detect_current_installation
        from core.update.force_update_dialog_clean import ForceUpdateDialog
        
        # 获取当前应用信息
        app_info = detect_current_installation()
        print(f"📍 检测到安装位置: {app_info['app_root']}")
        print(f"🖥️  平台: {app_info['platform']}")
        print(f"📁 用户数据目录: {app_info['user_data_dir']}")
        
        # 模拟强制更新版本信息
        version_info = {
            'data': {
                'version': '1.0.6',
                'force_update': True,
                'security_update': True,
                'changes': [
                    '🔒 重要安全修复：修复数据泄露漏洞',
                    '🚨 紧急修复：修复程序崩溃问题',
                    '⚡ 性能优化：提升系统运行速度30%',
                    '💾 新增功能：增强数据备份机制',
                    '🛡️ 系统加固：增强防护能力',
                    '🔄 智能更新：支持程序内自动更新'
                ],
                'package_size': 52428800,  # 50MB
                'mac_download_url': 'https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.6/GeneticImprove_v1.0.6_mac.dmg',
                'win_download_url': 'https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.6/GeneticImprove_v1.0.6_win.exe',
                'md5': 'abc123def456789ghi'
            }
        }
        
        print("💡 即将显示强制更新对话框...")
        print("🔒 测试特性:")
        print("   - 无法通过X按钮关闭")
        print("   - ESC键被禁用")
        print("   - 必须点击'立即更新'按钮")
        print("   - 显示详细的更新内容")
        print("   - 包含安装位置信息")
        
        # 创建并显示强制更新对话框
        dialog = ForceUpdateDialog(version_info, app_info)
        result = dialog.exec()
        
        print(f"✅ 对话框测试完成，结果代码: {result}")
        
        # 如果用户点击了更新，这里通常程序会退出
        # 在测试环境下我们只是显示结果
        if result == 1:  # QDialog.Accepted
            print("🔄 用户选择了立即更新")
            print("📦 在实际环境中，这里会:")
            print("   1. 下载更新包") 
            print("   2. 启动独立更新器")
            print("   3. 主程序退出")
            print("   4. 更新器替换程序文件")
            print("   5. 启动新版本")
        else:
            print("❌ 对话框被意外关闭（这在强制更新中不应该发生）")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("="*80)
    print("🔥 伊利奶牛选配系统 - 强制更新测试")
    print("="*80)
    print()
    print("📋 测试内容:")
    print("   ✅ 强制更新对话框UI")
    print("   ✅ 无法关闭的特性")
    print("   ✅ 更新内容展示")
    print("   ✅ 安装位置检测")
    print("   ✅ 用户交互流程")
    print()
    
    success = test_force_update_dialog_directly()
    
    print("\n" + "="*80)
    if success:
        print("🎉 强制更新对话框测试成功！")
        print("💡 下一步: 集成到主程序并测试完整流程")
    else:
        print("😞 测试失败，请检查错误日志")
    print("="*80)

if __name__ == '__main__':
    main()