# utils/file_manager.py
from pathlib import Path
import shutil
from datetime import datetime

class FileManager:
    """文件管理工具类"""
    
    @staticmethod
    def create_project(base_path: Path, farm_name: str) -> Path:
        """
        创建新项目目录
        
        Args:
            base_path: 基础路径
            farm_name: 牧场名称
            
        Returns:
            项目路径
        """
        timestamp = datetime.now().strftime('%Y_%m_%d_%H_%M')
        project_name = f"{farm_name}_{timestamp}"
        project_path = base_path / project_name
        
        subdirs = [
            'raw_data',
            'standardized_data',
            'analysis_results',
            'reports'
        ]
        
        try:
            project_path.mkdir(parents=True, exist_ok=True)
            for subdir in subdirs:
                (project_path / subdir).mkdir(exist_ok=True)
            return project_path
        except Exception as e:
            print(f"创建项目目录失败: {e}")
            raise

    @staticmethod
    def get_projects(base_path: Path) -> list[Path]:
        """
        获取所有项目列表（按修改时间逆序排序）
        
        Args:
            base_path: 基础路径
            
        Returns:
            项目路径列表
        """
        try:
            return sorted(
                [d for d in base_path.iterdir() if d.is_dir()],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
        except Exception as e:
            print(f"获取项目列表失败: {e}")
            return []

    @staticmethod
    def delete_project(project_path: Path):
        """
        删除项目目录
        
        Args:
            project_path: 项目路径
        """
        try:
            shutil.rmtree(project_path)
        except Exception as e:
            print(f"删除项目失败: {e}")
            raise
