from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import run_group_supplemental_acceptance as acceptance


class SupplementalAcceptanceRunnerTests(unittest.TestCase):
    def test_matching_skips_only_missing_index_bulls_and_reports_count(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            shadow = Path(temporary_dir)
            (shadow / "standardized_data").mkdir()
            (shadow / "analysis_results").mkdir()

            executor = mock.Mock()
            executor.execute.return_value = {
                "success": True,
                "skipped_bulls": ["redacted-a", "redacted-b"],
            }

            with (
                mock.patch.object(
                    acceptance,
                    "_load_inventory",
                    return_value=({("BULL", "常规"): 10}, 1),
                ),
                mock.patch.object(
                    acceptance,
                    "_xlsx_summary",
                    return_value={"max_rows": {"选配结果": 4}},
                ),
                mock.patch(
                    "core.matching.complete_mating_executor."
                    "CompleteMatingExecutor",
                    return_value=executor,
                ),
            ):
                rows, inventory_items, skipped_count = (
                    acceptance._run_matching(shadow)
                )

        self.assertEqual((rows, inventory_items, skipped_count), (3, 1, 2))
        self.assertTrue(
            executor.execute.call_args.kwargs["skip_missing_bulls"]
        )

    def test_existing_completed_result_is_reused_only_after_integrity_checks(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary_dir:
            group = Path(temporary_dir)
            child = group / "farm_projects" / "1001_测试牧场"
            (child / "group_store").mkdir(parents=True)
            artifact_specs = {}
            required_names = (
                *acceptance.SUPPLEMENTAL_FILENAMES,
                "processed_index_cow_index_scores.xlsx",
                "备选公牛_近交系数及隐性基因分析结果_20260730.xlsx",
                "已配公牛_近交系数及隐性基因分析结果_20260730.xlsx",
                "育种分析综合报告_20260730.xlsx",
            )
            for name in required_names:
                directory = (
                    child / "reports"
                    if name.startswith("育种分析综合报告_")
                    else child / "analysis_results"
                )
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / name
                path.write_bytes(f"artifact:{name}".encode("utf-8"))
                relative = path.relative_to(child).as_posix()
                artifact_specs[relative] = {
                    "relative_path": relative,
                    "size": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }

            manifest = {
                "schema_version": 1,
                "execution": {
                    "hmy_push": False,
                    "ppt_generated": False,
                    "sequential": True,
                },
                "counts": {
                    "cow_self_rows": 10,
                    "candidate_inbreeding_rows": 20,
                    "mated_inbreeding_rows": 30,
                    "matching_rows": 5,
                    "inventory_items": 2,
                    "matching_skipped_bulls": 1,
                },
                "artifacts": list(artifact_specs.values()),
            }
            manifest_path = (
                child
                / "group_store"
                / acceptance.SUPPLEMENTAL_MANIFEST_FILENAME
            )
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )
            task = {"task_id": "task-1", "farm_code": "1001"}

            with (
                mock.patch.object(
                    acceptance,
                    "_safe_child_path",
                    return_value=child,
                ),
                mock.patch(
                    "core.group_tasks.stage_policy.validate_child_stage",
                    return_value={"valid": True},
                ) as validate_stage,
            ):
                result = (
                    acceptance._validated_existing_supplemental_result(
                        group,
                        task,
                    )
                )
                self.assertIsNotNone(result)
                self.assertTrue(result["reused"])
                self.assertEqual(validate_stage.call_count, 3)

                first_path = child / next(iter(artifact_specs))
                first_path.write_bytes(b"tampered")
                self.assertIsNone(
                    acceptance._validated_existing_supplemental_result(
                        group,
                        task,
                    )
                )


if __name__ == "__main__":
    unittest.main()
