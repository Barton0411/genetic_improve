"""牧场组长任务的独立后台租约续租器。

调用方先通过 :class:`utils.group_task_store.GroupTaskStore` 获取租约，再把
租约令牌交给本模块。续租线程不依赖业务进度回调，因此即使一个 Excel
分卷、SQLite 排序或文件校验长时间没有进度事件，租约也能继续保持。

选择范围变化属于 fencing 错误：后台线程会记录错误，但仍继续续租，直至
调用方在安全点调用 :meth:`GroupLeaseHeartbeat.check` 后停止任务。这样在
业务代码完成当前原子写入之前，不会让另一个运行取得同一组级租约。
"""

from __future__ import annotations

import math
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Protocol


class LeaseStore(Protocol):
    """后台续租所需的最小存储接口。"""

    def refresh_run_lease(
        self,
        lease_token: str,
        *,
        lease_seconds: float = 300,
    ) -> Optional[Dict[str, Any]]:
        ...

    def release_run_lease(self, lease_token: str) -> bool:
        ...


class GroupLeaseHeartbeatError(RuntimeError):
    """后台续租器检测到任务不再具备安全发布条件。"""


class GroupLeaseLostError(GroupLeaseHeartbeatError):
    """租约已经过期、被替换或令牌不再匹配。"""


class GroupSelectionFenceError(GroupLeaseHeartbeatError):
    """租约仍被持有，但纳入汇总的选择范围已经变化。"""

    def __init__(self, expected: int, current: int):
        self.expected = int(expected)
        self.current = int(current)
        super().__init__(
            "牧场组纳入范围发生变化，当前运行不得发布："
            f"启动版本 {self.expected}，当前版本 {self.current}"
        )


class GroupLeaseRenewalUncertainError(GroupLeaseHeartbeatError):
    """数据库持续不可用，已经无法保证租约仍有足够安全余量。"""


class GroupLeaseHeartbeatInternalError(GroupLeaseHeartbeatError):
    """续租线程遇到非预期实现错误。"""


@dataclass(frozen=True)
class LeaseHeartbeatSnapshot:
    """不包含租约令牌的线程安全诊断快照。"""

    started: bool
    running: bool
    stopped: bool
    refresh_attempts: int
    successful_refreshes: int
    transient_error_count: int
    consecutive_transient_errors: int
    selection_fenced: bool
    lease_lost: bool
    renewal_uncertain: bool
    last_error: str
    last_lease: Dict[str, Any]


