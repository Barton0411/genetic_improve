# utils/file_manager.py
from pathlib import Path
import shutil
import json
import os
import re
import uuid
import zipfile
from datetime import datetime
from typing import List, Dict, Optional

class FileManager:
    """文件管理工具类"""
    
    @staticmethod
    def create_project(base_path: Path, farm_name: str) -> Path:
        """
        创建新项目目录
        
        Args:
            base_path: 基础路径
            farm_name: 牧场名称
            
        Returns:
            项目路径
        """
        timestamp = datetime.now().strftime('%Y_%m_%d_%H_%M')
        project_name = f"{farm_name}_{timestamp}"
        project_path = base_path / project_name
        
        subdirs = [
            'raw_data',
            'standardized_data',
            'analysis_results',
            'reports'
        ]
        
        try:
            project_path.mkdir(parents=True, exist_ok=True)
            for subdir in subdirs:
                (project_path / subdir).mkdir(exist_ok=True)
            return project_path
        except Exception as e:
            print(f"创建项目目录失败: {e}")
            raise

    @staticmethod
    def get_projects(base_path: Path) -> list[Path]:
        """
        获取所有项目列表（按修改时间逆序排序）
        
        Args:
            base_path: 基础路径
            
        Returns:
            项目路径列表
        """
        try:
            return sorted(
                [d for d in base_path.iterdir() if d.is_dir()],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
        except Exception as e:
            print(f"获取项目列表失败: {e}")
            return []

    @staticmethod
    def delete_project(project_path: Path):
        """
        删除项目目录

        Args:
            project_path: 项目路径
        """
        try:
            shutil.rmtree(project_path)
        except Exception as e:
            print(f"删除项目失败: {e}")
            raise

    @staticmethod
    def create_merged_project(
        base_path: Path, farms: List[Dict], data_source: str = "伊起牛"
    ) -> Path:
        """
        创建合并牧场项目目录

        Args:
            base_path: 基础路径
            farms: 牧场列表，每个牧场包含 code, name, cow_count

        Returns:
            项目路径
        """
        timestamp = datetime.now().strftime('%Y%m%d')
        project_name = f"合并牧场_{timestamp}"
        project_path = base_path / project_name

        # 如果已存在，添加序号
        counter = 1
        original_project_path = project_path
        while project_path.exists():
            project_path = base_path / f"{original_project_path.name}_{counter}"
            counter += 1

        subdirs = [
            'raw_data',
            'standardized_data',
            'analysis_results',
            'reports'
        ]

        try:
            project_path.mkdir(parents=True, exist_ok=True)
            for subdir in subdirs:
                (project_path / subdir).mkdir(exist_ok=True)

            # 生成合并说明文件
            FileManager.generate_merged_farms_info(project_path, farms)

            # 生成项目元数据
            FileManager.save_project_metadata(project_path, farms, data_source=data_source)

            return project_path
        except Exception as e:
            print(f"创建合并项目目录失败: {e}")
            raise

    @staticmethod
    def _safe_folder_name(value: str) -> str:
        """生成跨平台可用的项目子目录名称。"""
        text = re.sub(r'[\\/:*?"<>|]+', "_", str(value or "").strip())
        text = re.sub(r"\s+", " ", text).strip(" ._")
        return text[:80] or "未命名牧场"

    @staticmethod
    def _write_json_atomic(path: Path, payload: Dict) -> None:
        """避免任务状态更新中断后留下半个 JSON 文件。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
            os.replace(temp_path, path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    @staticmethod
    def create_group_project(
        base_path: Path,
        farms: List[Dict],
        data_source: str,
        task_mode: str = "analysis",
    ) -> Path:
        """创建牧场组父项目，并为每个牧场创建独立子项目。"""
        timestamp = datetime.now().strftime("%Y%m%d")
        project_path = Path(base_path) / f"牧场组_{timestamp}"
        counter = 1
        while project_path.exists():
            project_path = Path(base_path) / f"牧场组_{timestamp}_{counter}"
            counter += 1

        for subdir in (
            "raw_data",
            "standardized_data",
            "analysis_results",
            "reports",
            "farm_projects",
            "group_store",
        ):
            (project_path / subdir).mkdir(parents=True, exist_ok=True)

        tasks = []
        used_names = set()
        required_stages = (
            ("data",)
            if task_mode == "data_only"
            else ("data", "analysis", "child_excel")
        )
        for sort_order, farm in enumerate(farms):
            normalized = FileManager._normalize_farm(farm, data_source)
            code = str(normalized.get("code") or "").strip()
            name = str(
                normalized.get("display_name")
                or normalized.get("name")
                or code
                or "未命名牧场"
            ).strip()
            task_id = str(uuid.uuid4())
            farm["task_id"] = task_id
            folder_base = FileManager._safe_folder_name(f"{code}_{name}")
            folder_name = folder_base
            suffix = 2
            while folder_name in used_names:
                folder_name = f"{folder_base}_{suffix}"
                suffix += 1
            used_names.add(folder_name)

            relative_path = Path("farm_projects") / folder_name
            child_path = project_path / relative_path
            for subdir in (
                "raw_data",
                "standardized_data",
                "analysis_results",
                "reports",
            ):
                (child_path / subdir).mkdir(parents=True, exist_ok=True)

            FileManager.save_project_metadata(
                child_path,
                [normalized],
                data_source=data_source,
                project_type="group_child",
                extra={
                    "parent_group": "../..",
                    "group_farm_code": code,
                    "group_api_farmcode": normalized.get(
                        "api_farmcode", ""
                    ),
                    "group_farm_number": normalized.get(
                        "farm_number", ""
                    ),
                    "group_task_id": task_id,
                },
            )
            tasks.append(
                {
                    "task_id": task_id,
                    "farm_code": code,
                    "farm_name": name,
                    "relative_path": relative_path.as_posix(),
                    "source_kind": normalized.get("source_kind", "api"),
                    "source_system": normalized.get("source_system", data_source),
                    "metadata": {
                        "api_farmcode": normalized.get(
                            "api_farmcode", ""
                        ),
                        "farm_number": normalized.get(
                            "farm_number", ""
                        ),
                        "display_name": name,
                        "source_farm_name": normalized.get(
                            "source_farm_name", name
                        ),
                    },
                    "included_in_summary": True,
                    "required_stages": list(required_stages),
                    "sort_order": sort_order,
                    "status": "pending",
                    "stage": "等待处理",
                    "progress": 0,
                    "error": "",
                    "updated_at": datetime.now().isoformat(),
                }
            )

        metadata = {
            "is_merged": False,
            "is_group": True,
            "project_type": "multi_farm_group",
            "data_source": data_source,
            "interface_source": data_source,
            "task_mode": task_mode,
            "farms": [FileManager._normalize_farm(f, data_source) for f in farms],
            "group_tasks": tasks,
            "all_tasks_complete": False,
            "created_at": datetime.now().isoformat(),
        }
        FileManager._write_json_atomic(
            project_path / "project_metadata.json", metadata
        )
        from utils.group_task_store import GroupTaskStore

        GroupTaskStore(
            project_path / "group_store" / "group_tasks.sqlite3"
        ).initialize_tasks(
            tasks,
            required_stages=required_stages,
        )
        FileManager.generate_merged_farms_info(project_path, metadata["farms"])
        return project_path

    @staticmethod
    def _group_task_store(project_path: Path):
        database_path = (
            Path(project_path) / "group_store" / "group_tasks.sqlite3"
        )
        if not database_path.exists():
            return None
        from utils.group_task_store import GroupTaskStore

        return GroupTaskStore(database_path)

    @staticmethod
    def _resolve_group_task(metadata: Dict, identifier: str) -> Dict:
        identifier = str(identifier)
        tasks = metadata.get("group_tasks", [])
        exact = [
            task for task in tasks
            if str(task.get("task_id", "")) == identifier
        ]
        if exact:
            return exact[0]
        by_code = [
            task for task in tasks
            if str(task.get("farm_code", "")) == identifier
        ]
        if len(by_code) == 1:
            return by_code[0]
        if len(by_code) > 1:
            raise KeyError(
                f"牧场编号 {identifier} 对应多个任务，请使用 task_id"
            )
        raise KeyError(f"牧场组中不存在牧场任务：{identifier}")

    @staticmethod
    def get_group_child_path(project_path: Path, identifier: str) -> Optional[Path]:
        metadata = FileManager.load_project_metadata(Path(project_path))
        try:
            task = FileManager._resolve_group_task(metadata, identifier)
        except KeyError:
            return None
        return Path(project_path) / task["relative_path"]

    @staticmethod
    def update_group_task(
        project_path: Path,
        farm_code: str,
        *,
        status: Optional[str] = None,
        stage: Optional[str] = None,
        progress: Optional[int] = None,
        error: Optional[str] = None,
        result: Optional[Dict] = None,
    ) -> Dict:
        """更新一个牧场子任务状态，并同步父项目完成状态。"""
        project_path = Path(project_path)
        store = FileManager._group_task_store(project_path)
        target = None
        if store is not None:
            target = store.get_task(str(farm_code), with_stages=False)
        if target is None:
            metadata = FileManager.load_project_metadata(project_path)
            target = FileManager._resolve_group_task(metadata, farm_code)
        if store is not None and target.get("task_id"):
            kwargs = {}
            metadata_update = {}
            if status is not None:
                kwargs["status"] = status
            if stage is not None:
                metadata_update["display_stage"] = str(stage)
            if progress is not None:
                kwargs["progress"] = max(0, min(100, int(progress)))
            if error is not None:
                kwargs["error"] = str(error)[:1000]
            if result:
                metadata_update["result"] = result
            if metadata_update:
                kwargs["metadata"] = metadata_update
            if kwargs:
                store.update_task(target["task_id"], **kwargs)
            if status is not None:
                FileManager._mark_group_results_stale(project_path)
            return store.get_task(target["task_id"], with_stages=True) or {}

        metadata = FileManager.load_project_metadata(project_path)
        target = FileManager._resolve_group_task(metadata, farm_code)
        if status is not None:
            target["status"] = status
        if stage is not None:
            target["stage"] = stage
        if progress is not None:
            target["progress"] = max(0, min(100, int(progress)))
        if error is not None:
            target["error"] = str(error)[:1000]
        if result:
            target.setdefault("result", {}).update(result)
        target["updated_at"] = datetime.now().isoformat()

        FileManager._refresh_group_completion(metadata)
        metadata["updated_at"] = datetime.now().isoformat()
        FileManager._write_json_atomic(
            project_path / "project_metadata.json", metadata
        )
        return metadata

    @staticmethod
    def update_group_stage(
        project_path: Path,
        task_id: str,
        stage_name: str,
        *,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        error: str = "",
        artifacts: Optional[Dict] = None,
        warning: str = "",
        detail_count: Optional[int] = None,
    ) -> Dict:
        """持久化一个子任务阶段，支持程序中断后从首个未完成阶段继续。"""
        project_path = Path(project_path)
        store = FileManager._group_task_store(project_path)
        if store is None:
            return FileManager.update_group_task(
                project_path,
                task_id,
                stage=stage_name,
                progress=progress,
                error=error,
            )
        output_path = ""
        if artifacts:
            output_path = next(
                (str(value) for value in artifacts.values() if value),
                "",
            )
        task = store.update_stage(
            task_id,
            stage_name,
            status=status,
            progress=progress,
            error=error or warning,
            output_path=output_path,
            detail_count=detail_count,
        )
        if artifacts or warning:
            store.update_task(
                task_id,
                metadata={
                    f"{stage_name}_artifacts": artifacts or {},
                    f"{stage_name}_warning": warning,
                },
            )
        if status in {
            "completed",
            "completed_with_warning",
            "failed",
            "interrupted",
            "stale",
        }:
            FileManager._mark_group_results_stale(project_path)
        return FileManager.load_project_metadata(project_path)

    @staticmethod
    def _refresh_group_completion(metadata: Dict) -> None:
        """按“纳入汇总范围”的任务计算牧场组是否已完成。"""
        tasks = metadata.get("group_tasks", [])
        active_tasks = [
            task
            for task in tasks
            if task.get("included_in_summary", True)
        ]
        metadata["active_task_count"] = len(active_tasks)
        metadata["excluded_task_count"] = len(tasks) - len(active_tasks)
        metadata["all_tasks_complete"] = bool(active_tasks) and all(
            task.get("status") in {"completed", "completed_with_warning"}
            for task in active_tasks
        )

    @staticmethod
    def _valid_xlsx_file(path: Path) -> bool:
        """轻量校验 xlsx 容器，避免把 0KB/半成品当作已完成产物。"""
        path = Path(path)
        if not path.is_file() or path.stat().st_size <= 0:
            return False
        try:
            if not zipfile.is_zipfile(path):
                return False
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                required = {"[Content_Types].xml", "xl/workbook.xml"}
                if not required.issubset(names):
                    return False
                # 只读取两个很小的结构文件验证 CRC；不能在界面刷新时对每个
                # 大型工作簿执行 testzip()，否则会把全部明细重新解压一遍。
                return all(archive.read(name) for name in required)
        except (OSError, zipfile.BadZipFile):
            return False

    @staticmethod
    def _group_summary_readiness(project_path: Path, metadata: Dict) -> Dict:
        """报告就绪与“数据任务完成”分开判断。

        data_only 牧场组在标准化数据完成后即可结束创建任务，但只有每个纳入
        牧场都具备四个核心分析产物和单牧场综合报告时，才允许最终汇总。
        """
        project_path = Path(project_path)
        active_tasks = [
            task
            for task in metadata.get("group_tasks", [])
            if task.get("included_in_summary", True)
        ]
        missing_tasks = []
        for task in active_tasks:
            child_path = project_path / task.get("relative_path", "")
            missing = []
            try:
                from core.group_tasks.stage_policy import (
                    validate_child_stage,
                )

                for stage_name, label in (
                    ("data", "数据阶段提交清单"),
                    ("analysis", "分析阶段提交清单"),
                    ("child_excel", "单牧场Excel阶段提交清单"),
                ):
                    validation = validate_child_stage(
                        child_path,
                        stage_name,
                        expected_task_id=task.get("task_id") or None,
                        expected_farm_code=task.get("farm_code") or None,
                    )
                    if not validation.get("valid"):
                        missing.append(
                            f"{label}无效"
                            f"（{validation.get('status', 'unknown')}）"
                        )
            except Exception as exc:
                missing.append(f"阶段完整性校验失败（{type(exc).__name__}）")
            if missing:
                missing_tasks.append(
                    {
                        "task_id": task.get("task_id", ""),
                        "farm_code": task.get("farm_code", ""),
                        "farm_name": task.get("farm_name", ""),
                        "missing": missing,
                    }
                )
        return {
            "ready": bool(active_tasks) and not missing_tasks,
            "included_count": len(active_tasks),
            "ready_count": len(active_tasks) - len(missing_tasks),
            "missing_count": len(missing_tasks),
            "missing_tasks": missing_tasks,
        }

    @staticmethod
    def get_group_summary_readiness(project_path: Path) -> Dict:
        metadata = FileManager.load_project_metadata(Path(project_path))
        if metadata.get("project_type") != "multi_farm_group":
            return {
                "ready": False,
                "included_count": 0,
                "ready_count": 0,
                "missing_count": 0,
                "missing_tasks": [],
            }
        return FileManager._group_summary_readiness(project_path, metadata)

    @staticmethod
    def set_group_task_excluded(
        project_path: Path, farm_code: str, excluded: bool = True
    ) -> Dict:
        """移出/重新纳入最终汇总范围；只改状态，不删除子项目和结果。"""
        project_path = Path(project_path)
        metadata = FileManager.load_project_metadata(project_path)
        target = FileManager._resolve_group_task(metadata, farm_code)
        store = FileManager._group_task_store(project_path)
        if store is not None and target.get("task_id"):
            store.set_included_in_summary(target["task_id"], not excluded)
            FileManager._mark_group_results_stale(project_path)
            return FileManager.load_project_metadata(project_path)

        target["included_in_summary"] = not excluded
        target["stage"] = (
            "已移出最终汇总范围"
            if excluded
            else "已重新纳入最终汇总范围"
        )
        target["updated_at"] = datetime.now().isoformat()
        FileManager._refresh_group_completion(metadata)
        metadata["updated_at"] = datetime.now().isoformat()
        FileManager._write_json_atomic(
            project_path / "project_metadata.json", metadata
        )
        return metadata

    @staticmethod
    def reset_group_task_for_retry(
        project_path: Path,
        identifier: str,
        from_stage: Optional[str] = None,
    ) -> Dict:
        project_path = Path(project_path)
        metadata = FileManager.load_project_metadata(project_path)
        target = FileManager._resolve_group_task(metadata, identifier)
        store = FileManager._group_task_store(project_path)
        if store is None:
            return FileManager.update_group_task(
                project_path,
                identifier,
                status="pending",
                stage="等待重试",
                progress=0,
                error="",
            )
        reset_task = store.reset_for_retry(
            target["task_id"],
            from_stage=from_stage,
        )
        retry_stage = (
            from_stage
            or reset_task.get("current_stage")
            or "data"
        )
        store.update_task(
            target["task_id"],
            metadata={"force_recompute_from": str(retry_stage)},
        )
        FileManager._mark_group_results_stale(project_path)
        return FileManager.load_project_metadata(project_path)

    @staticmethod
    def refresh_group_task_statuses(project_path: Path) -> Dict:
        """按原子阶段清单重新校验子项目，禁止仅凭文件存在续用。"""
        project_path = Path(project_path)
        metadata = FileManager.load_project_metadata(project_path)
        task_mode = metadata.get("task_mode", "analysis")
        store = FileManager._group_task_store(project_path)
        manifest_invalidated = False
        for task in metadata.get("group_tasks", []):
            if not task.get("included_in_summary", True):
                continue
            child_path = project_path / task.get("relative_path", "")
            if store is not None and task.get("task_id"):
                from core.group_tasks.stage_policy import (
                    validate_child_stage,
                )

                validations = {
                    stage_name: validate_child_stage(
                        child_path,
                        stage_name,
                        expected_task_id=task.get("task_id") or None,
                        expected_farm_code=task.get("farm_code") or None,
                    )
                    for stage_name in ("data", "analysis", "child_excel")
                }
                stages = task.get("stages", {})
                upstream_valid = True
                for stage_name in ("data", "analysis", "child_excel"):
                    stage = stages.get(stage_name, {})
                    required = bool(stage.get("required"))
                    validation = validations[stage_name]
                    is_valid = bool(validation.get("valid"))
                    if stage_name != "data" and not upstream_valid:
                        is_valid = False
                    if is_valid:
                        previous_status = str(stage.get("status") or "")
                        status = (
                            "completed_with_warning"
                            if previous_status == "completed_with_warning"
                            else "completed"
                        )
                        manifest = validation.get("manifest") or {}
                        outputs = manifest.get("outputs") or []
                        output_path = (
                            str(
                                child_path
                                / str(outputs[0].get("relative_path") or "")
                            )
                            if outputs
                            else ""
                        )
                        store.update_stage(
                            task["task_id"],
                            stage_name,
                            status=status,
                            output_path=output_path,
                        )
                    else:
                        validation_status = str(
                            validation.get("status") or "invalid"
                        )
                        current_status = str(stage.get("status") or "")
                        never_started = (
                            current_status == "pending"
                            and not (
                                child_path
                                / "group_store"
                                / "stage_manifests"
                                / f"{stage_name}.json"
                            ).exists()
                        )
                        if (
                            not never_started
                            and (
                                required
                                or current_status
                                not in {"pending", "skipped"}
                            )
                        ):
                            manifest_invalidated = True
                            store.update_stage(
                                task["task_id"],
                                stage_name,
                                status="stale",
                                error=(
                                    "阶段提交清单无效或与当前输入不一致："
                                    f"{validation_status}"
                                ),
                            )
                    upstream_valid = upstream_valid and is_valid
                continue

            cow_path = (
                child_path / "standardized_data" / "processed_cow_data.xlsx"
            )
            cow_ready = FileManager._valid_xlsx_file(cow_path)
            if cow_ready and task.get("source_kind") == "local":
                try:
                    from core.data.composite_farm_manager import (
                        validate_local_data_commit,
                    )

                    validate_local_data_commit(
                        child_path,
                        expected_task_id=task.get("task_id") or None,
                        expected_farm_code=task.get("farm_code") or None,
                    )
                except Exception:
                    cow_ready = False
            analysis_paths = [
                child_path
                / "analysis_results"
                / "processed_cow_data_key_traits_final.xlsx",
                child_path
                / "analysis_results"
                / "processed_index_cow_index_scores.xlsx",
                child_path
                / "analysis_results"
                / "关键育种性状分析结果.xlsx",
                child_path
                / "analysis_results"
                / "系谱识别分析结果.xlsx",
            ]
            analysis_ready = all(
                FileManager._valid_xlsx_file(path)
                for path in analysis_paths
            )
            valid_reports = [
                path
                for path in (
                    child_path / "reports"
                ).glob("育种分析综合报告_*.xlsx")
                if FileManager._valid_xlsx_file(path)
            ]
            report_ready = bool(valid_reports)
            ready = cow_ready and (
                task_mode != "analysis"
                or (analysis_ready and report_ready)
            )
            if ready:
                task["status"] = "completed"
                task["stage"] = "已完成（根据现有结果确认）"
                task["progress"] = 100
                task["error"] = ""
            elif task.get("status") == "completed":
                task["status"] = "pending"
                task["stage"] = "结果不完整，等待重新处理"
                task["progress"] = 0
            task["updated_at"] = datetime.now().isoformat()
        FileManager._refresh_group_completion(metadata)
        metadata["updated_at"] = datetime.now().isoformat()
        FileManager._write_json_atomic(
            project_path / "project_metadata.json", metadata
        )
        if manifest_invalidated:
            FileManager._mark_group_results_stale(project_path)
        return metadata

    @staticmethod
    def _mark_group_results_stale(project_path: Path) -> None:
        metadata_file = Path(project_path) / "project_metadata.json"
        if not metadata_file.exists():
            return
        try:
            with open(metadata_file, "r", encoding="utf-8") as file:
                metadata = json.load(file)
        except Exception:
            return
        results = metadata.get("group_results")
        if not results or results.get("status") == "stale":
            return
        results["status"] = "stale"
        results["stale_at"] = datetime.now().isoformat()
        FileManager._write_json_atomic(metadata_file, metadata)

    @staticmethod
    def update_group_result(project_path: Path, **result_paths) -> Dict:
        """保存牧场组最终汇总报告路径。"""
        project_path = Path(project_path)
        store = FileManager._group_task_store(project_path)
        expected_revision = result_paths.get("selection_revision")
        if store is not None and expected_revision is not None:
            current_revision = store.get_selection_revision()
            if int(expected_revision) != current_revision:
                raise RuntimeError(
                    "牧场汇总范围已变化，当前结果不能标记为正式"
                )
        metadata = FileManager.load_project_metadata(project_path)
        def serialize(value):
            if isinstance(value, Path):
                return str(value)
            if isinstance(value, (list, tuple)):
                return [serialize(item) for item in value]
            if isinstance(value, dict):
                return {
                    str(key): serialize(item) for key, item in value.items()
                }
            return value

        metadata.setdefault("group_results", {}).update(
            {
                key: serialize(value)
                for key, value in result_paths.items()
                if value is not None
            }
        )
        metadata["group_results"]["status"] = "current"
        metadata["updated_at"] = datetime.now().isoformat()
        FileManager._write_json_atomic(
            project_path / "project_metadata.json", metadata
        )
        if store is not None and expected_revision is not None:
            current_revision = store.get_selection_revision()
            if int(expected_revision) != current_revision:
                FileManager._mark_group_results_stale(project_path)
                raise RuntimeError(
                    "牧场汇总范围在发布时发生变化，结果已标记为过期"
                )
        return metadata

    @staticmethod
    def generate_merged_farms_info(project_path: Path, farms: List[Dict]):
        """
        生成合并牧场说明文件

        Args:
            project_path: 项目路径
            farms: 牧场列表
        """
        total_count = sum(f.get('cow_count', 0) for f in farms)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        content_lines = [
            "本项目合并了以下牧场数据：",
            ""
        ]

        for i, farm in enumerate(farms, 1):
            code = str(
                farm.get("code") or farm.get("farmCode") or ""
            )
            api_farmcode = str(
                farm.get("api_farmcode")
                or (
                    code
                    if farm.get("source_kind", "api") != "local"
                    else ""
                )
            )
            farm_number = str(
                farm.get("farm_number")
                if "farm_number" in farm
                else code
            )
            name = farm.get('name', 'N/A')
            count = farm.get('cow_count', 0)
            source_kind = farm.get("source_kind", "api")
            source_system = farm.get("source_system", "")
            source_label = "本地" if source_kind == "local" else "接口"
            source_text = (
                f"，{source_label}·{source_system}" if source_system else ""
            )
            content_lines.append(
                f"{i}. API farmcode: {api_farmcode or '-'}；"
                f"牧场编号: {farm_number or '-'}；"
                f"牧场名称: {name} ({count}头{source_text})"
            )

        content_lines.extend([
            "",
            f"合计: {total_count}头",
            f"创建时间：{now}"
        ])

        info_file = project_path / "merged_farms.txt"
        info_file.write_text("\n".join(content_lines), encoding='utf-8')

    @staticmethod
    def save_project_metadata(
        project_path: Path,
        farms: List[Dict],
        data_source: str = "伊起牛",
        project_type: Optional[str] = None,
        extra: Optional[Dict] = None,
    ):
        """
        保存项目元数据

        Args:
            project_path: 项目路径
            farms: 牧场列表
        """
        normalized_farms = [
            FileManager._normalize_farm(farm, data_source) for farm in farms
        ]

        metadata = {
            "is_merged": len(farms) > 1,
            "data_source": data_source,
            "interface_source": data_source,
            "project_type": project_type or (
                "interface_composite" if len(farms) > 1 else "single_farm"
            ),
            "farms": normalized_farms,
            "created_at": datetime.now().isoformat()
        }
        if extra:
            metadata.update(extra)

        metadata_file = project_path / "project_metadata.json"
        FileManager._write_json_atomic(metadata_file, metadata)
        if len(farms) > 1:
            FileManager.generate_merged_farms_info(project_path, farms)

    @staticmethod
    def _normalize_farm(farm: Dict, data_source: str) -> Dict:
        code = str(
            farm.get("code") or farm.get("farmCode") or ""
        ).strip()
        source_kind = str(farm.get("source_kind") or "api")
        source_system = str(
            farm.get("source_system") or data_source
        ).strip()
        source_name = str(
            farm.get("source_farm_name")
            or farm.get("name")
            or ""
        ).strip()
        display_name = str(farm.get("display_name") or "").strip()
        farm_number = str(farm.get("farm_number") or "").strip()

        is_hmy_api = (
            source_kind != "local"
            and (source_system == "慧牧云" or data_source == "慧牧云")
        )
        if is_hmy_api:
            from core.data.hmy_data_converter import HMYDataConverter

            parsed_number, parsed_name = HMYDataConverter.split_farm_name(
                source_name
            )
            farm_number = farm_number or parsed_number
            display_name = display_name or parsed_name or source_name
            api_farmcode = str(
                farm.get("api_farmcode") or code
            ).strip()
        else:
            display_name = display_name or source_name
            # 伊起牛和本地项目原本就把 code 作为牧场编号；继续保持该
            # 语义，同时为统一的组报告提供显式字段。
            farm_number = farm_number or code
            api_farmcode = str(
                farm.get("api_farmcode")
                or (code if source_kind != "local" else "")
            ).strip()

        return {
            # code 是任务寻址与接口调用使用的稳定编码。慧牧云场景下
            # 它始终等于 API farmcode，绝不能被七位业务牧场编号替换。
            "code": code,
            "api_farmcode": api_farmcode,
            "farm_number": farm_number,
            "name": display_name,
            "display_name": display_name,
            "source_farm_name": source_name or display_name,
            "cow_count": int(farm.get("cow_count", 0) or 0),
            "source_kind": source_kind,
            "source_system": source_system,
            "has_breeding_records": bool(
                farm.get("has_breeding_records", False)
            ),
            "breeding_count": int(farm.get("breeding_count", 0) or 0),
        }

    @staticmethod
    def load_project_metadata(project_path: Path) -> Dict:
        """
        加载项目元数据

        Args:
            project_path: 项目路径

        Returns:
            元数据字典，如果不存在返回默认值
        """
        metadata_file = project_path / "project_metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                if metadata.get("project_type") == "multi_farm_group":
                    store = FileManager._group_task_store(project_path)
                    if store is not None:
                        tasks = store.list_tasks(with_stages=True)
                        metadata["group_tasks"] = [
                            {
                                **task,
                                "api_farmcode": task.get(
                                    "metadata", {}
                                ).get(
                                    "api_farmcode",
                                    (
                                        task.get("farm_code", "")
                                        if task.get("source_kind") != "local"
                                        else ""
                                    ),
                                ),
                                "farm_number": task.get(
                                    "metadata", {}
                                ).get(
                                    "farm_number",
                                    task.get("farm_code", ""),
                                ),
                                "display_name": task.get(
                                    "metadata", {}
                                ).get(
                                    "display_name",
                                    task.get("farm_name", ""),
                                ),
                                "source_farm_name": task.get(
                                    "metadata", {}
                                ).get(
                                    "source_farm_name",
                                    task.get("farm_name", ""),
                                ),
                                "stage": (
                                    task.get("metadata", {}).get(
                                        "display_stage"
                                    )
                                    or task.get("current_stage")
                                    or (
                                        "已完成"
                                        if task.get("status")
                                        in {
                                            "completed",
                                            "completed_with_warning",
                                        }
                                        else "等待处理"
                                    )
                                ),
                                "result": task.get("metadata", {}).get(
                                    "result", {}
                                ),
                            }
                            for task in tasks
                        ]
                        state = store.completion_state()
                        metadata["all_tasks_complete"] = state["is_complete"]
                        metadata["active_task_count"] = state[
                            "included_count"
                        ]
                        metadata["excluded_task_count"] = state[
                            "excluded_count"
                        ]
                        revision = store.get_selection_revision()
                        metadata["selection_revision"] = revision
                        results = metadata.get("group_results", {})
                        if (
                            results.get("status") == "current"
                            and results.get("selection_revision") != revision
                        ):
                            results["status"] = "stale"
                return metadata
            except Exception:
                pass

        return {"is_merged": False, "farms": []}
