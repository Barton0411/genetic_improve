#!/usr/bin/env python3
"""
离线测试应用启动
跳过网络验证，直接进入主界面
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 模拟成功登录
from gui.main_window import MainWindow
from PyQt6.QtWidgets import QApplication

def test_main():
    """直接启动主窗口，跳过登录"""
    app = QApplication(sys.argv)

    # 创建主窗口，模拟已登录用户
    main_window = MainWindow(username="test_user")
    main_window.show()

    print("========================================")
    print("离线测试模式 - 已跳过登录")
    print("测试账号: test_user")
    print("========================================")
    print("\n可以测试的功能：")
    print("1. 数据上传和处理（使用本地数据库）")
    print("2. 遗传评估和选配计算")
    print("3. 报告生成")
    print("4. 所有不需要网络的功能")
    print("========================================")

    sys.exit(app.exec())

if __name__ == "__main__":
    test_main()