class GroupLeaseHeartbeat:
    """在独立短周期线程中保持一个已经获取的组级租约。

    ``check()`` 只抛出 fencing/失租错误。短暂的 ``sqlite3.Error`` 会在
    后台重试；成功续租后不会把已经恢复的瞬时错误传播给业务线程。
    """

    def __init__(
        self,
        store: LeaseStore,
        lease: Mapping[str, Any],
        *,
        lease_seconds: float = 300,
        refresh_interval: Optional[float] = None,
        retry_interval: Optional[float] = None,
        uncertainty_after: Optional[float] = None,
        thread_name: str = "group-lease-heartbeat",
    ):
        token = str(lease.get("lease_token") or "").strip()
        if not token:
            raise ValueError("lease 缺少 lease_token")
        duration = float(lease_seconds)
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("lease_seconds 必须是大于 0 的有限数值")

        interval = (
            min(30.0, duration / 3.0)
            if refresh_interval is None
            else float(refresh_interval)
        )
        if (
            not math.isfinite(interval)
            or interval <= 0
            or interval >= duration
        ):
            raise ValueError(
                "refresh_interval 必须大于 0 且小于 lease_seconds"
            )
        retry = (
            min(interval, 1.0)
            if retry_interval is None
            else float(retry_interval)
        )
        if not math.isfinite(retry) or retry <= 0:
            raise ValueError("retry_interval 必须是大于 0 的有限数值")

        uncertain = (
            duration * 0.8
            if uncertainty_after is None
            else float(uncertainty_after)
        )
        if (
            not math.isfinite(uncertain)
            or uncertain <= 0
            or uncertain >= duration
        ):
            raise ValueError(
                "uncertainty_after 必须大于 0 且小于 lease_seconds"
            )

        self._store = store
        self._lease_token = token
        self._lease_seconds = duration
        self._refresh_interval = interval
        self._retry_interval = retry
        self._uncertainty_after = uncertain
        self._expected_selection_revision = int(
            lease.get("selection_revision", 0) or 0
        )
        self._thread_name = str(thread_name or "group-lease-heartbeat")

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._first_attempt_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._started = False
        self._stopped = False
        self._refresh_attempts = 0
        self._successful_refreshes = 0
        self._transient_error_count = 0
        self._consecutive_transient_errors = 0
        self._last_success_monotonic = time.monotonic()
        self._last_error = ""
        self._last_lease = self._public_lease(lease)
        self._selection_error: Optional[GroupSelectionFenceError] = None
        self._lease_lost_error: Optional[GroupLeaseLostError] = None
        self._renewal_error: Optional[
            GroupLeaseRenewalUncertainError
        ] = None
        self._internal_error: Optional[
            GroupLeaseHeartbeatInternalError
        ] = None

    @staticmethod
    def _public_lease(lease: Mapping[str, Any]) -> Dict[str, Any]:
        """移除令牌后保存最近一次续租结果。"""
        return {
            str(key): value
            for key, value in lease.items()
            if str(key) != "lease_token"
        }

    def start(self) -> "GroupLeaseHeartbeat":
        """启动续租线程；同一个实例只能启动一次。"""
        with self._lock:
            if self._started:
                raise RuntimeError("组级租约续租器已经启动")
            if self._stopped:
                raise RuntimeError("已经停止的续租器不能重新启动")
            self._started = True
            thread = threading.Thread(
                target=self._run,
                name=self._thread_name,
                daemon=True,
            )
            self._thread = thread
            thread.start()
        return self

    def _record_sqlite_error(self, exc: sqlite3.Error) -> None:
        now = time.monotonic()
        with self._lock:
            self._transient_error_count += 1
            self._consecutive_transient_errors += 1
            self._last_error = f"{type(exc).__name__}: {exc}"
            if (
                now - self._last_success_monotonic
                >= self._uncertainty_after
            ):
                self._renewal_error = GroupLeaseRenewalUncertainError(
                    "组级租约数据库持续不可用，已无法确认租约仍安全有效"
                )

    def _record_success(self, lease: Mapping[str, Any]) -> None:
        expected = int(
            lease.get(
                "selection_revision",
                self._expected_selection_revision,
            )
            or 0
        )
        current = int(
            lease.get("current_selection_revision", expected) or 0
        )
        selection_is_current = bool(
            lease.get("selection_is_current", expected == current)
        )
        with self._lock:
            self._successful_refreshes += 1
            self._consecutive_transient_errors = 0
            self._last_success_monotonic = time.monotonic()
            self._last_error = ""
            self._last_lease = self._public_lease(lease)
            self._renewal_error = None
            if not selection_is_current and self._selection_error is None:
                self._selection_error = GroupSelectionFenceError(
                    expected,
                    current,
                )

    def _run(self) -> None:
        delay = 0.0
        while not self._stop_event.wait(delay):
            with self._lock:
                self._refresh_attempts += 1
            try:
                refreshed = self._store.refresh_run_lease(
                    self._lease_token,
                    lease_seconds=self._lease_seconds,
                )
            except sqlite3.Error as exc:
                self._record_sqlite_error(exc)
                delay = self._retry_interval
            except Exception as exc:
                with self._lock:
                    self._last_error = f"{type(exc).__name__}: {exc}"
                    self._internal_error = (
                        GroupLeaseHeartbeatInternalError(
                            "组级租约续租线程发生非预期错误"
                        )
                    )
                self._first_attempt_event.set()
                return
            else:
                if refreshed is None:
                    with self._lock:
                        self._last_error = "租约已失效或令牌不匹配"
                        self._lease_lost_error = GroupLeaseLostError(
                            "组级租约已失效或被其他运行替换"
                        )
                    self._first_attempt_event.set()
                    return
                self._record_success(refreshed)
                delay = self._refresh_interval
            finally:
                self._first_attempt_event.set()

    def wait_for_first_attempt(self, timeout: Optional[float] = None) -> bool:
        """等待后台完成第一次续租尝试，便于启动阶段建立安全屏障。"""
        return self._first_attempt_event.wait(timeout)

    def check(self) -> None:
        """在业务安全点检查 fencing 状态，有问题则抛出明确异常。"""
        with self._lock:
            error = (
                self._lease_lost_error
                or self._internal_error
                or self._selection_error
                or self._renewal_error
            )
        if error is not None:
            raise error

    def snapshot(self) -> LeaseHeartbeatSnapshot:
        """返回不泄露租约令牌的当前状态。"""
        with self._lock:
            thread = self._thread
            return LeaseHeartbeatSnapshot(
                started=self._started,
                running=bool(thread and thread.is_alive()),
                stopped=self._stopped,
                refresh_attempts=self._refresh_attempts,
                successful_refreshes=self._successful_refreshes,
                transient_error_count=self._transient_error_count,
                consecutive_transient_errors=(
                    self._consecutive_transient_errors
                ),
                selection_fenced=self._selection_error is not None,
                lease_lost=self._lease_lost_error is not None,
                renewal_uncertain=self._renewal_error is not None,
                last_error=self._last_error,
                last_lease=dict(self._last_lease),
            )

    def stop(
        self,
        *,
        timeout: Optional[float] = None,
        release: bool = True,
    ) -> bool:
        """停止线程并可释放租约；返回租约是否已成功释放。

        如果线程在 ``timeout`` 内没有退出，则不会抢先释放租约，以免后台
        线程仍在运行时让另一批任务取得同一租约。
        """
        self._stop_event.set()
        with self._lock:
            thread = self._thread
        if thread is threading.current_thread():
            raise RuntimeError("不能从续租线程内部调用 stop()")
        if thread is not None:
            thread.join(timeout)
            if thread.is_alive():
                raise TimeoutError("组级租约续租线程未在限定时间内退出")
        with self._lock:
            self._stopped = True
        if not release:
            return False
        try:
            return bool(
                self._store.release_run_lease(self._lease_token)
            )
        except sqlite3.Error as exc:
            with self._lock:
                self._last_error = f"{type(exc).__name__}: {exc}"
            return False

    def __enter__(self) -> "GroupLeaseHeartbeat":
        return self.start()

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.stop()


__all__ = [
    "GroupLeaseHeartbeat",
    "GroupLeaseHeartbeatError",
    "GroupLeaseHeartbeatInternalError",
    "GroupLeaseLostError",
    "GroupLeaseRenewalUncertainError",
    "GroupSelectionFenceError",
    "LeaseHeartbeatSnapshot",
]
