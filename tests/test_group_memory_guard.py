from __future__ import annotations

import unittest

from core.group_tasks.memory_guard import (
    GIB,
    AdaptiveMemoryGuard,
    MemoryGuardConfig,
    MemorySnapshot,
    boundary_pause_message,
    runtime_pause_message,
)


def _snapshot(total_gib: float, available_gib: float) -> MemorySnapshot:
    return MemorySnapshot(
        total_bytes=int(total_gib * GIB),
        available_bytes=int(available_gib * GIB),
        source="test",
        captured_at=0,
    )


class AdaptiveMemoryGuardTests(unittest.TestCase):
    def test_high_memory_machine_runs_without_fixed_farm_limit(self):
        guard = AdaptiveMemoryGuard(
            provider=lambda: _snapshot(64, 40),
        )

        for _ in range(100):
            assessment = guard.assess_boundary()
            self.assertEqual(assessment.status, "ok")
            self.assertFalse(assessment.should_pause)

    def test_low_available_memory_pauses_at_safe_boundary(self):
        guard = AdaptiveMemoryGuard(
            provider=lambda: _snapshot(8, 0.75),
        )

        assessment = guard.assess_boundary()

        self.assertEqual(assessment.status, "boundary_low")
        self.assertTrue(assessment.should_pause)
        message = boundary_pause_message(assessment)
        self.assertIn("已完成牧场和已提交阶段均已保留", message)
        self.assertIn("重新点击继续处理", message)

    def test_runtime_requires_sustained_pressure_then_recovers(self):
        snapshots = iter(
            [
                _snapshot(16, 0.8),
                _snapshot(16, 4),
                _snapshot(16, 0.7),
                _snapshot(16, 0.6),
            ]
        )
        guard = AdaptiveMemoryGuard(
            provider=lambda: next(snapshots),
            config=MemoryGuardConfig(
                danger_floor_bytes=1 * GIB,
                danger_fraction=0,
                danger_cap_bytes=1 * GIB,
                sustained_danger_samples=2,
                runtime_check_interval_seconds=0,
            ),
        )

        self.assertEqual(guard.poll_runtime().status, "danger")
        self.assertEqual(guard.poll_runtime().status, "ok")
        self.assertEqual(guard.poll_runtime().status, "danger")
        assessment = guard.poll_runtime()
        self.assertEqual(assessment.status, "sustained_danger")
        self.assertTrue(assessment.should_pause)
        self.assertIn("当前阶段可重试", runtime_pause_message(assessment))

    def test_unavailable_monitor_never_blocks_business_task(self):
        def unavailable():
            raise OSError("monitor unavailable")

        guard = AdaptiveMemoryGuard(provider=unavailable)

        self.assertEqual(guard.assess_boundary().status, "unknown")
        self.assertEqual(
            guard.poll_runtime(force=True).status,
            "unknown",
        )


if __name__ == "__main__":
    unittest.main()
