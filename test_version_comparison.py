#!/usr/bin/env python3
"""
测试版本比较逻辑
验证当前版本(1.0.9.9)和服务器版本(1.0.5.2)不一致时是否正确触发强制更新
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from core.update.version_manager import VersionManager
from version import get_version
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_version_comparison():
    """测试版本比较逻辑"""
    
    print("🧪 开始测试版本比较逻辑...")
    print("=" * 50)
    
    # 获取当前版本
    current_version = get_version()
    print(f"📱 当前应用版本: {current_version}")
    
    # 读取version.json中的版本（仅供参考）
    version_json_path = Path(__file__).parent / "version.json"
    if version_json_path.exists():
        import json
        with open(version_json_path, 'r', encoding='utf-8') as f:
            local_data = json.load(f)
            local_version = local_data.get('version', 'unknown')
            print(f"📄 本地 version.json 版本: {local_version}")
    else:
        print("❌ version.json文件不存在")
        local_version = 'unknown'
    
    # 创建版本管理器
    vm = VersionManager()
    
    print("🔄 检查更新（连接API服务器）...")
    try:
        has_update, version_info, force_update = vm.check_for_updates()
        
        api_version = 'unknown'
        if version_info:
            api_version = version_info.get('data', {}).get('version', 'unknown')
        
        print("📋 检查结果:")
        print(f"   API服务器版本: {api_version}")
        print(f"   有更新: {has_update}")
        print(f"   强制更新: {force_update}")
        
        if version_info:
            changes = version_info.get('data', {}).get('changes', [])
            if changes:
                print("   更新内容:")
                for change in changes[:3]:  # 只显示前3条
                    print(f"     - {change}")
                if len(changes) > 3:
                    print(f"     ... 还有 {len(changes) - 3} 项更新")
        
        print()
        print(f"🔍 版本比较分析:")
        print(f"   当前版本: {current_version}")
        print(f"   API服务器版本: {api_version}")
        print(f"   版本是否相等: {current_version == api_version}")
        print(f"   是否需要更新: {current_version != api_version}")
        print()
        
        # 验证预期结果（基于API服务器版本）
        expected_has_update = (current_version != api_version)
        expected_force_update = expected_has_update  # 版本不一致就强制更新
        
        print("✅ 预期结果验证:")
        print(f"   预期有更新: {expected_has_update}")
        print(f"   实际有更新: {has_update}")
        print(f"   预期强制更新: {expected_force_update}")
        print(f"   实际强制更新: {force_update}")
        
        # 检查结果是否符合预期
        success = (has_update == expected_has_update and force_update == expected_force_update)
        
        if success:
            print("🎉 测试通过！版本比较逻辑工作正常")
            print(f"   ✓ 版本不一致 ({current_version} ≠ {api_version}) 正确触发强制更新")
        else:
            print("❌ 测试失败！版本比较逻辑有问题")
            if has_update != expected_has_update:
                print(f"   ✗ 更新检测错误: 预期 {expected_has_update}, 实际 {has_update}")
            if force_update != expected_force_update:
                print(f"   ✗ 强制更新检测错误: 预期 {expected_force_update}, 实际 {force_update}")
        
        return success
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_version_comparison()
    exit_code = 0 if success else 1
    print(f"\n📊 测试完成，退出码: {exit_code}")
    sys.exit(exit_code)