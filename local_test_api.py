#!/usr/bin/env python3
"""
本地测试API服务器 - 用于测试强制更新功能
"""

from flask import Flask, jsonify
import json

app = Flask(__name__)

# 模拟版本数据
VERSION_DATA = {
    "1.0.5": {
        "id": 2,
        "version": "1.0.5",
        "release_date": "2025-09-16 20:00:00",
        "is_latest": False,
        "changes": [
            "完善版本自动更新系统，支持GUI选择下载",
            "修复版本检查逻辑，优化服务器连接稳定性", 
            "更新文档和部署指南"
        ],
        "mac_download_url": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.5/GeneticImprove_v1.0.5_mac.dmg",
        "win_download_url": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.5/GeneticImprove_v1.0.5_win.exe",
        "force_update": False,
        "security_update": False,
        "min_supported_version": None,
        "package_size": 50331648,
        "mac_md5": "def456abc123789",
        "win_md5": "abc123def456789"
    },
    "1.0.6": {
        "id": 3,
        "version": "1.0.6",
        "release_date": "2025-09-16 22:00:00", 
        "is_latest": True,
        "changes": [
            "🔒 重要安全修复：修复数据泄露漏洞",
            "🚨 紧急修复：修复程序崩溃问题",
            "⚡ 性能优化：提升系统运行速度30%",
            "💾 新增功能：增强数据备份机制",
            "🛡️ 系统加固：增强防护能力",
            "🔄 智能更新：支持程序内自动更新"
        ],
        "mac_download_url": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.6/GeneticImprove_v1.0.6_mac.dmg",
        "win_download_url": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.6/GeneticImprove_v1.0.6_win.exe",
        "force_update": True,  # 🔥 强制更新
        "security_update": True,  # 🔒 安全更新
        "min_supported_version": "1.0.5",  # 最低支持版本
        "package_size": 52428800,  # 50MB
        "mac_md5": "abc123def456789ghi",
        "win_md5": "def456abc123789ghi"
    }
}

@app.route('/api/health')
def health_check():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "service": "local-test-version-api",
        "version": "1.0.0"
    })

@app.route('/api/version/latest')
def get_latest_version():
    """获取最新版本 - 1.0.6强制更新版本"""
    latest_version = VERSION_DATA["1.0.6"]
    
    return jsonify({
        "success": True,
        "data": latest_version
    })

@app.route('/api/version/<version>')
def get_specific_version(version):
    """获取指定版本信息"""
    if version in VERSION_DATA:
        return jsonify({
            "success": True,
            "data": VERSION_DATA[version]
        })
    else:
        return jsonify({
            "success": False,
            "error": f"Version {version} not found"
        }), 404

@app.route('/api/versions')
def list_versions():
    """列出所有版本"""
    versions = list(VERSION_DATA.values())
    # 按版本号倒序排列
    versions.sort(key=lambda x: x['version'], reverse=True)
    
    return jsonify({
        "success": True,
        "data": versions
    })

def main():
    print("🚀 启动本地测试API服务器...")
    print("📡 服务地址: http://localhost:8080")
    print("🔧 测试端点:")
    print("   健康检查: http://localhost:8080/api/health")
    print("   最新版本: http://localhost:8080/api/version/latest")
    print("   指定版本: http://localhost:8080/api/version/1.0.6")
    print("   版本列表: http://localhost:8080/api/versions")
    print()
    print("⚠️  当前配置为强制更新模式:")
    print("   版本: 1.0.6")
    print("   强制更新: 是")
    print("   安全更新: 是")
    print("   最低支持版本: 1.0.5")
    print()
    print("🎯 要测试强制更新，请在另一个终端运行:")
    print("   python3 test_smart_update.py --gui")
    print()
    
    app.run(host='0.0.0.0', port=8080, debug=True)

if __name__ == '__main__':
    main()