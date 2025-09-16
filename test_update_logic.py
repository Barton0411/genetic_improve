#!/usr/bin/env python3
"""
测试强制更新逻辑
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from core.update.force_update_dialog_clean import ForceUpdateDialog
import logging

logging.basicConfig(level=logging.INFO)

def test_force_update():
    """测试强制更新对话框"""
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 模拟版本信息 - 使用小文件测试下载逻辑
    version_info = {
        'data': {
            'version': '1.0.5.2',
            'changes': [
                '调整近交系数默认阈值从3.125%改为6.25%',
                '优化选配约束条件，提供更多选配组合',
                '更新GUI界面默认选择为6.25%阈值',
                '完善个体选配和完整选配的默认参数'
            ],
            'package_size': 1024,  # 1KB用于测试
            # 使用小文件测试下载逻辑
            'mac_download_url': 'https://httpbin.org/bytes/1024',  # 1KB测试文件
            'win_download_url': 'https://httpbin.org/bytes/1024'
        }
    }
    
    # 模拟应用信息
    app_info = {
        'platform': 'darwin',  # macOS
        'app_root': str(Path(__file__).parent),
        'user_data_dir': str(Path.home() / '.genetic_improve')
    }
    
    # 创建对话框
    dialog = ForceUpdateDialog(version_info, app_info)
    
    print("🧪 开始测试强制更新对话框...")
    print(f"   版本: {version_info['data']['version']}")
    print(f"   下载URL: {version_info['data']['mac_download_url']}")
    print(f"   平台: {app_info['platform']}")
    
    result = dialog.exec()
    print(f"\n📋 测试结果: {result}")
    
    return result

if __name__ == '__main__':
    result = test_force_update()
    print(f"强制更新测试完成，结果: {result}")