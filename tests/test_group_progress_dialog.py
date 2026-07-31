from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QCoreApplication  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from gui.progress import ProgressDialog  # noqa: E402


class GroupProgressDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        existing = QCoreApplication.instance()
        if existing is not None and not isinstance(existing, QApplication):
            raise RuntimeError(
                "界面测试不能复用 QCoreApplication；"
                "请统一使用 QApplication。"
            )
        cls.app = existing or QApplication([])

    def test_finished_farm_always_exposes_open_child_action(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            for success in (True, False):
                with self.subTest(success=success):
                    child_path = root / (
                        "successful-child" if success else "failed-child"
                    )
                    child_path.mkdir()
                    task_id = "success-task" if success else "failed-task"
                    dialog = ProgressDialog()
                    self.addCleanup(dialog.close)
                    dialog.show_sub_tasks(
                        [
                            {
                                "id": task_id,
                                "name": child_path.name,
                                "path": str(child_path),
                            }
                        ]
                    )

                    open_button = dialog._sub_task_widgets[task_id]["open"]
                    self.assertIsNotNone(open_button)
                    self.assertTrue(open_button.isHidden())

                    dialog.complete_sub_task(task_id, success)

                    expected_status = "已完成" if success else "失败"
                    self.assertIn(
                        expected_status,
                        dialog._sub_task_widgets[task_id]["name"].text(),
                    )
                    self.assertFalse(
                        open_button.isHidden(),
                        "牧场任务无论成功或失败，结束后都应允许打开子项目",
                    )
                    with patch(
                        "gui.progress.QDesktopServices.openUrl",
                        return_value=True,
                    ) as open_url:
                        open_button.click()

                    open_url.assert_called_once()
                    opened_url = open_url.call_args.args[0]
                    self.assertEqual(
                        Path(opened_url.toLocalFile()),
                        child_path,
                    )


if __name__ == "__main__":
    unittest.main()
