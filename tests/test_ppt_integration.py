"""
PPT生成集成测试

测试PPT生成功能与主窗口的集成
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QMessageBox
from PyQt6.QtCore import Qt

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.report.ppt_generator import PPTGenerator


class TestMainWindow(QMainWindow):
    """测试主窗口"""
    
    def __init__(self):
        super().__init__()
        self.selected_project_path = Path("test_output")
        self.username = "测试用户"
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("PPT生成测试")
        self.resize(400, 200)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QVBoxLayout(central_widget)
        
        # 创建按钮
        self.generate_button = QPushButton("生成PPT报告")
        self.generate_button.clicked.connect(self.on_generate_ppt)
        layout.addWidget(self.generate_button)
        
        # 创建准备数据按钮
        self.prepare_button = QPushButton("准备测试数据")
        self.prepare_button.clicked.connect(self.prepare_test_data)
        layout.addWidget(self.prepare_button)
        
    def prepare_test_data(self):
        """准备测试数据"""
        from tests.test_ppt_generation import create_test_data
        
        try:
            # 创建输出文件夹
            output_folder = self.selected_project_path / "analysis_results"
            output_folder.mkdir(parents=True, exist_ok=True)
            
            # 创建测试数据
            create_test_data(output_folder)
            
            QMessageBox.information(self, "成功", "测试数据准备完成！")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"准备测试数据时出错：{str(e)}")
    
    def on_generate_ppt(self):
        """生成PPT报告（从main_window.py复制的方法）"""
        if not self.selected_project_path:
            QMessageBox.warning(self, "警告", "请先选择一个项目")
            return
            
        try:
            # 导入新的PPT生成器
            from core.report.ppt_generator import PPTGenerator
            
            # 获取用户名（从设置或默认值）
            username = getattr(self, 'username', '用户')
            
            # 创建输出文件夹路径
            output_folder = self.selected_project_path / "analysis_results"
            output_folder.mkdir(exist_ok=True)
            
            # 创建PPT生成器
            ppt_generator = PPTGenerator(str(output_folder), username)
            
            # 生成报告
            success = ppt_generator.generate_report(parent_widget=self)
            
            if success:
                # 询问是否打开
                reply = QMessageBox.question(
                    self,
                    "生成成功",
                    "PPT报告生成成功！是否立即打开查看？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    import os
                    import platform
                    
                    ppt_path = output_folder / f"{ppt_generator.farm_name}牧场遗传改良项目专项服务报告.pptx"
                    
                    if platform.system() == 'Darwin':  # macOS
                        os.system(f'open "{ppt_path}"')
                    elif platform.system() == 'Windows':
                        os.startfile(str(ppt_path))
                    else:  # Linux
                        os.system(f'xdg-open "{ppt_path}"')
                        
        except Exception as e:
            import logging
            logging.error(f"生成PPT时发生错误: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"生成PPT报告时发生错误：\n{str(e)}")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle('Fusion')
    
    # 创建主窗口
    window = TestMainWindow()
    window.show()
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()