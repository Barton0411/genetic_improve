#!/usr/bin/env python3
"""测试选配前确认对话框功能"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from gui.mating_confirmation_dialog import MatingConfirmationDialog

def test_confirmation_dialog():
    """测试确认对话框"""
    app = QApplication(sys.argv)

    # 测试项目路径
    project_path = Path("/Users/bozhenwang/projects/mating/genetic_improve/genetic_projects/测试项目")

    # 创建并显示对话框
    dialog = MatingConfirmationDialog(project_path)

    # 显示对话框
    result = dialog.exec()

    # 获取用户选择
    confirmation = dialog.get_confirmation_result()

    print("\n=== 测试结果 ===")
    print(f"用户选择: {'继续选配' if confirmation['proceed'] else '取消'}")
    print(f"跳过缺失数据的公牛: {'是' if confirmation['skip_missing'] else '否'}")

    sys.exit(app.exec() if result else 0)

if __name__ == "__main__":
    test_confirmation_dialog()