from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.stress_group_detail_export import (
    ResourceMonitor,
    _evaluate_resource_limits,
    run_resume_acceptance,
    run_stress,
)


class StressGroupDetailExportTests(unittest.TestCase):
    def test_small_run_verifies_every_identity_order_and_volume_boundary(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            result = run_stress(
                Path(temporary_dir),
                farms=2,
                rows_per_farm=4,
                rows_per_volume=3,
            )

        self.assertTrue(result["zero_detail_rows_lost"])
        self.assertEqual(
            result["ranked"]["identity_and_order_verified_rows"],
            8,
        )
        self.assertEqual(
            result["reconciliation"]["identity_and_order_verified_rows"],
            8,
        )
        self.assertTrue(result["ranked"]["volume_boundaries_verified"])
        self.assertTrue(
            result["reconciliation"]["volume_boundaries_verified"]
        )
        self.assertEqual(result["ranked"]["volumes"], 3)

    def test_small_interruption_resumes_without_rewriting_first_volume(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            result = run_resume_acceptance(
                Path(temporary_dir),
                farms=2,
                rows_per_farm=3,
                rows_per_volume=2,
            )

        self.assertTrue(result["passed"])
        self.assertEqual(result["sources_reused"], 2)
        self.assertTrue(result["first_committed_volume_reused"])
        self.assertTrue(result["resume_directory_removed_after_publish"])
        self.assertTrue(result["verification"]["zero_detail_rows_lost"])

    def test_resource_monitor_records_disk_and_enforces_thresholds(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            monitor = ResourceMonitor(root, interval_seconds=0.01).start()
            (root / "allocated.bin").write_bytes(b"x" * 8192)
            monitor.sample()
            metrics = monitor.stop()

        self.assertGreater(metrics["peak_rss_bytes"], 0)
        self.assertGreaterEqual(metrics["workspace_peak_logical_bytes"], 8192)
        self.assertGreater(metrics["workspace_peak_allocated_bytes"], 0)
        self.assertGreaterEqual(metrics["samples"], 3)

        passed = _evaluate_resource_limits(
            metrics,
            max_peak_rss_mib=metrics["peak_rss_mib"] + 1,
            max_workspace_peak_gib=1,
        )
        self.assertTrue(passed["passed"])
        failed = _evaluate_resource_limits(
            metrics,
            max_peak_rss_mib=0.000001,
            max_workspace_peak_gib=1,
        )
        self.assertFalse(failed["peak_rss_within_limit"])
        self.assertFalse(failed["passed"])


if __name__ == "__main__":
    unittest.main()
