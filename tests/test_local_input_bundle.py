from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from core.data.composite_farm_manager import (
    LOCAL_INPUT_BUNDLE_RELATIVE_PATH,
    LOCAL_STAGING_PREFIX,
    cleanup_local_farm,
    materialize_single_local_project,
    persist_local_input_bundle,
    stage_local_farm,
    validate_local_data_commit,
    validate_local_input_bundle,
)


def _write_staging(staging: Path, *, with_breeding: bool = True) -> None:
    (staging / "input_sources").mkdir(parents=True)
    (staging / "raw_data").mkdir(parents=True)
    (staging / "standardized_data").mkdir(parents=True)

    cow_frame = pd.DataFrame(
        {
            "cow_id": ["0001", "0002"],
            "dam": ["D001", "D002"],
            "sire": ["S001", "S002"],
        }
    )
    cow_original = staging / "input_sources" / "cow_original.xlsx"
    cow_frame.to_excel(cow_original, index=False)
    shutil.copy2(cow_original, staging / "raw_data" / "cow_data.xlsx")
    cow_frame.to_excel(
        staging / "standardized_data" / "processed_cow_data.xlsx",
        index=False,
    )

    if with_breeding:
        breeding_frame = pd.DataFrame(
            {
                "耳号": ["0001"],
                "父号": ["S003"],
                "冻精编号": ["BULL-1"],
                "配种日期": ["2026-07-01"],
                "冻精类型": ["普通冻精"],
            }
        )
        breeding_original = (
            staging / "input_sources" / "breeding_original.xlsx"
        )
        breeding_frame.to_excel(breeding_original, index=False)
        shutil.copy2(
            breeding_original,
            staging / "raw_data" / "breeding_records.xlsx",
        )
        breeding_frame.to_excel(
            staging
            / "standardized_data"
            / "processed_breeding_data.xlsx",
            index=False,
        )


class LocalInputBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_dir.name)
        self.managed_staging = Path(
            tempfile.mkdtemp(prefix=LOCAL_STAGING_PREFIX)
        )

    def tearDown(self):
        shutil.rmtree(self.managed_staging, ignore_errors=True)
        self.temporary_dir.cleanup()

    def _farm(self, *, with_breeding: bool = True) -> dict:
        return {
            "task_id": str(uuid.uuid4()),
            "farmCode": "LOCAL001",
            "name": "本地一场",
            "source_kind": "local",
            "source_system": "伊起牛",
            "cow_count": 2,
            "breeding_count": 1 if with_breeding else 0,
            "has_breeding_records": with_breeding,
            "staging_path": str(self.managed_staging),
            "cow_source_name": "母牛原表.xlsx",
            "breeding_source_name": (
                "配种原表.xlsx" if with_breeding else ""
            ),
        }

    def test_bundle_is_atomic_hashed_and_detects_corruption(self):
        _write_staging(self.managed_staging, with_breeding=True)
        child = self.root / "child"
        farm = self._farm(with_breeding=True)

        created = persist_local_input_bundle(child, farm)
        bundle = child / LOCAL_INPUT_BUNDLE_RELATIVE_PATH

        self.assertTrue((bundle / "manifest.json").is_file())
        self.assertTrue((bundle / "manifest.sha256").is_file())
        self.assertTrue(created["original_source_preserved"])
        self.assertTrue(created["has_breeding_records"])
        self.assertEqual(created["farm_code"], "LOCAL001")
        self.assertEqual(created["task_id"], farm["task_id"])
        self.assertEqual(
            created["manifest_sha256"],
            validate_local_input_bundle(
                child,
                expected_task_id=farm["task_id"],
                expected_farm_code="LOCAL001",
            )["manifest_sha256"],
        )

        reused = persist_local_input_bundle(child, farm)
        self.assertEqual(
            reused["manifest_sha256"], created["manifest_sha256"]
        )

        breeding = bundle / "raw_data" / "breeding_records.xlsx"
        with breeding.open("ab") as output:
            output.write(b"corrupt")
        with self.assertRaisesRegex(ValueError, "摘要不一致|大小不一致"):
            validate_local_input_bundle(child)

    def test_materialize_prefers_bundle_and_writes_verified_commit(self):
        _write_staging(self.managed_staging, with_breeding=True)
        child = self.root / "child"
        farm = self._farm(with_breeding=True)
        manifest = persist_local_input_bundle(child, farm)

        self.assertTrue(cleanup_local_farm(farm))
        self.assertFalse(self.managed_staging.exists())
        result = materialize_single_local_project(
            child,
            farm,
            data_source="伊起牛",
        )

        self.assertTrue(result["has_breeding_records"])
        self.assertEqual(result["breeding_count"], 1)
        commit = validate_local_data_commit(
            child,
            expected_input_manifest_sha256=manifest["manifest_sha256"],
            expected_farm_code="LOCAL001",
        )
        self.assertEqual(commit["task_id"], farm["task_id"])
        self.assertEqual(commit["cow_count"], 2)
        self.assertEqual(commit["breeding_count"], 1)

        metadata = json.loads(
            (child / "project_metadata.json").read_text(encoding="utf-8")
        )
        self.assertEqual(metadata["group_task_id"], farm["task_id"])
        self.assertEqual(
            metadata["local_input_bundle"]["manifest_sha256"],
            manifest["manifest_sha256"],
        )

        output = (
            child
            / "standardized_data"
            / "processed_breeding_data.xlsx"
        )
        with output.open("ab") as stream:
            stream.write(b"corrupt")
        with self.assertRaisesRegex(ValueError, "摘要不一致|大小不一致"):
            validate_local_data_commit(child)

    def test_failed_atomic_publish_keeps_staging_and_no_final_bundle(self):
        _write_staging(self.managed_staging, with_breeding=False)
        child = self.root / "child"
        farm = self._farm(with_breeding=False)
        final_bundle = child / LOCAL_INPUT_BUNDLE_RELATIVE_PATH
        real_replace = os.replace

        def fail_final_publish(source, target):
            if Path(target) == final_bundle:
                raise OSError("模拟提交中断")
            return real_replace(source, target)

        with patch(
            "core.data.composite_farm_manager.os.replace",
            side_effect=fail_final_publish,
        ):
            with self.assertRaisesRegex(OSError, "模拟提交中断"):
                persist_local_input_bundle(child, farm)

        self.assertTrue(self.managed_staging.is_dir())
        self.assertFalse(final_bundle.exists())
        leftovers = list(
            (child / "raw_data").glob(".input_bundle.*")
        )
        self.assertEqual(leftovers, [])

    def test_no_breeding_bundle_does_not_retain_stale_breeding_output(self):
        _write_staging(self.managed_staging, with_breeding=False)
        child = self.root / "child"
        stale = (
            child
            / "standardized_data"
            / "processed_breeding_data.xlsx"
        )
        stale.parent.mkdir(parents=True)
        pd.DataFrame({"耳号": ["stale"]}).to_excel(stale, index=False)
        farm = self._farm(with_breeding=False)
        manifest = persist_local_input_bundle(child, farm)
        cleanup_local_farm(farm)

        result = materialize_single_local_project(
            child, farm, data_source="伊起牛"
        )
        commit = validate_local_data_commit(
            child,
            expected_input_manifest_sha256=manifest["manifest_sha256"],
            expected_task_id=farm["task_id"],
        )
        self.assertFalse(result["has_breeding_records"])
        self.assertFalse(commit["has_breeding_records"])
        self.assertFalse(stale.exists())

    def test_stage_keeps_exact_originals_and_cleanup_rejects_other_paths(self):
        cow_source = self.root / "cow.csv"
        cow_bytes = b"cow_id,farm_code,dam,sire\n0001,LOCAL002,D001,S001\n"
        cow_source.write_bytes(cow_bytes)
        breeding_source = self.root / "breeding.xlsx"
        breeding_frame = pd.DataFrame(
            {
                "耳号": ["0001"],
                "父号": ["S002"],
                "冻精编号": ["BULL-2"],
                "配种日期": ["2026-07-01"],
                "冻精类型": ["普通冻精"],
            }
        )
        breeding_frame.to_excel(breeding_source, index=False)
        breeding_bytes = breeding_source.read_bytes()

        def fake_cow_upload(input_files, project_path, **_kwargs):
            raw = project_path / "raw_data" / "cow_data.xlsx"
            raw.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_files[0], raw)
            frame = pd.read_excel(input_files[0], dtype={"cow_id": str})
            output = (
                project_path
                / "standardized_data"
                / "processed_cow_data.xlsx"
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            frame.to_excel(output, index=False)
            return output

        def fake_breeding_upload(input_files, project_path, **_kwargs):
            raw = project_path / "raw_data" / "breeding_records.xlsx"
            shutil.copy2(input_files[0], raw)
            frame = pd.read_excel(input_files[0], dtype={"耳号": str})
            output = (
                project_path
                / "standardized_data"
                / "processed_breeding_data.xlsx"
            )
            frame.to_excel(output, index=False)
            return output

        with (
            patch(
                "core.data.composite_farm_manager."
                "upload_and_standardize_cow_data",
                side_effect=fake_cow_upload,
            ),
            patch(
                "core.data.composite_farm_manager."
                "upload_and_standardize_breeding_data",
                side_effect=fake_breeding_upload,
            ),
        ):
            farm = stage_local_farm(
                cow_source,
                breeding_source,
                "伊起牛",
                "LOCAL002",
                "本地二场",
            )

        staging = Path(farm["staging_path"])
        try:
            self.assertEqual(
                (staging / "input_sources" / "cow_original.csv").read_bytes(),
                cow_bytes,
            )
            self.assertEqual(
                (
                    staging
                    / "input_sources"
                    / "breeding_original.xlsx"
                ).read_bytes(),
                breeding_bytes,
            )
        finally:
            cleanup_local_farm(farm)

        unmanaged = self.root / f"{LOCAL_STAGING_PREFIX}not-managed"
        unmanaged.mkdir()
        self.assertFalse(
            cleanup_local_farm({"staging_path": str(unmanaged)})
        )
        self.assertTrue(unmanaged.exists())


if __name__ == "__main__":
    unittest.main()
