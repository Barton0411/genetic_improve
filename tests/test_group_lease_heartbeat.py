from __future__ import annotations

import sqlite3
import threading
import time
import tempfile
import unittest
from collections import deque
from pathlib import Path
from typing import Any, Dict, Optional

from core.group_tasks.lease_heartbeat import (
    GroupLeaseHeartbeat,
    GroupLeaseLostError,
    GroupSelectionFenceError,
)
from utils.group_task_store import GroupTaskStore


def _lease(
    *,
    current: int = 3,
    expected: int = 3,
) -> Dict[str, Any]:
    return {
        "lease_token": "test-token",
        "selection_revision": expected,
        "current_selection_revision": current,
        "selection_is_current": current == expected,
        "heartbeat_at": "2026-07-29T00:00:00Z",
        "expires_at": "2026-07-29T00:01:00Z",
    }


class _FakeLeaseStore:
    def __init__(self, responses):
        self.responses = deque(responses)
        self.refresh_calls = 0
        self.release_calls = 0
        self.refresh_event = threading.Event()
        self._lock = threading.Lock()
        self.last_response: Optional[Dict[str, Any]] = None

    def refresh_run_lease(
        self,
        lease_token: str,
        *,
        lease_seconds: float = 300,
    ) -> Optional[Dict[str, Any]]:
        self.assert_token(lease_token)
        with self._lock:
            self.refresh_calls += 1
            response = (
                self.responses.popleft()
                if self.responses
                else self.last_response
            )
        self.refresh_event.set()
        if isinstance(response, BaseException):
            raise response
        if response is not None:
            self.last_response = dict(response)
            return dict(response)
        return None

    def release_run_lease(self, lease_token: str) -> bool:
        self.assert_token(lease_token)
        with self._lock:
            self.release_calls += 1
        return True

    def assert_token(self, value: str) -> None:
        if value != "test-token":
            raise AssertionError("续租器传入了错误令牌")

    def counts(self) -> tuple[int, int]:
        with self._lock:
            return self.refresh_calls, self.release_calls


class GroupLeaseHeartbeatTests(unittest.TestCase):
    def _heartbeat(
        self,
        store: _FakeLeaseStore,
    ) -> GroupLeaseHeartbeat:
        return GroupLeaseHeartbeat(
            store,
            _lease(),
            lease_seconds=0.3,
            refresh_interval=0.02,
            retry_interval=0.005,
            uncertainty_after=0.2,
        )

    def test_background_thread_refreshes_without_progress_callbacks(self):
        store = _FakeLeaseStore([_lease()])
        heartbeat = self._heartbeat(store).start()
        self.assertTrue(heartbeat.wait_for_first_attempt(1))
        deadline = time.monotonic() + 1
        while store.counts()[0] < 3 and time.monotonic() < deadline:
            time.sleep(0.005)

        heartbeat.check()
        snapshot = heartbeat.snapshot()
        self.assertGreaterEqual(snapshot.successful_refreshes, 3)
        self.assertTrue(snapshot.running)

        self.assertTrue(heartbeat.stop(timeout=1))
        calls_after_stop = store.counts()[0]
        time.sleep(0.05)
        self.assertEqual(store.counts()[0], calls_after_stop)
        self.assertEqual(store.counts()[1], 1)
        self.assertTrue(heartbeat.snapshot().stopped)

    def test_selection_change_is_fenced_but_lease_keeps_refreshing(self):
        changed = _lease(current=4, expected=3)
        store = _FakeLeaseStore([changed])
        heartbeat = self._heartbeat(store).start()
        self.assertTrue(heartbeat.wait_for_first_attempt(1))

        with self.assertRaises(GroupSelectionFenceError) as context:
            heartbeat.check()
        self.assertEqual(context.exception.expected, 3)
        self.assertEqual(context.exception.current, 4)

        first_count = store.counts()[0]
        deadline = time.monotonic() + 1
        while store.counts()[0] <= first_count and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertGreater(store.counts()[0], first_count)
        self.assertTrue(heartbeat.snapshot().selection_fenced)
        self.assertTrue(heartbeat.stop(timeout=1))

    def test_transient_sqlite_errors_retry_and_recovery_is_not_fenced(self):
        store = _FakeLeaseStore(
            [
                sqlite3.OperationalError("database is locked"),
                sqlite3.OperationalError("temporarily unavailable"),
                _lease(),
            ]
        )
        heartbeat = self._heartbeat(store).start()
        deadline = time.monotonic() + 1
        while (
            heartbeat.snapshot().successful_refreshes < 1
            and time.monotonic() < deadline
        ):
            time.sleep(0.005)

        heartbeat.check()
        snapshot = heartbeat.snapshot()
        self.assertEqual(snapshot.transient_error_count, 2)
        self.assertEqual(snapshot.consecutive_transient_errors, 0)
        self.assertFalse(snapshot.renewal_uncertain)
        self.assertEqual(snapshot.last_error, "")
        self.assertTrue(heartbeat.stop(timeout=1))

    def test_lost_lease_is_reported_at_safe_point(self):
        store = _FakeLeaseStore([None])
        heartbeat = self._heartbeat(store).start()
        self.assertTrue(heartbeat.wait_for_first_attempt(1))

        with self.assertRaises(GroupLeaseLostError):
            heartbeat.check()
        snapshot = heartbeat.snapshot()
        self.assertTrue(snapshot.lease_lost)
        self.assertFalse(snapshot.running)
        self.assertTrue(heartbeat.stop(timeout=1))

    def test_real_store_selection_fence_still_holds_exclusive_lease(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            store = GroupTaskStore(
                Path(temporary_dir) / "group_tasks.sqlite3"
            )
            task_id = store.initialize_tasks(
                [{"farm_code": "1001", "farm_name": "线程续租牧场"}]
            )[0]
            revision = store.get_selection_revision()
            lease = store.acquire_run_lease(
                "heartbeat-test",
                run_kind="group-summary",
                lease_seconds=0.5,
                expected_selection_revision=revision,
            )
            self.assertIsNotNone(lease)
            assert lease is not None
            heartbeat = GroupLeaseHeartbeat(
                store,
                lease,
                lease_seconds=0.5,
                refresh_interval=0.03,
                retry_interval=0.01,
                uncertainty_after=0.4,
            ).start()
            self.assertTrue(heartbeat.wait_for_first_attempt(1))

            store.set_included_in_summary(task_id, False)
            deadline = time.monotonic() + 1
            while (
                not heartbeat.snapshot().selection_fenced
                and time.monotonic() < deadline
            ):
                time.sleep(0.005)
            with self.assertRaises(GroupSelectionFenceError):
                heartbeat.check()

            blocked = store.acquire_run_lease(
                "replacement",
                run_kind="group-summary",
                lease_seconds=0.5,
            )
            self.assertIsNone(blocked)
            self.assertTrue(heartbeat.stop(timeout=1))

            replacement = store.acquire_run_lease(
                "replacement",
                run_kind="group-summary",
                lease_seconds=0.5,
            )
            self.assertIsNotNone(replacement)
            assert replacement is not None
            self.assertTrue(
                store.release_run_lease(replacement["lease_token"])
            )


if __name__ == "__main__":
    unittest.main()
