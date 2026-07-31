"""
伊起牛牧场数据对接页面 - 支持多选模式
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QMessageBox, QTableWidget, QTableWidgetItem,
    QDialog, QListWidget, QProgressDialog, QGroupBox, QFrame,
    QTreeWidget, QTreeWidgetItem, QCheckBox, QSplitter,
    QHeaderView, QButtonGroup, QRadioButton, QListWidgetItem,
    QAbstractItemView, QComboBox, QInputDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QBrush
from pathlib import Path
from datetime import datetime
import logging
import pandas as pd

from api.yqn_api_client import YQNApiClient
from api.hmy_api_client import HMYApiClient
from core.data.hmy_data_converter import HMYDataConverter
from core.data.yqn_data_converter import YQNDataConverter
from config.hmy_access import can_use_interface_data, is_hmy_user_allowed
from utils.file_manager import FileManager
from core.data.uploader import (
    upload_and_standardize_breeding_data,
    upload_and_standardize_cow_data,
)


HMY_CLASSIFICATION_OPTIONS = (
    ("大区", "area"),
    ("有机(HP)", "organic_hp"),
    ("热应激区域", "heat_stress"),
    ("牛源模式", "source_mode"),
    ("A2", "a2"),
    ("DHA", "dha"),
)

DEFAULT_GROUP_DATASET_SELECTION = {
    "herd": True,
    "breeding": True,
}


def group_dataset_selection_policy(
    selection=None,
    *,
    full_analysis: bool,
    has_local_farms: bool = False,
) -> dict:
    """校验牧场组下载范围，并返回 UI 可直接使用的说明。"""

    raw = (
        DEFAULT_GROUP_DATASET_SELECTION
        if selection is None
        else selection
    )
    if not isinstance(raw, dict):
        raw = {}
    normalized = {
        "herd": bool(raw.get("herd", False)),
        "breeding": bool(raw.get("breeding", False)),
    }
    if not any(normalized.values()):
        error = "请至少选择“牛群/系谱数据”或“配种记录”中的一项。"
    elif has_local_farms and not normalized["herd"]:
        error = (
            "包含本地补充牧场时，必须下载牛群/系谱数据；"
            "本地补充牧场项目至少需要牛群/系谱文件。"
        )
    elif full_analysis and not normalized["herd"]:
        error = "创建牧场组并批量分析时，必须下载牛群/系谱数据。"
    else:
        error = ""

    selected_labels = []
    if normalized["herd"]:
        selected_labels.append("牛群/系谱数据")
    if normalized["breeding"]:
        selected_labels.append("配种记录")

    notice = ""
    if full_analysis and normalized["herd"] and not normalized["breeding"]:
        notice = (
            "未下载配种记录时，已配公牛性状、已配公牛近交系数及"
            "隐性基因分析会自动跳过。"
        )

    return {
        "selection": normalized,
        "valid": not error,
        "error": error,
        "notice": notice,
        "selected_text": "、".join(selected_labels),
    }


class GroupDatasetSelectionDialog(QDialog):
    """牧场组开始下载前的数据范围选择。"""

    def __init__(
        self,
        *,
        full_analysis: bool,
        has_local_farms: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.full_analysis = bool(full_analysis)
        self.has_local_farms = bool(has_local_farms)
        self.setWindowTitle("选择下载数据")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        title = QLabel(
            "请选择本次牧场组需要下载的数据："
        )
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        self.herd_checkbox = QCheckBox("牛群/系谱数据")
        self.herd_checkbox.setChecked(True)
        self.herd_checkbox.setToolTip(
            "用于母牛性状、指数、系谱及母牛近交等分析"
        )
        layout.addWidget(self.herd_checkbox)

        self.breeding_checkbox = QCheckBox("配种记录")
        self.breeding_checkbox.setChecked(True)
        self.breeding_checkbox.setToolTip(
            "用于已配公牛性状、近交系数及隐性基因分析"
        )
        layout.addWidget(self.breeding_checkbox)

        if self.full_analysis or self.has_local_farms:
            self.herd_checkbox.setEnabled(False)
            self.herd_checkbox.setToolTip(
                "批量分析或本地补充牧场必须包含牛群/系谱数据"
            )

        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.herd_checkbox.toggled.connect(self._refresh_policy)
        self.breeding_checkbox.toggled.connect(self._refresh_policy)
        self._refresh_policy()

    def dataset_selection(self) -> dict:
        return {
            "herd": self.herd_checkbox.isChecked(),
            "breeding": self.breeding_checkbox.isChecked(),
        }

    def _refresh_policy(self):
        policy = group_dataset_selection_policy(
            self.dataset_selection(),
            full_analysis=self.full_analysis,
            has_local_farms=self.has_local_farms,
        )
        ok_button = self.buttons.button(
            QDialogButtonBox.StandardButton.Ok
        )
        if ok_button is not None:
            ok_button.setEnabled(policy["valid"])
        message = policy["error"] or policy["notice"]
        color = "#c0392b" if policy["error"] else "#8a6d3b"
        self.hint_label.setText(message)
        self.hint_label.setStyleSheet(f"color: {color};")


def _category_name(value) -> str:
    """把缺失分类统一归入“其他”组。"""
    normalized = str(value or "").strip()
    return normalized or "其他"


def _group_sort_key(name: str):
    """“其他”固定排在正常分类之后。"""
    if name == "是":
        return (0, name)
    if name == "否":
        return (1, name)
    if name == "其他":
        return (3, name)
    return (2, name)


def group_hmy_farms(farms: list, field: str) -> dict:
    """按慧牧云指定分类维度组织牧场。"""
    groups = {}
    for farm in farms:
        group_name = _category_name(farm.get(field))
        groups.setdefault(group_name, []).append(farm)
    return {
        name: groups[name]
        for name in sorted(groups, key=_group_sort_key)
    }


def farm_selection_action_policy(selected_count: int) -> dict:
    """返回单选/多选对应的创建入口策略，避免 UI 与执行分支不一致。"""
    count = max(0, int(selected_count or 0))
    has_selection = count > 0
    is_group = count >= 2
    return {
        "preview_enabled": has_selection,
        "create_enabled": has_selection,
        "auto_report_enabled": has_selection,
        "create_text": (
            "创建牧场组项目" if is_group else "创建牧场项目"
        ),
        "auto_report_text": (
            "创建牧场组并批量分析"
            if is_group
            else "创建项目并自动生成报告"
        ),
        "auto_report_tooltip": (
            "逐场下载并完成育种分析，最终生成牧场组汇总Excel；"
            "不执行个体选配，不批量生成PPT"
            if is_group
            else ""
        ),
    }


def build_group_task_completion_lines(result: dict) -> list[str]:
    """构建牧场组完成提示，确保失败任务不会被描述为已保存成功。"""
    completed = result.get("completed", [])
    all_incomplete = result.get("failed", [])
    paused = [
        item for item in all_incomplete
        if item.get("memory_pressure")
    ]
    failed = [
        item for item in all_incomplete
        if not item.get("memory_pressure")
    ]
    summary_error = str(result.get("summary_error") or "")
    excel_path = result.get("excel_path")
    full_analysis = bool(result.get("full_analysis"))

    if paused:
        summary_line = (
            f"牧场组任务处理完成：成功 {len(completed)} 个，"
            f"安全暂停 {len(paused)} 个，失败 {len(failed)} 个。"
        )
    else:
        summary_line = (
            f"牧场组任务处理完成：成功 {len(completed)} 个，"
            f"失败 {len(failed)} 个。"
        )
    lines = [summary_line, ""]
    if excel_path:
        lines.append("✅ 已生成最终牧场组汇总Excel")
        lines.append("ℹ️ 牧场组不生成PPT；PPT请按单牧场需要生成")
    elif paused:
        lines.append("⏸️ 检测到内存安全余量不足，批处理已安全暂停")
        lines.append("已完成牧场和已提交阶段均已保留，不需要重新开始。")
        lines.append(
            "请先关闭其他应用释放内存，再点击“释放内存后继续处理”。"
        )
    elif full_analysis and failed:
        lines.append("⚠️ 存在失败牧场，未生成牧场组汇总Excel")
        lines.append("已完成牧场的子项目结果已保留。")
        lines.append("请检查失败任务，重试或从汇总范围移除后再生成。")
    elif full_analysis and summary_error:
        lines.append("⚠️ 单牧场任务已完成，但最终汇总未发布")
        lines.append(summary_error[:240])
        lines.append("单牧场结果均已保留，可修复问题后仅重试最终汇总。")
    elif full_analysis:
        lines.append("⚠️ 单牧场任务已完成，但最终汇总Excel未生成")
        lines.append("单牧场结果均已保留，请检查汇总任务状态后重试。")
    elif completed and not failed:
        lines.append("✅ 每个牧场的数据已保存到独立子项目目录")
    elif completed:
        lines.append(
            f"✅ 已完成的 {len(completed)} 个牧场数据已保存到独立子项目目录"
        )
        lines.append(
            f"⚠️ 另有 {len(failed)} 个牧场未完成，修复问题后可继续处理。"
        )
    else:
        lines.append("⚠️ 本次没有牧场完成，未生成可用的子项目数据")
        lines.append("请检查失败原因，修复后继续处理未完成任务。")

    if paused:
        lines.append("")
        lines.append("暂停任务：")
        for item in paused[:8]:
            lines.append(
                f"• {item.get('farm_name')}: {str(item.get('error', ''))[:80]}"
            )

    if failed:
        lines.append("")
        lines.append("失败任务：")
        for item in failed[:8]:
            lines.append(
                f"• {item.get('farm_name')}: {str(item.get('error', ''))[:80]}"
            )

    return lines


class DataDownloadWorker(QThread):
    """后台下载和处理数据的工作线程"""
    progress = pyqtSignal(int, str)  # (百分比, 状态消息)
    finished = pyqtSignal(Path)  # Excel文件路径
    error = pyqtSignal(str)  # 错误消息

    def __init__(
        self,
        api_client,
        farms,
        project_path,
        is_merged=False,
        local_farms=None,
    ):
        """
        初始化下载工作线程

        参数:
            api_client: API客户端
            farms: 牧场列表 [{"code": ..., "name": ..., "cow_count": ...}, ...]
            project_path: 项目路径
            is_merged: 是否为合并模式（多选）
        """
        super().__init__()
        self.api_client = api_client
        self.farms = farms
        self.project_path = project_path
        self.is_merged = is_merged
        self.local_farms = local_farms or []
        self.logger = logging.getLogger(__name__)

    def run(self):
        """执行数据下载和标准化流程"""
        try:
            total_farms = len(self.farms)
            all_api_data = []

            # 步骤1: 下载各牧场牛群数据
            for i, farm in enumerate(self.farms):
                farm_code = farm['code']
                farm_name = farm['name']

                progress_pct = int(10 + (i / total_farms) * 15)
                self.progress.emit(progress_pct, f"正在下载 {farm_name} 数据...")

                api_data = self.api_client.get_farm_herd(farm_code)
                cow_count = len(api_data.get('data', []))
                farm['cow_count'] = cow_count  # 更新实际数量

                all_api_data.append((farm_code, api_data))
                self.logger.info(f"下载牧场 {farm_code} 数据完成: {cow_count} 头")
                if cow_count:
                    farm_raw_dir = (
                        self.project_path
                        / "raw_data"
                        / "farms"
                        / str(farm_code)
                    )
                    YQNDataConverter.convert_herd_to_excel(
                        api_data, farm_raw_dir / "cow_data.xlsx"
                    )

            # 步骤2: 合并数据（如果是多选模式）
            self.progress.emit(25, "正在合并数据...")
            if self.is_merged:
                merged_data = YQNDataConverter.merge_herd_data(all_api_data)
            else:
                # 单选模式，直接使用
                merged_data = all_api_data[0][1]

            total_cows = len(merged_data.get('data', []))
            self.progress.emit(28, f"数据合并完成，共 {total_cows} 头")

            # 步骤3: 转换为Excel
            self.progress.emit(28, "正在转换数据格式...")
            raw_data_dir = self.project_path / "raw_data"
            raw_data_dir.mkdir(parents=True, exist_ok=True)

            excel_path = raw_data_dir / "cow_data.xlsx"

            # 使用转换器（不需要再添加前缀，merge_herd_data已处理）
            YQNDataConverter.convert_herd_to_excel(merged_data, excel_path)
            self.progress.emit(32, "数据格式转换完成")

            # 步骤3.5: 下载配种记录
            self.progress.emit(32, "正在下载配种记录...")
            try:
                all_breeding_data = []
                for i, farm in enumerate(self.farms):
                    farm_code = farm['code']
                    farm_name = farm['name']
                    progress_pct = int(32 + (i / total_farms) * 10)
                    self.progress.emit(progress_pct, f"正在下载 {farm_name} 配种记录...")

                    breeding_data = self.api_client.get_breeding_records(farm_code)
                    all_breeding_data.append((farm_code, breeding_data))

                    # 统计记录数
                    data = breeding_data.get("data", {})
                    count = len(data.get("rows", [])) if isinstance(data, dict) else 0
                    self.logger.info(f"下载牧场 {farm_code} 配种记录完成: {count} 条")
                    if count:
                        farm_raw_dir = (
                            self.project_path
                            / "raw_data"
                            / "farms"
                            / str(farm_code)
                        )
                        YQNDataConverter.convert_breeding_records_to_excel(
                            breeding_data,
                            farm_raw_dir / "breeding_records.xlsx",
                        )

                # 合并配种记录（多牧场时加站号前缀）
                self.progress.emit(42, "正在转换配种记录...")
                merged_breeding = YQNDataConverter.merge_breeding_records(
                    all_breeding_data, force_prefix=self.is_merged
                )

                if merged_breeding:
                    # 构建合并后的 api_data 格式供转换方法使用
                    merged_breeding_api = {"data": {"rows": merged_breeding}}
                    breeding_excel_path = raw_data_dir / "breeding_records.xlsx"
                    YQNDataConverter.convert_breeding_records_to_excel(
                        merged_breeding_api, breeding_excel_path
                    )
                    self.progress.emit(45, f"配种记录下载完成，共 {len(merged_breeding)} 条")
                else:
                    self.logger.warning("配种记录为空，跳过")
                    self.progress.emit(45, "配种记录为空，已跳过")

            except Exception as e:
                self.logger.warning(f"配种记录下载失败（不影响主流程）: {e}")
                self.progress.emit(45, f"配种记录下载失败: {str(e)[:50]}，继续处理...")

            # 步骤4: 标准化处理
            self.progress.emit(50, "正在进行数据标准化...")

            def standardize_progress(*args):
                if len(args) == 2:
                    pct, msg = args
                elif len(args) == 1:
                    pct = args[0]
                    msg = f"{pct}%"
                else:
                    return

                try:
                    mapped_pct = 60 + int(pct * 0.28)
                    self.progress.emit(mapped_pct, f"标准化: {msg}")
                except Exception as e:
                    self.logger.warning(f"进度回调出错: {e}, args={args}")

            standardized_path = upload_and_standardize_cow_data(
                input_files=[excel_path],
                project_path=self.project_path,
                progress_callback=standardize_progress,
                source_system="伊起牛"
            )

            self.progress.emit(88, "牛群数据标准化完成")

            # 步骤4.5: 配种记录标准化
            breeding_excel = self.project_path / "raw_data" / "breeding_records.xlsx"
            if breeding_excel.exists():
                self.progress.emit(90, "正在标准化配种记录...")
                try:
                    from core.data.uploader import upload_and_standardize_breeding_data
                    upload_and_standardize_breeding_data(
                        input_files=[breeding_excel],
                        project_path=self.project_path,
                        source_system="伊起牛"
                    )
                    self.progress.emit(93, "配种记录标准化完成")
                except Exception as e:
                    self.logger.warning(f"配种记录标准化失败（不影响主流程）: {e}")

            # 步骤4.6: 下载冻精库存并标准化为备选公牛
            self.progress.emit(93, "正在下载冻精库存...")
            try:
                all_stock_records = []
                for farm in self.farms:
                    farm_code = farm['code']
                    farm_name = farm['name']
                    self.progress.emit(93, f"正在下载 {farm_name} 冻精库存...")

                    stock_data = self.api_client.get_stock_detail(farm_code)
                    stock_records = stock_data.get("data", [])
                    all_stock_records.extend(stock_records)
                    self.logger.info(f"下载牧场 {farm_code} 冻精库存: {len(stock_records)} 条")

                if all_stock_records:
                    merged_stock_data = {"code": 200, "data": all_stock_records}
                    semen_inventory_path = raw_data_dir / "semen_inventory.xlsx"
                    YQNDataConverter.convert_stock_to_semen_inventory(
                        merged_stock_data, semen_inventory_path
                    )
                    in_stock = sum(1 for r in all_stock_records if r.get("stockSum", 0) > 0)
                    self.progress.emit(95, f"冻精库存下载完成，{in_stock} 种有库存")

                    # 自动标准化为备选公牛数据
                    self.progress.emit(96, "正在标准化冻精库存为备选公牛...")
                    from core.data.uploader import upload_and_standardize_bull_data
                    upload_and_standardize_bull_data(
                        input_files=[semen_inventory_path],
                        project_path=self.project_path,
                        progress_callback=None
                    )
                    self.progress.emit(98, "备选公牛数据标准化完成")
                else:
                    self.logger.warning("冻精库存为空，跳过")
                    self.progress.emit(95, "冻精库存为空，已跳过")

            except Exception as e:
                self.logger.warning(f"冻精库存下载/标准化失败（不影响主流程）: {e}")
                self.progress.emit(95, f"冻精库存处理失败: {str(e)[:50]}，继续处理...")

            self.progress.emit(98, "正在合并本地补充牧场...")
            from core.data.composite_farm_manager import (
                finalize_composite_project,
            )

            finalize_composite_project(
                self.project_path,
                self.farms,
                self.local_farms,
                data_source="伊起牛",
                ids_are_prefixed=self.is_merged,
                progress_callback=lambda pct, msg: self.progress.emit(
                    98 + int(pct * 0.02), msg
                ),
            )

            # 步骤5: 完成
            self.progress.emit(100, "牧场项目创建成功!")
            self.finished.emit(excel_path)

        except Exception as e:
            self.logger.exception("数据下载处理失败")
            self.error.emit(f"处理失败: {str(e)}")


class HMYDataDownloadWorker(QThread):
    """慧牧云牛群及配种数据下载和标准化线程。"""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(Path)
    error = pyqtSignal(str)

    def __init__(
        self,
        api_client,
        farms,
        project_path,
        is_merged=False,
        local_farms=None,
    ):
        super().__init__()
        self.api_client = api_client
        self.farms = farms
        self.project_path = Path(project_path)
        self.is_merged = is_merged
        self.local_farms = local_farms or []

    def run(self):
        try:
            all_api_data = []
            total_farms = len(self.farms)
            for index, farm in enumerate(self.farms):
                pct = 5 + int(index / max(total_farms, 1) * 35)
                self.progress.emit(pct, f"正在下载 {farm['name']} 牛群数据...")
                api_data = self.api_client.get_farm_herd(farm["code"])
                api_farm_name = str(api_data.get("farmName") or "").strip()
                if api_farm_name:
                    farm["name"] = api_farm_name
                farm["cow_count"] = len(api_data.get("data") or [])
                all_api_data.append((farm["code"], api_data))
                if farm["cow_count"]:
                    farm_raw_dir = (
                        self.project_path
                        / "raw_data"
                        / "farms"
                        / str(farm["code"])
                    )
                    HMYDataConverter.convert_herd_to_excel(
                        api_data, farm_raw_dir / "cow_data.xlsx"
                    )

            self.progress.emit(40, "正在合并牛群数据...")
            if self.is_merged:
                merged_data = HMYDataConverter.merge_herd_data(all_api_data)
            else:
                merged_data = all_api_data[0][1]

            raw_dir = self.project_path / "raw_data"
            raw_dir.mkdir(parents=True, exist_ok=True)
            excel_path = raw_dir / "cow_data.xlsx"
            HMYDataConverter.convert_herd_to_excel(merged_data, excel_path)

            breeding_excel_path = None
            self.progress.emit(45, "正在下载慧牧云配种记录...")
            try:
                all_breeding_data = []
                for index, farm in enumerate(self.farms):
                    pct = 45 + int(index / max(total_farms, 1) * 15)
                    self.progress.emit(
                        pct,
                        f"正在下载 {farm['name']} 配种记录...",
                    )
                    breeding_data = self.api_client.get_breeding_records(
                        farm["code"]
                    )
                    farm["breeding_count"] = len(
                        breeding_data.get("data") or []
                    )
                    all_breeding_data.append(
                        (farm["code"], breeding_data)
                    )
                    if farm["breeding_count"]:
                        farm_raw_dir = (
                            self.project_path
                            / "raw_data"
                            / "farms"
                            / str(farm["code"])
                        )
                        HMYDataConverter.convert_breeding_records_to_excel(
                            breeding_data,
                            farm_raw_dir / "breeding_records.xlsx",
                        )

                merged_breeding = HMYDataConverter.merge_breeding_records(
                    all_breeding_data,
                    force_prefix=self.is_merged,
                )
                if merged_breeding.get("data"):
                    breeding_excel_path = (
                        raw_dir / "breeding_records.xlsx"
                    )
                    HMYDataConverter.convert_breeding_records_to_excel(
                        merged_breeding,
                        breeding_excel_path,
                    )
                self.progress.emit(60, "慧牧云配种记录下载完成")
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "慧牧云配种记录下载失败（不影响牛群数据）: %s",
                    exc,
                )
                self.progress.emit(
                    60,
                    f"配种记录下载失败: {str(exc)[:50]}，继续处理牛群数据...",
                )

            self.progress.emit(65, "正在标准化慧牧云牛群数据...")

            def standardize_progress(*args):
                if not args:
                    return
                value = args[0]
                message = args[1] if len(args) > 1 else ""
                try:
                    numeric_value = float(value)
                except (TypeError, ValueError):
                    # 标准化器有少量仅发送文字状态的回调。
                    self.progress.emit(65, f"标准化: {message or value}")
                    return
                self.progress.emit(
                    65 + int(numeric_value * 0.15),
                    f"标准化: {message or value}",
                )

            upload_and_standardize_cow_data(
                input_files=[excel_path],
                project_path=self.project_path,
                progress_callback=standardize_progress,
                source_system="慧牧云",
            )

            if breeding_excel_path and breeding_excel_path.exists():
                self.progress.emit(80, "正在标准化慧牧云配种记录...")

                def breeding_progress(*args):
                    if not args:
                        return
                    value = args[0]
                    message = args[1] if len(args) > 1 else ""
                    try:
                        numeric_value = float(value)
                    except (TypeError, ValueError):
                        self.progress.emit(
                            80,
                            f"标准化配种记录: {message or value}",
                        )
                        return
                    self.progress.emit(
                        80 + int(numeric_value * 0.15),
                        f"标准化配种记录: {message or value}",
                    )

                try:
                    upload_and_standardize_breeding_data(
                        input_files=[breeding_excel_path],
                        project_path=self.project_path,
                        progress_callback=breeding_progress,
                        source_system="慧牧云",
                    )
                except Exception as exc:
                    logging.getLogger(__name__).warning(
                        "慧牧云配种记录标准化失败（不影响牛群数据）: %s",
                        exc,
                    )
                    self.progress.emit(
                        95,
                        f"配种记录标准化失败: {str(exc)[:50]}，继续创建项目...",
                    )

            self.progress.emit(95, "正在合并本地补充牧场...")
            from core.data.composite_farm_manager import (
                finalize_composite_project,
            )

            finalize_composite_project(
                self.project_path,
                self.farms,
                self.local_farms,
                data_source="慧牧云",
                ids_are_prefixed=self.is_merged,
                progress_callback=lambda pct, msg: self.progress.emit(
                    95 + int(pct * 0.05), msg
                ),
            )
            self.progress.emit(100, "慧牧云牧场项目创建成功")
            self.finished.emit(excel_path)
        except Exception as exc:
            logging.getLogger(__name__).exception("慧牧云数据下载处理失败")
            self.error.emit(f"处理失败: {exc}")


class FarmListItem(QWidget):
    """牧场列表项（带勾选框）"""

    checked_changed = pyqtSignal(str, bool)  # farm_code, is_checked

    API_FARMCODE_WIDTH = 105
    FARM_NUMBER_WIDTH = 90

    def __init__(
        self,
        farm_data: dict,
        show_hmy_identity: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.farm_data = farm_data
        self.show_hmy_identity = show_hmy_identity
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        # 勾选框
        self.checkbox = QCheckBox()
        self.checkbox.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(self.checkbox)

        api_farmcode = str(self.farm_data.get("farmCode", "")).strip()
        full_name = str(self.farm_data.get("name", "")).strip()
        if self.show_hmy_identity:
            farm_number, farm_name = HMYDataConverter.split_farm_name(
                full_name
            )
        else:
            farm_number, farm_name = "", full_name

        self.api_farmcode_label = QLabel(api_farmcode)
        self.api_farmcode_label.setFixedWidth(self.API_FARMCODE_WIDTH)
        self.api_farmcode_label.setToolTip(api_farmcode)
        self.api_farmcode_label.setStyleSheet(
            "font-size: 12px; color: #606266;"
        )
        layout.addWidget(self.api_farmcode_label)

        self.farm_name_label = QLabel(farm_name)
        self.farm_name_label.setToolTip(farm_name)
        self.farm_name_label.setStyleSheet(
            "font-size: 13px; color: #303133;"
        )
        layout.addWidget(self.farm_name_label, 1)

        self.farm_number_label = None
        if self.show_hmy_identity:
            self.farm_number_label = QLabel(farm_number)
            self.farm_number_label.setFixedWidth(self.FARM_NUMBER_WIDTH)
            self.farm_number_label.setToolTip(farm_number)
            self.farm_number_label.setStyleSheet(
                "font-size: 12px; color: #606266;"
            )
            layout.addWidget(self.farm_number_label)

    def _on_checkbox_changed(self, state):
        is_checked = state == Qt.CheckState.Checked.value
        farm_code = self.farm_data.get('farmCode', '')
        self.checked_changed.emit(farm_code, is_checked)

    def mousePressEvent(self, event):
        """点击整行任意位置切换勾选"""
        self.checkbox.setChecked(not self.checkbox.isChecked())

    def is_checked(self):
        return self.checkbox.isChecked()

    def set_checked(self, checked: bool):
        self.checkbox.setChecked(checked)


class LocalFarmListItem(QWidget):
    """本地补充牧场列表项。"""

    checked_changed = pyqtSignal(str, bool)
    view_requested = pyqtSignal(str)
    reupload_requested = pyqtSignal(str)
    remove_requested = pyqtSignal(str)

    def __init__(self, farm_data: dict, parent=None):
        super().__init__(parent)
        self.farm_data = farm_data
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        self.checkbox = QCheckBox()
        self.checkbox.stateChanged.connect(
            lambda state: self.checked_changed.emit(
                str(self.farm_data.get("farmCode", "")),
                state == Qt.CheckState.Checked.value,
            )
        )
        layout.addWidget(self.checkbox)

        code = str(self.farm_data.get("farmCode", ""))
        code_label = QLabel(code)
        code_label.setFixedWidth(90)
        code_label.setStyleSheet("font-size: 12px; color: #606266;")
        layout.addWidget(code_label)

        name_label = QLabel(str(self.farm_data.get("name", "")))
        name_label.setStyleSheet("font-size: 13px; color: #303133;")
        layout.addWidget(name_label, 1)

        source_label = QLabel(
            f"本地·{self.farm_data.get('source_system', '')} "
            f"({self.farm_data.get('cow_count', 0)}头)"
        )
        source_label.setStyleSheet("font-size: 11px; color: #909399;")
        layout.addWidget(source_label)

        button_style = """
            QPushButton {
                padding: 3px 6px; color: #606266; background: white;
                border: 1px solid #dcdfe6; border-radius: 3px;
            }
            QPushButton:hover { background: #f5f7fa; }
        """
        view_button = QPushButton("详情")
        view_button.setFixedWidth(48)
        view_button.setStyleSheet(button_style)
        view_button.clicked.connect(lambda: self.view_requested.emit(code))
        layout.addWidget(view_button)

        reupload_button = QPushButton("重传")
        reupload_button.setFixedWidth(48)
        reupload_button.setStyleSheet(button_style)
        reupload_button.clicked.connect(
            lambda: self.reupload_requested.emit(code)
        )
        layout.addWidget(reupload_button)

        remove_button = QPushButton("移除")
        remove_button.setFixedWidth(48)
        remove_button.setStyleSheet(button_style)
        remove_button.clicked.connect(
            lambda: self.remove_requested.emit(code)
        )
        layout.addWidget(remove_button)

    def set_checked(self, checked: bool):
        self.checkbox.setChecked(checked)


class FarmSelectionPage(QWidget):
    """牧场数据对接页面，支持伊起牛和慧牧云。"""

    project_created = pyqtSignal(Path)  # 项目创建完成信号，携带项目路径
    user_name_fetched = pyqtSignal(str)  # 获取到用户真实姓名

    def __init__(self, yqn_token=None, username=None, parent=None):
        super().__init__(parent)
        self.yqn_token = yqn_token
        self.username = username  # 登录账号，作为姓名获取失败时的 fallback
        self.interface_access_allowed = can_use_interface_data(username)
        self.hmy_access_allowed = is_hmy_user_allowed(username)
        if yqn_token and self.interface_access_allowed:
            self.data_source = "伊起牛"
        elif self.hmy_access_allowed:
            self.data_source = "慧牧云"
        else:
            self.data_source = ""
        self.api_client = None
        self.all_farms = []  # 所有牧场数据
        self.selected_farms = {}  # 已选牧场 {farm_code: farm_data}
        self.local_farms = {}  # 本地补充牧场 {farm_code: farm_data}
        self.local_farm_list_items = {}
        self.current_region = None  # 当前选中的区域
        self.current_group_farms = []  # 当前分组或搜索结果中的牧场
        self.farm_list_items = {}  # farm_code -> FarmListItem
        self.logger = logging.getLogger(__name__)

        self.init_ui()

        from PyQt6.QtCore import QTimer
        if self.data_source:
            QTimer.singleShot(500, lambda: self.switch_data_source(self.data_source))

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 顶部标题栏
        header_layout = QHBoxLayout()
        header_layout.setSpacing(20)

        # 标题
        title_label = QLabel("🐄 牧场数据对接")
        title_font = QFont("微软雅黑", 16, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #303133;")
        header_layout.addWidget(title_label)

        self.source_buttons = {}
        for source in ("伊起牛", "慧牧云"):
            button = QPushButton(source)
            button.setCheckable(True)
            button.setMinimumWidth(90)
            button.clicked.connect(
                lambda checked=False, selected=source: self.switch_data_source(selected)
            )
            self.source_buttons[source] = button
            header_layout.addWidget(button)

        header_layout.addStretch()

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索牧场名称或站号...")
        self.search_input.setFixedWidth(200)
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 6px 12px;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #409eff;
            }
        """)
        self.search_input.returnPressed.connect(self._do_search)
        header_layout.addWidget(self.search_input)

        # 搜索按钮
        self.search_btn = QPushButton("搜索")
        self.search_btn.setFixedWidth(60)
        self.search_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                background-color: #409eff;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #66b1ff;
            }
            QPushButton:pressed {
                background-color: #3a8ee6;
            }
        """)
        self.search_btn.clicked.connect(self._do_search)
        header_layout.addWidget(self.search_btn)

        layout.addLayout(header_layout)

        # 主内容区域（左右分栏）
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background-color: #e4e7ed; }")

        # 左侧面板：状态筛选 + 区域树
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(15)

        # 状态筛选
        status_group = QGroupBox("状态筛选")
        self.status_filter_widget = status_group
        status_group.setStyleSheet("""
            QGroupBox {
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #e4e7ed;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(10, 10, 10, 10)

        self.status_group = QButtonGroup(self)
        status_options = [("可用", "0"), ("关停", "1"), ("全部", "all")]

        for i, (label, value) in enumerate(status_options):
            radio = QRadioButton(label)
            radio.setProperty("status_value", value)
            radio.setStyleSheet("font-size: 12px; font-weight: normal;")
            self.status_group.addButton(radio, i)
            status_layout.addWidget(radio)
            if i == 0:  # 默认选中"可用"
                radio.setChecked(True)

        self.status_group.buttonClicked.connect(self.on_status_changed)

        # 排除Z牧场复选框（默认勾选）
        self.exclude_z_checkbox = QCheckBox("排除Z牧场")
        self.exclude_z_checkbox.setChecked(True)
        self.exclude_z_checkbox.setStyleSheet("font-size: 12px; font-weight: normal;")
        self.exclude_z_checkbox.setToolTip("排除牧场名称以Z结尾的牧场")
        self.exclude_z_checkbox.stateChanged.connect(self.on_status_changed)
        status_layout.addWidget(self.exclude_z_checkbox)

        status_group.setLayout(status_layout)
        left_layout.addWidget(status_group)

        # 牧场类型筛选（多选，两列布局）
        type_group = QGroupBox("牧场类型")
        self.type_filter_widget = type_group
        type_group.setStyleSheet("""
            QGroupBox {
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #e4e7ed;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        type_layout = QVBoxLayout()
        type_layout.setContentsMargins(10, 10, 10, 10)
        type_layout.setSpacing(5)

        # 牧场类型选项：(显示名称, 实际值)
        self.farm_type_options = [
            ("主要供应商", "主要供应商"),
            ("大型牧业", "大型牧业"),
            ("合资牧场", "合资牧场"),
            ("社会奶源", "社会奶源"),
            ("畜牧公司", "畜牧公司"),
            ("其他(1)", "1"),
            ("其他(2)", "2"),
            ("未分类", None),
        ]

        # 两列布局
        from PyQt6.QtWidgets import QGridLayout
        type_grid = QGridLayout()
        type_grid.setSpacing(2)

        self.farm_type_checkboxes = []
        for i, (label, value) in enumerate(self.farm_type_options):
            cb = QCheckBox(label)
            cb.setProperty("type_value", value)
            cb.setStyleSheet("font-size: 11px; font-weight: normal;")
            # 默认只选中"社会奶源"
            cb.setChecked(value == "社会奶源")
            cb.stateChanged.connect(self.on_status_changed)
            row = i // 3
            col = i % 3
            type_grid.addWidget(cb, row, col)
            self.farm_type_checkboxes.append(cb)

        type_layout.addLayout(type_grid)

        # 全选/取消全选按钮
        type_btn_layout = QHBoxLayout()
        type_btn_layout.setSpacing(5)
        select_all_btn = QPushButton("全选")
        select_all_btn.setFixedHeight(22)
        select_all_btn.setStyleSheet("font-size: 11px;")
        select_all_btn.clicked.connect(self._select_all_farm_types)
        deselect_all_btn = QPushButton("取消")
        deselect_all_btn.setFixedHeight(22)
        deselect_all_btn.setStyleSheet("font-size: 11px;")
        deselect_all_btn.clicked.connect(self._deselect_all_farm_types)
        type_btn_layout.addWidget(select_all_btn)
        type_btn_layout.addWidget(deselect_all_btn)
        type_layout.addLayout(type_btn_layout)

        type_group.setLayout(type_layout)
        left_layout.addWidget(type_group)

        # 慧牧云分类方式
        classification_group = QGroupBox("分类方式")
        self.classification_widget = classification_group
        classification_group.setStyleSheet("""
            QGroupBox {
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #e4e7ed;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        classification_layout = QVBoxLayout(classification_group)
        classification_layout.setContentsMargins(10, 10, 10, 10)
        self.classification_combo = QComboBox()
        for label, field in HMY_CLASSIFICATION_OPTIONS:
            self.classification_combo.addItem(label, field)
        self.classification_combo.setStyleSheet(
            "font-size: 12px; padding: 4px 8px;"
        )
        self.classification_combo.currentIndexChanged.connect(
            self.on_hmy_classification_changed
        )
        classification_layout.addWidget(self.classification_combo)
        left_layout.addWidget(classification_group)
        classification_group.setVisible(False)

        # 区域树
        self.tree_group = QGroupBox("大区/区域")
        self.tree_group.setStyleSheet("""
            QGroupBox {
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #e4e7ed;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        tree_layout = QVBoxLayout()
        tree_layout.setContentsMargins(5, 5, 5, 5)

        self.region_tree = QTreeWidget()
        self.region_tree.setHeaderHidden(True)
        self.region_tree.setStyleSheet("""
            QTreeWidget {
                border: none;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 5px 2px;
            }
            QTreeWidget::item:hover {
                background-color: #ecf5ff;
            }
            QTreeWidget::item:selected {
                background-color: #409eff;
                color: white;
            }
        """)
        self.region_tree.itemClicked.connect(self.on_region_selected)
        tree_layout.addWidget(self.region_tree)
        self.tree_group.setLayout(tree_layout)
        left_layout.addWidget(self.tree_group, 1)

        splitter.addWidget(left_panel)

        # 右侧面板：牧场列表
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(10)

        # 牧场列表标题
        list_header = QHBoxLayout()
        self.region_title_label = QLabel("请选择区域")
        self.region_title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #303133;")
        list_header.addWidget(self.region_title_label)

        list_header.addStretch()

        self.add_local_farm_btn = QPushButton("添加本地牧场")
        self.add_local_farm_btn.setToolTip(
            "为当前伊起牛或慧牧云接口项目补充接口中没有的牧场"
        )
        self.add_local_farm_btn.setFixedHeight(32)
        self.add_local_farm_btn.setMinimumWidth(104)
        self.add_local_farm_btn.setStyleSheet(
            """
            QPushButton {
                padding: 5px 12px;
                color: #67c23a;
                background-color: white;
                border: 1px solid #67c23a;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #f0f9eb;
                border-color: #85ce61;
            }
            QPushButton:pressed { background-color: #e1f3d8; }
            QPushButton:disabled {
                color: #c0c4cc;
                background-color: #f5f7fa;
                border-color: #e4e7ed;
            }
            """
        )
        self.add_local_farm_btn.clicked.connect(self.on_add_local_farm)
        list_header.addWidget(self.add_local_farm_btn)

        self.select_group_btn = QPushButton("全选当前分组")
        self.select_group_btn.setEnabled(False)
        self.select_group_btn.setToolTip("选择当前大区、区域或分类中的全部牧场")
        self.select_group_btn.setFixedHeight(32)
        self.select_group_btn.setMinimumWidth(104)
        self.select_group_btn.setStyleSheet(
            """
            QPushButton {
                padding: 5px 12px;
                color: #409eff;
                background-color: white;
                border: 1px solid #409eff;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #ecf5ff;
                border-color: #66b1ff;
            }
            QPushButton:pressed { background-color: #d9ecff; }
            QPushButton:disabled {
                color: #c0c4cc;
                background-color: #f5f7fa;
                border-color: #e4e7ed;
            }
            """
        )
        self.select_group_btn.clicked.connect(
            lambda: self.set_current_group_checked(True)
        )
        list_header.addWidget(self.select_group_btn)

        self.deselect_group_btn = QPushButton("取消当前分组")
        self.deselect_group_btn.setEnabled(False)
        self.deselect_group_btn.setToolTip("取消当前大区、区域或分类中的全部牧场")
        self.deselect_group_btn.setFixedHeight(32)
        self.deselect_group_btn.setMinimumWidth(104)
        self.deselect_group_btn.setStyleSheet(
            """
            QPushButton {
                padding: 5px 12px;
                color: #606266;
                background-color: white;
                border: 1px solid #dcdfe6;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                color: #409eff;
                background-color: #ecf5ff;
                border-color: #c6e2ff;
            }
            QPushButton:pressed { background-color: #d9ecff; }
            QPushButton:disabled {
                color: #c0c4cc;
                background-color: #f5f7fa;
                border-color: #e4e7ed;
            }
            """
        )
        self.deselect_group_btn.clicked.connect(
            lambda: self.set_current_group_checked(False)
        )
        list_header.addWidget(self.deselect_group_btn)

        self.selected_count_label = QLabel("已选: 0个")
        self.selected_count_label.setStyleSheet("font-size: 13px; color: #409eff; font-weight: bold;")
        list_header.addWidget(self.selected_count_label)

        right_layout.addLayout(list_header)

        self.farm_column_header = QFrame()
        self.farm_column_header.setStyleSheet(
            """
            QFrame {
                background-color: #f5f7fa;
                border: 1px solid #e4e7ed;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QLabel {
                border: none;
                color: #606266;
                font-size: 12px;
                font-weight: bold;
            }
            """
        )
        column_header_layout = QHBoxLayout(self.farm_column_header)
        column_header_layout.setContentsMargins(8, 5, 8, 5)
        column_header_layout.setSpacing(10)
        column_header_layout.addSpacing(18)

        api_farmcode_header = QLabel("API farmcode")
        api_farmcode_header.setFixedWidth(
            FarmListItem.API_FARMCODE_WIDTH
        )
        column_header_layout.addWidget(api_farmcode_header)

        farm_name_header = QLabel("牧场名称")
        column_header_layout.addWidget(farm_name_header, 1)

        farm_number_header = QLabel("牧场编号")
        farm_number_header.setFixedWidth(FarmListItem.FARM_NUMBER_WIDTH)
        column_header_layout.addWidget(farm_number_header)

        self.farm_column_header.setVisible(self.data_source == "慧牧云")
        right_layout.addWidget(self.farm_column_header)

        # 牧场列表
        self.farm_list = QListWidget()
        self.farm_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e4e7ed;
                border-radius: 4px;
                font-size: 13px;
            }
            QListWidget::item {
                border-bottom: 1px solid #f2f6fc;
            }
            QListWidget::item:hover {
                background-color: #f5f7fa;
            }
        """)
        self.farm_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        right_layout.addWidget(self.farm_list, 1)

        self.local_farm_group = QGroupBox("本地补充牧场")
        local_layout = QVBoxLayout(self.local_farm_group)
        local_layout.setContentsMargins(5, 8, 5, 5)
        self.local_farm_list = QListWidget()
        self.local_farm_list.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.local_farm_list.setMaximumHeight(150)
        self.local_farm_list.setStyleSheet(
            """
            QListWidget {
                border: 1px solid #d9ecff; border-radius: 4px;
                background: #f8fbff;
            }
            QListWidget::item { border-bottom: 1px solid #edf5ff; }
            """
        )
        local_layout.addWidget(self.local_farm_list)
        self.local_farm_group.setVisible(False)
        right_layout.addWidget(self.local_farm_group)

        # 多选警告提示（初始隐藏）
        self.warning_frame = QFrame()
        self.warning_frame.setStyleSheet("""
            QFrame {
                background-color: #fdf6ec;
                border: 1px solid #faecd8;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        warning_layout = QVBoxLayout(self.warning_frame)
        warning_layout.setContentsMargins(12, 10, 12, 10)
        warning_layout.setSpacing(5)

        warning_title = QLabel("⚠️ 多选模式注意事项")
        warning_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #e6a23c;")
        warning_layout.addWidget(warning_title)

        warning_items = [
            "· 牛号和母亲号将添加牧场站号前缀避免重号",
            "· 开始处理前可选择下载牛群/系谱数据、配种记录或两者",
            "· 分析功能将根据本次下载的数据动态开放"
        ]
        for item in warning_items:
            item_label = QLabel(item)
            item_label.setStyleSheet("font-size: 11px; color: #909399;")
            item_label.setWordWrap(True)
            warning_layout.addWidget(item_label)

        self.warning_frame.setVisible(False)
        right_layout.addWidget(self.warning_frame)

        splitter.addWidget(right_panel)

        # 设置左右面板比例
        splitter.setSizes([250, 550])

        layout.addWidget(splitter, 1)

        # 底部按钮区域
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.preview_btn = QPushButton("预览选中数据")
        self.preview_btn.clicked.connect(self.on_preview_clicked)
        self.preview_btn.setEnabled(False)
        self.preview_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 25px;
                background-color: #409eff;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #66b1ff;
            }
            QPushButton:disabled {
                background-color: #c0c4cc;
            }
        """)
        bottom_layout.addWidget(self.preview_btn)

        self.create_btn = QPushButton("创建牧场项目")
        self.create_btn.clicked.connect(self.on_create_project_clicked)
        self.create_btn.setEnabled(False)
        self.create_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 25px;
                background-color: #67c23a;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #85ce61;
            }
            QPushButton:disabled {
                background-color: #c0c4cc;
            }
        """)
        bottom_layout.addWidget(self.create_btn)

        self.auto_report_btn = QPushButton("创建项目并自动生成报告")
        self.auto_report_btn.clicked.connect(self.on_auto_report_clicked)
        self.auto_report_btn.setEnabled(False)
        self.auto_report_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 25px;
                background-color: #e6a23c;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ebb563;
            }
            QPushButton:disabled {
                background-color: #c0c4cc;
            }
        """)
        bottom_layout.addWidget(self.auto_report_btn)

        layout.addLayout(bottom_layout)
        if not self.yqn_token or not self.interface_access_allowed:
            self.source_buttons["伊起牛"].setEnabled(False)
            if self.interface_access_allowed:
                self.source_buttons["伊起牛"].setToolTip(
                    "伊起牛数据源需要伊起牛账号登录"
                )
            else:
                self.source_buttons["伊起牛"].setToolTip(
                    "当前账号未开通接口数据功能"
                )
        if not self.hmy_access_allowed:
            self.source_buttons["慧牧云"].setEnabled(False)
            if self.interface_access_allowed:
                self.source_buttons["慧牧云"].setToolTip(
                    "当前账号未开通慧牧云功能"
                )
            else:
                self.source_buttons["慧牧云"].setToolTip(
                    "当前账号未开通接口数据功能"
                )
            if not self.yqn_token or not self.interface_access_allowed:
                self.region_title_label.setText("当前账号没有可用的数据源")
    # 无伊起牛 token 时保留慧牧云入口。
    def show_no_token_message(self):
        """显示无token提示"""
        self.source_buttons["伊起牛"].setEnabled(False)

    def _update_source_button_styles(self):
        active = """
            QPushButton { background:#409eff; color:white; border:1px solid #3a8ee6;
                          border-radius:4px; padding:7px 18px; font-weight:bold; }
        """
        normal = """
            QPushButton { background:#ffffff; color:#409eff; border:1px solid #409eff;
                          border-radius:4px; padding:7px 18px; font-weight:bold; }
            QPushButton:hover { background:#ecf5ff; }
        """
        for source, button in self.source_buttons.items():
            button.setChecked(source == self.data_source)
            button.setStyleSheet(active if source == self.data_source else normal)

    def switch_data_source(self, source: str):
        """切换牧场数据来源，不允许跨来源混合选择。"""
        if source == self.data_source and self.api_client is not None:
            self._update_source_button_styles()
            return
        if not self.interface_access_allowed:
            QMessageBox.information(
                self,
                "未开通",
                "当前账号未开通接口数据功能。",
            )
            return
        if source == "伊起牛" and not self.yqn_token:
            QMessageBox.information(self, "提示", "伊起牛数据源需要使用伊起牛账号登录")
            return
        if source == "慧牧云" and not self.hmy_access_allowed:
            QMessageBox.information(
                self,
                "未开通",
                "当前账号未开通慧牧云功能。",
            )
            return

        if self.selected_farms or self.local_farms:
            reply = QMessageBox.question(
                self,
                "确认切换数据源",
                "切换接口数据源会清空当前勾选和已暂存的本地补充牧场，"
                "是否继续？",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._update_source_button_styles()
                return

        self._clear_local_farms()
        self.data_source = source
        self.selected_farms.clear()
        self.all_farms = []
        self.current_group_farms = []
        self.farm_list.clear()
        self.farm_list_items.clear()
        self.region_tree.clear()
        self.select_group_btn.setEnabled(False)
        self.deselect_group_btn.setEnabled(False)
        self.update_selection_ui()
        self._update_source_button_styles()

        is_hmy = source == "慧牧云"
        self.farm_column_header.setVisible(is_hmy)
        self.search_input.setPlaceholderText(
            "搜索名称、编号或farmcode..." if is_hmy
            else "搜索牧场名称或站号..."
        )
        self.status_filter_widget.setVisible(not is_hmy)
        self.type_filter_widget.setVisible(not is_hmy)
        self.classification_widget.setVisible(is_hmy)
        if is_hmy:
            for checkbox in self.farm_type_checkboxes:
                checkbox.blockSignals(True)
                checkbox.setChecked(checkbox.property("type_value") is None)
                checkbox.blockSignals(False)
        else:
            for checkbox in self.farm_type_checkboxes:
                checkbox.blockSignals(True)
                checkbox.setChecked(
                    checkbox.property("type_value") == "社会奶源"
                )
                checkbox.blockSignals(False)

        try:
            if is_hmy:
                self.api_client = HMYApiClient()
                self.login_user_name = self.username or ""
                result = self.api_client.get_farm_list()
                self.all_farms = result.get("data", [])
                self.build_region_tree()
                self.select_first_region_group()
            else:
                self.init_api_client()
        except Exception as exc:
            self.api_client = None
            QMessageBox.critical(self, "数据源初始化失败", str(exc))

    def on_add_local_farm(self):
        """为当前接口项目添加一个本地补充牧场。"""
        if not self.data_source or self.api_client is None:
            QMessageBox.warning(
                self, "数据源不可用", "请先选择可用的接口数据源"
            )
            return

        source_system, accepted = QInputDialog.getItem(
            self,
            "选择牧场数据源",
            "请选择本地补充文件的数据来源：",
            ["伊起牛", "优源-DC305", "慧牧云"],
            0,
            False,
        )
        if not accepted:
            return

        from gui.local_farm_dialog import LocalFarmUploadDialog
        from core.data.composite_farm_manager import cleanup_local_farm

        dialog = LocalFarmUploadDialog(source_system, self)
        if (
            dialog.exec() != QDialog.DialogCode.Accepted
            or not dialog.result_farm
        ):
            return

        farm = dialog.result_farm
        farm_code = str(farm.get("farmCode", "")).strip()
        interface_codes = {
            str(item.get("farmCode", "")).strip()
            for item in self.all_farms
        }
        if farm_code in interface_codes:
            cleanup_local_farm(farm)
            QMessageBox.warning(
                self,
                "牧场编号重复",
                "该牧场编号已存在于当前接口牧场清单中，"
                "不能同时作为本地补充牧场添加。",
            )
            return
        if farm_code in self.local_farms:
            cleanup_local_farm(farm)
            QMessageBox.warning(
                self,
                "牧场编号重复",
                "已经添加过相同牧场编号的本地补充牧场。",
            )
            return

        self.local_farms[farm_code] = farm
        self.selected_farms[farm_code] = farm
        self._refresh_local_farm_list()
        self.update_selection_ui()

    def _refresh_local_farm_list(self):
        self.local_farm_list.clear()
        self.local_farm_list_items.clear()
        for farm_code, farm in self.local_farms.items():
            item = QListWidgetItem(self.local_farm_list)
            item.setSizeHint(QSize(0, 40))
            widget = LocalFarmListItem(farm)
            widget.checked_changed.connect(self._on_local_farm_checked)
            widget.view_requested.connect(self._show_local_farm_summary)
            widget.reupload_requested.connect(self._reupload_local_farm)
            widget.remove_requested.connect(self._remove_local_farm)
            widget.set_checked(farm_code in self.selected_farms)
            self.local_farm_list.setItemWidget(item, widget)
            self.local_farm_list_items[farm_code] = widget
        self.local_farm_group.setVisible(bool(self.local_farms))

    def _on_local_farm_checked(self, farm_code: str, checked: bool):
        if checked:
            farm = self.local_farms.get(farm_code)
            if farm:
                self.selected_farms[farm_code] = farm
        else:
            self.selected_farms.pop(farm_code, None)
        self.update_selection_ui()

    def _remove_local_farm(self, farm_code: str):
        from core.data.composite_farm_manager import cleanup_local_farm

        farm = self.local_farms.pop(farm_code, None)
        self.selected_farms.pop(farm_code, None)
        if farm:
            cleanup_local_farm(farm)
        self._refresh_local_farm_list()
        self.update_selection_ui()

    def _show_local_farm_summary(self, farm_code: str):
        farm = self.local_farms.get(farm_code)
        if not farm:
            return
        breeding_text = (
            f"{farm.get('breeding_count', 0)} 条"
            if farm.get("has_breeding_records")
            else "未上传"
        )
        QMessageBox.information(
            self,
            "本地补充牧场详情",
            f"牧场编号：{farm_code}\n"
            f"牧场名称：{farm.get('name', '')}\n"
            f"数据来源：{farm.get('source_system', '')}\n"
            f"有效母牛：{farm.get('cow_count', 0)} 头\n"
            f"配种记录：{breeding_text}",
        )

    def _reupload_local_farm(self, farm_code: str):
        old_farm = self.local_farms.get(farm_code)
        if not old_farm:
            return

        from gui.local_farm_dialog import LocalFarmUploadDialog
        from core.data.composite_farm_manager import cleanup_local_farm

        dialog = LocalFarmUploadDialog(
            old_farm.get("source_system", "伊起牛"), self
        )
        if (
            dialog.exec() != QDialog.DialogCode.Accepted
            or not dialog.result_farm
        ):
            return

        new_farm = dialog.result_farm
        new_code = str(new_farm.get("farmCode", "")).strip()
        interface_codes = {
            str(item.get("farmCode", "")).strip()
            for item in self.all_farms
        }
        other_local_codes = set(self.local_farms) - {farm_code}
        if new_code in interface_codes or new_code in other_local_codes:
            cleanup_local_farm(new_farm)
            QMessageBox.warning(
                self,
                "牧场编号重复",
                "重新上传后的牧场编号与现有牧场重复。",
            )
            return

        was_selected = farm_code in self.selected_farms
        cleanup_local_farm(old_farm)
        self.local_farms.pop(farm_code, None)
        self.selected_farms.pop(farm_code, None)
        self.local_farms[new_code] = new_farm
        if was_selected:
            self.selected_farms[new_code] = new_farm
        self._refresh_local_farm_list()
        self.update_selection_ui()

    def _clear_local_farms(self):
        from core.data.composite_farm_manager import cleanup_local_farm

        for farm in self.local_farms.values():
            cleanup_local_farm(farm)
        self.local_farms.clear()
        self.local_farm_list_items.clear()
        if hasattr(self, "local_farm_list"):
            self.local_farm_list.clear()
        if hasattr(self, "local_farm_group"):
            self.local_farm_group.setVisible(False)

    def _build_selected_farm_specs(self):
        """构建工作线程使用的接口牧场和本地牧场定义。"""
        interface_farms = []
        local_farms = []
        for farm in self.selected_farms.values():
            if farm.get("source_kind") == "local":
                local_farms.append(
                    {
                        "code": str(farm.get("farmCode", "")).strip(),
                        "name": str(farm.get("name", "")).strip(),
                        "cow_count": int(farm.get("cow_count", 0)),
                        "breeding_count": int(
                            farm.get("breeding_count", 0)
                        ),
                        "has_breeding_records": bool(
                            farm.get("has_breeding_records", False)
                        ),
                        "source_kind": "local",
                        "source_system": farm.get("source_system", ""),
                        "staging_path": farm.get("staging_path", ""),
                    }
                )
            else:
                interface_farms.append(
                    {
                        "code": str(
                            farm.get("farmCode", "")
                        ).strip(),
                        "name": str(farm.get("name", "")).strip(),
                        "cow_count": 0,
                        "has_breeding_records": (
                            self.data_source == "伊起牛"
                        ),
                        "source_kind": "api",
                        "source_system": self.data_source,
                    }
                )
        return interface_farms, local_farms

    def init_api_client(self):
        """初始化API客户端并加载牧场列表"""
        self.logger.info("开始初始化伊起牛API客户端")

        try:
            self.api_client = YQNApiClient(self.yqn_token)
            self.logger.info("API客户端对象已创建")

            # 获取用户信息（含姓名）
            try:
                user_info_result = self.api_client.get_user_info()
                # user 可能在顶层或 data 下
                user_data = user_info_result.get("data") or user_info_result
                user_obj = user_data.get("user") or {}
                self.login_user_name = (
                    user_obj.get("nickName")
                    or user_obj.get("realName")
                    or user_obj.get("userName")
                    or ""
                )
                self.logger.info(f"✓ 获取用户姓名: {self.login_user_name}")
                if self.login_user_name:
                    self.user_name_fetched.emit(self.login_user_name)
            except Exception as e:
                self.logger.warning(f"获取用户信息失败: {e}")
                self.login_user_name = ""

            # 获取牧场列表（带大区/区域信息）
            self.logger.info("正在调用 get_farm_list() API...")
            farm_list_result = self.api_client.get_farm_list()

            # 提取牧场列表 - data 是数组
            self.all_farms = farm_list_result.get("data", [])

            self.logger.info(f"✓ 已加载 {len(self.all_farms)} 个牧场")

            if self.all_farms:
                # 构建区域树
                self.build_region_tree()
                self.select_first_region_group()
            else:
                self.logger.warning("⚠️ 牧场列表为空!")
                QMessageBox.warning(
                    self,
                    "提示",
                    "您的账号下没有可用的牧场数据"
                )

        except Exception as e:
            self.logger.exception(f"初始化API客户端失败: {e}")

            # 确保all_farms不是None
            if self.all_farms is None:
                self.all_farms = []

            QMessageBox.critical(
                self,
                "初始化失败",
                f"无法连接到伊起牛服务器:\n{str(e)}\n\n请检查网络连接或稍后重试"
            )

    def build_region_tree(self):
        """构建大区/区域树"""
        self.region_tree.clear()

        # 获取当前状态筛选
        status_filter = self.get_current_status_filter()

        # 过滤牧场
        # 字段说明: isAvailable=1 表示可用, isAvailable=0 表示关停
        exclude_z = self.exclude_z_checkbox.isChecked()
        selected_types = self.get_selected_farm_types()

        filtered_farms = []
        for farm in self.all_farms:
            is_available = farm.get('isAvailable', 1)
            farm_name = farm.get('name', '')
            farm_type = farm.get('farmType')

            # status_filter: "0"=可用, "1"=关停, "all"=全部
            if status_filter == "0" and is_available != 1:
                continue
            if status_filter == "1" and is_available != 0:
                continue

            # 排除名称以Z结尾的牧场
            if exclude_z and farm_name.endswith('Z'):
                continue

            # 牧场类型筛选
            if farm_type not in selected_types:
                continue

            filtered_farms.append(farm)

        if self.data_source == "慧牧云":
            classification_label = self.classification_combo.currentText()
            classification_field = self.classification_combo.currentData()
            grouped_farms = group_hmy_farms(
                filtered_farms,
                classification_field,
            )
            for group_name, farms in grouped_farms.items():
                group_item = QTreeWidgetItem(
                    [f"{group_name} ({len(farms)}个)"]
                )
                group_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {
                        "type": "hmy_group",
                        "name": group_name,
                        "classification": classification_label,
                        "farms": farms,
                    },
                )
                self.region_tree.addTopLevelItem(group_item)

            self.tree_group.setTitle(
                f"{classification_label} (共{len(filtered_farms)}个)"
            )
            return

        # 检查是否有大区/区域信息
        # 字段说明: area=大区, region=区域
        has_region_info = any(
            farm.get('area') or farm.get('region')
            for farm in filtered_farms
        )

        if has_region_info:
            # 按大区和区域组织数据
            big_areas = {}
            for farm in filtered_farms:
                big_area = _category_name(farm.get('area'))
                area = _category_name(farm.get('region'))

                if big_area not in big_areas:
                    big_areas[big_area] = {}
                if area not in big_areas[big_area]:
                    big_areas[big_area][area] = []
                big_areas[big_area][area].append(farm)

            # 构建树
            for big_area in sorted(big_areas, key=_group_sort_key):
                areas = big_areas[big_area]
                big_area_item = QTreeWidgetItem([big_area])
                big_area_farms = [
                    farm
                    for area_farms in areas.values()
                    for farm in area_farms
                ]
                big_area_item.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "big_area",
                    "name": big_area,
                    "farms": big_area_farms
                })

                total_farms = 0
                for area in sorted(areas, key=_group_sort_key):
                    farms = areas[area]
                    area_item = QTreeWidgetItem([f"{area} ({len(farms)}个)"])
                    area_item.setData(0, Qt.ItemDataRole.UserRole, {
                        "type": "area",
                        "name": area,
                        "big_area": big_area,
                        "farms": farms
                    })
                    big_area_item.addChild(area_item)
                    total_farms += len(farms)

                big_area_item.setText(0, f"{big_area} ({total_farms}个)")
                self.region_tree.addTopLevelItem(big_area_item)
        else:
            # 没有区域信息，创建单一节点"全部牧场"
            all_farms_item = QTreeWidgetItem([f"全部牧场 ({len(filtered_farms)}个)"])
            all_farms_item.setData(0, Qt.ItemDataRole.UserRole, {
                "type": "area",
                "name": "全部牧场",
                "big_area": "",
                "farms": filtered_farms
            })
            self.region_tree.addTopLevelItem(all_farms_item)

        # 展开所有节点
        self.region_tree.expandAll()

        # 更新标题显示合计数
        self.tree_group.setTitle(f"大区/区域 (共{len(filtered_farms)}个)")

    def select_first_region_group(self):
        """显示第一个分组，避免数据加载后右侧保持空白。"""
        first_item = self.region_tree.topLevelItem(0)
        if not first_item:
            self.current_group_farms = []
            self.select_group_btn.setEnabled(False)
            self.deselect_group_btn.setEnabled(False)
            return
        self.region_tree.setCurrentItem(first_item)
        self.on_region_selected(first_item, 0)

    def on_hmy_classification_changed(self, _index=None):
        """切换慧牧云分类维度并显示第一个分组。"""
        if self.data_source != "慧牧云" or not self.all_farms:
            return
        self.build_region_tree()
        self.select_first_region_group()

    def get_current_status_filter(self) -> str:
        """获取当前状态筛选值"""
        checked_btn = self.status_group.checkedButton()
        if checked_btn:
            return checked_btn.property("status_value")
        return "0"  # 默认可用

    def on_status_changed(self, button=None):
        """状态筛选变化"""
        self.build_region_tree()
        self.select_first_region_group()

    def _select_all_farm_types(self):
        """全选所有牧场类型"""
        for cb in self.farm_type_checkboxes:
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
        self.on_status_changed()

    def _deselect_all_farm_types(self):
        """取消全选所有牧场类型"""
        for cb in self.farm_type_checkboxes:
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        self.on_status_changed()

    def get_selected_farm_types(self) -> list:
        """获取选中的牧场类型"""
        selected = []
        for cb in self.farm_type_checkboxes:
            if cb.isChecked():
                selected.append(cb.property("type_value"))
        return selected
        self.region_title_label.setText("请选择区域")

    def on_region_selected(self, item, column):
        """区域选择变化"""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if data.get("type") in {"area", "big_area", "hmy_group"}:
            farms = data.get("farms", [])
            area_name = data.get("name", "")
            classification = data.get("classification")
            if classification:
                title = f"{classification}：{area_name}"
            else:
                title = area_name
            self.region_title_label.setText(
                f"{title} ({len(farms)}个牧场)"
            )
            self.current_region = area_name
            self.current_group_farms = list(farms)
            has_farms = bool(farms)
            self.select_group_btn.setEnabled(has_farms)
            self.deselect_group_btn.setEnabled(has_farms)
            self.populate_farm_list(farms)

    def populate_farm_list(self, farms: list):
        """填充牧场列表"""
        self.farm_list.setUpdatesEnabled(False)
        self.farm_list.clear()
        self.farm_list_items.clear()

        item_size = QSize(0, 36)

        for farm in farms:
            farm_code = farm.get('farmCode', '')

            # 创建列表项
            item = QListWidgetItem(self.farm_list)
            item.setSizeHint(item_size)

            # 创建自定义widget
            farm_widget = FarmListItem(
                farm,
                show_hmy_identity=self.data_source == "慧牧云",
            )
            farm_widget.checked_changed.connect(self.on_farm_checked_changed)

            # 如果之前已选中，恢复选中状态
            if farm_code in self.selected_farms:
                farm_widget.set_checked(True)

            self.farm_list.setItemWidget(item, farm_widget)
            self.farm_list_items[farm_code] = farm_widget

        self.farm_list.setUpdatesEnabled(True)

    def on_farm_checked_changed(self, farm_code: str, is_checked: bool):
        """牧场勾选状态变化"""
        if is_checked:
            # 查找完整的farm数据
            for farm in self.all_farms:
                if farm.get('farmCode') == farm_code:
                    self.selected_farms[farm_code] = farm
                    break
        else:
            if farm_code in self.selected_farms:
                del self.selected_farms[farm_code]

        self.update_selection_ui()

    def set_current_group_checked(self, checked: bool):
        """批量选择或取消当前大区、区域、分类或搜索结果。"""
        for farm in self.current_group_farms:
            farm_code = str(farm.get("farmCode", "")).strip()
            if not farm_code:
                continue
            if checked:
                self.selected_farms[farm_code] = farm
            else:
                self.selected_farms.pop(farm_code, None)

        for farm_code, farm_widget in self.farm_list_items.items():
            farm_widget.checkbox.blockSignals(True)
            farm_widget.set_checked(farm_code in self.selected_farms)
            farm_widget.checkbox.blockSignals(False)

        self.update_selection_ui()

    def update_selection_ui(self):
        """更新选择相关的UI"""
        count = len(self.selected_farms)
        local_count = sum(
            1
            for farm in self.selected_farms.values()
            if farm.get("source_kind") == "local"
        )
        interface_count = count - local_count
        self.selected_count_label.setText(
            f"已选: {count}个（接口{interface_count}/本地{local_count}）"
        )

        # 多选警告
        self.warning_frame.setVisible(count >= 2)

        # 按钮状态
        policy = farm_selection_action_policy(count)
        self.preview_btn.setEnabled(policy["preview_enabled"])
        self.create_btn.setEnabled(policy["create_enabled"])
        self.auto_report_btn.setEnabled(policy["auto_report_enabled"])
        self.create_btn.setText(policy["create_text"])
        self.auto_report_btn.setText(policy["auto_report_text"])
        self.auto_report_btn.setToolTip(policy["auto_report_tooltip"])

    def on_search_changed(self, text: str):
        """搜索文本变化 - 搜索范围为所有牧场，不受左侧筛选限制"""
        text = text.strip().lower()

        if not text:
            # 搜索清空时，恢复当前区域选择的牧场列表
            selected_items = self.region_tree.selectedItems()
            if selected_items:
                self.on_region_selected(selected_items[0], 0)
            else:
                self.farm_list.clear()
                self.farm_list_items.clear()
                self.current_group_farms = []
                self.select_group_btn.setEnabled(False)
                self.deselect_group_btn.setEnabled(False)
                self.region_title_label.setText("请选择区域")
            return

        # 在所有牧场中搜索匹配项
        matched_farms = []
        for farm in self.all_farms:
            farm_code = str(farm.get('farmCode', '')).lower()
            farm_name = str(farm.get('name', '')).lower()
            if text in farm_code or text in farm_name:
                matched_farms.append(farm)

        self.region_title_label.setText(f"搜索结果 ({len(matched_farms)}个)")
        self.current_group_farms = matched_farms
        has_matches = bool(matched_farms)
        self.select_group_btn.setEnabled(has_matches)
        self.deselect_group_btn.setEnabled(has_matches)
        self.populate_farm_list(matched_farms)

    def _do_search(self):
        """防抖后执行搜索"""
        self.on_search_changed(self.search_input.text())

    def on_preview_clicked(self):
        """预览按钮点击"""
        if not self.selected_farms:
            QMessageBox.warning(self, "提示", "请先选择牧场")
            return

        # 显示选中牧场的汇总信息
        farm_list = list(self.selected_farms.values())

        info_lines = ["已选择的牧场：\n"]
        for i, farm in enumerate(farm_list, 1):
            code = farm.get('farmCode', '')
            name = farm.get('name', '')
            if farm.get("source_kind") == "local":
                source = f"本地·{farm.get('source_system', '')}"
            else:
                source = f"接口·{self.data_source}"
            info_lines.append(f"{i}. {code} - {name}（{source}）")

        info_lines.append(f"\n合计: {len(farm_list)} 个牧场")

        if len(farm_list) >= 2:
            info_lines.append("\n⚠️ 多选模式注意：")
            info_lines.append("• 每个牧场将作为独立子项目处理")
            info_lines.append("• 绿色按钮只创建项目并逐场准备数据")
            info_lines.append("• 橙色按钮会逐场完成育种分析并生成最终汇总Excel")
            info_lines.append("• 批量分析不执行个体选配，也不批量生成PPT")
            info_lines.append("• 个体选配需进入对应单牧场子项目单独执行")
            info_lines.append("• 不生成阶段性汇总Excel")
            info_lines.append("• PPT请进入对应单牧场子项目按需生成")

        QMessageBox.information(self, "预览选中数据", "\n".join(info_lines))

    def _choose_group_dataset_selection(
        self,
        *,
        full_analysis: bool,
        has_local_farms: bool,
    ):
        dialog = GroupDatasetSelectionDialog(
            full_analysis=full_analysis,
            has_local_farms=has_local_farms,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        policy = group_dataset_selection_policy(
            dialog.dataset_selection(),
            full_analysis=full_analysis,
            has_local_farms=has_local_farms,
        )
        return policy["selection"] if policy["valid"] else None

    def on_create_project_clicked(self):
        """创建项目按钮点击"""
        if not self.selected_farms:
            QMessageBox.warning(self, "提示", "请先选择牧场")
            return

        interface_farms, local_farms = self._build_selected_farm_specs()
        if not interface_farms:
            QMessageBox.warning(
                self,
                "缺少接口牧场",
                "接口复合项目至少需要勾选一个接口牧场。",
            )
            return
        farm_list = interface_farms + local_farms
        is_merged = len(farm_list) > 1
        dataset_selection = None
        dataset_policy = None
        if is_merged:
            dataset_selection = self._choose_group_dataset_selection(
                full_analysis=False,
                has_local_farms=bool(local_farms),
            )
            if dataset_selection is None:
                return
            dataset_policy = group_dataset_selection_policy(
                dataset_selection,
                full_analysis=False,
                has_local_farms=bool(local_farms),
            )

        # 确认对话框
        if is_merged:
            confirm_msg = (
                f"即将创建{self.data_source}牧场组项目\n\n"
                f"包含 {len(interface_farms)} 个接口牧场"
                f"和 {len(local_farms)} 个本地补充牧场\n\n"
                f"系统将为每个牧场创建独立子项目并分别下载、标准化数据，"
                f"不会把所有牛只明细合并到一个超大文件。\n\n"
                f"本次下载：{dataset_policy['selected_text']}。\n\n"
                f"每个牧场完成后可立即打开对应子项目目录。\n\n"
                f"是否继续?"
            )
        else:
            farm = farm_list[0]
            confirm_msg = (
                f"即将为牧场 '{farm.get('name', '')}' 创建项目\n\n"
                f"系统将自动下载并标准化牛群数据\n\n"
                f"是否继续?"
            )

        reply = QMessageBox.question(
            self,
            "确认创建",
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.create_farm_project(
                dataset_selection=dataset_selection,
            )

    def create_farm_project(self, dataset_selection=None):
        """创建牧场项目"""
        if self.data_source == "慧牧云" and not self.hmy_access_allowed:
            QMessageBox.warning(self, "未开通", "当前账号未开通慧牧云功能。")
            return

        interface_farms, local_farms = self._build_selected_farm_specs()
        if not interface_farms:
            QMessageBox.warning(
                self, "缺少接口牧场", "接口复合项目至少需要一个接口牧场。"
            )
            return
        farms_info = interface_farms + local_farms
        is_merged = len(farms_info) > 1
        if is_merged:
            dataset_policy = group_dataset_selection_policy(
                dataset_selection,
                full_analysis=False,
                has_local_farms=bool(local_farms),
            )
            if not dataset_policy["valid"]:
                QMessageBox.warning(
                    self,
                    "下载数据选择无效",
                    dataset_policy["error"],
                )
                return
            dataset_selection = dataset_policy["selection"]

        try:
            # 创建项目文件夹
            from config.settings import Settings
            settings = Settings()
            base_path = Path(settings.get_default_storage())

            if is_merged:
                project_path = FileManager.create_group_project(
                    base_path,
                    farms_info,
                    data_source=self.data_source,
                    task_mode="data_only",
                    dataset_selection=dataset_selection,
                )
                from core.data.composite_farm_manager import (
                    persist_group_local_input_bundles,
                )

                persist_group_local_input_bundles(
                    project_path,
                    farms_info,
                )
            else:
                project_path = FileManager.create_project(base_path, farms_info[0]['name'])
                # 单选也保存元数据
                FileManager.save_project_metadata(
                    project_path, farms_info, data_source=self.data_source
                )

            self.logger.info(f"项目文件夹已创建: {project_path}")

            if is_merged:
                self._start_group_tasks(
                    project_path,
                    farms_info,
                    full_analysis=False,
                    dataset_selection=dataset_selection,
                )
                return

            # 创建进度对话框
            progress_dialog = QProgressDialog(self)
            progress_dialog.setWindowTitle("创建项目")
            progress_dialog.setLabelText("正在准备...")
            progress_dialog.setRange(0, 100)
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.setCancelButton(None)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.show()

            # 创建后台工作线程
            worker_class = (
                HMYDataDownloadWorker
                if self.data_source == "慧牧云"
                else DataDownloadWorker
            )
            self.worker = worker_class(
                self.api_client,
                interface_farms,
                project_path,
                is_merged,
                local_farms=local_farms,
            )

            # 连接信号
            self.worker.progress.connect(
                lambda pct, msg: self.on_worker_progress(progress_dialog, pct, msg)
            )
            self.worker.finished.connect(
                lambda path: self.on_worker_finished(progress_dialog, project_path, path, is_merged)
            )
            self.worker.error.connect(
                lambda err: self.on_worker_error(progress_dialog, project_path, err)
            )

            # 启动线程
            self.worker.start()

        except Exception as e:
            self.logger.exception("创建项目失败")
            QMessageBox.critical(
                self,
                "创建失败",
                f"无法创建项目文件夹:\n{str(e)}"
            )

    def on_worker_progress(self, dialog, percentage, message):
        """工作线程进度更新"""
        dialog.setValue(percentage)
        dialog.setLabelText(message)

    def on_worker_finished(self, dialog, project_path, excel_path, is_merged):
        """工作线程完成"""
        dialog.close()
        breeding_file = (
            Path(project_path)
            / "standardized_data"
            / "processed_breeding_data.xlsx"
        )
        breeding_ready = breeding_file.exists()

        # 构建成功消息
        if is_merged:
            farm_count = len(self.selected_farms)
            restricted_text = ""
            if self.data_source == "伊起牛":
                restricted_text = (
                    "\n⚠️ 以下功能已禁用:\n"
                    "• 基因组检测数据上传\n"
                    "• 体型外貌数据上传\n"
                    "• 个体选配"
                )
            breeding_text = (
                "\n✅ 配种记录已自动下载、合并并标准化"
                if breeding_ready
                else "\nℹ️ 本次未取得可用配种记录"
            )
            success_msg = (
                f"合并牧场项目已创建成功!\n\n"
                f"项目位置: {project_path}\n\n"
                f"已完成:\n"
                f"✅ {farm_count} 个牧场数据已合并处理\n"
                f"✅ 牛号和母亲号已添加牧场前缀\n"
                f"✅ 数据已自动标准化\n"
                f"✅ 已生成 merged_farms.txt 说明文件"
                f"{breeding_text}"
                f"{restricted_text}"
            )
        else:
            # 检查备选公牛数据是否已自动生成
            from pathlib import Path
            bull_file = Path(project_path) / "standardized_data" / "processed_bull_data.xlsx"
            bull_ready = bull_file.exists()

            if self.data_source == "慧牧云":
                breeding_line = (
                    "✅ 配种记录已自动下载并标准化\n"
                    if breeding_ready
                    else "ℹ️ 本次未取得可用配种记录\n"
                )
                completed_lines = (
                    "✅ 牛群明细已自动下载\n"
                    "✅ 数据已自动标准化\n"
                    f"{breeding_line}"
                    "ℹ️ 选配结果推送暂不可用"
                )
            else:
                completed_lines = (
                    "✅ 牛群明细已自动下载\n"
                    "✅ 配种记录已自动下载\n"
                    "✅ 冻精库存已自动下载并标准化\n"
                    "✅ 数据已自动标准化"
                )
            if bull_ready:
                completed_lines += f"\n✅ 备选公牛已从冻精库存自动生成"

            pending_lines = ""
            pending_items = []
            if not bull_ready:
                pending_items.append("⚠️ 备选公牛清单")
            pending_items.append("⚠️ 体型外貌数据 (可选)")
            pending_items.append("⚠️ 基因组数据 (可选)")
            if pending_items:
                pending_lines = "\n\n待手动上传:\n" + "\n".join(pending_items)

            success_msg = (
                f"牧场项目已创建成功!\n\n"
                f"项目位置: {project_path}\n\n"
                f"已完成:\n"
                f"{completed_lines}"
                f"{pending_lines}"
            )

        QMessageBox.information(self, "创建成功", success_msg)

        # 重置状态
        self.selected_farms.clear()
        self._clear_local_farms()
        self.update_selection_ui()

        # 更新列表中的勾选状态
        for farm_code, widget in self.farm_list_items.items():
            widget.set_checked(False)

        self.logger.info(f"项目创建完成: {project_path}")

        # 通知主窗口自动选择新创建的项目
        self.project_created.emit(project_path)

    def on_worker_error(self, dialog, project_path, error_message):
        """工作线程错误"""
        dialog.close()

        self.logger.error(f"项目创建失败: {error_message}")

        # 尝试清理失败的项目文件夹
        try:
            import shutil
            if project_path.exists():
                shutil.rmtree(project_path)
                self.logger.info(f"已清理失败的项目文件夹: {project_path}")
        except Exception as e:
            self.logger.warning(f"清理项目文件夹失败: {e}")

        QMessageBox.critical(
            self,
            "创建失败",
            f"项目创建过程中发生错误:\n\n{error_message}\n\n"
            f"请检查网络连接或稍后重试"
        )

    # ============ 自动报告功能 ============

    def on_auto_report_clicked(self):
        """创建项目并自动生成报告按钮点击"""
        if not self.selected_farms:
            QMessageBox.warning(self, "提示", "请先选择牧场")
            return

        interface_farms, local_farms = self._build_selected_farm_specs()
        if not interface_farms:
            QMessageBox.warning(
                self,
                "缺少接口牧场",
                "接口复合项目至少需要勾选一个接口牧场。",
            )
            return

        farms_info = interface_farms + local_farms
        dataset_selection = None
        dataset_policy = None
        if len(farms_info) > 1:
            dataset_selection = self._choose_group_dataset_selection(
                full_analysis=True,
                has_local_farms=bool(local_farms),
            )
            if dataset_selection is None:
                return
            dataset_policy = group_dataset_selection_policy(
                dataset_selection,
                full_analysis=True,
                has_local_farms=bool(local_farms),
            )
            breeding_notice = (
                f"\n注意：{dataset_policy['notice']}\n"
                if dataset_policy["notice"]
                else ""
            )
            confirm_msg = (
                f"即将创建{self.data_source}牧场组并批量分析\n\n"
                f"包含 {len(interface_farms)} 个接口牧场"
                f"和 {len(local_farms)} 个本地补充牧场。\n\n"
                f"本次下载：{dataset_policy['selected_text']}。\n\n"
                "系统将按牧场逐个执行：\n"
                "1. 下载并标准化本场数据\n"
                "2. 完成本场可用的育种性状、指数及近交分析\n"
                "3. 保存本场分析结果\n"
                "4. 全部成功后生成最终牧场组汇总Excel\n\n"
                "不会批量执行个体选配，也不会批量生成PPT。\n"
                "个体选配请进入对应的单牧场子项目操作。\n\n"
                f"{breeding_notice}\n是否继续？"
            )
        elif self.data_source == "慧牧云":
            confirm_msg = (
                "即将创建慧牧云项目并自动生成当前可用报告\n\n"
                "系统将自动执行:\n"
                "1. 下载并标准化牛群数据和配种记录\n"
                "2. 在群母牛关键育种性状分析\n"
                "3. 已配公牛关键育种数据分析\n"
                "4. 已配公牛近交系数及隐性基因分析\n"
                "5. 母牛群指数排名 (NM$权重)\n"
                "6. 生成当前可用的Excel和PPT报告\n\n"
                "如配种接口临时不可用，系统仍会继续处理牛群数据；"
                "推送功能将跳过；"
                "备选公牛需在项目创建后手动上传。\n\n"
                "整个过程可能需要几分钟，是否继续?"
            )
        else:
            confirm_msg = (
                "即将创建项目并自动生成报告\n\n"
                "系统将自动执行以下步骤:\n"
                "1. 下载并标准化牛群数据\n"
                "2. 在群母牛关键育种数据分析\n"
                "3. 备选公牛关键育种数据分析\n"
                "4. 已配公牛关键育种数据分析\n"
                "5. 母牛群指数排名 (NM$权重)\n"
                "6. 备选公牛指数排名 (NM$权重)\n"
                "7. 近交系数及隐性基因分析\n"
                "8. 生成Excel综合报告\n"
                "9. 生成PPT汇报材料\n\n"
                "注意：不会自动进行个体选配\n\n"
                "整个过程可能需要几分钟，是否继续?"
            )

        reply = QMessageBox.question(
            self,
            "确认创建",
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._start_auto_report(
                dataset_selection=dataset_selection,
            )

    def _start_auto_report(self, dataset_selection=None):
        """启动自动报告生成流程"""
        if self.data_source == "慧牧云" and not self.hmy_access_allowed:
            QMessageBox.warning(self, "未开通", "当前账号未开通慧牧云功能。")
            return

        interface_farms, local_farms = self._build_selected_farm_specs()
        if not interface_farms:
            QMessageBox.warning(
                self, "缺少接口牧场", "接口复合项目至少需要一个接口牧场。"
            )
            return
        farms_info = interface_farms + local_farms
        if len(farms_info) > 1:
            dataset_policy = group_dataset_selection_policy(
                dataset_selection,
                full_analysis=True,
                has_local_farms=bool(local_farms),
            )
            if not dataset_policy["valid"]:
                QMessageBox.warning(
                    self,
                    "下载数据选择无效",
                    dataset_policy["error"],
                )
                return
            dataset_selection = dataset_policy["selection"]
            try:
                from config.settings import Settings
                from core.data.composite_farm_manager import (
                    persist_group_local_input_bundles,
                )

                base_path = Path(Settings().get_default_storage())
                project_path = FileManager.create_group_project(
                    base_path,
                    farms_info,
                    data_source=self.data_source,
                    task_mode="analysis",
                    dataset_selection=dataset_selection,
                )
                persist_group_local_input_bundles(
                    project_path,
                    farms_info,
                )
                self.logger.info(
                    "牧场组批量分析项目已创建: %s",
                    project_path,
                )
                self._start_group_tasks(
                    project_path,
                    farms_info,
                    full_analysis=True,
                    dataset_selection=dataset_selection,
                )
            except Exception as exc:
                self.logger.exception("创建牧场组批量分析项目失败")
                QMessageBox.critical(
                    self,
                    "创建失败",
                    f"无法创建牧场组批量分析项目：\n{exc}",
                )
            return

        try:
            # 创建项目文件夹
            from config.settings import Settings
            settings = Settings()
            base_path = Path(settings.get_default_storage())

            project_path = FileManager.create_project(
                base_path, farms_info[0]["name"]
            )
            FileManager.save_project_metadata(
                project_path, farms_info, data_source=self.data_source
            )

            self.logger.info(f"项目文件夹已创建: {project_path}")

            # 创建进度对话框
            from gui.progress import ProgressDialog
            # 使用主窗口作为真实父级并设为窗口级模态，确保处理期间
            # 始终位于主窗口上方，同时不会压住其他应用。
            main_window = self.window()
            progress_dialog = ProgressDialog(main_window)
            progress_dialog.setWindowTitle("创建项目并自动生成报告")
            progress_dialog.setWindowModality(
                Qt.WindowModality.WindowModal
            )
            progress_dialog.setWindowFlag(
                Qt.WindowType.WindowMinimizeButtonHint, False
            )
            progress_dialog.set_task_info("正在准备...")
            progress_dialog.adjustSize()
            dialog_geometry = progress_dialog.frameGeometry()
            dialog_geometry.moveCenter(main_window.frameGeometry().center())
            progress_dialog.move(dialog_geometry.topLeft())
            progress_dialog.show()
            progress_dialog.raise_()
            progress_dialog.activateWindow()

            # 自动报告为无人值守流程，强制关闭对比牧场总开关：
            # 避免历史勾选残留导致自动生成的报告静默带上对比牧场。
            # 需要对比时请走手动生成 Excel 报告并在弹窗中确认。
            try:
                from core.benchmark import BenchmarkManager
                BenchmarkManager().set_comparison_enabled(False)
            except Exception as e:
                self.logger.warning(f"关闭对比牧场总开关失败（不影响生成）: {e}")

            # 创建 AutoReportWorker
            from gui.auto_report_worker import AutoReportWorker
            self.auto_worker = AutoReportWorker(
                self.api_client,
                interface_farms,
                project_path,
                False,
                service_staff=getattr(self, 'login_user_name', None) or '',
                data_source=self.data_source,
                local_farms=local_farms,
            )

            # 连接信号
            self.auto_worker.progress.connect(
                lambda pct, msg: self._on_auto_report_progress(progress_dialog, pct, msg)
            )
            self.auto_worker.finished.connect(
                lambda results: self._on_auto_report_finished(progress_dialog, project_path, results)
            )
            self.auto_worker.error.connect(
                lambda err: self.on_worker_error(progress_dialog, project_path, err)
            )

            # 连接并行子任务进度信号
            self.auto_worker.parallel_start.connect(
                lambda tasks: progress_dialog.show_sub_tasks(tasks)
            )
            self.auto_worker.sub_task_progress.connect(
                lambda task_id, pct: progress_dialog.update_sub_task(task_id, pct)
            )
            self.auto_worker.sub_task_done.connect(
                lambda task_id, ok: progress_dialog.complete_sub_task(task_id, ok)
            )
            self.auto_worker.parallel_end.connect(
                lambda: progress_dialog.hide_sub_tasks()
            )

            # 启动线程
            self.auto_worker.start()

        except Exception as e:
            self.logger.exception("创建自动报告项目失败")
            QMessageBox.critical(
                self,
                "创建失败",
                f"无法创建项目文件夹:\n{str(e)}"
            )

    def _start_group_tasks(
        self,
        project_path,
        farms_info,
        full_analysis,
        dataset_selection=None,
    ):
        """启动牧场组逐场处理；子项目完成后在进度窗口开放目录。"""
        from gui.multi_farm_task_worker import MultiFarmTaskWorker
        from gui.progress import ProgressDialog

        main_window = self.window()
        dialog = ProgressDialog(main_window)
        dialog.setWindowTitle(
            "牧场组自动分析" if full_analysis else "创建牧场组项目"
        )
        dialog.title_label.setText(
            "牧场组自动分析" if full_analysis else "牧场组数据准备"
        )
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.cancel_button.hide()
        dialog.setMinimumWidth(720)
        dialog.set_task_info("正在准备牧场子任务...")
        dialog.show()

        self.group_worker = MultiFarmTaskWorker(
            self.api_client,
            farms_info,
            project_path,
            data_source=self.data_source,
            service_staff=getattr(self, "login_user_name", None) or "",
            full_analysis=full_analysis,
            dataset_selection=dataset_selection,
        )
        self.group_worker.progress.connect(
            lambda pct, msg: self._on_auto_report_progress(dialog, pct, msg)
        )
        self.group_worker.parallel_start.connect(dialog.show_sub_tasks)
        self.group_worker.sub_task_progress.connect(dialog.update_sub_task)
        self.group_worker.sub_task_done.connect(dialog.complete_sub_task)
        self.group_worker.finished.connect(
            lambda result: self._on_group_tasks_finished(dialog, project_path, result)
        )
        self.group_worker.error.connect(
            lambda error: self._on_group_tasks_error(dialog, project_path, error)
        )
        self.group_worker.start()

    def continue_group_project(self, project_path: Path):
        """从父项目状态库继续未完成/失败的牧场任务。"""
        project_path = Path(project_path)
        metadata = FileManager.load_project_metadata(project_path)
        if metadata.get("project_type") != "multi_farm_group":
            QMessageBox.warning(self, "提示", "当前项目不是牧场组项目。")
            return

        source = metadata.get("data_source") or "伊起牛"
        if source != self.data_source or self.api_client is None:
            # 避免切换数据源时弹出清空当前勾选的二次确认。
            self.selected_farms.clear()
            self._clear_local_farms()
            self.switch_data_source(source)
        if self.api_client is None:
            QMessageBox.warning(
                self,
                "数据源不可用",
                f"无法初始化{source}数据源，暂不能继续接口任务。",
            )
            return

        tasks = metadata.get("group_tasks", [])
        farms_info = [
            {
                "task_id": task.get("task_id"),
                "code": str(task.get("farm_code", "")),
                "farmCode": str(task.get("farm_code", "")),
                # 慧牧云接口名称可能仍带七位业务牧场编号。恢复任务时
                # 使用原始接口名称，展示名称和业务编号继续独立保留。
                "name": str(
                    task.get("source_farm_name")
                    or task.get("farm_name", "")
                ),
                "display_name": str(
                    task.get("display_name")
                    or task.get("farm_name", "")
                ),
                "farm_number": str(task.get("farm_number", "")),
                "api_farmcode": str(task.get("api_farmcode", "")),
                "source_kind": task.get("source_kind", "api"),
                "source_system": task.get("source_system", source),
            }
            for task in tasks
        ]
        self._start_group_tasks(
            project_path,
            farms_info,
            full_analysis=metadata.get("task_mode") == "analysis",
            dataset_selection=metadata.get("dataset_selection"),
        )

    def _on_group_tasks_finished(self, dialog, project_path, result):
        dialog.update_progress(100)
        dialog.set_task_info("牧场组任务处理完成")
        dialog.close()

        excel_path = result.get("excel_path")
        lines = build_group_task_completion_lines(result)

        message = QMessageBox(self)
        message.setWindowTitle("牧场组任务完成")
        message.setText("\n".join(lines))
        open_group = message.addButton("打开牧场组目录", QMessageBox.ButtonRole.ActionRole)
        if excel_path:
            open_excel = message.addButton("打开汇总Excel", QMessageBox.ButtonRole.ActionRole)
        else:
            open_excel = None
        if result.get("resume_available"):
            resume_button = message.addButton(
                "释放内存后继续处理",
                QMessageBox.ButtonRole.ActionRole,
            )
        else:
            resume_button = None
        message.addButton("关闭", QMessageBox.ButtonRole.AcceptRole)
        message.exec()
        if message.clickedButton() is open_group:
            self._open_path(str(project_path))
        elif open_excel is not None and message.clickedButton() is open_excel:
            self._open_file(excel_path)
        elif (
            resume_button is not None
            and message.clickedButton() is resume_button
        ):
            self.continue_group_project(project_path)

        self.selected_farms.clear()
        self._clear_local_farms()
        self.update_selection_ui()
        for _, widget in self.farm_list_items.items():
            widget.set_checked(False)
        self.project_created.emit(Path(project_path))

    def _on_group_tasks_error(self, dialog, project_path, error_message):
        dialog.close()
        self.logger.error("牧场组任务失败: %s", error_message)
        message = QMessageBox(self)
        message.setWindowTitle("牧场组任务异常")
        message.setText(
            f"牧场组处理发生异常：\n\n{error_message}\n\n"
            "已完成的子项目会保留，不会被删除。"
        )
        open_group = message.addButton("打开牧场组目录", QMessageBox.ButtonRole.ActionRole)
        message.addButton("关闭", QMessageBox.ButtonRole.AcceptRole)
        message.exec()
        if message.clickedButton() is open_group:
            self._open_path(str(project_path))

    def _on_auto_report_progress(self, dialog, percentage, message):
        """自动报告进度更新"""
        dialog.update_progress(percentage)
        dialog.set_task_info(message)

    def _on_auto_report_finished(self, dialog, project_path, results):
        """自动报告生成完成 - 显示汇总对话框"""
        # 计算总用时（从进度对话框的开始时间）
        import time as _time
        elapsed_seconds = _time.time() - dialog._start_time
        elapsed_min, elapsed_sec = divmod(int(elapsed_seconds), 60)
        elapsed_text = f"{elapsed_min}分{elapsed_sec:02d}秒"

        dialog.close()

        success_items = results.get('success_items', [])
        failed_items = results.get('failed_items', [])
        excel_path = results.get('excel_path')
        ppt_path = results.get('ppt_path')

        # 构建汇总对话框
        summary_dialog = QDialog(self)
        summary_dialog.setWindowTitle("自动报告完成")
        summary_dialog.setMinimumWidth(500)
        layout = QVBoxLayout(summary_dialog)

        # 标题
        if failed_items:
            title = QLabel("报告生成完成（部分步骤失败）")
        else:
            title = QLabel("报告生成完成")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 总用时
        time_label = QLabel(f"总用时: {elapsed_text}")
        time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_label.setStyleSheet("color: #7f8c8d; font-size: 13px;")
        layout.addWidget(time_label)

        # 成功项：2列网格 + 绿色对勾
        if success_items:
            success_label = QLabel("成功项目:")
            bold_font = success_label.font()
            bold_font.setBold(True)
            success_label.setFont(bold_font)
            success_label.setStyleSheet("color: #27ae60;")
            layout.addWidget(success_label)

            from PyQt6.QtWidgets import QGridLayout
            grid = QGridLayout()
            grid.setSpacing(6)
            for i, item in enumerate(success_items):
                label = QLabel(f"  \u2713  {item}")
                label.setStyleSheet("color: #2c3e50; font-size: 13px;")
                grid.addWidget(label, i // 2, i % 2)
            layout.addLayout(grid)

        # 失败项
        if failed_items:
            fail_label = QLabel("失败项目:")
            fail_font = fail_label.font()
            fail_font.setBold(True)
            fail_label.setFont(fail_font)
            fail_label.setStyleSheet("color: #e74c3c;")
            layout.addWidget(fail_label)
            for name, err in failed_items:
                err_short = err[:80] if len(err) > 80 else err
                err_label = QLabel(f"  \u2717  {name}: {err_short}")
                err_label.setStyleSheet("color: #c0392b; font-size: 13px;")
                layout.addWidget(err_label)

        # 提示
        layout.addSpacing(8)
        tip_label = QLabel("个体选配需手动执行")
        tip_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        layout.addWidget(tip_label)

        # 按钮样式
        primary_style = """
            QPushButton {
                background-color: #3498db; color: white;
                border: none; border-radius: 6px;
                padding: 8px 20px; font-size: 13px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """
        secondary_style = """
            QPushButton {
                background-color: white; color: #333;
                border: 1px solid #ddd; border-radius: 6px;
                padding: 8px 20px; font-size: 13px;
            }
            QPushButton:hover { background-color: #f5f5f5; }
        """
        close_style = """
            QPushButton {
                background-color: transparent; color: #999;
                border: none; padding: 8px 16px; font-size: 13px;
            }
            QPushButton:hover { color: #666; }
        """

        # 按钮区域
        layout.addSpacing(8)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        if excel_path:
            btn_open_excel = QPushButton("打开Excel报告")
            btn_open_excel.setStyleSheet(primary_style)
            btn_open_excel.clicked.connect(
                lambda: self._open_file(excel_path)
            )
            btn_layout.addWidget(btn_open_excel)

        if ppt_path:
            btn_open_ppt = QPushButton("打开PPT报告")
            btn_open_ppt.setStyleSheet(primary_style)
            btn_open_ppt.clicked.connect(
                lambda: self._open_file(ppt_path)
            )
            btn_layout.addWidget(btn_open_ppt)

        btn_open_folder = QPushButton("打开项目文件夹")
        btn_open_folder.setStyleSheet(secondary_style)
        btn_open_folder.clicked.connect(
            lambda: self._open_path(str(project_path))
        )
        btn_layout.addWidget(btn_open_folder)

        btn_close = QPushButton("关闭")
        btn_close.setStyleSheet(close_style)
        btn_close.clicked.connect(summary_dialog.accept)
        btn_layout.addWidget(btn_close)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        summary_dialog.exec()

        # 重置状态
        self.selected_farms.clear()
        self._clear_local_farms()
        self.update_selection_ui()

        for farm_code, widget in self.farm_list_items.items():
            widget.set_checked(False)

        self.logger.info(f"自动报告项目完成: {project_path}")

        # 通知主窗口自动选择新创建的项目
        self.project_created.emit(project_path)

    def _open_path(self, path):
        """用系统文件管理器打开文件夹"""
        import subprocess, sys
        if sys.platform == 'darwin':
            subprocess.Popen(['open', path])
        elif sys.platform == 'win32':
            subprocess.Popen(['explorer', path])
        else:
            subprocess.Popen(['xdg-open', path])

    def _open_file(self, file_path):
        """用系统默认应用打开文件"""
        import subprocess, sys
        if sys.platform == 'darwin':
            subprocess.Popen(['open', file_path])
        elif sys.platform == 'win32':
            import os
            os.startfile(file_path)
        else:
            subprocess.Popen(['xdg-open', file_path])
