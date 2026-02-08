# utils/file_manager.py
from pathlib import Path
import shutil
import json
from datetime import datetime
from typing import List, Dict

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

    @staticmethod
    def create_merged_project(base_path: Path, farms: List[Dict]) -> Path:
        """
        创建合并牧场项目目录

        Args:
            base_path: 基础路径
            farms: 牧场列表，每个牧场包含 code, name, cow_count

        Returns:
            项目路径
        """
        timestamp = datetime.now().strftime('%Y%m%d')
        project_name = f"合并牧场_{timestamp}"
        project_path = base_path / project_name

        # 如果已存在，添加序号
        counter = 1
        original_project_path = project_path
        while project_path.exists():
            project_path = base_path / f"{original_project_path.name}_{counter}"
            counter += 1

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

            # 生成合并说明文件
            FileManager.generate_merged_farms_info(project_path, farms)

            # 生成项目元数据
            FileManager.save_project_metadata(project_path, farms)

            return project_path
        except Exception as e:
            print(f"创建合并项目目录失败: {e}")
            raise

    @staticmethod
    def generate_merged_farms_info(project_path: Path, farms: List[Dict]):
        """
        生成合并牧场说明文件

        Args:
            project_path: 项目路径
            farms: 牧场列表
        """
        total_count = sum(f.get('cow_count', 0) for f in farms)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        content_lines = [
            "本项目合并了以下牧场数据：",
            ""
        ]

        for i, farm in enumerate(farms, 1):
            code = farm.get('code', 'N/A')
            name = farm.get('name', 'N/A')
            count = farm.get('cow_count', 0)
            content_lines.append(f"{i}. {code} - {name} ({count}头)")

        content_lines.extend([
            "",
            f"合计: {total_count}头",
            f"创建时间：{now}"
        ])

        info_file = project_path / "merged_farms.txt"
        info_file.write_text("\n".join(content_lines), encoding='utf-8')

    @staticmethod
    def save_project_metadata(project_path: Path, farms: List[Dict]):
        """
        保存项目元数据

        Args:
            project_path: 项目路径
            farms: 牧场列表
        """
        metadata = {
            "is_merged": len(farms) > 1,
            "farms": [
                {
                    "code": f.get('code', ''),
                    "name": f.get('name', ''),
                    "cow_count": f.get('cow_count', 0)
                }
                for f in farms
            ],
            "created_at": datetime.now().isoformat()
        }

        metadata_file = project_path / "project_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load_project_metadata(project_path: Path) -> Dict:
        """
        加载项目元数据

        Args:
            project_path: 项目路径

        Returns:
            元数据字典，如果不存在返回默认值
        """
        metadata_file = project_path / "project_metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

        return {"is_merged": False, "farms": []}
