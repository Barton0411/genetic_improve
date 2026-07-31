from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PackagingReleaseSafetyTests(unittest.TestCase):
    def test_main_window_defers_annotation_evaluation_for_python_39(self):
        source = (PROJECT_ROOT / "gui" / "main_window.py").read_text(
            encoding="utf-8"
        )

        self.assertTrue(
            source.startswith("from __future__ import annotations\n"),
            "gui.main_window uses PEP 604 annotations and must remain "
            "importable by the Python 3.9 Windows build",
        )

    def test_macos_bundle_metadata_uses_application_version(self):
        spec = (PROJECT_ROOT / "GeneticImprove.spec").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "from version import VERSION as APP_VERSION",
            spec,
        )
        self.assertIn("version=APP_VERSION", spec)
        self.assertIn("'CFBundleVersion': APP_VERSION", spec)
        self.assertIn(
            "'CFBundleShortVersionString': APP_VERSION",
            spec,
        )

    def test_release_tree_has_no_embedded_offline_credentials(self):
        self.assertFalse(
            (PROJECT_ROOT / "auth" / "offline_auth.py").exists()
        )
        self.assertFalse(
            (
                PROJECT_ROOT
                / "config"
                / "api_config_local.json"
            ).exists()
        )


if __name__ == "__main__":
    unittest.main()
