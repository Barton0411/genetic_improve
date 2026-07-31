"""牧场组顺序任务的跨平台自适应内存保护。

保护逻辑只看系统当前可用内存，不限制牧场数量，也不按机器总内存
简单拒绝任务。牧场仍逐个处理：

* 在下一牧场/下一子进程的安全边界检查可用内存；
* 运行期间只有连续多次进入危险区才建议终止当前子进程；
* 无法读取内存状态时降级为不拦截，避免因监控能力缺失误伤任务。
"""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable, Optional


MIB = 1024 * 1024
GIB = 1024 * MIB


@dataclass(frozen=True)
class MemorySnapshot:
    """一次系统内存状态快照。"""

    total_bytes: int
    available_bytes: int
    source: str
    captured_at: float

    @property
    def available_gib(self) -> float:
        return self.available_bytes / GIB


@dataclass(frozen=True)
class MemoryGuardConfig:
    """内存保护阈值。

    ``*_floor`` 避免小内存机器把安全余量压得过低，``*_fraction`` 让
    大内存机器保留合理比例，``*_cap`` 则避免大内存机器因为固定比例
    被过早拦截。最终阈值为 ``max(floor, min(total*fraction, cap))``。
    """

    boundary_floor_bytes: int = 1536 * MIB
    boundary_fraction: float = 0.12
    boundary_cap_bytes: int = 4 * GIB
    danger_floor_bytes: int = 1 * GIB
    danger_fraction: float = 0.08
    danger_cap_bytes: int = 2 * GIB
    sustained_danger_samples: int = 3
    runtime_check_interval_seconds: float = 1.0


@dataclass(frozen=True)
class MemoryAssessment:
    """内存保护判断结果。"""

    status: str
    snapshot: Optional[MemorySnapshot]
    threshold_bytes: int = 0
    consecutive_danger_samples: int = 0

    @property
    def should_pause(self) -> bool:
        return self.status in {"boundary_low", "sustained_danger"}


MemoryProvider = Callable[[], Optional[MemorySnapshot]]


class ResourcePressureError(RuntimeError):
    """资源保护主动暂停；业务代码不得把它当作可选步骤异常吞掉。"""


def _threshold(
    total_bytes: int,
    *,
    floor_bytes: int,
    fraction: float,
    cap_bytes: int,
) -> int:
    proportional = int(max(total_bytes, 0) * max(fraction, 0.0))
    return max(int(floor_bytes), min(proportional, int(cap_bytes)))


def _psutil_snapshot() -> Optional[MemorySnapshot]:
    try:
        import psutil

        memory = psutil.virtual_memory()
        total = int(memory.total)
        available = int(memory.available)
        if total <= 0 or available < 0:
            return None
        return MemorySnapshot(
            total_bytes=total,
            available_bytes=min(available, total),
            source="psutil",
            captured_at=time.time(),
        )
    except (ImportError, AttributeError, OSError, ValueError):
        return None


def _windows_snapshot() -> Optional[MemorySnapshot]:
    if sys.platform != "win32":
        return None

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    try:
        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(
            ctypes.byref(status)
        ):
            return None
        total = int(status.ullTotalPhys)
        available = int(status.ullAvailPhys)
    except (AttributeError, OSError, ValueError):
        return None
    if total <= 0 or available < 0:
        return None
    return MemorySnapshot(
        total_bytes=total,
        available_bytes=min(available, total),
        source="windows",
        captured_at=time.time(),
    )


def _posix_sysconf_snapshot() -> Optional[MemorySnapshot]:
    if os.name != "posix":
        return None
    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        total_pages = int(os.sysconf("SC_PHYS_PAGES"))
        available_pages = int(os.sysconf("SC_AVPHYS_PAGES"))
    except (AttributeError, OSError, TypeError, ValueError):
        return None
    total = total_pages * page_size
    available = available_pages * page_size
    if total <= 0 or available < 0:
        return None
    return MemorySnapshot(
        total_bytes=total,
        available_bytes=min(available, total),
        source="sysconf",
        captured_at=time.time(),
    )


def _linux_proc_snapshot() -> Optional[MemorySnapshot]:
    """在 Linux 无 psutil 时读取内核给出的 MemAvailable。"""

    if not sys.platform.startswith("linux"):
        return None
    try:
        values = {}
        with open("/proc/meminfo", "r", encoding="ascii") as stream:
            for line in stream:
                key, _, value = line.partition(":")
                match = re.search(r"\d+", value)
                if match:
                    values[key] = int(match.group()) * 1024
        total = int(values["MemTotal"])
        available = int(values.get("MemAvailable", 0))
        if available <= 0:
            # 老内核没有 MemAvailable；使用可立即回收项的保守近似。
            available = (
                int(values.get("MemFree", 0))
                + int(values.get("Buffers", 0))
                + int(values.get("Cached", 0))
                + int(values.get("SReclaimable", 0))
                - int(values.get("Shmem", 0))
            )
    except (KeyError, OSError, TypeError, ValueError):
        return None
    if total <= 0 or available < 0:
        return None
    return MemorySnapshot(
        total_bytes=total,
        available_bytes=min(available, total),
        source="proc_meminfo",
        captured_at=time.time(),
    )


