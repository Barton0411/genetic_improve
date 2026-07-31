from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.group_tasks.memory_guard import ResourcePressureError
from gui.auto_report_worker import AutoReportWorker


class AutoReportWorkerResourceCheckTests(unittest.TestCase):
    def test_data_phase_checks_resources_before_and_after_work(self):
        checks = []

        def check():
            checks.append(len(checks) + 1)
            if len(checks) == 2:
                raise ResourcePressureError("内存保护暂停")

        with tempfile.TemporaryDirectory() as temporary_dir:
            worker = AutoReportWorker(
                None,
                [{"code": "010", "name": "测试牧场"}],
                Path(temporary_dir),
                data_source="慧牧云",
                reliability_mode=True,
                group_batch_mode=True,
                resource_check=check,
            )
            with patch.object(
                worker,
                "_phase_download_and_standardize",
            ) as phase:
                with self.assertRaisesRegex(
                    ResourcePressureError,
                    "内存保护暂停",
                ):
                    worker.execute(
                        download=True,
                        analysis=False,
                        excel=False,
                        ppt=False,
                    )

        phase.assert_called_once_with()
        self.assertEqual(checks, [1, 2])


if __name__ == "__main__":
    unittest.main()
