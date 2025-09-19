# core/breeding_calc/base_calculation.py

from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text
from PyQt6.QtWidgets import QMessageBox
from typing import Tuple, Optional
import numpy as np
import datetime

from core.data.update_manager import (
    CLOUD_DB_HOST, CLOUD_DB_PORT, CLOUD_DB_USER, 
    CLOUD_DB_PASSWORD, CLOUD_DB_NAME, LOCAL_DB_PATH
)

class BaseCowCalculation:
    def __init__(self):
        self.output_prefix = "processed_cow_data"
        self.required_columns = []  # 子类需要定义所需的列
        self.db_engine = None

    def init_db_connection(self):
        """初始化数据库连接"""
        try:
            print(f"尝试连接数据库：{LOCAL_DB_PATH}")
            if self.db_engine:
                self.db_engine.dispose()
                self.db_engine = None
                
            self.db_engine = create_engine(f'sqlite:///{LOCAL_DB_PATH}')
            
            # 测试连接
            with self.db_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                print("数据库连接成功")
                
            return True
        except Exception as e:
            print(f"数据库连接失败，错误信息: {str(e)}")
            if self.db_engine:
                self.db_engine.dispose()
                self.db_engine = None
            return False
            

    def check_project_data(self, project_path: Path, data_filename: str) -> Tuple[bool, str]:
        """
        检查项目数据是否存在并可读

        Args:
            project_path: 项目路径
            data_filename: 数据文件名

        Returns:
            Tuple[bool, str]: (是否成功, 错误消息)
        """
        data_path = project_path / "standardized_data" / data_filename
        if not data_path.exists():
            return False, f"未找到数据文件：{data_filename}"
        
        try:
            df = pd.read_excel(data_path)
            for col in self.required_columns:
                if col not in df.columns:
                    return False, f"数据文件缺少必需的列：{col}"
            return True, ""
        except Exception as e:
            return False, f"读取数据文件失败：{str(e)}"

    def read_data(self, project_path: Path, data_filename: str) -> Optional[pd.DataFrame]:
        """读取数据文件"""
        try:
            data_path = project_path / "standardized_data" / data_filename
            return pd.read_excel(data_path)
        except Exception as e:
            print(f"读取数据失败: {e}")
            return None

    def save_results_with_retry(self, df: pd.DataFrame, output_path: Path) -> bool:
        """
        保存结果，如果文件被占用则提供重试选项

        Args:
            df: 要保存的数据
            output_path: 保存路径

        Returns:
            bool: 是否保存成功
        """
        while True:
            try:
                df.to_excel(output_path, index=False)
                return True
            except PermissionError:
                reply = QMessageBox.question(
                    None,
                    "文件被占用",
                    f"文件 {output_path.name} 正在被其他程序使用。\n"
                    "请关闭该文件后点击'重试'继续，或点击'取消'停止操作。",
                    QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel
                )
                if reply == QMessageBox.StandardButton.Cancel:
                    return False
            except Exception as e:
                QMessageBox.critical(None, "错误", f"保存文件时发生错误：{str(e)}")
                return False

    def process_missing_bulls(self, missing_bulls: list, source: str, username: str) -> bool:
        """
        处理缺失的公牛信息并通过API上传到云端数据库

        Args:
            missing_bulls: 缺失的公牛ID列表
            source: 数据来源标识
            username: 用户名

        Returns:
            bool: 是否处理成功
        """
        try:
            if not missing_bulls:
                return True

            # 通过API上传缺失公牛信息
            from api.api_client import APIClient

            api_client = APIClient()

            # 准备上传数据
            bulls_data = []
            for bull_id in missing_bulls:
                bulls_data.append({
                    'bull': bull_id,
                    'source': source,
                    'time': datetime.datetime.now().isoformat(),
                    'user': username
                })

            # 调用API上传
            success = api_client.upload_missing_bulls(bulls_data)

            if success:
                print(f"成功上传 {len(missing_bulls)} 条缺失公牛记录到云端")
                return True
            else:
                print(f"上传缺失公牛信息到云端失败")
                return False

        except Exception as e:
            print(f"处理缺失公牛信息失败: {e}")
            # 如果API方式失败，尝试直接连接（仅用于开发环境）
            if CLOUD_DB_PASSWORD:
                try:
                    missing_df = pd.DataFrame({
                        'bull': missing_bulls,
                        'source': source,
                        'time': datetime.datetime.now(),
                        'user': username
                    })

                    cloud_engine = create_engine(
                        f"mysql+pymysql://{CLOUD_DB_USER}:{CLOUD_DB_PASSWORD}"
                        f"@{CLOUD_DB_HOST}:{CLOUD_DB_PORT}/{CLOUD_DB_NAME}?charset=utf8mb4"
                    )

                    missing_df.to_sql('miss_bull', cloud_engine, if_exists='append', index=False)
                    print(f"通过直接连接上传了 {len(missing_bulls)} 条缺失公牛记录")
                    return True
                except Exception as db_error:
                    print(f"直接数据库连接也失败: {db_error}")

            return False

    def query_bull_traits(self, bull_id: str, selected_traits: list) -> Tuple[dict, bool]:
        """
        从数据库查询公牛的性状数据

        Args:
            bull_id: 公牛ID
            selected_traits: 选中的性状列表

        Returns:
            Tuple[dict, bool]: (性状数据字典, 是否找到)
        """
        try:
            with self.db_engine.connect() as conn:
                # 先尝试用 BULL NAAB 查询
                result = conn.execute(
                    text("SELECT * FROM bull_library WHERE `BULL NAAB`=:bull_id"),
                    {"bull_id": bull_id}
                ).fetchone()
                
                if not result:
                    # 如果找不到，再尝试用 BULL REG 查询
                    result = conn.execute(
                        text("SELECT * FROM bull_library WHERE `BULL REG`=:bull_id"),
                        {"bull_id": bull_id}
                    ).fetchone()

                if result:
                    result_dict = dict(result._mapping)
                    trait_data = {trait: result_dict.get(trait) for trait in selected_traits}
                    return trait_data, True
                return {}, False

        except Exception as e:
            print(f"查询公牛性状数据失败: {e}")
            return {}, False

    def create_output_directory(self, project_path: Path) -> Optional[Path]:
        """创建输出目录"""
        try:
            output_dir = project_path / "analysis_results"
            output_dir.mkdir(parents=True, exist_ok=True)
            return output_dir
        except Exception as e:
            print(f"创建输出目录失败: {e}")
            return None

    def process_data(self, main_window, selected_traits: list, progress_callback=None) -> Tuple[bool, str]:
        """
        处理数据的主方法，子类必须实现
        
        Args:
            main_window: 主窗口实例
            selected_traits: 选中的性状列表
            progress_callback: 进度回调函数

        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        raise NotImplementedError("子类必须实现此方法")