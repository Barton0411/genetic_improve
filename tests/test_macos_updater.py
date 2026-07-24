import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.update.macos_updater import launch_macos_update, resolve_target_app
from core.update.smart_updater import PathDetector
from core.update.version_manager import VersionManager


class MacOSPathDetectionTests(unittest.TestCase):
    def test_detects_chinese_named_app_bundle(self):
        executable = Path(
            "/Applications/伊利奶牛选配.app/Contents/MacOS/伊利奶牛选配"
        )
        detector = PathDetector()
        detector.platform = "darwin"

        with patch.object(sys, "frozen", True, create=True), patch.object(
            sys, "executable", str(executable)
        ):
            info = detector.get_current_app_info()

        self.assertEqual(
            Path(info["app_root"]),
            Path("/Applications/伊利奶牛选配.app"),
        )

    def test_resolve_target_prefers_detected_app_bundle(self):
        target = resolve_target_app(
            "/Users/test/Applications/伊利奶牛选配.app",
            "伊利奶牛选配.app",
        )
        self.assertEqual(
            target,
            Path("/Users/test/Applications/伊利奶牛选配.app"),
        )

    def test_resolve_target_uses_applications_when_running_from_dmg(self):
        target = resolve_target_app(
            "/Volumes/伊利奶牛选配/伊利奶牛选配.app",
            "伊利奶牛选配.app",
        )
        self.assertEqual(target, Path("/Applications/伊利奶牛选配.app"))

    def test_version_manager_exits_after_helper_is_ready(self):
        class FakeDialog:
            user_chose_exit = False
            should_exit_for_update = True

            def __init__(self, version_info, app_info):
                pass

            def exec(self):
                return 1

        with patch(
            "core.update.smart_updater.detect_current_installation",
            return_value={"platform": "darwin"},
        ), patch(
            "core.update.force_update_dialog_clean.ForceUpdateDialog",
            FakeDialog,
        ):
            manager = VersionManager()
            self.assertTrue(manager.handle_force_update({"version": "9.9.9"}))


@unittest.skipUnless(sys.platform == "darwin", "仅在 macOS 验证独立替换流程")
class MacOSUpdateHelperTests(unittest.TestCase):
    def test_helper_replaces_app_after_old_process_exits(self):
        with tempfile.TemporaryDirectory(prefix="yili updater ") as temp:
            root = Path(temp)
            source = root / "mounted image" / "伊利奶牛选配.app"
            target = root / "Applications" / "伊利奶牛选配.app"
            support = root / "Application Support" / "updater"

            source_exec = source / "Contents" / "MacOS" / "伊利奶牛选配"
            target_exec = target / "Contents" / "MacOS" / "伊利奶牛选配"
            source_exec.parent.mkdir(parents=True)
            target_exec.parent.mkdir(parents=True)
            source_exec.write_text("new-version", encoding="utf-8")
            target_exec.write_text("old-version", encoding="utf-8")

            process = launch_macos_update(
                source_app=str(source),
                target_app=str(target),
                main_pid=99999999,
                mount_point=str(source.parent),
                support_dir=str(support),
                relaunch=False,
            )
            self.assertEqual(process.wait(timeout=15), 0)

            self.assertEqual(target_exec.read_text(encoding="utf-8"), "new-version")
            self.assertFalse(
                Path(f"{target}.backup-99999999").exists()
            )
            self.assertFalse(
                Path(f"{target}.update-99999999").exists()
            )

    def test_rejects_non_app_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "not-an-app"
            source.mkdir()

            with self.assertRaises(ValueError):
                launch_macos_update(
                    source_app=str(source),
                    target_app=str(root / "Target.app"),
                    main_pid=os.getpid(),
                    mount_point=str(root),
                    support_dir=str(root / "support"),
                    relaunch=False,
                )
