"""低内存、原子化地保存大型 DataFrame 到 Excel。"""

from __future__ import annotations

import datetime as dt
import math
import numbers
import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import xlsxwriter


EXCEL_MAX_ROWS = 1_048_576
EXCEL_MAX_COLUMNS = 16_384

DEFAULT_TEXT_COLUMNS = frozenset(
    {
        "cow_id",
        "母牛号",
        "耳号",
        "bull_id",
        "公牛号",
        "naab",
        "sire",
        "父号",
        "父亲号",
        "dam",
        "母号",
        "母亲号",
        "mgs",
        "外祖父",
        "外祖父号",
        "mgd",
        "外祖母",
        "外祖母号",
        "mmgs",
        "外曾祖父",
        "外曾祖父号",
        "api farmcode",
        "farmcode",
        "farm_code",
        "牧场编号",
    }
)


class ExcelSizeError(ValueError):
    """数据超过单个 Excel 工作表的硬限制。"""


def _is_missing(value) -> bool:
    if value is None:
        return True
    try:
        result = pd.isna(value)
        return bool(result) if isinstance(result, (bool, np.bool_)) else False
    except (TypeError, ValueError):
        return False


def normalize_identifier(value) -> str:
    """统一牛号/牧场号等标识符，兼容 Excel 的整数型浮点表示。"""
    if _is_missing(value):
        return ""
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, numbers.Integral) and not isinstance(value, bool):
        return str(int(value))
    if isinstance(value, numbers.Real) and not isinstance(value, bool):
        numeric_value = float(value)
        if math.isfinite(numeric_value) and numeric_value.is_integer():
            return str(int(numeric_value))
    return str(value).strip()


def _normalize_excel_value(value, force_text: bool = False):
    """转换 pandas/numpy 标量，同时保留标识符和小数精度语义。"""
    if _is_missing(value):
        return None
    if force_text:
        return normalize_identifier(value)

    if isinstance(value, np.datetime64):
        value = pd.Timestamp(value)
    elif isinstance(value, np.timedelta64):
        value = pd.Timedelta(value)
    elif isinstance(value, np.generic):
        value = value.item()

    if isinstance(value, pd.Timestamp):
        if value.tzinfo is not None:
            value = value.tz_localize(None)
        return value.to_pydatetime()
    if isinstance(value, pd.Timedelta):
        return value.to_pytimedelta()
    if isinstance(value, dt.datetime) and value.tzinfo is not None:
        return value.replace(tzinfo=None)

    if isinstance(value, numbers.Real) and not isinstance(value, bool):
        numeric_value = float(value)
        if math.isinf(numeric_value):
            return "inf" if numeric_value > 0 else "-inf"
        return value

    if isinstance(
        value,
        (
            str,
            bool,
            numbers.Number,
            dt.datetime,
            dt.date,
            dt.time,
            dt.timedelta,
        ),
    ):
        return value

    return str(value)


def _source_level(value) -> int | None:
    """把 1/2/3 形式的来源标记稳定转换为整数。"""
    if _is_missing(value):
        return None
    try:
        level = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None
    return level if level in {1, 2, 3} else None


def _build_source_style_targets(columns) -> list[tuple[int, tuple[int, ...]]]:
    """建立“结果列 -> 同行来源列”的索引关系。"""
    column_names = [str(column) for column in columns]
    indexes = {
        column_name: index
        for index, column_name in enumerate(column_names)
    }
    targets = []

    for target_index, column_name in enumerate(column_names):
        if column_name.endswith("_source"):
            continue

        source_names = []
        if column_name.endswith("_score"):
            trait = column_name[:-6]
            source_names = [
                f"sire_{trait}_source",
                f"mgs_{trait}_source",
                f"mmgs_{trait}_source",
            ]
            if not any(name in indexes for name in source_names):
                source_names = [f"{column_name}_source"]
        elif (
            column_name.startswith(("sire_", "mgs_", "mmgs_"))
            and not column_name.endswith("_identified")
        ):
            source_names = [f"{column_name}_source"]

        source_indexes = tuple(
            indexes[name]
            for name in source_names
            if name in indexes
        )
        if source_indexes:
            targets.append((target_index, source_indexes))

    return targets


