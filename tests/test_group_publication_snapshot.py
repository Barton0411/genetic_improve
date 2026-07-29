from __future__ import annotations

import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from core.group_tasks import stage_manifest as stage_manifest_module
from core.group_report.publication_snapshot import (
    PublicationInputsChangedError,
    PublicationSnapshotError,
    capture_group_publication_snapshot,
    compare_group_publication_snapshots,
    recompute_and_compare_group_publication_snapshot,
)
from core.group_tasks.stage_manifest import commit_stage_manifest
from utils.group_task_store import GroupTaskStore


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


class GroupPublicationSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary_dir.name) / "group"
        self.project.mkdir()
        self.store = GroupTaskStore(
            self.project / "group_store" / "group_tasks.sqlite3"
        )

    def tearDown(self):
        self.temporary_dir.cleanup()

    def _add_completed_task(
        self,
        farm_code: str,
        *,
        included: bool = True,
        secret: str = "",
    ) -> tuple[str, Path]:
        task_id = str(uuid.uuid4())
        relative = f"farm_projects/{farm_code}_farm"
        child = self.project / relative
        child.mkdir(parents=True)
        self.store.initialize_tasks(
            [
                {
                    "task_id": task_id,
                    "farm_code": farm_code,
                    "farm_name": f"{farm_code}场",
                    "relative_path": relative,
                    "included_in_summary": included,
                    "metadata": {
                        "token": secret,
                        "password": secret,
                    },
                }
            ]
        )

        cows = child / "standardized_data" / "cows.txt"
        analysis = child / "analysis_results" / "result.txt"
        report = child / "reports" / "report.txt"
        _write_text(cows, f"{farm_code}:cows:v1")
        _write_text(analysis, f"{farm_code}:analysis:v1")
        _write_text(report, f"{farm_code}:report:v1")

        manifests = {
            "data": (
                child
                / "standardized_data"
                / ".manifests"
                / "data.json"
            ),
            "analysis": (
                child
                / "analysis_results"
                / ".manifests"
                / "analysis.json"
            ),
            "child_excel": (
                child
                / "reports"
                / ".manifests"
                / "child_excel.json"
            ),
        }
        commit_stage_manifest(
            child,
            manifests["data"],
            task_id=task_id,
            farm_code=farm_code,
            stage="data",
            config={"version": 1},
            inputs=[],
            outputs={"cows": cows},
        )
        commit_stage_manifest(
            child,
            manifests["analysis"],
            task_id=task_id,
            farm_code=farm_code,
            stage="analysis",
            config={"version": 1},
            inputs={"cows": cows},
            outputs={"analysis": analysis},
        )
        commit_stage_manifest(
            child,
            manifests["child_excel"],
            task_id=task_id,
            farm_code=farm_code,
            stage="child_excel",
            config={"version": 1},
            inputs={"analysis": analysis},
            outputs={"report": report},
        )
        for stage in ("data", "analysis", "child_excel"):
            self.store.update_stage(task_id, stage, status="running")
            self.store.update_stage(task_id, stage, status="completed")
        return task_id, child

    def _recommit_analysis_chain(
        self,
        task_id: str,
        farm_code: str,
        child: Path,
        *,
        suffix: str,
    ) -> None:
        cows = child / "standardized_data" / "cows.txt"
        analysis = child / "analysis_results" / "result.txt"
        report = child / "reports" / "report.txt"
        _write_text(analysis, f"{farm_code}:analysis:{suffix}")
        _write_text(report, f"{farm_code}:report:{suffix}")
        commit_stage_manifest(
            child,
            child
            / "analysis_results"
            / ".manifests"
            / "analysis.json",
            task_id=task_id,
            farm_code=farm_code,
            stage="analysis",
            config={"version": 1},
            inputs={"cows": cows},
            outputs={"analysis": analysis},
        )
        commit_stage_manifest(
            child,
            child / "reports" / ".manifests" / "child_excel.json",
            task_id=task_id,
            farm_code=farm_code,
            stage="child_excel",
            config={"version": 1},
            inputs={"analysis": analysis},
            outputs={"report": report},
        )
        for stage in ("analysis", "child_excel"):
            self.store.update_stage(task_id, stage, status="running")
            self.store.update_stage(task_id, stage, status="completed")

    def test_stable_snapshot_is_atomic_and_omits_task_metadata_secrets(self):
        included_id, _ = self._add_completed_task(
            "001",
            secret="DO-NOT-LEAK-SECRET",
        )
        excluded_id, _ = self._add_completed_task("002", included=False)
        output = (
            self.project
            / "group_store"
            / "publication_snapshots"
            / "before.json"
        )

        before = capture_group_publication_snapshot(
            self.project,
            output_path=output,
        )
        after = capture_group_publication_snapshot(self.project)
        comparison = compare_group_publication_snapshots(before, after)

        self.assertTrue(comparison["unchanged"])
        self.assertEqual(
            before["basis"]["selection_scope"]["included_task_ids"],
            [included_id],
        )
        self.assertEqual(
            before["basis"]["selection_scope"]["excluded_task_ids"],
            [excluded_id],
        )
        self.assertEqual(len(before["basis"]["tasks"][0]["stages"]), 3)
        for stage in before["basis"]["tasks"][0]["stages"]:
            self.assertEqual(len(stage["manifest_sha256"]), 64)
            self.assertEqual(stage["attempt"], 1)
            self.assertEqual(len(stage["artifact_state_sha256"]), 64)
            self.assertTrue(stage["artifact_states"])
            for artifact in stage["artifact_states"]:
                self.assertGreaterEqual(artifact["size_bytes"], 0)
                self.assertGreaterEqual(artifact["mtime_ns"], 0)
        serialized = output.read_text(encoding="utf-8")
        self.assertNotIn("DO-NOT-LEAK-SECRET", serialized)
        self.assertNotIn(str(self.project), serialized)
        self.assertFalse(
            list(output.parent.glob(f".{output.name}.*.tmp"))
        )

    def test_selection_revision_and_scope_change_block_publication(self):
        self._add_completed_task("010")
        second_id, _ = self._add_completed_task("020")
        before = capture_group_publication_snapshot(self.project)
        self.store.set_included_in_summary(second_id, False)

        result = recompute_and_compare_group_publication_snapshot(
            self.project,
            before,
            raise_on_change=False,
        )
        comparison = result["comparison"]
        self.assertFalse(comparison["unchanged"])
        codes = {change["code"] for change in comparison["changes"]}
        self.assertIn("selection_revision_changed", codes)
        self.assertIn("selection_scope_changed", codes)
        with self.assertRaises(PublicationInputsChangedError):
            recompute_and_compare_group_publication_snapshot(
                self.project,
                before,
            )

    def test_stage_attempt_and_manifest_change_block_publication(self):
        task_id, child = self._add_completed_task("030")
        before = capture_group_publication_snapshot(self.project)
        self._recommit_analysis_chain(
            task_id,
            "030",
            child,
            suffix="v2",
        )

        result = recompute_and_compare_group_publication_snapshot(
            self.project,
            before,
            raise_on_change=False,
        )
        comparison = result["comparison"]
        self.assertFalse(comparison["unchanged"])
        changes = comparison["changes"]
        self.assertIn(
            "stage_manifest_changed",
            {change["code"] for change in changes},
        )
        self.assertTrue(
            any(
                change.get("task_id") == task_id
                and change.get("stage") in {"analysis", "child_excel"}
                for change in changes
            )
        )

    def test_artifact_change_without_new_manifest_rejects_and_preserves_json(self):
        _, child = self._add_completed_task("040")
        output = self.project / "group_store" / "snapshot.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('{"old": true}', encoding="utf-8")
        _write_text(
            child / "analysis_results" / "result.txt",
            "changed-without-manifest",
        )

        with self.assertRaisesRegex(
            PublicationSnapshotError,
            "manifest 校验失败",
        ):
            capture_group_publication_snapshot(
                self.project,
                output_path=output,
            )
        self.assertEqual(
            json.loads(output.read_text(encoding="utf-8")),
            {"old": True},
        )
        self.assertFalse(
            list(output.parent.glob(f".{output.name}.*.tmp"))
        )

    def test_recompute_uses_stat_and_detects_mtime_change(self):
        _, child = self._add_completed_task("041")
        before = capture_group_publication_snapshot(self.project)
        artifact = child / "analysis_results" / "result.txt"
        state = artifact.stat()
        os.utime(
            artifact,
            ns=(state.st_atime_ns, state.st_mtime_ns + 1),
        )

        with patch(
            "core.group_tasks.stage_manifest.stream_sha256",
            side_effect=AssertionError(
                "发布后 stat 复核不应读取产物内容"
            ),
        ):
            with self.assertRaisesRegex(
                PublicationSnapshotError,
                "manifest 校验失败",
            ):
                recompute_and_compare_group_publication_snapshot(
                    self.project,
                    before,
                )

    def test_recompute_uses_stat_and_detects_size_change(self):
        _, child = self._add_completed_task("042")
        before = capture_group_publication_snapshot(self.project)
        artifact = child / "analysis_results" / "result.txt"
        artifact.write_text(
            artifact.read_text(encoding="utf-8") + "-expanded",
            encoding="utf-8",
        )

        with patch(
            "core.group_tasks.stage_manifest.stream_sha256",
            side_effect=AssertionError(
                "发布后 stat 复核不应读取产物内容"
            ),
        ):
            with self.assertRaisesRegex(
                PublicationSnapshotError,
                "manifest 校验失败",
            ):
                recompute_and_compare_group_publication_snapshot(
                    self.project,
                    before,
                )

    def test_recompute_legacy_manifest_without_mtime_falls_back_to_full(self):
        _, child = self._add_completed_task("043")
        manifest_paths = (
            child
            / "standardized_data"
            / ".manifests"
            / "data.json",
            child
            / "analysis_results"
            / ".manifests"
            / "analysis.json",
            child / "reports" / ".manifests" / "child_excel.json",
        )
        for manifest_path in manifest_paths:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for artifact in manifest["inputs"] + manifest["outputs"]:
                artifact.pop("mtime_ns")
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )
        before = capture_group_publication_snapshot(self.project)

        with patch(
            "core.group_tasks.stage_manifest.stream_sha256",
            wraps=stage_manifest_module.stream_sha256,
        ) as hash_file:
            result = recompute_and_compare_group_publication_snapshot(
                self.project,
                before,
            )
        self.assertTrue(result["comparison"]["unchanged"])
        self.assertGreater(hash_file.call_count, 0)

    def test_legacy_manifest_artifact_state_digest_detects_mtime_change(self):
        _, child = self._add_completed_task("044")
        manifest_paths = (
            child
            / "standardized_data"
            / ".manifests"
            / "data.json",
            child
            / "analysis_results"
            / ".manifests"
            / "analysis.json",
            child / "reports" / ".manifests" / "child_excel.json",
        )
        for manifest_path in manifest_paths:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for artifact in manifest["inputs"] + manifest["outputs"]:
                artifact.pop("mtime_ns")
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )
        before = capture_group_publication_snapshot(self.project)
        artifact = child / "analysis_results" / "result.txt"
        state = artifact.stat()
        os.utime(
            artifact,
            ns=(state.st_atime_ns, state.st_mtime_ns + 1),
        )

        result = recompute_and_compare_group_publication_snapshot(
            self.project,
            before,
            raise_on_change=False,
        )
        self.assertFalse(result["comparison"]["unchanged"])
        self.assertIn(
            "stage_artifact_state_changed",
            {
                change["code"]
                for change in result["comparison"]["changes"]
            },
        )

    def test_tampered_snapshot_basis_is_rejected(self):
        self._add_completed_task("050")
        snapshot = capture_group_publication_snapshot(self.project)
        tampered = json.loads(json.dumps(snapshot, ensure_ascii=False))
        tampered["basis"]["selection_revision"] += 1
        with self.assertRaisesRegex(
            PublicationSnapshotError,
            "basis 摘要校验失败",
        ):
            compare_group_publication_snapshots(snapshot, tampered)

    def test_task_change_during_capture_is_rejected(self):
        task_id, _ = self._add_completed_task("060")
        changed = False

        def changing_resolver(task, stage, child):
            nonlocal changed
            if not changed:
                changed = True
                self.store.update_stage(
                    task_id,
                    "analysis",
                    status="running",
                )
            defaults = {
                "data": (
                    child
                    / "standardized_data"
                    / ".manifests"
                    / "data.json"
                ),
                "analysis": (
                    child
                    / "analysis_results"
                    / ".manifests"
                    / "analysis.json"
                ),
                "child_excel": (
                    child
                    / "reports"
                    / ".manifests"
                    / "child_excel.json"
                ),
            }
            return defaults[stage]

        with self.assertRaisesRegex(
            PublicationSnapshotError,
            "任务状态或选择范围发生变化",
        ):
            capture_group_publication_snapshot(
                self.project,
                manifest_resolver=changing_resolver,
            )


if __name__ == "__main__":
    unittest.main()
