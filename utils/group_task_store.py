"""牧场组任务的可恢复 SQLite 状态存储。

每个牧场组使用一个独立数据库。所有公开操作都会创建短生命周期连接，
因此后台工作线程和界面线程可以安全地依次或并发访问同一状态库。
"""

from __future__ import annotations

import json
import math
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Union,
)


GROUP_TASK_STAGES = ("data", "analysis", "child_excel")
TASK_STATUSES = {
    "pending",
    "running",
    "completed",
    "completed_with_warning",
    "failed",
    "interrupted",
    "stale",
    "cancelled",
}
STAGE_STATUSES = {
    "pending",
    "running",
    "completed",
    "completed_with_warning",
    "failed",
    "interrupted",
    "stale",
    "skipped",
}
_UNSET = object()


class GroupTaskStoreError(RuntimeError):
    """牧场组任务状态库错误。"""


class TaskNotFoundError(GroupTaskStoreError):
    """找不到指定任务。"""


class SelectionRevisionMismatchError(GroupTaskStoreError):
    """获取组运行租约时，调用方持有的选择版本已经过期。"""

    def __init__(self, expected: int, current: int):
        self.expected = int(expected)
        self.current = int(current)
        super().__init__(
            f"牧场选择版本已变化: 期望 {self.expected}，当前 {self.current}"
        )


def _as_utc_datetime(value: Optional[datetime] = None) -> datetime:
    moment = value or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _utc_timestamp(value: Optional[datetime] = None) -> str:
    return (
        _as_utc_datetime(value)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _validate_stage_names(stages: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(stage) for stage in stages))
    unknown = set(normalized) - set(GROUP_TASK_STAGES)
    if unknown:
        raise ValueError(f"不支持的任务阶段: {', '.join(sorted(unknown))}")
    if not normalized:
        raise ValueError("至少需要一个任务阶段")
    return normalized


