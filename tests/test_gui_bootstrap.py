from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class GuiBootstrapTests(unittest.TestCase):
    def _run_python(self, source: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["QT_QPA_PLATFORM"] = "offscreen"
        return subprocess.run(
            [sys.executable, "-c", source],
            cwd=PROJECT_ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )

    def test_rejects_existing_qcore_application_without_aborting(self):
        result = self._run_python(
            "\n".join(
                [
                    "from PyQt6.QtCore import QCoreApplication",
                    "from main import _create_gui_application",
                    "core = QCoreApplication([])",
                    "try:",
                    "    _create_gui_application(['bootstrap-test'])",
                    "except RuntimeError as exc:",
                    "    print(str(exc))",
                    "else:",
                    "    raise SystemExit(9)",
                ]
            )
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("不能继续启动图形界面", result.stdout)

    def test_reuses_existing_qapplication(self):
        result = self._run_python(
            "\n".join(
                [
                    "from PyQt6.QtWidgets import QApplication",
                    "from main import _create_gui_application",
                    "app = QApplication([])",
                    "same = _create_gui_application(['bootstrap-test'])",
                    "raise SystemExit(0 if same is app else 8)",
                ]
            )
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_direct_codex_gui_launch_is_blocked_before_qapplication(self):
        from main import _macos_gui_launch_block_reason

        with (
            patch("main.sys.platform", "darwin"),
            patch.dict(os.environ, {"QT_QPA_PLATFORM": ""}),
        ):
            reason = _macos_gui_launch_block_reason(parent_name="codex")

        self.assertIn("启动开发版.command", reason)


if __name__ == "__main__":
    unittest.main()
