"""接口复合项目的本地补充牧场上传窗口。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
)

from core.data.composite_farm_manager import stage_local_farm


logger = logging.getLogger(__name__)

_FARM_CODE_ALIASES = (
    "牧场编号",
    "牧场代码",
    "站号",
    "farmCode",
    "farm_code",
    "farm_id",
)
_FARM_NAME_ALIASES = (
    "牧场名称",
    "牧场名",
    "场名",
    "farmName",
    "farm_name",
)


class LocalFarmPrepareWorker(QThread):
    progress = pyqtSignal(int, str)
    completed = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(
        self,
        cow_file: Path,
        breeding_file: Optional[Path],
        source_system: str,
        farm_code: str,
        farm_name: str,
        parent=None,
    ):
        super().__init__(parent)
        self.cow_file = cow_file
        self.breeding_file = breeding_file
        self.source_system = source_system
        self.farm_code = farm_code
        self.farm_name = farm_name

    def run(self):
        try:
            result = stage_local_farm(
                self.cow_file,
                self.breeding_file,
                self.source_system,
                self.farm_code,
                self.farm_name,
                progress_callback=lambda value, message: self.progress.emit(
                    int(value), str(message)
                ),
            )
            self.completed.emit(result)
        except Exception as exc:
            logger.exception("本地补充牧场处理失败")
            self.error.emit(str(exc))


class FileUploadRow(QFrame):
    """与现有上传页一致的文件选择卡片。"""

    file_changed = pyqtSignal(object)

    def __init__(self, title: str, required: bool, parent=None):
        super().__init__(parent)
        self.path: Optional[Path] = None
        self.setStyleSheet(
            """
            QFrame {
                border: 1px solid #dcdfe6;
                border-radius: 6px;
                background: #fafafa;
            }
            """
        )
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        title_label = QLabel(f"{title}{'（必填）' if required else '（选填）'}")
        title_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #303133; border: none;"
        )
        header.addWidget(title_label)
        header.addStretch()
        self.select_button = QPushButton("选择文件")
        self.select_button.clicked.connect(self._select_file)
        header.addWidget(self.select_button)
        layout.addLayout(header)

        self.path_label = QLabel("尚未选择文件")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet(
            "font-size: 12px; color: #909399; border: none;"
        )
        layout.addWidget(self.path_label)

    def _select_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "选择数据文件",
            "",
            "数据文件 (*.xlsx *.xls *.csv);;Excel Files (*.xlsx *.xls);;CSV Files (*.csv)",
        )
        if not filename:
            return
        self.path = Path(filename)
        self.path_label.setText(str(self.path))
        self.path_label.setStyleSheet(
            "font-size: 12px; color: #409eff; border: none;"
        )
        self.file_changed.emit(self.path)


class LocalFarmUploadDialog(QDialog):
    """上传一个本地补充牧场的母牛信息和可选配种记录。"""

    def __init__(self, source_system: str, parent=None):
        super().__init__(parent)
        self.source_system = source_system
        self.result_farm: Optional[dict] = None
        self.worker: Optional[LocalFarmPrepareWorker] = None
        self.progress_dialog: Optional[QProgressDialog] = None
        self.setWindowTitle("上传牧场信息")
        self.setMinimumWidth(620)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        source_label = QLabel(f"数据来源：{self.source_system}")
        source_label.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #2980b9;"
        )
        layout.addWidget(source_label)

        hint = QLabel(
            "母牛信息为必填，配种记录为选填。系统会复用现有单牧场上传规则进行校验和标准化。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 12px; color: #606266;")
        layout.addWidget(hint)

        form = QFormLayout()
        self.farm_code_input = QLineEdit()
        self.farm_code_input.setPlaceholderText("可从文件识别；识别不到时请手动填写")
        self.farm_name_input = QLineEdit()
        self.farm_name_input.setPlaceholderText("可从文件识别；识别不到时请手动填写")
        form.addRow("牧场编号：", self.farm_code_input)
        form.addRow("牧场名称：", self.farm_name_input)
        layout.addLayout(form)

        self.cow_row = FileUploadRow("母牛信息", required=True)
        self.cow_row.file_changed.connect(self._on_cow_file_selected)
        layout.addWidget(self.cow_row)

        self.breeding_row = FileUploadRow("配种记录", required=False)
        layout.addWidget(self.breeding_row)

        self.status_label = QLabel("请选择母牛信息文件")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 12px; color: #909399;")
        layout.addWidget(self.status_label)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = self.button_box.button(
            QDialogButtonBox.StandardButton.Ok
        )
        self.ok_button.setText("确定添加")
        self.ok_button.setEnabled(False)
        self.button_box.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText("取消")
        self.button_box.accepted.connect(self._start_prepare)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.farm_code_input.textChanged.connect(self._update_ok_state)
        self.farm_name_input.textChanged.connect(self._update_ok_state)

    @staticmethod
    def _read_preview(path: Path) -> pd.DataFrame:
        if path.suffix.lower() == ".csv":
            for encoding in ("utf-8-sig", "gb18030"):
                try:
                    return pd.read_csv(path, nrows=500, encoding=encoding)
                except UnicodeDecodeError:
                    continue
            return pd.read_csv(path, nrows=500)
        return pd.read_excel(path, nrows=500)

    @staticmethod
    def _first_unique_value(frame: pd.DataFrame, aliases) -> str:
        for column in aliases:
            if column not in frame.columns:
                continue
            values = [
                str(value).strip()
                for value in frame[column].dropna().tolist()
                if str(value).strip()
                and str(value).strip().lower() not in {"nan", "none", "null"}
            ]
            unique_values = list(dict.fromkeys(values))
            if len(unique_values) > 1:
                raise ValueError(f"文件中的“{column}”包含多个不同值")
            if unique_values:
                value = unique_values[0]
                return value[:-2] if value.endswith(".0") else value
        return ""

    def _on_cow_file_selected(self, path: Path):
        try:
            frame = self._read_preview(path)
            if frame.empty:
                raise ValueError("文件中没有可读取的数据")
            farm_code = self._first_unique_value(frame, _FARM_CODE_ALIASES)
            farm_name = self._first_unique_value(frame, _FARM_NAME_ALIASES)
            if farm_code and not self.farm_code_input.text().strip():
                self.farm_code_input.setText(farm_code)
            if farm_name and not self.farm_name_input.text().strip():
                self.farm_name_input.setText(farm_name)
            detected = []
            if farm_code:
                detected.append(f"牧场编号 {farm_code}")
            if farm_name:
                detected.append(f"牧场名称 {farm_name}")
            suffix = f"，已识别：{'、'.join(detected)}" if detected else ""
            self.status_label.setText(
                f"母牛文件已选择，预览 {len(frame)} 行{suffix}"
            )
            self.status_label.setStyleSheet(
                "font-size: 12px; color: #67c23a;"
            )
        except Exception as exc:
            self.status_label.setText(f"无法读取母牛文件：{exc}")
            self.status_label.setStyleSheet(
                "font-size: 12px; color: #f56c6c;"
            )
            self.cow_row.path = None
        self._update_ok_state()

    def _update_ok_state(self):
        ready = bool(
            self.cow_row.path
            and self.farm_code_input.text().strip()
            and self.farm_name_input.text().strip()
        )
        self.ok_button.setEnabled(ready and not (self.worker and self.worker.isRunning()))

    def _start_prepare(self):
        if not self.cow_row.path:
            QMessageBox.warning(self, "缺少文件", "请先选择母牛信息文件")
            return
        farm_code = self.farm_code_input.text().strip()
        farm_name = self.farm_name_input.text().strip()
        if not farm_code or not farm_name:
            QMessageBox.warning(self, "信息不完整", "请填写牧场编号和牧场名称")
            return

        self.progress_dialog = QProgressDialog(self)
        self.progress_dialog.setWindowTitle("处理本地牧场")
        self.progress_dialog.setLabelText("正在准备...")
        self.progress_dialog.setRange(0, 100)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.show()

        self.worker = LocalFarmPrepareWorker(
            self.cow_row.path,
            self.breeding_row.path,
            self.source_system,
            farm_code,
            farm_name,
            parent=self,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.completed.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.ok_button.setEnabled(False)
        self.worker.start()

    def _on_progress(self, value: int, message: str):
        if self.progress_dialog:
            self.progress_dialog.setValue(value)
            self.progress_dialog.setLabelText(message)

    def _on_finished(self, farm: dict):
        if self.progress_dialog:
            self.progress_dialog.close()
        self.result_farm = farm
        self.accept()

    def _on_error(self, message: str):
        if self.progress_dialog:
            self.progress_dialog.close()
        QMessageBox.critical(
            self,
            "处理失败",
            f"本地牧场信息处理失败：\n\n{message}",
        )
        self.ok_button.setEnabled(
            bool(
                self.cow_row.path
                and self.farm_code_input.text().strip()
                and self.farm_name_input.text().strip()
            )
        )