def _darwin_vm_stat_snapshot() -> Optional[MemorySnapshot]:
    """在未安装 psutil 时从 macOS ``vm_stat`` 读取可回收内存。"""

    if sys.platform != "darwin":
        return None
    try:
        output = subprocess.check_output(
            ["/usr/bin/vm_stat"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        first_line = output.splitlines()[0]
        page_match = re.search(r"page size of\s+(\d+)\s+bytes", first_line)
        page_size = int(page_match.group(1)) if page_match else 4096
        values = {}
        for line in output.splitlines()[1:]:
            match = re.match(r"([^:]+):\s+(\d+)", line)
            if match:
                values[match.group(1).strip()] = int(match.group(2))

        # 与 psutil 的 available 语义接近：立即可用或可快速回收的页。
        available_pages = sum(
            values.get(key, 0)
            for key in (
                "Pages free",
                "Pages inactive",
                "Pages speculative",
                "Pages purgeable",
            )
        )
        total_pages = int(os.sysconf("SC_PHYS_PAGES"))
        total = total_pages * page_size
        available = available_pages * page_size
    except (
        IndexError,
        OSError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ):
        return None
    if total <= 0 or available < 0:
        return None
    return MemorySnapshot(
        total_bytes=total,
        available_bytes=min(available, total),
        source="vm_stat",
        captured_at=time.time(),
    )


def system_memory_snapshot() -> Optional[MemorySnapshot]:
    """读取系统内存；psutil 不可用时使用操作系统原生降级路径。"""

    for provider in (
        _psutil_snapshot,
        _windows_snapshot,
        _linux_proc_snapshot,
        _posix_sysconf_snapshot,
        _darwin_vm_stat_snapshot,
    ):
        snapshot = provider()
        if snapshot is not None:
            return snapshot
    return None


def format_gib(byte_count: int) -> str:
    return f"{max(int(byte_count), 0) / GIB:.2f} GB"


class AdaptiveMemoryGuard:
    """对安全边界和运行中持续内存压力作出判断。"""

    def __init__(
        self,
        *,
        provider: MemoryProvider = system_memory_snapshot,
        config: Optional[MemoryGuardConfig] = None,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self.provider = provider
        self.config = config or MemoryGuardConfig()
        self.monotonic = monotonic
        self._danger_samples = 0
        self._last_runtime_check: Optional[float] = None

    def _read_snapshot(self) -> Optional[MemorySnapshot]:
        # 内存监控是保护层，监控本身不可成为业务任务失败原因。
        try:
            return self.provider()
        except Exception:
            return None

    def reset_runtime_monitor(self) -> None:
        self._danger_samples = 0
        self._last_runtime_check = None

    def assess_boundary(self) -> MemoryAssessment:
        """判断是否适合开始下一个不可分割的单牧场工作单元。"""

        self.reset_runtime_monitor()
        snapshot = self._read_snapshot()
        if snapshot is None:
            return MemoryAssessment("unknown", None)
        threshold = _threshold(
            snapshot.total_bytes,
            floor_bytes=self.config.boundary_floor_bytes,
            fraction=self.config.boundary_fraction,
            cap_bytes=self.config.boundary_cap_bytes,
        )
        status = (
            "boundary_low"
            if snapshot.available_bytes < threshold
            else "ok"
        )
        return MemoryAssessment(status, snapshot, threshold)

    def poll_runtime(self, *, force: bool = False) -> MemoryAssessment:
        """轮询运行中内存。

        危险状态必须连续出现 ``sustained_danger_samples`` 次才返回
        ``sustained_danger``。短暂尖峰只会返回 ``danger``，不会中断。
        未到轮询间隔时返回 ``not_due``，且不会读取系统状态。
        """

        now = self.monotonic()
        interval = max(
            float(self.config.runtime_check_interval_seconds),
            0.0,
        )
        if (
            not force
            and self._last_runtime_check is not None
            and now - self._last_runtime_check < interval
        ):
            return MemoryAssessment(
                "not_due",
                None,
                consecutive_danger_samples=self._danger_samples,
            )
        self._last_runtime_check = now

        snapshot = self._read_snapshot()
        if snapshot is None:
            self._danger_samples = 0
            return MemoryAssessment("unknown", None)
        threshold = _threshold(
            snapshot.total_bytes,
            floor_bytes=self.config.danger_floor_bytes,
            fraction=self.config.danger_fraction,
            cap_bytes=self.config.danger_cap_bytes,
        )
        if snapshot.available_bytes < threshold:
            self._danger_samples += 1
            required = max(int(self.config.sustained_danger_samples), 1)
            status = (
                "sustained_danger"
                if self._danger_samples >= required
                else "danger"
            )
        else:
            self._danger_samples = 0
            status = "ok"
        return MemoryAssessment(
            status,
            snapshot,
            threshold,
            consecutive_danger_samples=self._danger_samples,
        )


def boundary_pause_message(assessment: MemoryAssessment) -> str:
    snapshot = assessment.snapshot
    if snapshot is None:
        return ""
    return (
        "系统当前可用内存约 "
        f"{format_gib(snapshot.available_bytes)}，低于开始下一牧场所需的"
        f"安全余量 {format_gib(assessment.threshold_bytes)}。"
        "已完成牧场和已提交阶段均已保留；请关闭其他应用释放内存后，"
        "重新点击继续处理。"
    )


def runtime_pause_message(assessment: MemoryAssessment) -> str:
    snapshot = assessment.snapshot
    if snapshot is None:
        available = "未知"
        threshold = "安全线"
    else:
        available = format_gib(snapshot.available_bytes)
        threshold = format_gib(assessment.threshold_bytes)
    return (
        f"检测到系统可用内存持续处于危险区（当前约 {available}，"
        f"安全线 {threshold}）。已安全终止当前牧场子进程；"
        "此前已提交阶段均已保留，当前阶段可重试。"
        "请关闭其他应用释放内存后继续处理。"
    )