def write_dataframe_atomic(
    df: pd.DataFrame,
    output_path: Path | str,
    *,
    sheet_name: str = "Sheet1",
    text_columns: Iterable[str] | None = None,
    apply_source_formatting: bool = False,
) -> None:
    """以恒定内存写入 DataFrame，成功后再原子替换正式文件。

    写入过程中只保留当前一行，避免 openpyxl 为整张工作表建立内存对象。
    临时文件与目标文件位于同一目录；任何失败都不会截断已有的有效结果。
    """
    output_path = Path(output_path)
    row_count, column_count = df.shape
    if row_count + 1 > EXCEL_MAX_ROWS:
        raise ExcelSizeError(
            f"数据共 {row_count:,} 行，超过 Excel 单工作表最多 "
            f"{EXCEL_MAX_ROWS - 1:,} 行数据的限制"
        )
    if column_count > EXCEL_MAX_COLUMNS:
        raise ExcelSizeError(
            f"数据共 {column_count:,} 列，超过 Excel 最多 "
            f"{EXCEL_MAX_COLUMNS:,} 列的限制"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    target_mode = 0o644
    if output_path.exists():
        target_mode = stat.S_IMODE(output_path.stat().st_mode)
        # Windows 下若文件正被 Excel 占用，这里会在耗时写入前失败。
        with output_path.open("r+b"):
            pass

    requested_text_columns = {
        str(column).strip().casefold()
        for column in (text_columns or ())
    }
    text_column_indexes = {
        index
        for index, column in enumerate(df.columns)
        if str(column).strip().casefold()
        in (DEFAULT_TEXT_COLUMNS | requested_text_columns)
    }

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.stem}.",
        suffix=".tmp.xlsx",
        dir=output_path.parent,
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    workbook = None

    try:
        workbook = xlsxwriter.Workbook(
            temporary_path,
            {
                "constant_memory": True,
                "default_date_format": "yyyy-mm-dd hh:mm:ss",
                "remove_timezone": True,
                "strings_to_formulas": False,
                "strings_to_urls": False,
                "use_zip64": True,
            },
        )
        worksheet = workbook.add_worksheet(sheet_name)
        header_format = workbook.add_format(
            {
                "bold": True,
                "border": 1,
                "align": "center",
                "valign": "top",
            }
        )
        text_format = workbook.add_format({"num_format": "@"})
        red_format = workbook.add_format({"font_color": "#FF0000"})
        yellow_format = workbook.add_format(
            {
                "font_color": "#FFFF00",
                "bg_color": "#808080",
            }
        )
        source_style_targets = (
            _build_source_style_targets(df.columns)
            if apply_source_formatting
            else []
        )

        worksheet.write_row(
            0,
            0,
            [_normalize_excel_value(column) for column in df.columns],
            header_format,
        )
        for column_index in text_column_indexes:
            worksheet.set_column(
                column_index,
                column_index,
                None,
                text_format,
            )

        for row_index, row in enumerate(
            df.itertuples(index=False, name=None),
            start=1,
        ):
            normalized_row = [
                _normalize_excel_value(
                    value,
                    force_text=column_index in text_column_indexes,
                )
                for column_index, value in enumerate(row)
            ]
            worksheet.write_row(row_index, 0, normalized_row)
            for target_index, source_indexes in source_style_targets:
                source_levels = [
                    level
                    for source_index in source_indexes
                    if (level := _source_level(row[source_index])) is not None
                ]
                if not source_levels:
                    continue
                source_level = max(source_levels)
                if source_level == 2:
                    cell_format = red_format
                elif source_level == 3:
                    cell_format = yellow_format
                else:
                    continue
                worksheet.write(
                    row_index,
                    target_index,
                    normalized_row[target_index],
                    cell_format,
                )

        workbook.close()
        workbook = None
        try:
            os.chmod(temporary_path, target_mode)
        except OSError:
            pass
        os.replace(temporary_path, output_path)
    except Exception:
        if workbook is not None:
            try:
                workbook.close()
            except Exception:
                pass
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def copy_file_atomic(source_path: Path | str, output_path: Path | str) -> None:
    """同目录复制到临时文件后原子替换，避免留下 0 KB/半截正式文件。"""
    source_path = Path(source_path)
    output_path = Path(output_path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    target_mode = stat.S_IMODE(source_path.stat().st_mode)
    if output_path.exists():
        target_mode = stat.S_IMODE(output_path.stat().st_mode)
        with output_path.open("r+b"):
            pass

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.stem}.",
        suffix=".tmp.xlsx",
        dir=output_path.parent,
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        shutil.copyfile(source_path, temporary_path)
        try:
            os.chmod(temporary_path, target_mode)
        except OSError:
            pass
        os.replace(temporary_path, output_path)
    except Exception:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
