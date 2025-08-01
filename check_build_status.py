#!/usr/bin/env python3
"""
检查GitHub Actions构建状态的脚本
"""
import requests
import time
import sys

def check_build_status():
    """检查最新的GitHub Actions构建状态"""
    repo = "Barton0411/genetic_improve"
    api_url = f"https://api.github.com/repos/{repo}/actions/runs"
    
    try:
        # 获取最新的运行信息
        response = requests.get(api_url, headers={"Accept": "application/vnd.github.v3+json"})
        
        if response.status_code != 200:
            print(f"错误: 无法访问GitHub API (状态码: {response.status_code})")
            return False
            
        data = response.json()
        
        if not data.get("workflow_runs"):
            print("没有找到任何构建运行记录")
            return False
            
        # 获取最新的运行
        latest_run = data["workflow_runs"][0]
        
        print(f"最新构建信息:")
        print(f"- 状态: {latest_run['status']}")
        print(f"- 结论: {latest_run.get('conclusion', '进行中')}")
        print(f"- 开始时间: {latest_run['created_at']}")
        print(f"- 提交信息: {latest_run['head_commit']['message']}")
        print(f"- 运行URL: {latest_run['html_url']}")
        
        # 如果构建完成，检查是否有artifacts
        if latest_run['status'] == 'completed':
            if latest_run['conclusion'] == 'success':
                print("\n✅ 构建成功!")
                
                # 检查artifacts
                artifacts_url = latest_run['artifacts_url']
                artifacts_response = requests.get(artifacts_url, headers={"Accept": "application/vnd.github.v3+json"})
                
                if artifacts_response.status_code == 200:
                    artifacts_data = artifacts_response.json()
                    if artifacts_data.get('artifacts'):
                        print("\n可下载的文件:")
                        for artifact in artifacts_data['artifacts']:
                            print(f"- {artifact['name']} (大小: {artifact['size_in_bytes'] / 1024 / 1024:.2f} MB)")
                            
                # 检查releases
                releases_url = f"https://api.github.com/repos/{repo}/releases/latest"
                releases_response = requests.get(releases_url, headers={"Accept": "application/vnd.github.v3+json"})
                
                if releases_response.status_code == 200:
                    release_data = releases_response.json()
                    print(f"\n最新发布版本: {release_data['name']}")
                    print(f"下载链接: {release_data['html_url']}")
                    
                    if release_data.get('assets'):
                        print("\n可下载文件:")
                        for asset in release_data['assets']:
                            print(f"- {asset['name']}")
                            print(f"  下载: {asset['browser_download_url']}")
                            print(f"  大小: {asset['size'] / 1024 / 1024:.2f} MB")
                            
                return True
            else:
                print(f"\n❌ 构建失败: {latest_run['conclusion']}")
                return False
        else:
            print("\n⏳ 构建正在进行中...")
            return None
            
    except Exception as e:
        print(f"检查过程中出错: {e}")
        return False

def monitor_build(check_interval=30, max_wait=600):
    """监控构建状态直到完成"""
    start_time = time.time()
    
    while True:
        result = check_build_status()
        
        if result is not None:  # 构建已完成
            break
            
        elapsed = time.time() - start_time
        if elapsed > max_wait:
            print(f"\n超时: 已等待 {max_wait} 秒")
            break
            
        print(f"\n等待 {check_interval} 秒后再次检查...")
        time.sleep(check_interval)
        print("-" * 50)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--monitor":
        monitor_build()
    else:
        check_build_status()