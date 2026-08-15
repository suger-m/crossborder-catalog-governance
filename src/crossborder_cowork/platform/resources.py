from __future__ import annotations

from typing import Any, Iterable

from ..util import json_dumps, json_loads, new_id, utc_now
from .database import Database


RESOURCE_STATES = {"candidate", "active", "superseded", "blocked", "rejected"}


class ProjectResourceAccessError(ValueError):
    """A protocol-safe project ownership failure."""


class ProjectResourceService:
    """Index durable business resources without copying their payloads."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create(
        self,
        *,
        project_id: str,
        resource_type: str,
        logical_key: str,
        owner_worker_name: str,
        source_task_id: str,
        storage_kind: str,
        storage_ref: str,
        source_step_id: str = "",
        version: int | None = None,
        status: str = "candidate",
        metadata: dict[str, Any] | None = None,
        resource_id: str = "",
    ) -> dict[str, Any]:
        project_id = self._required(project_id, "project_id")
        resource_type = self._required(resource_type, "resource_type")
        logical_key = self._required(logical_key, "logical_key")
        source_task_id = self._required(source_task_id, "source_task_id")
        storage_kind = self._required(storage_kind, "storage_kind")
        storage_ref = self._required(storage_ref, "storage_ref")
        self._validate_status(status)
        now = utc_now()

        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            task = conn.execute(
                "SELECT project_id FROM tasks WHERE id=?", (source_task_id,),
            ).fetchone()
            if not task:
                raise KeyError(f"Task not found: {source_task_id}")
            if task["project_id"] != project_id:
                raise ProjectResourceAccessError("Source task does not belong to this project")
            if source_step_id:
                step = conn.execute(
                    "SELECT task_id FROM task_steps WHERE id=?", (source_step_id,),
                ).fetchone()
                if not step or step["task_id"] != source_task_id:
                    raise ProjectResourceAccessError("Source step does not belong to the source task")

            if version is None:
                row = conn.execute(
                    """SELECT COALESCE(MAX(version), 0) AS version FROM project_resources
                       WHERE project_id=? AND resource_type=? AND logical_key=?""",
                    (project_id, resource_type, logical_key),
                ).fetchone()
                resolved_version = int(row["version"] or 0) + 1
            else:
                resolved_version = int(version)
                if resolved_version < 1:
                    raise ValueError("Resource version must be positive")

            if status == "active":
                conn.execute(
                    """UPDATE project_resources SET status='superseded',updated_at=?
                       WHERE project_id=? AND resource_type=? AND logical_key=? AND status='active'""",
                    (now, project_id, resource_type, logical_key),
                )
            record = {
                "id": resource_id or new_id("res"),
                "project_id": project_id,
                "resource_type": resource_type,
                "logical_key": logical_key,
                "owner_worker_name": str(owner_worker_name).strip(),
                "source_task_id": source_task_id,
                "source_step_id": str(source_step_id).strip(),
                "storage_kind": storage_kind,
                "storage_ref": storage_ref,
                "version": resolved_version,
                "status": status,
                "metadata": dict(metadata or {}),
                "created_at": now,
                "updated_at": now,
            }
            conn.execute(
                """INSERT INTO project_resources(
                       id,project_id,resource_type,logical_key,owner_worker_name,
                       source_task_id,source_step_id,storage_kind,storage_ref,version,
                       status,metadata_json,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record["id"], project_id, resource_type, logical_key,
                    record["owner_worker_name"], source_task_id, record["source_step_id"],
                    storage_kind, storage_ref, resolved_version, status,
                    json_dumps(record["metadata"]), now, now,
                ),
            )
        return record

    def get(self, resource_id: str, project_id: str) -> dict[str, Any]:
        row = self.db.fetchone("SELECT * FROM project_resources WHERE id=?", (resource_id,))
        if not row:
            raise KeyError(f"Project resource not found: {resource_id}")
        if row["project_id"] != project_id:
            raise ProjectResourceAccessError("Resource does not belong to this project")
        return self._decode(row)

    def list(
        self,
        project_id: str,
        *,
        resource_types: Iterable[str] | None = None,
        statuses: Iterable[str] | None = None,
        owner_worker_name: str = "",
        source_task_id: str = "",
        source_step_id: str = "",
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        clauses = ["project_id=?"]
        params: list[object] = [project_id]
        type_list = self._values(resource_types)
        status_list = self._values(statuses)
        for status in status_list:
            self._validate_status(status)
        if type_list:
            clauses.append(f"resource_type IN ({','.join('?' for _ in type_list)})")
            params.extend(type_list)
        if status_list:
            clauses.append(f"status IN ({','.join('?' for _ in status_list)})")
            params.extend(status_list)
        for column, value in (
            ("owner_worker_name", owner_worker_name),
            ("source_task_id", source_task_id),
            ("source_step_id", source_step_id),
        ):
            if value:
                clauses.append(f"{column}=?")
                params.append(value)
        params.append(min(max(int(limit), 1), 2000))
        rows = self.db.fetchall(
            f"""SELECT * FROM project_resources WHERE {' AND '.join(clauses)}
                ORDER BY resource_type,logical_key,version DESC,created_at DESC LIMIT ?""",
            params,
        )
        return [self._decode(row) for row in rows]

    def resolve(
        self,
        project_id: str,
        *,
        resource_types: Iterable[str] | None = None,
        explicit_resource_ids: Iterable[str] | None = None,
        upstream_step_ids: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        type_set = set(self._values(resource_types))
        explicit_ids = self._values(explicit_resource_ids)
        if explicit_ids:
            items = [self.get(resource_id, project_id) for resource_id in explicit_ids]
            return [item for item in items if not type_set or item["resource_type"] in type_set]

        step_ids = self._values(upstream_step_ids)
        if step_ids:
            placeholders = ",".join("?" for _ in step_ids)
            rows = self.db.fetchall(
                f"""SELECT * FROM project_resources
                    WHERE project_id=? AND source_step_id IN ({placeholders})
                    ORDER BY created_at,version""",
                (project_id, *step_ids),
            )
            items = [self._decode(row) for row in rows]
            items = [item for item in items if not type_set or item["resource_type"] in type_set]
            if items:
                return items

        return self.list(
            project_id,
            resource_types=type_set or None,
            statuses=("active",),
        )

    def activate(self, resource_id: str, project_id: str) -> dict[str, Any]:
        now = utc_now()
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM project_resources WHERE id=?", (resource_id,)).fetchone()
            if not row:
                raise KeyError(f"Project resource not found: {resource_id}")
            if row["project_id"] != project_id:
                raise ProjectResourceAccessError("Resource does not belong to this project")
            if row["status"] in {"blocked", "rejected"}:
                raise ValueError(f"Cannot activate a {row['status']} resource")
            conn.execute(
                """UPDATE project_resources SET status='superseded',updated_at=?
                   WHERE project_id=? AND resource_type=? AND logical_key=?
                     AND status='active' AND id<>?""",
                (now, project_id, row["resource_type"], row["logical_key"], resource_id),
            )
            conn.execute(
                "UPDATE project_resources SET status='active',updated_at=? WHERE id=?",
                (now, resource_id),
            )
        return self.get(resource_id, project_id)

    def set_status(self, resource_id: str, project_id: str, status: str) -> dict[str, Any]:
        self._validate_status(status)
        if status == "active":
            return self.activate(resource_id, project_id)
        self.get(resource_id, project_id)
        self.db.execute(
            "UPDATE project_resources SET status=?,updated_at=? WHERE id=?",
            (status, utc_now(), resource_id),
        )
        return self.get(resource_id, project_id)

    @staticmethod
    def _decode(row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        item["metadata"] = json_loads(item.pop("metadata_json"), {})
        return item

    @staticmethod
    def _required(value: str, field: str) -> str:
        result = str(value).strip()
        if not result:
            raise ValueError(f"{field} is required")
        return result

    @staticmethod
    def _values(values: Iterable[str] | None) -> list[str]:
        if isinstance(values, str):
            values = [values]
        return list(dict.fromkeys(str(value).strip() for value in (values or []) if str(value).strip()))

    @staticmethod
    def _validate_status(status: str) -> None:
        if status not in RESOURCE_STATES:
            raise ValueError(f"Invalid project resource status: {status}")
