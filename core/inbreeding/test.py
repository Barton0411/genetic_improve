import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

from PyQt6.QtWidgets import QApplication
from genetic_improve.core.inbreeding.inbreeding_calculator import InbreedingCalculator
from genetic_improve.core.inbreeding.pedigree_tree_widget import PedigreeTreeWidget

def main():
    # 设置数据路径
    db_path = project_root / "genetic_improve" / "local_bull_library.db"
    cow_data_path = project_root / "genetic_projects" / "测试-基因组检测数据上传_2024_12_25_16_14" / "standardized_data" / "processed_cow_data.xlsx"
    
    # 检查文件是否存在
    if not db_path.exists():
        print(f"错误: 数据库文件不存在: {db_path}")
        return
    if not cow_data_path.exists():
        print(f"错误: 母牛数据文件不存在: {cow_data_path}")
        return
        
    print(f"使用数据库文件: {db_path}")
    print(f"使用母牛数据文件: {cow_data_path}")
    
    try:
        # 创建计算器实例
        calculator = InbreedingCalculator(db_path, cow_data_path)
        
        # 创建Qt应用
        app = QApplication(sys.argv)
        
        # 创建系谱树窗口
        window = PedigreeTreeWidget(calculator, "23208")  # 示例牛号
        window.setWindowTitle("奶牛系谱分析")
        window.resize(1200, 800)
        window.show()
        
        # 运行应用
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()