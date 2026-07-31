"""牧场组 SQLite 任务状态存储测试。"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from utils.group_task_store import (
    GROUP_TASK_STAGES,
    GroupTaskStore,
    SelectionRevisionMismatchError,
    TaskNotFoundError,
)


class GroupTaskStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_dir.name) / "state" / "group_tasks.sqlite3"
        )
        self.store = GroupTaskStore(self.database_path)

    def tearDown(self):
        self.temporary_dir.cleanup()

    def test_initializes_uuid_tasks_and_all_three_stages_in_wal_mode(self):
        task_ids = self.store.initialize_tasks(
            [
                {"farm_code": "1001", "farm_name": "一号牧场"},
                {"farm_code": "1001", "farm_name": "一号牧场复算"},
            ]
        )

        self.assertEqual(self.store.journal_mode, "wal")
        self.assertEqual(len(task_ids), 2)
        self.assertNotEqual(task_ids[0], task_ids[1])
        for task_id in task_ids:
            self.assertEqual(str(uuid.UUID(task_id)), task_id)

        tasks = self.store.list_tasks()
        self.assertEqual([task["farm_code"] for task in tasks], ["1001", "1001"])
        self.assertEqual(
            tuple(tasks[0]["stages"]),
            GROUP_TASK_STAGES,
        )
        self.assertTrue(
            all(stage["required"] for stage in tasks[0]["stages"].values())
        )
        self.assertFalse(self.store.is_complete())

    def test_stage_updates_are_atomic_and_derive_overall_completion(self):
        task_id = self.store.initialize_tasks(
            [{"farm_code": "1002", "farm_name": "二号牧场"}]
        )[0]

        task = self.store.update_stage(
            task_id,
            "data",
            status="running",
            progress=25,
        )
        self.assertEqual(task["status"], "running")
        self.assertEqual(task["current_stage"], "data")
        self.assertAlmostEqual(task["progress"], 25 / 3)

        self.store.update_stage(
            task_id,
            "data",
            status="completed",
            output_path="standardized_data/cows.xlsx",
            detail_count=1_500_000,
        )
        self.store.update_stage(
            task_id,
            "analysis",
            status="completed",
            output_path="analysis_results",
        )
        task = self.store.update_stage(
            task_id,
            "child_excel",
            status="completed",
            output_path="reports/单牧场报告.xlsx",
        )

        self.assertEqual(task["status"], "completed")
        self.assertEqual(task["progress"], 100)
        self.assertIsNone(task["current_stage"])
        self.assertEqual(
            task["stages"]["data"]["detail_count"],
            1_500_000,
        )
        self.assertTrue(self.store.is_complete())

    def test_included_flag_is_independent_from_execution_status(self):
        first, second = self.store.initialize_tasks(
            [
                {"farm_code": "1003", "farm_name": "三号牧场"},
                {"farm_code": "1004", "farm_name": "四号牧场"},
            ],
            required_stages=("data",),
        )
        self.store.update_stage(first, "data", status="completed")
        self.store.update_stage(
            second,
            "data",
            status="failed",
            error="接口暂时不可用",
        )
        failed_before = self.store.get_task(second)
        self.assertEqual(failed_before["status"], "failed")
        self.assertFalse(self.store.is_complete())

        excluded = self.store.set_included_in_summary(second, False)
        self.assertFalse(excluded["included_in_summary"])
        self.assertEqual(excluded["status"], "failed")
        self.assertTrue(self.store.is_complete())

        included = self.store.set_included_in_summary(second, True)
        self.assertTrue(included["included_in_summary"])
        self.assertEqual(included["status"], "failed")
        self.assertFalse(self.store.is_complete())

    def test_non_required_stages_are_skipped_and_do_not_block_completion(self):
        task_id = self.store.initialize_tasks(
            [{"farm_code": "1005", "farm_name": "五号牧场"}],
            required_stages=("data",),
        )[0]
        task = self.store.get_task(task_id)
        self.assertEqual(task["stages"]["analysis"]["status"], "skipped")
        self.assertFalse(task["stages"]["analysis"]["required"])

        self.store.update_stage(task_id, "data", status="completed")
        self.assertTrue(self.store.is_complete())
        self.assertTrue(
            self.store.is_complete(required_stages=("data",))
        )
        self.assertFalse(
            self.store.is_complete(required_stages=("data", "analysis"))
        )

    def test_mark_stale_uses_heartbeat_and_can_reset_for_retry(self):
        task_id = self.store.initialize_tasks(
            [{"farm_code": "1006", "farm_name": "六号牧场"}]
        )[0]
        old_time = datetime(2026, 7, 29, 8, 0, tzinfo=timezone.utc)
        self.store.update_stage(
            task_id,
            "data",
            status="running",
            at=old_time,
        )
        self.store.heartbeat(task_id, stage="data", at=old_time)

        stale_ids = self.store.mark_stale(
            stale_after_seconds=60,
            now=old_time + timedelta(minutes=2),
        )
        self.assertEqual(stale_ids, [task_id])
        stale_task = self.store.get_task(task_id)
        self.assertEqual(stale_task["status"], "stale")
        self.assertEqual(stale_task["stages"]["data"]["status"], "stale")

        retry_task = self.store.reset_for_retry(task_id)
        self.assertEqual(retry_task["status"], "pending")
        self.assertEqual(retry_task["stages"]["data"]["status"], "pending")
        self.assertEqual(retry_task["stages"]["analysis"]["status"], "pending")

    def test_initialization_rolls_back_all_rows_if_any_task_is_invalid(self):
        with self.assertRaisesRegex(ValueError, "farm_code"):
            self.store.initialize_tasks(
                [
                    {"farm_code": "1007", "farm_name": "七号牧场"},
                    {"farm_code": "", "farm_name": "无编号"},
                ]
            )
        self.assertEqual(self.store.list_tasks(), [])

    def test_separate_thread_connections_can_heartbeat_same_database(self):
        task_ids = self.store.initialize_tasks(
            [
                {"farm_code": str(2000 + index), "farm_name": f"牧场{index}"}
                for index in range(20)
            ],
            required_stages=("data",),
        )
        for task_id in task_ids:
            self.store.update_stage(task_id, "data", status="running")

        def pulse(task_id: str) -> None:
            independent_store = GroupTaskStore(self.database_path)
            for progress in (10, 30, 60, 90):
                independent_store.heartbeat(
                    task_id,
                    stage="data",
                    progress=progress,
                )

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(pulse, task_ids))

        for task_id in task_ids:
            task = self.store.get_task(task_id)
            self.assertEqual(task["status"], "running")
            self.assertEqual(task["stages"]["data"]["progress"], 90)

    def test_missing_task_update_raises_specific_error(self):
        with self.assertRaises(TaskNotFoundError):
            self.store.update_task(str(uuid.uuid4()), status="running")

    def test_completion_state_reports_included_and_excluded_counts(self):
        first, second, third = self.store.initialize_tasks(
            [
                {"farm_code": "3001", "farm_name": "甲"},
                {"farm_code": "3002", "farm_name": "乙"},
                {
                    "farm_code": "3003",
                    "farm_name": "丙",
                    "included_in_summary": False,
                },
            ],
            required_stages=("data",),
        )
        self.store.update_stage(first, "data", status="completed")
        self.store.update_stage(second, "data", status="completed")
        self.store.update_stage(third, "data", status="failed")

        state = self.store.completion_state()
        self.assertEqual(state["total_count"], 3)
        self.assertEqual(state["included_count"], 2)
        self.assertEqual(state["excluded_count"], 1)
        self.assertEqual(state["completed_count"], 2)
        self.assertTrue(state["is_complete"])

    def test_database_enforces_primary_key_without_farm_code_uniqueness(self):
        fixed_id = str(uuid.uuid4())
        self.store.initialize_tasks(
            [
                {
                    "task_id": fixed_id,
                    "farm_code": "4001",
                    "farm_name": "第一次",
                }
            ]
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.initialize_tasks(
                [
                    {
                        "task_id": fixed_id,
                        "farm_code": "4001",
                        "farm_name": "第二次",
                    }
                ]
            )

    def test_list_tasks_loads_all_stages_with_one_batch_query(self):
        self.store.initialize_tasks(
            [
                {"farm_code": f"500{index}", "farm_name": f"牧场{index}"}
                for index in range(6)
            ]
        )
        statements = []
        original_connect = self.store._connect

        def traced_connect():
            connection = original_connect()
            connection.set_trace_callback(statements.append)
            return connection

        with patch.object(
            self.store,
            "_connect",
            side_effect=traced_connect,
        ):
            tasks = self.store.list_tasks(with_stages=True)

        stage_selects = [
            statement
            for statement in statements
            if statement.lstrip().upper().startswith("SELECT")
            and "FROM group_task_stages AS s" in statement
        ]
        self.assertEqual(len(tasks), 6)
        self.assertEqual(len(stage_selects), 1)
        for task in tasks:
            self.assertEqual(tuple(task["stages"]), GROUP_TASK_STAGES)

    def test_selection_revision_only_increments_for_real_flag_changes(self):
        task_id = self.store.initialize_tasks(
            [{"farm_code": "6001", "farm_name": "选择版本牧场"}]
        )[0]

        self.assertEqual(self.store.get_selection_revision(), 0)
        self.store.set_included_in_summary(task_id, False)
        self.assertEqual(self.store.get_selection_revision(), 1)

        self.store.set_included_in_summary(task_id, False)
        self.store.update_task(task_id, status="running")
        self.assertEqual(self.store.get_selection_revision(), 1)

        self.store.update_task(task_id, included_in_summary=True)
        self.assertEqual(self.store.get_selection_revision(), 2)

    def test_run_lease_is_exclusive_refreshable_and_releasable(self):
        task_id = self.store.initialize_tasks(
            [{"farm_code": "6002", "farm_name": "租约牧场"}]
        )[0]
        start = datetime(2026, 7, 29, 9, 0, tzinfo=timezone.utc)
        revision = self.store.get_selection_revision()

        lease = self.store.acquire_run_lease(
            "batch-worker-1",
            run_kind="batch",
            lease_seconds=60,
            expected_selection_revision=revision,
            at=start,
        )
        self.assertIsNotNone(lease)
        self.assertEqual(lease["owner_id"], "batch-worker-1")
        self.assertEqual(lease["run_kind"], "batch")
        self.assertEqual(lease["selection_revision"], revision)
        self.assertTrue(lease["selection_is_current"])

        blocked = self.store.acquire_run_lease(
            "summary-worker-1",
            run_kind="summary",
            lease_seconds=60,
            at=start + timedelta(seconds=1),
        )
        self.assertIsNone(blocked)

        self.store.set_included_in_summary(task_id, False)
        refreshed = self.store.refresh_run_lease(
            lease["lease_token"],
            lease_seconds=120,
            at=start + timedelta(seconds=10),
        )
        self.assertIsNotNone(refreshed)
        self.assertEqual(
            refreshed["current_selection_revision"],
            revision + 1,
        )
        self.assertFalse(refreshed["selection_is_current"])
        self.assertFalse(self.store.release_run_lease("wrong-token"))
        self.assertTrue(
            self.store.release_run_lease(lease["lease_token"])
        )

        replacement = self.store.acquire_run_lease(
            "summary-worker-1",
            run_kind="summary",
            at=start + timedelta(seconds=11),
        )
        self.assertIsNotNone(replacement)

    def test_expired_run_lease_can_be_taken_over(self):
        start = datetime(2026, 7, 29, 10, 0, tzinfo=timezone.utc)
        first = self.store.acquire_run_lease(
            "first-worker",
            run_kind="batch",
            lease_seconds=30,
            at=start,
        )
        self.assertIsNotNone(first)

        second = self.store.acquire_run_lease(
            "second-worker",
            run_kind="summary",
            lease_seconds=30,
            at=start + timedelta(seconds=30),
        )
        self.assertIsNotNone(second)
        self.assertNotEqual(
            first["lease_token"],
            second["lease_token"],
        )
        self.assertIsNone(
            self.store.refresh_run_lease(
                first["lease_token"],
                at=start + timedelta(seconds=31),
            )
        )
        self.assertFalse(
            self.store.release_run_lease(first["lease_token"])
        )
        self.assertTrue(
            self.store.release_run_lease(second["lease_token"])
        )

    def test_expired_matching_lease_can_resume_after_host_sleep(self):
        start = datetime(2026, 7, 29, 10, 30, tzinfo=timezone.utc)
        lease = self.store.acquire_run_lease(
            "sleeping-worker",
            run_kind="batch",
            lease_seconds=30,
            at=start,
        )
        self.assertIsNotNone(lease)
        assert lease is not None

        refreshed = self.store.refresh_run_lease(
            lease["lease_token"],
            lease_seconds=60,
            at=start + timedelta(hours=2),
        )

        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(
            refreshed["lease_token"],
            lease["lease_token"],
        )
        blocked = self.store.acquire_run_lease(
            "replacement",
            run_kind="summary",
            at=start + timedelta(hours=2, seconds=1),
        )
        self.assertIsNone(blocked)
        self.assertTrue(
            self.store.release_run_lease(lease["lease_token"])
        )

    def test_acquire_run_lease_rejects_stale_selection_revision(self):
        task_id = self.store.initialize_tasks(
            [{"farm_code": "6003", "farm_name": "版本校验牧场"}]
        )[0]
        expected = self.store.get_selection_revision()
        self.store.set_included_in_summary(task_id, False)

        with self.assertRaises(SelectionRevisionMismatchError) as context:
            self.store.acquire_run_lease(
                "summary-worker",
                run_kind="summary",
                expected_selection_revision=expected,
            )
        self.assertEqual(context.exception.expected, expected)
        self.assertEqual(context.exception.current, expected + 1)

    def test_concurrent_run_lease_acquisition_has_one_winner(self):
        start = datetime(2026, 7, 29, 11, 0, tzinfo=timezone.utc)

        def acquire(index: int):
            independent_store = GroupTaskStore(self.database_path)
            return independent_store.acquire_run_lease(
                f"worker-{index}",
                run_kind="batch",
                lease_seconds=60,
                at=start,
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(acquire, range(12)))

        winners = [lease for lease in results if lease is not None]
        self.assertEqual(len(winners), 1)


if __name__ == "__main__":
    unittest.main()