class GroupTaskStore:
    """使用 SQLite/WAL 保存大量牧场子任务的执行状态。"""

    def __init__(
        self,
        database_path: Union[Path, str],
        timeout: float = 30.0,
    ):
        self.database_path = Path(database_path)
        self.timeout = float(timeout)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.database_path),
            timeout=self.timeout,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS group_tasks (
                    task_id TEXT PRIMARY KEY,
                    farm_code TEXT NOT NULL,
                    farm_name TEXT NOT NULL,
                    relative_path TEXT NOT NULL DEFAULT '',
                    source_kind TEXT NOT NULL DEFAULT 'api',
                    source_system TEXT NOT NULL DEFAULT '',
                    included_in_summary INTEGER NOT NULL DEFAULT 1
                        CHECK (included_in_summary IN (0, 1)),
                    status TEXT NOT NULL DEFAULT 'pending',
                    current_stage TEXT,
                    progress REAL NOT NULL DEFAULT 0
                        CHECK (progress >= 0 AND progress <= 100),
                    attempt INTEGER NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    heartbeat_at TEXT
                );

                CREATE TABLE IF NOT EXISTS group_task_stages (
                    task_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    required INTEGER NOT NULL DEFAULT 1
                        CHECK (required IN (0, 1)),
                    status TEXT NOT NULL DEFAULT 'pending',
                    progress REAL NOT NULL DEFAULT 0
                        CHECK (progress >= 0 AND progress <= 100),
                    attempt INTEGER NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT '',
                    output_path TEXT NOT NULL DEFAULT '',
                    detail_count INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    PRIMARY KEY (task_id, stage),
                    FOREIGN KEY (task_id) REFERENCES group_tasks(task_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS group_run_control (
                    singleton_id INTEGER PRIMARY KEY
                        CHECK (singleton_id = 1),
                    selection_revision INTEGER NOT NULL DEFAULT 0
                        CHECK (selection_revision >= 0),
                    lease_token TEXT,
                    lease_owner_id TEXT,
                    lease_run_kind TEXT,
                    lease_selection_revision INTEGER,
                    lease_acquired_at TEXT,
                    lease_heartbeat_at TEXT,
                    lease_expires_at TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_group_tasks_status
                    ON group_tasks(status);
                CREATE INDEX IF NOT EXISTS idx_group_tasks_included
                    ON group_tasks(included_in_summary, sort_order);
                CREATE INDEX IF NOT EXISTS idx_group_tasks_farm_code
                    ON group_tasks(farm_code);
                CREATE INDEX IF NOT EXISTS idx_group_task_stages_status
                    ON group_task_stages(stage, status);
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO group_run_control (
                    singleton_id, selection_revision, updated_at
                ) VALUES (1, 0, ?)
                """,
                (_utc_timestamp(),),
            )
            connection.execute("PRAGMA user_version = 2")
        finally:
            connection.close()

    @property
    def journal_mode(self) -> str:
        """返回当前 SQLite 日志模式，正常情况下为 ``wal``。"""
        connection = self._connect()
        try:
            row = connection.execute("PRAGMA journal_mode").fetchone()
            return str(row[0]).lower()
        finally:
            connection.close()

    def initialize_tasks(
        self,
        tasks: Sequence[Dict[str, Any]],
        *,
        required_stages: Sequence[str] = GROUP_TASK_STAGES,
        replace: bool = False,
    ) -> List[str]:
        """原子初始化任务及其三个阶段。

        ``farm_code`` 不设唯一约束，同一牧场可以出现在多个独立任务中。
        每个任务也可通过字典中的 ``required_stages`` 覆盖全局阶段要求。
        非必需阶段会以 ``skipped`` 状态保存，不影响任务完成。
        """

        default_required = _validate_stage_names(required_stages)
        timestamp = _utc_timestamp()
        prepared: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()

        for offset, source in enumerate(tasks):
            task = dict(source)
            raw_task_id = str(task.get("task_id") or uuid.uuid4())
            try:
                task_id = str(uuid.UUID(raw_task_id))
            except (ValueError, AttributeError) as exc:
                raise ValueError(f"task_id 不是有效 UUID: {raw_task_id}") from exc
            if task_id in seen_ids:
                raise ValueError(f"本次初始化存在重复 task_id: {task_id}")
            seen_ids.add(task_id)

            farm_code = str(
                task.get("farm_code") or task.get("code") or ""
            ).strip()
            farm_name = str(
                task.get("farm_name") or task.get("name") or farm_code
            ).strip()
            if not farm_code:
                raise ValueError("farm_code 不能为空")
            if not farm_name:
                raise ValueError(f"牧场 {farm_code} 的 farm_name 不能为空")

            task_required = _validate_stage_names(
                task.get("required_stages", default_required)
            )
            metadata = task.get("metadata", {})
            if not isinstance(metadata, dict):
                raise ValueError("metadata 必须是字典")

            prepared.append(
                {
                    "task_id": task_id,
                    "farm_code": farm_code,
                    "farm_name": farm_name,
                    "relative_path": str(task.get("relative_path") or ""),
                    "source_kind": str(task.get("source_kind") or "api"),
                    "source_system": str(task.get("source_system") or ""),
                    "included": int(
                        bool(task.get("included_in_summary", True))
                    ),
                    "metadata_json": json.dumps(
                        metadata,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    "sort_order": int(task.get("sort_order", offset)),
                    "required_stages": task_required,
                }
            )

        with self._transaction() as connection:
            if replace:
                connection.execute("DELETE FROM group_tasks")

            for task in prepared:
                connection.execute(
                    """
                    INSERT INTO group_tasks (
                        task_id, farm_code, farm_name, relative_path,
                        source_kind, source_system, included_in_summary,
                        status, current_stage, progress, attempt, error,
                        metadata_json, sort_order, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', NULL, 0, 0, '',
                              ?, ?, ?, ?)
                    """,
                    (
                        task["task_id"],
                        task["farm_code"],
                        task["farm_name"],
                        task["relative_path"],
                        task["source_kind"],
                        task["source_system"],
                        task["included"],
                        task["metadata_json"],
                        task["sort_order"],
                        timestamp,
                        timestamp,
                    ),
                )
                for stage in GROUP_TASK_STAGES:
                    required = int(stage in task["required_stages"])
                    status = "pending" if required else "skipped"
                    progress = 0 if required else 100
                    completed_at = None if required else timestamp
                    connection.execute(
                        """
                        INSERT INTO group_task_stages (
                            task_id, stage, required, status, progress,
                            attempt, error, output_path, detail_count,
                            created_at, updated_at, completed_at
                        ) VALUES (?, ?, ?, ?, ?, 0, '', '', NULL, ?, ?, ?)
                        """,
                        (
                            task["task_id"],
                            stage,
                            required,
                            status,
                            progress,
                            timestamp,
                            timestamp,
                            completed_at,
                        ),
                    )

        return [task["task_id"] for task in prepared]

    def list_tasks(
        self,
        *,
        included_only: Optional[bool] = None,
        statuses: Optional[Union[Sequence[str], str]] = None,
        with_stages: bool = True,
    ) -> List[Dict[str, Any]]:
        clauses: List[str] = []
        parameters: List[Any] = []
        if included_only is not None:
            clauses.append("t.included_in_summary = ?")
            parameters.append(int(included_only))
        if statuses:
            normalized = [statuses] if isinstance(statuses, str) else list(statuses)
            unknown = set(normalized) - TASK_STATUSES
            if unknown:
                raise ValueError(
                    f"不支持的任务状态: {', '.join(sorted(unknown))}"
                )
            placeholders = ",".join("?" for _ in normalized)
            clauses.append(f"t.status IN ({placeholders})")
            parameters.extend(normalized)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        connection = self._connect()
        try:
            rows = connection.execute(
                f"""
                SELECT t.* FROM group_tasks AS t
                {where}
                ORDER BY t.sort_order, t.created_at, t.task_id
                """,
                parameters,
            ).fetchall()
            stages_by_task: Dict[str, List[sqlite3.Row]] = {}
            if with_stages and rows:
                stage_rows = connection.execute(
                    f"""
                    SELECT s.*
                    FROM group_task_stages AS s
                    INNER JOIN group_tasks AS t ON t.task_id = s.task_id
                    {where}
                    ORDER BY t.sort_order, t.created_at, t.task_id,
                        CASE s.stage
                            WHEN 'data' THEN 1
                            WHEN 'analysis' THEN 2
                            WHEN 'child_excel' THEN 3
                            ELSE 99
                        END
                    """,
                    parameters,
                ).fetchall()
                for stage_row in stage_rows:
                    stages_by_task.setdefault(
                        str(stage_row["task_id"]),
                        [],
                    ).append(stage_row)
            return [
                self._task_from_row(
                    connection,
                    row,
                    with_stages,
                    preloaded_stages=stages_by_task.get(
                        str(row["task_id"]),
                        [],
                    )
                    if with_stages
                    else None,
                )
                for row in rows
            ]
        finally:
            connection.close()

    def get_task(
        self,
        task_id: str,
        *,
        with_stages: bool = True,
    ) -> Optional[Dict[str, Any]]:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM group_tasks WHERE task_id = ?",
                (str(task_id),),
            ).fetchone()
            if row is None:
                return None
            return self._task_from_row(connection, row, with_stages)
        finally:
            connection.close()

    def _task_from_row(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        with_stages: bool,
        *,
        preloaded_stages: Optional[Sequence[sqlite3.Row]] = None,
    ) -> Dict[str, Any]:
        task = dict(row)
        task["included_in_summary"] = bool(task["included_in_summary"])
        try:
            task["metadata"] = json.loads(task.pop("metadata_json"))
        except (TypeError, json.JSONDecodeError):
            task["metadata"] = {}
            task.pop("metadata_json", None)
        if with_stages:
            stage_rows = preloaded_stages
            if stage_rows is None:
                stage_rows = connection.execute(
                    """
                    SELECT * FROM group_task_stages
                    WHERE task_id = ?
                    ORDER BY CASE stage
                        WHEN 'data' THEN 1
                        WHEN 'analysis' THEN 2
                        WHEN 'child_excel' THEN 3
                        ELSE 99
                    END
                    """,
                    (task["task_id"],),
                ).fetchall()
            task["stages"] = {
                stage_row["stage"]: {
                    **dict(stage_row),
                    "required": bool(stage_row["required"]),
                }
                for stage_row in stage_rows
            }
        return task

    def update_task(
        self,
        task_id: str,
        *,
        status: Optional[str] = None,
        included_in_summary: Optional[bool] = None,
        current_stage: Any = _UNSET,
        progress: Optional[float] = None,
        error: Any = _UNSET,
        farm_name: Optional[str] = None,
        relative_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """原子更新任务字段。

        ``included_in_summary`` 与 ``status`` 完全独立：排除失败任务不会
        修改其执行状态，重新纳入也不会把任务伪装成已完成。
        """

        if status is not None and status not in TASK_STATUSES:
            raise ValueError(f"不支持的任务状态: {status}")
        if progress is not None and not 0 <= float(progress) <= 100:
            raise ValueError("progress 必须在 0 到 100 之间")
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("metadata 必须是字典")

        timestamp = _utc_timestamp()
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM group_tasks WHERE task_id = ?",
                (str(task_id),),
            ).fetchone()
            if existing is None:
                raise TaskNotFoundError(f"找不到牧场组任务: {task_id}")

            values: Dict[str, Any] = {"updated_at": timestamp}
            if status is not None:
                values["status"] = status
                if status == "running":
                    values["started_at"] = existing["started_at"] or timestamp
                    values["heartbeat_at"] = timestamp
                    if existing["status"] != "running":
                        values["attempt"] = int(existing["attempt"]) + 1
                if status in {"completed", "completed_with_warning"}:
                    values["progress"] = 100
                    values["completed_at"] = timestamp
                    values["error"] = ""
                elif status in {
                    "pending",
                    "running",
                    "failed",
                    "interrupted",
                    "stale",
                }:
                    values["completed_at"] = None
            if included_in_summary is not None:
                included_value = int(bool(included_in_summary))
                values["included_in_summary"] = included_value
                selection_changed = (
                    included_value != int(existing["included_in_summary"])
                )
            else:
                selection_changed = False
            if current_stage is not _UNSET:
                if current_stage is not None:
                    _validate_stage_names((str(current_stage),))
                values["current_stage"] = current_stage
            if progress is not None:
                values["progress"] = float(progress)
            if error is not _UNSET:
                values["error"] = str(error or "")
            if farm_name is not None:
                values["farm_name"] = str(farm_name)
            if relative_path is not None:
                values["relative_path"] = str(relative_path)
            if metadata is not None:
                merged = json.loads(existing["metadata_json"] or "{}")
                merged.update(metadata)
                values["metadata_json"] = json.dumps(
                    merged,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )

            assignments = ", ".join(f"{column} = ?" for column in values)
            connection.execute(
                f"UPDATE group_tasks SET {assignments} WHERE task_id = ?",
                [*values.values(), str(task_id)],
            )
            if selection_changed:
                connection.execute(
                    """
                    UPDATE group_run_control
                    SET selection_revision = selection_revision + 1,
                        updated_at = ?
                    WHERE singleton_id = 1
                    """,
                    (timestamp,),
                )

        task = self.get_task(task_id)
        assert task is not None
        return task

    def set_included_in_summary(
        self,
        task_id: str,
        included: bool,
    ) -> Dict[str, Any]:
        return self.update_task(
            task_id,
            included_in_summary=bool(included),
        )

    def get_selection_revision(self) -> int:
        """返回当前纳入汇总范围的单调递增版本号。"""

        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT selection_revision
                FROM group_run_control
                WHERE singleton_id = 1
                """
            ).fetchone()
            if row is None:
                raise GroupTaskStoreError("牧场组运行控制记录不存在")
            return int(row["selection_revision"])
        finally:
            connection.close()

    @staticmethod
    def _validate_lease_arguments(
        owner_id: str,
        run_kind: str,
        lease_seconds: float,
    ) -> tuple[str, str, float]:
        normalized_owner = str(owner_id).strip()
        normalized_kind = str(run_kind).strip()
        duration = float(lease_seconds)
        if not normalized_owner:
            raise ValueError("owner_id 不能为空")
        if not normalized_kind:
            raise ValueError("run_kind 不能为空")
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("lease_seconds 必须是大于 0 的有限数值")
        return normalized_owner, normalized_kind, duration

    @staticmethod
    def _lease_from_control_row(row: sqlite3.Row) -> Dict[str, Any]:
        current_revision = int(row["selection_revision"])
        lease_revision = int(row["lease_selection_revision"])
        return {
            "lease_token": str(row["lease_token"]),
            "owner_id": str(row["lease_owner_id"]),
            "run_kind": str(row["lease_run_kind"]),
            "selection_revision": lease_revision,
            "current_selection_revision": current_revision,
            "selection_is_current": lease_revision == current_revision,
            "acquired_at": str(row["lease_acquired_at"]),
            "heartbeat_at": str(row["lease_heartbeat_at"]),
            "expires_at": str(row["lease_expires_at"]),
        }

    def acquire_run_lease(
        self,
        owner_id: str,
        *,
        run_kind: str,
        lease_seconds: float = 300,
        expected_selection_revision: Optional[int] = None,
        at: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """尝试获取父组批处理/汇总共用的排他运行租约。

        成功时返回带随机 ``lease_token`` 的租约字典；存在尚未过期的租约
        时返回 ``None``。调用方可传入已读取的选择版本做原子校验，防止
        在选择范围变化后误启动旧范围的运行。
        """

        owner, kind, duration = self._validate_lease_arguments(
            owner_id,
            run_kind,
            lease_seconds,
        )
        if expected_selection_revision is not None:
            expected_selection_revision = int(expected_selection_revision)
            if expected_selection_revision < 0:
                raise ValueError("expected_selection_revision 不能为负数")

        current = _as_utc_datetime(at)
        timestamp = _utc_timestamp(current)
        expires_at = _utc_timestamp(
            current + timedelta(seconds=duration)
        )
        lease_token = str(uuid.uuid4())

        with self._transaction() as connection:
            row = connection.execute(
                """
                SELECT * FROM group_run_control
                WHERE singleton_id = 1
                """
            ).fetchone()
            if row is None:
                raise GroupTaskStoreError("牧场组运行控制记录不存在")
            current_revision = int(row["selection_revision"])
            if (
                expected_selection_revision is not None
                and expected_selection_revision != current_revision
            ):
                raise SelectionRevisionMismatchError(
                    expected_selection_revision,
                    current_revision,
                )
            if (
                row["lease_token"]
                and row["lease_expires_at"]
                and str(row["lease_expires_at"]) > timestamp
            ):
                return None

            connection.execute(
                """
                UPDATE group_run_control
                SET lease_token = ?, lease_owner_id = ?,
                    lease_run_kind = ?,
                    lease_selection_revision = ?,
                    lease_acquired_at = ?, lease_heartbeat_at = ?,
                    lease_expires_at = ?, updated_at = ?
                WHERE singleton_id = 1
                """,
                (
                    lease_token,
                    owner,
                    kind,
                    current_revision,
                    timestamp,
                    timestamp,
                    expires_at,
                    timestamp,
                ),
            )
            refreshed = connection.execute(
                """
                SELECT * FROM group_run_control
                WHERE singleton_id = 1
                """
            ).fetchone()
            assert refreshed is not None
            return self._lease_from_control_row(refreshed)

    def refresh_run_lease(
        self,
        lease_token: str,
        *,
        lease_seconds: float = 300,
        at: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """刷新仍有效且令牌匹配的租约；失效或不匹配时返回 ``None``。"""

        token = str(lease_token).strip()
        if not token:
            raise ValueError("lease_token 不能为空")
        _, _, duration = self._validate_lease_arguments(
            "lease-owner",
            "lease-refresh",
            lease_seconds,
        )
        current = _as_utc_datetime(at)
        timestamp = _utc_timestamp(current)
        expires_at = _utc_timestamp(
            current + timedelta(seconds=duration)
        )

        with self._transaction() as connection:
            row = connection.execute(
                """
                SELECT * FROM group_run_control
                WHERE singleton_id = 1
                """
            ).fetchone()
            if row is None:
                raise GroupTaskStoreError("牧场组运行控制记录不存在")
            if (
                row["lease_token"] != token
                or not row["lease_expires_at"]
                or str(row["lease_expires_at"]) <= timestamp
            ):
                return None
            connection.execute(
                """
                UPDATE group_run_control
                SET lease_heartbeat_at = ?, lease_expires_at = ?,
                    updated_at = ?
                WHERE singleton_id = 1 AND lease_token = ?
                """,
                (timestamp, expires_at, timestamp, token),
            )
            refreshed = connection.execute(
                """
                SELECT * FROM group_run_control
                WHERE singleton_id = 1
                """
            ).fetchone()
            assert refreshed is not None
            return self._lease_from_control_row(refreshed)

    def release_run_lease(
        self,
        lease_token: str,
        *,
        at: Optional[datetime] = None,
    ) -> bool:
        """按令牌释放运行租约；令牌不匹配时不影响当前租约。"""

        token = str(lease_token).strip()
        if not token:
            raise ValueError("lease_token 不能为空")
        timestamp = _utc_timestamp(at)
        with self._transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE group_run_control
                SET lease_token = NULL, lease_owner_id = NULL,
                    lease_run_kind = NULL,
                    lease_selection_revision = NULL,
                    lease_acquired_at = NULL, lease_heartbeat_at = NULL,
                    lease_expires_at = NULL, updated_at = ?
                WHERE singleton_id = 1 AND lease_token = ?
                """,
                (timestamp, token),
            )
            return cursor.rowcount == 1

    def update_stage(
        self,
        task_id: str,
        stage: str,
        *,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        error: Any = _UNSET,
        output_path: Optional[str] = None,
        detail_count: Optional[int] = None,
        at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """原子更新阶段，并重新计算任务总状态和总进度。"""

        stage = _validate_stage_names((stage,))[0]
        if status is not None and status not in STAGE_STATUSES:
            raise ValueError(f"不支持的阶段状态: {status}")
        if progress is not None and not 0 <= float(progress) <= 100:
            raise ValueError("progress 必须在 0 到 100 之间")
        if detail_count is not None and int(detail_count) < 0:
            raise ValueError("detail_count 不能为负数")

        timestamp = _utc_timestamp(at)
        with self._transaction() as connection:
            task_row = connection.execute(
                "SELECT * FROM group_tasks WHERE task_id = ?",
                (str(task_id),),
            ).fetchone()
            if task_row is None:
                raise TaskNotFoundError(f"找不到牧场组任务: {task_id}")
            stage_row = connection.execute(
                """
                SELECT * FROM group_task_stages
                WHERE task_id = ? AND stage = ?
                """,
                (str(task_id), stage),
            ).fetchone()
            if stage_row is None:
                raise GroupTaskStoreError(
                    f"任务 {task_id} 缺少阶段记录: {stage}"
                )

            values: Dict[str, Any] = {"updated_at": timestamp}
            if status is not None:
                values["status"] = status
                if status == "running":
                    values["started_at"] = stage_row["started_at"] or timestamp
                    values["completed_at"] = None
                    if stage_row["status"] != "running":
                        values["attempt"] = int(stage_row["attempt"]) + 1
                elif status in {
                    "completed",
                    "completed_with_warning",
                    "skipped",
                }:
                    values["progress"] = 100
                    values["completed_at"] = timestamp
                    values["error"] = ""
                elif status == "pending":
                    values.update(
                        progress=0,
                        error="",
                        started_at=None,
                        completed_at=None,
                    )
                else:
                    values["completed_at"] = None
            if progress is not None:
                values["progress"] = float(progress)
            if error is not _UNSET:
                values["error"] = str(error or "")
            if output_path is not None:
                values["output_path"] = str(output_path)
            if detail_count is not None:
                values["detail_count"] = int(detail_count)

            assignments = ", ".join(f"{column} = ?" for column in values)
            connection.execute(
                f"""
                UPDATE group_task_stages
                SET {assignments}
                WHERE task_id = ? AND stage = ?
                """,
                [*values.values(), str(task_id), stage],
            )
            self._refresh_task_state(
                connection,
                str(task_id),
                touched_stage=stage,
                timestamp=timestamp,
            )

        task = self.get_task(task_id)
        assert task is not None
        return task

    def _refresh_task_state(
        self,
        connection: sqlite3.Connection,
        task_id: str,
        *,
        touched_stage: str,
        timestamp: str,
    ) -> None:
        task = connection.execute(
            "SELECT * FROM group_tasks WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        stages = connection.execute(
            """
            SELECT * FROM group_task_stages
            WHERE task_id = ? AND required = 1
            ORDER BY CASE stage
                WHEN 'data' THEN 1
                WHEN 'analysis' THEN 2
                WHEN 'child_excel' THEN 3
                ELSE 99
            END
            """,
            (task_id,),
        ).fetchall()
        if task is None or not stages:
            raise GroupTaskStoreError(f"任务阶段数据不完整: {task_id}")

        statuses = [row["status"] for row in stages]
        if "failed" in statuses:
            overall_status = "failed"
        elif "stale" in statuses:
            overall_status = "stale"
        elif "interrupted" in statuses:
            overall_status = "interrupted"
        elif "running" in statuses:
            overall_status = "running"
        elif all(
            value in {"completed", "completed_with_warning"}
            for value in statuses
        ):
            overall_status = (
                "completed_with_warning"
                if "completed_with_warning" in statuses
                else "completed"
            )
        else:
            overall_status = "pending"

        overall_progress = sum(float(row["progress"]) for row in stages) / len(
            stages
        )
        active = next(
            (
                row["stage"]
                for row in stages
                if row["status"] in {
                    "running",
                    "failed",
                    "interrupted",
                    "stale",
                }
            ),
            None,
        )
        if active is None:
            active = next(
                (
                    row["stage"]
                    for row in stages
                    if row["status"]
                    not in {"completed", "completed_with_warning"}
                ),
                None,
            )
        if overall_status in {"completed", "completed_with_warning"}:
            active = None

        stage_error = next(
            (
                str(row["error"] or "")
                for row in stages
                if row["status"] in {"failed", "interrupted", "stale"}
                and row["error"]
            ),
            "",
        )
        started_at = task["started_at"]
        attempt = int(task["attempt"])
        heartbeat_at = task["heartbeat_at"]
        if overall_status == "running":
            started_at = started_at or timestamp
            heartbeat_at = timestamp
            if task["status"] != "running":
                attempt += 1

        connection.execute(
            """
            UPDATE group_tasks
            SET status = ?, current_stage = ?, progress = ?, attempt = ?,
                error = ?, updated_at = ?, started_at = ?,
                completed_at = ?, heartbeat_at = ?
            WHERE task_id = ?
            """,
            (
                overall_status,
                active or touched_stage if overall_status != "completed" else None,
                overall_progress,
                attempt,
                stage_error,
                timestamp,
                started_at,
                timestamp
                if overall_status in {"completed", "completed_with_warning"}
                else None,
                heartbeat_at,
                task_id,
            ),
        )

    def heartbeat(
        self,
        task_id: str,
        *,
        stage: Optional[str] = None,
        progress: Optional[float] = None,
        at: Optional[datetime] = None,
    ) -> None:
        """刷新运行任务心跳，不改变执行状态。"""

        if stage is not None:
            stage = _validate_stage_names((stage,))[0]
        if progress is not None and not 0 <= float(progress) <= 100:
            raise ValueError("progress 必须在 0 到 100 之间")
        timestamp = _utc_timestamp(at)

        with self._transaction() as connection:
            task_row = connection.execute(
                "SELECT task_id FROM group_tasks WHERE task_id = ?",
                (str(task_id),),
            ).fetchone()
            if task_row is None:
                raise TaskNotFoundError(f"找不到牧场组任务: {task_id}")

            task_values: Dict[str, Any] = {
                "heartbeat_at": timestamp,
                "updated_at": timestamp,
            }
            if progress is not None and stage is None:
                task_values["progress"] = float(progress)
            assignments = ", ".join(
                f"{column} = ?" for column in task_values
            )
            connection.execute(
                f"UPDATE group_tasks SET {assignments} WHERE task_id = ?",
                [*task_values.values(), str(task_id)],
            )

            if stage is not None:
                stage_values: Dict[str, Any] = {"updated_at": timestamp}
                if progress is not None:
                    stage_values["progress"] = float(progress)
                stage_assignments = ", ".join(
                    f"{column} = ?" for column in stage_values
                )
                cursor = connection.execute(
                    f"""
                    UPDATE group_task_stages
                    SET {stage_assignments}
                    WHERE task_id = ? AND stage = ?
                    """,
                    [*stage_values.values(), str(task_id), stage],
                )
                if cursor.rowcount != 1:
                    raise GroupTaskStoreError(
                        f"任务 {task_id} 缺少阶段记录: {stage}"
                    )

    def mark_stale(
        self,
        *,
        stale_after_seconds: float = 900,
        now: Optional[datetime] = None,
        message: str = "任务长时间无心跳，已标记为可重试",
    ) -> List[str]:
        """将超过心跳期限的运行任务及其运行阶段标记为 ``stale``。"""

        if stale_after_seconds < 0:
            raise ValueError("stale_after_seconds 不能为负数")
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        cutoff = _utc_timestamp(
            current.astimezone(timezone.utc)
            - timedelta(seconds=float(stale_after_seconds))
        )
        timestamp = _utc_timestamp(current)

        with self._transaction() as connection:
            rows = connection.execute(
                """
                SELECT task_id FROM group_tasks
                WHERE status = 'running'
                  AND COALESCE(
                        heartbeat_at, updated_at, started_at, created_at
                      ) < ?
                ORDER BY sort_order, task_id
                """,
                (cutoff,),
            ).fetchall()
            task_ids = [str(row["task_id"]) for row in rows]
            for task_id in task_ids:
                connection.execute(
                    """
                    UPDATE group_task_stages
                    SET status = 'stale', error = ?, updated_at = ?
                    WHERE task_id = ? AND status = 'running'
                    """,
                    (message, timestamp, task_id),
                )
                connection.execute(
                    """
                    UPDATE group_tasks
                    SET status = 'stale', error = ?, updated_at = ?,
                        completed_at = NULL
                    WHERE task_id = ?
                    """,
                    (message, timestamp, task_id),
                )
        return task_ids

    def set_required_stages(
        self,
        task_id: str,
        required_stages: Sequence[str],
    ) -> Dict[str, Any]:
        """原子调整一个任务的必需阶段集合。"""

        required = set(_validate_stage_names(required_stages))
        timestamp = _utc_timestamp()
        with self._transaction() as connection:
            task = connection.execute(
                "SELECT task_id FROM group_tasks WHERE task_id = ?",
                (str(task_id),),
            ).fetchone()
            if task is None:
                raise TaskNotFoundError(f"找不到牧场组任务: {task_id}")
            for stage in GROUP_TASK_STAGES:
                is_required = int(stage in required)
                if is_required:
                    connection.execute(
                        """
                        UPDATE group_task_stages
                        SET required = 1,
                            status = CASE
                                WHEN status = 'skipped' THEN 'pending'
                                ELSE status
                            END,
                            progress = CASE
                                WHEN status = 'skipped' THEN 0
                                ELSE progress
                            END,
                            completed_at = CASE
                                WHEN status = 'skipped' THEN NULL
                                ELSE completed_at
                            END,
                            updated_at = ?
                        WHERE task_id = ? AND stage = ?
                        """,
                        (timestamp, str(task_id), stage),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE group_task_stages
                        SET required = 0, status = 'skipped', progress = 100,
                            error = '', completed_at = ?, updated_at = ?
                        WHERE task_id = ? AND stage = ?
                        """,
                        (timestamp, timestamp, str(task_id), stage),
                    )
            self._refresh_task_state(
                connection,
                str(task_id),
                touched_stage=min(
                    required,
                    key=GROUP_TASK_STAGES.index,
                ),
                timestamp=timestamp,
            )

        task_data = self.get_task(task_id)
        assert task_data is not None
        return task_data

    def reset_for_retry(
        self,
        task_id: str,
        *,
        from_stage: Optional[str] = None,
    ) -> Dict[str, Any]:
        """将失败或中断任务从指定阶段起恢复为待处理。"""

        if from_stage is not None:
            from_stage = _validate_stage_names((from_stage,))[0]
        timestamp = _utc_timestamp()
        with self._transaction() as connection:
            task = connection.execute(
                "SELECT * FROM group_tasks WHERE task_id = ?",
                (str(task_id),),
            ).fetchone()
            if task is None:
                raise TaskNotFoundError(f"找不到牧场组任务: {task_id}")

            stages = connection.execute(
                """
                SELECT * FROM group_task_stages
                WHERE task_id = ?
                ORDER BY CASE stage
                    WHEN 'data' THEN 1
                    WHEN 'analysis' THEN 2
                    WHEN 'child_excel' THEN 3
                    ELSE 99
                END
                """,
                (str(task_id),),
            ).fetchall()
            if from_stage is None:
                retry_stage = next(
                    (
                        row["stage"]
                        for row in stages
                        if row["required"]
                        and row["status"]
                        in {"failed", "interrupted", "stale", "running"}
                    ),
                    next(
                        (
                            row["stage"]
                            for row in stages
                            if row["required"]
                            and row["status"]
                            not in {"completed", "completed_with_warning"}
                        ),
                        None,
                    ),
                )
            else:
                retry_stage = from_stage
            if retry_stage is None:
                return self._task_from_row(connection, task, True)

            start_index = GROUP_TASK_STAGES.index(retry_stage)
            for row in stages:
                stage = row["stage"]
                if not row["required"]:
                    continue
                if GROUP_TASK_STAGES.index(stage) >= start_index:
                    connection.execute(
                        """
                        UPDATE group_task_stages
                        SET status = 'pending', progress = 0, error = '',
                            output_path = '', detail_count = NULL,
                            started_at = NULL, completed_at = NULL,
                            updated_at = ?
                        WHERE task_id = ? AND stage = ?
                        """,
                        (timestamp, str(task_id), stage),
                    )
            connection.execute(
                """
                UPDATE group_tasks
                SET status = 'pending', current_stage = ?, progress = 0,
                    error = '', completed_at = NULL, heartbeat_at = NULL,
                    updated_at = ?
                WHERE task_id = ?
                """,
                (retry_stage, timestamp, str(task_id)),
            )

        result = self.get_task(task_id)
        assert result is not None
        return result

    def completion_state(
        self,
        *,
        required_stages: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """返回汇总完成条件。

        只有 ``included_in_summary=1`` 的任务参与判断；执行失败但已排除的
        子任务会保留原始状态和目录，却不会阻塞最终汇总。
        """

        explicit_stages = (
            _validate_stage_names(required_stages)
            if required_stages is not None
            else None
        )
        tasks = self.list_tasks(with_stages=True)
        included = [task for task in tasks if task["included_in_summary"]]
        completed_ids: List[str] = []
        incomplete_ids: List[str] = []
        for task in included:
            stages = task["stages"]
            if explicit_stages is None:
                needed = [
                    name
                    for name in GROUP_TASK_STAGES
                    if stages[name]["required"]
                ]
            else:
                needed = list(explicit_stages)
            complete = bool(needed) and all(
                stages[name]["status"]
                in {"completed", "completed_with_warning"}
                for name in needed
            )
            (completed_ids if complete else incomplete_ids).append(
                task["task_id"]
            )

        status_counts = {
            status: sum(1 for task in included if task["status"] == status)
            for status in sorted(TASK_STATUSES)
        }
        return {
            "total_count": len(tasks),
            "included_count": len(included),
            "excluded_count": len(tasks) - len(included),
            "completed_count": len(completed_ids),
            "incomplete_count": len(incomplete_ids),
            "completed_task_ids": completed_ids,
            "incomplete_task_ids": incomplete_ids,
            "status_counts": status_counts,
            "required_stages": list(explicit_stages)
            if explicit_stages is not None
            else None,
            "is_complete": bool(included) and not incomplete_ids,
        }

    def is_complete(
        self,
        *,
        required_stages: Optional[Sequence[str]] = None,
    ) -> bool:
        return bool(
            self.completion_state(required_stages=required_stages)[
                "is_complete"
            ]
        )
