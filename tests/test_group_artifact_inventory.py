"""牧场组全部结果文件清单测试。"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import uuid
from pathlib import Path

import xlsxwriter

from core.group_report.artifact_inventory import (
    GroupArtifactInventory,
    build_group_artifact_inventory,
    inspect_xlsx_structure,
)
from core.group_tasks.stage_manifest import commit_stage_manifest
from utils.group_task_store import GroupTaskStore


def _write_workbook(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(path))
    first = workbook.add_worksheet("明细")
    first.write(0, 0, "牛号")
    first.write(3, 2, "C4")
    second = workbook.add_worksheet("空表")
    second.hide()
    workbook.close()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _commit_stage(
    child: Path,
    *,
    task_id: str,
    farm_code: str,
    stage: str,
    outputs: list[Path],
) -> None:
    commit_stage_manifest(
        child,
        child / "group_store" / "stage_manifests" / f"{stage}.json",
        task_id=task_id,
        farm_code=farm_code,
        stage=stage,
        config={"test": stage},
        inputs=[],
        outputs=outputs,
    )


def _required_stages(*stages: str) -> dict:
    return {
        stage: {"required": stage in stages}
        for stage in ("data", "analysis", "child_excel")
    }


class GroupArtifactInventoryTests(unittest.TestCase):
    def test_committed_outputs_are_managed_and_unmanaged_files_are_indexed(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            project = Path(temporary_dir) / "group"
            child_a = project / "farm_projects" / "001_A场"
            child_b = project / "farm_projects" / "002_B场"
            data_path = (
                child_a / "standardized_data" / "processed_cow_data.xlsx"
            )
            analysis_path = (
                child_a
                / "analysis_results"
                / "nested"
                / "关键育种性状分析结果.XLSX"
            )
            report_path = (
                child_a / "reports" / "育种分析综合报告_001.xlsx"
            )
            for path in (data_path, analysis_path, report_path):
                _write_workbook(path)
            _commit_stage(
                child_a,
                task_id="task-a",
                farm_code="001",
                stage="data",
                outputs=[data_path],
            )
            _commit_stage(
                child_a,
                task_id="task-a",
                farm_code="001",
                stage="analysis",
                outputs=[analysis_path],
            )
            _commit_stage(
                child_a,
                task_id="task-a",
                farm_code="001",
                stage="child_excel",
                outputs=[report_path],
            )
            unmanaged_path = child_a / "reports" / "历史损坏结果.xlsx"
            unmanaged_path.write_bytes(b"not-a-zip")
            (child_a / "reports" / ".隐藏.xlsx").write_bytes(b"hidden")
            (child_a / "reports" / "进行中.partial.xlsx").write_bytes(
                b"partial"
            )
            _write_workbook(
                child_b / "reports" / "不应纳入清单.xlsx"
            )
            (child_a / "reports" / "readme.txt").write_text(
                "not xlsx",
                encoding="utf-8",
            )
            (child_a / "reports" / "~$临时.xlsx").write_bytes(b"lock")

            tasks = [
                {
                    "task_id": "task-a",
                    "farm_code": "001",
                    "farm_name": "A场",
                    "relative_path": "farm_projects/001_A场",
                    "included_in_summary": True,
                    "stages": _required_stages(
                        "data",
                        "analysis",
                        "child_excel",
                    ),
                },
                {
                    "task_id": "task-b",
                    "farm_code": "002",
                    "farm_name": "B场",
                    "relative_path": "farm_projects/002_B场",
                    "included_in_summary": False,
                },
            ]
            manifest_path = project / "reports" / "inventory.json"
            result = build_group_artifact_inventory(
                project,
                tasks=tasks,
                manifest_path=manifest_path,
            )

            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["counts"]["included_tasks"], 1)
            self.assertEqual(result["counts"]["total_files"], 3)
            self.assertEqual(result["counts"]["valid_files"], 3)
            self.assertEqual(result["counts"]["invalid_files"], 0)
            self.assertEqual(result["counts"]["unmanaged_files"], 1)
            self.assertEqual(result["counts"]["index_files"], 4)
            self.assertEqual(
                result["counts"]["by_category"]["standardized_data"]["files"],
                1,
            )
            self.assertEqual(
                result["counts"]["by_category"]["analysis_results"]["files"],
                1,
            )
            self.assertEqual(
                result["counts"]["by_category"]["reports"]["files"],
                1,
            )
            self.assertEqual(
                {entry["task_id"] for entry in result["files"]},
                {"task-a"},
            )
            self.assertTrue(all(entry["managed"] for entry in result["files"]))
            self.assertEqual(
                [entry["file_name"] for entry in result["unmanaged_files"]],
                ["历史损坏结果.xlsx"],
            )
            self.assertIsNone(
                result["unmanaged_files"][0]["xlsx_valid"]
            )
            self.assertFalse(result["unmanaged_files"][0]["managed"])
            self.assertEqual(result["unmanaged_files"][0]["sha256"], "")
            first = result["files"][0]
            self.assertEqual(first["farm_code"], "001")
            self.assertTrue(first["relative_path"].startswith("farm_projects/"))
            self.assertGreater(first["bytes"], 0)
            self.assertEqual(
                first["sha256"],
                _sha256(project / first["relative_path"]),
            )
            self.assertTrue(first["xlsx_valid"])
            self.assertEqual(first["sheet_count"], 2)
            self.assertEqual(first["sheet_dimensions"], "明细:4×3；空表:1×1")
            self.assertEqual(
                [
                    (sheet["name"], sheet["max_row"], sheet["max_column"])
                    for sheet in first["sheets"]
                ],
                [("明细", 4, 3), ("空表", 1, 1)],
            )
            self.assertEqual(first["sheets"][1]["state"], "hidden")

            self.assertTrue(manifest_path.is_file())
            self.assertEqual(result["manifest_sha256"], _sha256(manifest_path))
            on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertNotIn("manifest_path", on_disk)
            self.assertEqual(on_disk["files"], result["files"])
            self.assertEqual(
                [column["label"] for column in on_disk["index_columns"]],
                [
                    "任务ID",
                    "牧场编号",
                    "牧场名称",
                    "类别",
                    "受管产物",
                    "阶段",
                    "逻辑名称",
                    "相对路径",
                    "字节数",
                    "SHA256",
                    "XLSX结构有效",
                    "校验错误",
                    "Sheet数",
                    "Sheet行列范围",
                ],
            )

    def test_tampered_managed_xlsx_marks_partial_but_unmanaged_does_not(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            project = Path(temporary_dir) / "group"
            child = project / "farm_projects" / "003_C场"
            good_path = child / "analysis_results" / "good.xlsx"
            _write_workbook(good_path)
            _commit_stage(
                child,
                task_id="task-c",
                farm_code="003",
                stage="analysis",
                outputs=[good_path],
            )
            good_path.write_bytes(b"tampered")
            bad_path = child / "reports" / "bad.xlsx"
            bad_path.parent.mkdir(parents=True)
            bad_path.write_bytes(b"not-a-zip")
            tasks = [
                {
                    "task_id": "task-c",
                    "farm_code": "003",
                    "farm_name": "C场",
                    "relative_path": "farm_projects/003_C场",
                    "stages": _required_stages("analysis"),
                }
            ]

            result = GroupArtifactInventory(project).build(tasks=tasks)

            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["counts"]["total_files"], 1)
            self.assertEqual(result["counts"]["valid_files"], 0)
            self.assertEqual(result["counts"]["invalid_files"], 1)
            self.assertEqual(result["counts"]["unmanaged_files"], 1)
            entry = result["files"][0]
            self.assertFalse(entry["xlsx_valid"])
            self.assertIn(
                "SHA-256",
                entry["validation_error"],
            )
            self.assertEqual(
                result["unmanaged_files"][0]["file_name"],
                "bad.xlsx",
            )
            self.assertEqual(result["tasks"][0]["invalid_file_count"], 1)

    def test_missing_required_committed_manifest_marks_partial(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            project = Path(temporary_dir) / "group"
            child = project / "farm_projects" / "008"
            _write_workbook(child / "analysis_results" / "unmanaged.xlsx")
            result = GroupArtifactInventory(project).build(
                tasks=[
                    {
                        "task_id": "task-008",
                        "farm_code": "008",
                        "farm_name": "缺清单场",
                        "relative_path": "farm_projects/008",
                        "stages": _required_stages("analysis"),
                    }
                ]
            )
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["counts"]["total_files"], 0)
            self.assertEqual(result["counts"]["unmanaged_files"], 1)
            self.assertIn(
                "committed manifest 不存在",
                result["task_issues"][0]["error"],
            )

    def test_invalid_child_path_is_partial_and_manifest_replace_is_atomic(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            project = Path(temporary_dir) / "group"
            (project / "reports").mkdir(parents=True)
            manifest_path = project / "reports" / "inventory.json"
            manifest_path.write_text('{"old": true}', encoding="utf-8")
            tasks = [
                {
                    "task_id": "task-outside",
                    "farm_code": "004",
                    "farm_name": "越界场",
                    "relative_path": "../outside",
                }
            ]

            result = GroupArtifactInventory(project).build(
                tasks=tasks,
                manifest_path=manifest_path,
            )

            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["counts"]["tasks_with_scan_errors"], 1)
            self.assertEqual(result["counts"]["total_files"], 0)
            self.assertIn(
                "超出牧场组目录",
                result["task_issues"][0]["error"],
            )
            on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["status"], "partial")
            self.assertFalse(
                list(manifest_path.parent.glob(f".{manifest_path.name}.*.tmp"))
            )

    def test_structure_inspection_reports_invalid_zip(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "broken.xlsx"
            path.write_bytes(b"broken")
            structure = inspect_xlsx_structure(path)
            self.assertFalse(structure["valid"])
            self.assertEqual(structure["sheet_count"], 0)
            self.assertIn("BadZipFile", structure["error"])

    def test_child_symlink_inside_group_can_inventory_existing_project(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            project = root / "group"
            external_child = root / "existing-project"
            result_path = (
                external_child / "analysis_results" / "result.xlsx"
            )
            _write_workbook(result_path)
            _commit_stage(
                external_child,
                task_id="linked-task",
                farm_code="005",
                stage="analysis",
                outputs=[result_path],
            )
            link = project / "farm_projects" / "linked"
            link.parent.mkdir(parents=True)
            link.symlink_to(external_child, target_is_directory=True)

            result = GroupArtifactInventory(project).build(
                tasks=[
                    {
                        "task_id": "linked-task",
                        "farm_code": "005",
                        "farm_name": "链接场",
                        "relative_path": "farm_projects/linked",
                        "stages": _required_stages("analysis"),
                    }
                ]
            )

            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["counts"]["total_files"], 1)
            self.assertEqual(
                result["files"][0]["relative_path"],
                "farm_projects/linked/analysis_results/result.xlsx",
            )

    def test_default_task_loading_uses_current_sqlite_inclusion(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            project = Path(temporary_dir) / "group"
            tasks = []
            for number in ("006", "007"):
                relative_path = f"farm_projects/{number}"
                result_path = (
                    project
                    / relative_path
                    / "analysis_results"
                    / "result.xlsx"
                )
                _write_workbook(result_path)
                task_id = str(uuid.uuid4())
                _commit_stage(
                    project / relative_path,
                    task_id=task_id,
                    farm_code=number,
                    stage="data",
                    outputs=[result_path],
                )
                tasks.append(
                    {
                        "task_id": task_id,
                        "farm_code": number,
                        "farm_name": f"{number}场",
                        "relative_path": relative_path,
                        "included_in_summary": True,
                    }
                )
            (project / "project_metadata.json").write_text(
                json.dumps(
                    {"group_tasks": tasks},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            store = GroupTaskStore(
                project / "group_store" / "group_tasks.sqlite3"
            )
            store.initialize_tasks(tasks, required_stages=("data",))
            store.set_included_in_summary(tasks[1]["task_id"], False)

            result = GroupArtifactInventory(project).build()

            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["counts"]["included_tasks"], 1)
            self.assertEqual(result["counts"]["total_files"], 1)
            self.assertEqual(result["files"][0]["farm_code"], "006")


if __name__ == "__main__":
    unittest.main()
