#!/usr/bin/env python3
"""
测试版本更新功能
"""

import sys
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_version_update():
    """测试版本更新功能"""
    print("\n" + "="*60)
    print("🧪 版本更新功能测试")
    print("="*60)
    
    # 导入版本管理器
    from core.update.version_manager import VersionManager
    from version import VERSION
    
    print(f"\n📌 当前本地版本: {VERSION}")
    print("📡 正在连接服务器检查更新...")
    
    # 创建版本管理器
    manager = VersionManager()
    
    # 检查更新
    has_update, version_info = manager.check_for_updates()
    
    if has_update:
        print(f"\n✅ 发现新版本!")
        if version_info and 'data' in version_info:
            data = version_info['data']
            print(f"   最新版本: {data.get('version')}")
            print(f"   发布日期: {data.get('release_date')}")
            print(f"   更新内容: {data.get('changes')}")
            print(f"\n📥 下载链接:")
            print(f"   Mac版: {data.get('mac_download_url')}")
            print(f"   Win版: {data.get('win_download_url')}")
        
        print("\n💡 提示: 运行 'python3 test_version_update.py --gui' 可以测试更新对话框")
        
        # 检查是否需要显示GUI
        if '--gui' in sys.argv:
            print("\n🔄 显示更新对话框...")
            try:
                from PyQt6.QtWidgets import QApplication
                app = QApplication.instance()
                if app is None:
                    app = QApplication(sys.argv)
                
                should_update, selected_platform = manager.show_update_dialog(version_info)
                if should_update:
                    print("✅ 用户选择了更新!")
                    if selected_platform:
                        print(f"   选择平台: {selected_platform}")
                else:
                    print("❌ 用户取消了更新")
            except Exception as e:
                print(f"GUI测试失败: {e}")
    else:
        print("\n✅ 当前已是最新版本，无需更新")
    
    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)

if __name__ == "__main__":
    test_version_update()