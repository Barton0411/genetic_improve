"""
选配结果推送模块
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import pandas as pd
import requests

from version import get_version


class MatingResultPusher:
    """选配结果推送器"""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.farm_info = self._load_farm_info()

    def _get_value(self, row, column_name, data_type, default_value):
        """从DataFrame行中安全获取值"""
        if column_name is None:
            # 列不存在，返回默认值
            return default_value

        try:
            value = row.get(column_name, default_value)
            if pd.isna(value):
                return default_value
            return data_type(value)
        except:
            return default_value

    def _load_farm_info(self) -> Optional[Dict]:
        """加载牧场信息"""
        farm_info_path = self.project_path / "farm_info.json"

        if not farm_info_path.exists():
            print(f"⚠️ 未找到牧场信息文件: {farm_info_path}")
            return None

        try:
            with open(farm_info_path, 'r', encoding='utf-8') as f:
                farm_info = json.load(f)
                # 验证必要字段
                if not farm_info.get("farm_code"):
                    print("⚠️ 牧场信息文件缺少 farm_code 字段")
                    return None
                return farm_info
        except Exception as e:
            print(f"❌ 加载牧场信息失败: {e}")
            return None

    def prepare_push_data(self) -> Optional[Dict]:
        """
        准备推送数据
        读取个体选配报告.xlsx中的选配结果
        """
        if not self.farm_info:
            print("⚠️ 未找到牧场信息")
            return None

        # 查找个体选配报告文件
        result_file = self.project_path / "analysis_results" / "个体选配报告.xlsx"

        if not result_file.exists():
            # 尝试其他可能的文件名
            possible_files = [
                "individual_mating_report.xlsx",
                "cycle_mating_results.xlsx",
                "选配分配结果.xlsx"
            ]

            for filename in possible_files:
                file_path = self.project_path / "analysis_results" / filename
                if file_path.exists():
                    result_file = file_path
                    break

        if not result_file.exists():
            print(f"⚠️ 未找到个体选配报告文件")
            return None

        print(f"读取选配结果: {result_file.name}")

        try:
            # 加载选配数据
            mating_df = pd.read_excel(result_file)

            # 准备要推送的记录
            records = []
            required_columns = [
                '母牛号',
                '分组',
                '1选性控',
                '2选性控',
                '3选性控',
                '4选性控',
                '1选常规',
                '2选常规',
                '3选常规',
                '4选常规',
                '肉牛冻精',
                '母牛指数得分'
            ]

            # 尝试寻找类似的列名
            column_mapping = {
                '母牛号': ['cow_id', '耳号', 'ear_id'],
                '分组': ['group', '组别'],
                '1选性控': ['1st_sexed', '第1选性控'],
                '2选性控': ['2nd_sexed', '第2选性控'],
                '3选性控': ['3rd_sexed', '第3选性控'],
                '4选性控': ['4th_sexed', '第4选性控'],
                '1选常规': ['1st_regular', '第1选常规'],
                '2选常规': ['2nd_regular', '第2选常规'],
                '3选常规': ['3rd_regular', '第3选常规'],
                '4选常规': ['4th_regular', '第4选常规'],
                '肉牛冻精': ['beef_semen', '肉牛'],
                '母牛指数得分': ['index_score', '指数得分', 'score']
            }

            # 创建列名映射，如果列不存在则映射为None
            actual_columns = {}
            for std_col in required_columns:
                if std_col in mating_df.columns:
                    actual_columns[std_col] = std_col
                else:
                    # 查找替代列名
                    found = False
                    for alt_col in column_mapping.get(std_col, []):
                        if alt_col in mating_df.columns:
                            actual_columns[std_col] = alt_col
                            found = True
                            break
                    if not found:
                        # 如果找不到列，映射为None，稍后将设为空值
                        actual_columns[std_col] = None

            # 提取数据
            for _, row in mating_df.iterrows():
                # 获取母牛号（必填字段）
                cow_id = self._get_value(row, actual_columns['母牛号'], str, '')

                # 跳过没有母牛号的记录
                if not cow_id or cow_id == 'nan':
                    print(f"警告：跳过没有母牛号的记录")
                    continue

                record = {
                    "母牛号": cow_id,
                    "上传日期": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "分组": self._get_value(row, actual_columns['分组'], str, ''),
                    "1选性控": self._get_value(row, actual_columns['1选性控'], str, ''),
                    "2选性控": self._get_value(row, actual_columns['2选性控'], str, ''),
                    "3选性控": self._get_value(row, actual_columns['3选性控'], str, ''),
                    "4选性控": self._get_value(row, actual_columns['4选性控'], str, ''),
                    "1选常规": self._get_value(row, actual_columns['1选常规'], str, ''),
                    "2选常规": self._get_value(row, actual_columns['2选常规'], str, ''),
                    "3选常规": self._get_value(row, actual_columns['3选常规'], str, ''),
                    "4选常规": self._get_value(row, actual_columns['4选常规'], str, ''),
                    "肉牛冻精": self._get_value(row, actual_columns['肉牛冻精'], str, ''),
                    "母牛指数得分": self._get_value(row, actual_columns['母牛指数得分'], float, 0)
                }

                # 清理空值
                for key in record:
                    if pd.isna(record[key]) or record[key] == 'nan':
                        record[key] = ""

                records.append(record)

            # 检查是否有有效记录
            if not records:
                print("❌ 没有有效的选配记录（所有记录都缺少母牛号）")
                return None

            # 检查牧场编号（必填字段）
            farm_code = self.farm_info.get("farm_code", "")
            if not farm_code:
                print("❌ 牧场编号未设置")
                return None

            # 组装推送数据
            push_data = {
                # 牧场编号（必填）
                "farm_code": farm_code,

                # 选配数据记录
                "records": records
            }

            print(f"✅ 准备推送 {len(records)} 条选配记录")
            return push_data

        except Exception as e:
            print(f"❌ 准备推送数据失败: {e}")
            import traceback
            print(traceback.format_exc())
            return None

    def push_to_api(self, api_url: str = None) -> bool:
        """
        推送到API

        Args:
            api_url: API地址，如果为None则保存到本地

        Returns:
            是否推送成功
        """
        push_data = self.prepare_push_data()
        if not push_data:
            return False

        if api_url:
            # 推送到真实API
            try:
                print(f"推送到API: {api_url}")

                # 创建session并禁用代理
                session = requests.Session()
                session.trust_env = False

                response = session.post(
                    api_url,
                    json=push_data,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )

                if response.status_code == 200:
                    print(f"✅ 选配结果推送成功")
                    self._save_push_log(True, f"HTTP {response.status_code}", api_url)
                    return True
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    print(f"❌ 推送失败: {error_msg}")
                    self._save_push_log(False, error_msg, api_url)
                    return False

            except requests.exceptions.Timeout:
                error_msg = "请求超时"
                print(f"❌ 推送失败: {error_msg}")
                self._save_push_log(False, error_msg, api_url)
                return False

            except requests.exceptions.ConnectionError:
                error_msg = "连接失败"
                print(f"❌ 推送失败: {error_msg}")
                self._save_push_log(False, error_msg, api_url)
                return False

            except Exception as e:
                error_msg = str(e)
                print(f"❌ 推送异常: {error_msg}")
                self._save_push_log(False, error_msg, api_url)
                return False
        else:
            # 保存到本地（用于测试）
            output_file = self.project_path / "api_push_data.json"
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(push_data, f, ensure_ascii=False, indent=2)
                print(f"✅ 推送数据已保存到: {output_file}")
                self._save_push_log(True, "保存到本地文件", str(output_file))
                return True
            except Exception as e:
                print(f"❌ 保存失败: {e}")
                self._save_push_log(False, str(e), "local")
                return False

    def _save_push_log(self, success: bool, message: str, target: str):
        """保存推送日志"""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "message": message,
            "target": target,
            "farm_code": self.farm_info.get("farm_code") if self.farm_info else None
        }

        # 追加到日志文件
        log_file = self.project_path / "push_log.json"

        # 读取现有日志
        logs = []
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                    if isinstance(existing, list):
                        logs = existing
                    else:
                        logs = [existing]
            except:
                pass

        # 添加新日志
        logs.append(log_data)

        # 只保留最近20条
        logs = logs[-20:]

        # 保存
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存日志失败: {e}")

    def get_last_push_status(self) -> Optional[Dict]:
        """获取最后一次推送状态"""
        log_file = self.project_path / "push_log.json"

        if not log_file.exists():
            return None

        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
                if isinstance(logs, list) and logs:
                    return logs[-1]
                elif isinstance(logs, dict):
                    return logs
        except:
            pass

        return None