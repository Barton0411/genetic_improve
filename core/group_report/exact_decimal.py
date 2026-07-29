"""跨 Python/SQLite 一致的精确十进制解析与排序辅助。

该模块不把十进制分值降为二进制 ``float``。每个有限数被拆成：

* ``sign``：负数 ``-1``、零 ``0``、正数 ``1``；
* ``adjusted_exponent``：科学计数法中首位有效数字的十进制指数；
* ``digits``：从首位到末位有效数字、去掉尾零后的纯数字文本。

这三个字段足以在 SQLite 中按精确数值排序。相同数值的不同写法（例如
``1.2300``、``123e-2``）会得到完全相同的规范化表示。
"""

from __future__ import annotations

import numbers
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Tuple


_DECIMAL_TEXT = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$"
)
_SQL_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SQLITE_INTEGER_MIN = -(2**63)
_SQLITE_INTEGER_MAX = 2**63 - 1


class ExactDecimalError(ValueError):
    """输入不是可安全保存并排序的有限十进制数。"""


@dataclass(frozen=True)
class ExactDecimal:
    """有限十进制的规范化、无损表示。"""

    value: Decimal
    text: str
    sign: int
    adjusted_exponent: int
    digits: str

    def sqlite_fields(self) -> Tuple[int, int, str]:
        """返回可直接写入 SQLite 的三个排序字段。"""

        return self.sign, self.adjusted_exponent, self.digits


def _decimal_from_value(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ExactDecimalError("布尔值不是十进制分值")
    if isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, numbers.Integral):
        decimal_value = Decimal(int(value))
    elif isinstance(value, numbers.Real):
        # str(float) 使用 Python 的最短往返文本，避免 Decimal(float)
        # 把二进制存储噪声扩展为几十位伪精度。
        decimal_value = Decimal(str(float(value)))
    elif isinstance(value, str):
        text = value.strip()
        if not text or not _DECIMAL_TEXT.fullmatch(text):
            raise ExactDecimalError("不是合法的十进制数字文本")
        try:
            decimal_value = Decimal(text)
        except InvalidOperation as exc:
            raise ExactDecimalError("无法解析十进制数字") from exc
    else:
        raise ExactDecimalError(
            f"不支持的十进制输入类型：{type(value).__name__}"
        )
    if not decimal_value.is_finite():
        raise ExactDecimalError("十进制分值必须是有限数")
    return decimal_value


def parse_exact_decimal(value: Any) -> ExactDecimal:
    """解析并规范化 int、float、Decimal 或十进制字符串。"""

    decimal_value = _decimal_from_value(value)
    if decimal_value.is_zero():
        return ExactDecimal(
            value=Decimal(0),
            text="0",
            sign=0,
            adjusted_exponent=0,
            digits="0",
        )

    tuple_value = decimal_value.as_tuple()
    digits_list = list(tuple_value.digits)
    exponent = int(tuple_value.exponent)
    while len(digits_list) > 1 and digits_list[-1] == 0:
        digits_list.pop()
        exponent += 1
    digits = "".join(str(digit) for digit in digits_list)
    adjusted_exponent = exponent + len(digits) - 1
    if not (
        _SQLITE_INTEGER_MIN
        <= adjusted_exponent
        <= _SQLITE_INTEGER_MAX
    ):
        raise ExactDecimalError(
            "十进制指数超过 SQLite 64 位整数可排序范围"
        )

    sign = -1 if tuple_value.sign else 1
    mantissa = digits[0]
    if len(digits) > 1:
        mantissa += "." + digits[1:]
    exponent_text = (
        f"+{adjusted_exponent}"
        if adjusted_exponent >= 0
        else str(adjusted_exponent)
    )
    text = f"{'-' if sign < 0 else ''}{mantissa}E{exponent_text}"
    # 根据规范化字段重建 Decimal，确保 value 与 text 不再保留尾零或负零。
    normalized_value = Decimal(
        (1 if sign < 0 else 0, tuple(int(digit) for digit in digits), exponent)
    )
    return ExactDecimal(
        value=normalized_value,
        text=text,
        sign=sign,
        adjusted_exponent=adjusted_exponent,
        digits=digits,
    )


def python_sort_key(value: Any) -> tuple:
    """返回精确数值升序键；降序可直接使用 ``reverse=True``。

    键只依赖规范化字段，不依赖 Decimal 的当前计算上下文。
    """

    parsed = (
        value if isinstance(value, ExactDecimal) else parse_exact_decimal(value)
    )
    if parsed.sign < 0:
        # 负数升序要求绝对值更大的排在前面。终止标记 1 使共同前缀下
        # 较长 digits（更大绝对值）排在较短 digits 之前。
        inverted_digits = tuple(-int(digit) for digit in parsed.digits) + (1,)
        return (0, -parsed.adjusted_exponent, inverted_digits)
    if parsed.sign == 0:
        return (1, 0, ())
    digits_key = tuple(int(digit) for digit in parsed.digits) + (-1,)
    return (2, parsed.adjusted_exponent, digits_key)


def compare_exact_decimal(left: Any, right: Any) -> int:
    """精确比较两个输入，返回 ``-1``、``0`` 或 ``1``。"""

    left_key = python_sort_key(left)
    right_key = python_sort_key(right)
    return (left_key > right_key) - (left_key < right_key)


def _quoted_identifier(value: str) -> str:
    if not isinstance(value, str) or not _SQL_IDENTIFIER.fullmatch(value):
        raise ValueError(f"不安全的 SQLite 字段名：{value!r}")
    return f'"{value}"'


def sqlite_order_by_clause(
    *,
    sign_column: str = "decimal_sign",
    exponent_column: str = "decimal_adjusted_exponent",
    digits_column: str = "decimal_digits",
    descending: bool = False,
) -> str:
    """生成精确十进制的 SQLite ``ORDER BY`` 表达式。

    返回值不包含 ``ORDER BY`` 关键字，调用方可继续追加稳定排序字段。
    """

    sign = _quoted_identifier(sign_column)
    exponent = _quoted_identifier(exponent_column)
    digits = _quoted_identifier(digits_column)
    if descending:
        parts = (
            f"{sign} DESC",
            f"CASE WHEN {sign} = 1 THEN {exponent} END DESC",
            f"CASE WHEN {sign} = 1 THEN {digits} END DESC",
            f"CASE WHEN {sign} = -1 THEN {exponent} END ASC",
            f"CASE WHEN {sign} = -1 THEN {digits} END ASC",
        )
    else:
        parts = (
            f"{sign} ASC",
            f"CASE WHEN {sign} = -1 THEN {exponent} END DESC",
            f"CASE WHEN {sign} = -1 THEN {digits} END DESC",
            f"CASE WHEN {sign} = 1 THEN {exponent} END ASC",
            f"CASE WHEN {sign} = 1 THEN {digits} END ASC",
        )
    return ", ".join(parts)

