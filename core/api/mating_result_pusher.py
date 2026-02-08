"""
选配结果推送模块
"""

import json
import logging
import re
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

from version import get_version

logger = logging.getLogger(__name__)


class MatingResultPusher:
    """选配结果推送器"""

    # Excel中文列名 → API英文字段名
    FIELD_MAPPING = {
        '母牛号': 'earNum',
        '分组': 'suggestedBreedingPlan',
        '1选性控': 'sexedSemen1',
        '2选性控': 'sexedSemen2',
        '3选性控': 'sexedSemen3',
        '4选性控': 'sexedSemen4',
        '1选常规': 'conventionalSemen1',
        '2选常规': 'conventionalSemen2',
        '3选常规': 'conventionalSemen3',
        '4选常规': 'conventionalSemen4',
        '肉牛冻精': 'beefCattleFrozenSemen',
        '母牛指数得分': 'indexScore',
    }

    # 备选列名映射（Excel中可能出现的其他列名 → 标准中文列名）
    COLUMN_ALIASES = {
        'cow_id': '母牛号', '耳号': '母牛号', 'ear_id': '母牛号',
        'group': '分组', '组别': '分组',
        '1st_sexed': '1选性控', '第1选性控': '1选性控',
        '2nd_sexed': '2选性控', '第2选性控': '2选性控',
        '3rd_sexed': '3选性控', '第3选性控': '3选性控',
        '4th_sexed': '4选性控', '第4选性控': '4选性控',
        '1st_regular': '1选常规', '第1选常规': '1选常规',
        '2nd_regular': '2选常规', '第2选常规': '2选常规',
        '3rd_regular': '3选常规', '第3选常规': '3选常规',
        '4th_regular': '4选常规', '第4选常规': '4选常规',
        'beef_semen': '肉牛冻精', '肉牛': '肉牛冻精',
        'index_score': '母牛指数得分', '指数得分': '母牛指数得分', 'score': '母牛指数得分',
    }

    def __init__(self, project_path: str, update_by: str = ''):
        self.project_path = Path(project_path)
        self.update_by = update_by
        self.farm_info = self._load_farm_info()

    def _load_farm_info(self) -> Optional[Dict]:
        """从 project_metadata.json 加载牧场信息"""
        metadata_path = self.project_path / "project_metadata.json"
        if not metadata_path.exists():
            # 兼容：尝试旧的 farm_info.json
            metadata_path = self.project_path / "farm_info.json"

        if not metadata_path.exists():
            logger.warning(f"未找到牧场信息文件: {self.project_path}")
            return None

        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # project_metadata.json 格式: {"farms": [{"code": "10042", "name": "..."}]}
            farms = data.get("farms", [])
            if farms and farms[0].get("code"):
                return {
                    "farm_code": farms[0]["code"],
                    "farm_name": farms[0].get("name", "")
                }

            # farm_info.json 兼容格式
            if data.get("farm_code"):
                return data

            logger.warning("牧场信息文件缺少有效的牧场编号")
            return None
        except Exception as e:
            logger.error(f"加载牧场信息失败: {e}")
            return None

    def _get_value(self, row, column_name, data_type, default_value):
        """从DataFrame行中安全获取值"""
        if column_name is None:
            return default_value

        try:
            value = row.get(column_name, default_value)
            if pd.isna(value):
                return default_value
            return data_type(value)
        except Exception:
            return default_value

    def _resolve_column(self, std_col: str, df_columns) -> Optional[str]:
        """解析标准列名在DataFrame中的实际列名"""
        if std_col in df_columns:
            return std_col
        # 查找备选列名
        for alias, target in self.COLUMN_ALIASES.items():
            if target == std_col and alias in df_columns:
                return alias
        return None

    def _find_result_file(self) -> Optional[Path]:
        """查找个体选配报告文件"""
        candidates = [
            "个体选配报告.xlsx",
            "individual_mating_report.xlsx",
            "cycle_mating_results.xlsx",
            "选配分配结果.xlsx",
        ]
        for filename in candidates:
            file_path = self.project_path / "analysis_results" / filename
            if file_path.exists():
                return file_path
        return None

    def prepare_push_data(self) -> Optional[List[Dict]]:
        """
        准备推送数据，返回 API 格式的记录列表

        返回:
            List[Dict] - 直接可推送到 batchAdd 接口的记录数组，每条包含 farmCode 等字段
            None - 无法准备数据时
        """
        if not self.farm_info:
            logger.warning("未找到牧场信息")
            return None

        farm_code = self.farm_info.get("farm_code", "")
        if not farm_code:
            logger.warning("牧场编号未设置")
            return None

        result_file = self._find_result_file()
        if not result_file:
            logger.warning("未找到个体选配报告文件")
            return None

        logger.info(f"读取选配结果: {result_file.name}")

        try:
            mating_df = pd.read_excel(result_file)

            # 解析实际列名
            actual_columns = {}
            for std_col in self.FIELD_MAPPING:
                actual_columns[std_col] = self._resolve_column(std_col, mating_df.columns)

            # 母牛号列必须存在
            if actual_columns['母牛号'] is None:
                logger.error("选配报告中缺少母牛号列")
                return None

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            records = []
            for _, row in mating_df.iterrows():
                cow_id = self._get_value(row, actual_columns['母牛号'], str, '')
                if not cow_id or cow_id == 'nan':
                    continue

                record = {
                    "farmCode": farm_code,
                    "updateBy": self.update_by,
                    "updateTime": now_str,
                }
                for std_col, api_field in self.FIELD_MAPPING.items():
                    col_name = actual_columns.get(std_col)
                    if api_field == 'indexScore':
                        value = self._get_value(row, col_name, float, 0)
                    else:
                        value = self._get_value(row, col_name, str, '')
                    # 清理 nan
                    if isinstance(value, str) and value == 'nan':
                        value = ''
                    record[api_field] = value

                records.append(record)

            if not records:
                logger.warning("没有有效的选配记录")
                return None

            logger.info(f"准备推送 {len(records)} 条选配记录")
            return records

        except Exception as e:
            logger.error(f"准备推送数据失败: {e}", exc_info=True)
            return None

    def get_push_summary(self, records: List[Dict]) -> Dict:
        """
        获取推送数据摘要信息

        返回:
            {"total": int, "has_sexed": int, "has_conventional": int, "has_beef": int,
             "farm_code": str, "farm_name": str}
        """
        has_sexed = sum(1 for r in records if any(r.get(f'sexedSemen{i}') for i in range(1, 5)))
        has_conventional = sum(1 for r in records if any(r.get(f'conventionalSemen{i}') for i in range(1, 5)))
        has_beef = sum(1 for r in records if r.get('beefCattleFrozenSemen'))

        return {
            "total": len(records),
            "has_sexed": has_sexed,
            "has_conventional": has_conventional,
            "has_beef": has_beef,
            "farm_code": self.farm_info.get("farm_code", ""),
            "farm_name": self.farm_info.get("farm_name", ""),
        }

    def push_records(self, yqn_client, records: List[Dict],
                     batch_size=200, progress_callback=None) -> Dict:
        """
        推送给定的记录列表到伊起牛

        参数:
            yqn_client: YQNApiClient 实例
            records: 要推送的记录列表
            batch_size: 每批推送数量
            progress_callback: 进度回调 callback(records_done, total_records)

        返回:
            {"success": bool, "total": int, "success_count": int,
             "fail_count": int, "failures": [...], "failed_records": [...]}
        """
        if not records:
            return {"success": False, "total": 0, "success_count": 0,
                    "fail_count": 0, "failures": [], "failed_records": [],
                    "error": "无有效数据"}

        all_failures = []
        failed_records = []
        total_success = 0
        total = len(records)

        for batch_idx in range(0, total, batch_size):
            batch = records[batch_idx:batch_idx + batch_size]

            try:
                result = yqn_client.batch_add_selection(batch)
                msg = result.get("msg", "")
                # 解析 msg: "共N条数据，成功N条，失败N条"
                match = re.search(r'成功(\d+)条', msg)
                if match:
                    total_success += int(match.group(1))
                else:
                    # 如果没有明确的成功数，假设本批全部成功
                    total_success += len(batch)

                # 收集失败详情
                fail_data = result.get("data")
                if fail_data and isinstance(fail_data, list):
                    all_failures.extend(fail_data)
                    # 收集失败的记录用于重试
                    failed_ear_nums = {str(f.get("earNum", "")) for f in fail_data if f.get("earNum")}
                    for r in batch:
                        if str(r.get("earNum", "")) in failed_ear_nums:
                            failed_records.append(r)

            except Exception as e:
                logger.error(f"批次推送失败: {e}")
                all_failures.append({
                    "batch": batch_idx // batch_size + 1,
                    "error": str(e),
                    "count": len(batch)
                })
                # 整批视为失败，全部加入重试列表
                failed_records.extend(batch)

            # 报告进度（当前已处理的记录数）
            records_done = min(batch_idx + len(batch), total)
            if progress_callback:
                progress_callback(records_done, total)

        self._save_push_log(
            success=len(all_failures) == 0,
            message=f"成功 {total_success} 条，失败 {total - total_success} 条",
            target="yqn_api"
        )

        return {
            "success": len(all_failures) == 0,
            "total": total,
            "success_count": total_success,
            "fail_count": total - total_success,
            "failures": all_failures,
            "failed_records": failed_records,
        }

    def push_to_yqn_api(self, yqn_client, batch_size=200, progress_callback=None) -> Dict:
        """
        通过 YQNApiClient 推送到伊起牛（自动准备数据）

        参数:
            yqn_client: YQNApiClient 实例
            batch_size: 每批推送数量
            progress_callback: 进度回调 callback(records_done, total_records)

        返回:
            同 push_records
        """
        records = self.prepare_push_data()
        if not records:
            return {"success": False, "total": 0, "success_count": 0,
                    "fail_count": 0, "failures": [], "failed_records": [],
                    "error": "无有效数据"}

        return self.push_records(yqn_client, records, batch_size, progress_callback)

    def push_to_local(self) -> bool:
        """保存推送数据到本地文件（测试/备份用）"""
        records = self.prepare_push_data()
        if not records:
            return False

        output_file = self.project_path / "api_push_data.json"
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            logger.info(f"推送数据已保存到: {output_file}")
            self._save_push_log(True, "保存到本地文件", str(output_file))
            return True
        except Exception as e:
            logger.error(f"保存失败: {e}")
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

        log_file = self.project_path / "push_log.json"

        logs = []
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                    if isinstance(existing, list):
                        logs = existing
                    else:
                        logs = [existing]
            except Exception:
                pass

        logs.append(log_data)
        logs = logs[-20:]

        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存日志失败: {e}")

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
        except Exception:
            pass

        return None
