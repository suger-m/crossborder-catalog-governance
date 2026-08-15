from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..util import json_dumps, json_loads, new_id, safe_name, sha256_file, utc_now
from .database import Database
from .events import EventStore
from .execution_context import current_execution_context
from .resources import ProjectResourceService


class ArtifactService:
    MAX_TEXT_PAGE_CHARS = 64 * 1024

    def __init__(self, db: Database, root: Path, events: EventStore, resources: ProjectResourceService | None = None) -> None:
        self.db = db
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.events = events
        self.resources = resources or ProjectResourceService(db)

    def set_resource_service(self, resources: ProjectResourceService) -> None:
        self.resources = resources

    def _task_root(self, task_id: str) -> Path:
        target = (self.root / safe_name(task_id)).resolve()
        target.relative_to(self.root)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def create_bytes(
        self,
        task_id: str,
        worker_name: str,
        artifact_type: str,
        title: str,
        content: bytes,
        extension: str,
        mime_type: str,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        process_task_id: str = "",
    ) -> dict:
        artifact_id = new_id("art")
        file_name = f"{safe_name(title)}-{artifact_id[-8:]}.{extension.lstrip('.')}"
        path = self._task_root(task_id) / file_name
        path.write_bytes(content)
        return self._record(task_id, worker_name, artifact_type, title, path, mime_type, dependencies, metadata, process_task_id)

    def create_text(self, *args: Any, content: str, **kwargs: Any) -> dict:
        return self.create_bytes(*args, content=content.encode("utf-8"), **kwargs)

    def import_file(
        self,
        task_id: str,
        worker_name: str,
        artifact_type: str,
        title: str,
        source: Path,
        mime_type: str,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        process_task_id: str = "",
    ) -> dict:
        source_sha256, source_size = sha256_file(source)
        existing = self.db.fetchone(
            """SELECT * FROM artifacts WHERE task_id=? AND worker_name=? AND artifact_type=?
               AND title=? AND sha256=? AND size_bytes=? ORDER BY created_at DESC LIMIT 1""",
            (task_id, worker_name, artifact_type, title, source_sha256, source_size),
        )
        if existing:
            return self._decode(existing)
        artifact_id = new_id("art")
        file_name = f"{safe_name(source.stem)}-{artifact_id[-8:]}{source.suffix.lower()}"
        path = self._task_root(task_id) / file_name
        shutil.copy2(source, path)
        return self._record(task_id, worker_name, artifact_type, title, path, mime_type, dependencies, metadata, process_task_id)

    def _record(self, task_id: str, worker_name: str, artifact_type: str, title: str, path: Path, mime_type: str, dependencies: list[str] | None, metadata: dict[str, Any] | None, process_task_id: str = "") -> dict:
        task = self.db.fetchone("SELECT id,project_id FROM tasks WHERE id=?", (task_id,))
        if not task:
            raise KeyError(f"Task not found: {task_id}")
        execution = current_execution_context(required=False)
        if execution and execution.task_id == task_id:
            process_task_id = process_task_id or execution.process_task_id
        metadata_value = dict(metadata or {})
        process_task_id = str(process_task_id or metadata_value.get("worker_task_id") or task_id)
        if process_task_id != task_id:
            step = self.db.fetchone("SELECT task_id,worker_name FROM task_steps WHERE id=?", (process_task_id,))
            if not step or step["task_id"] != task_id or step["worker_name"] != worker_name:
                raise ValueError("Artifact process task does not belong to this Worker task")
        sha256, size = sha256_file(path)
        artifact = {
            "id": new_id("artrec"),
            "task_id": task_id,
            "project_id": task["project_id"],
            "process_task_id": process_task_id,
            "worker_name": worker_name,
            "artifact_type": artifact_type,
            "title": title,
            "file_name": path.name,
            "absolute_path": str(path),
            "relative_path": path.relative_to(self.root).as_posix(),
            "mime_type": mime_type,
            "size_bytes": size,
            "sha256": sha256,
            "dependency_ids": dependencies or [],
            "metadata": metadata_value,
            "created_at": utc_now(),
        }
        self.db.execute(
            """INSERT INTO artifacts(
                   id,task_id,project_id,process_task_id,worker_name,artifact_type,title,
                   file_name,absolute_path,relative_path,mime_type,size_bytes,sha256,
                   dependency_ids_json,metadata_json,created_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                artifact["id"], task_id, artifact["project_id"], process_task_id,
                worker_name, artifact_type, title, path.name,
                str(path), artifact["relative_path"], mime_type, size, sha256,
                json_dumps(artifact["dependency_ids"]), json_dumps(artifact["metadata"]), artifact["created_at"],
            ),
        )
        try:
            resource = self.resources.create(
                project_id=artifact["project_id"],
                resource_type=artifact_type,
                logical_key=str(metadata_value.get("logical_key") or title or artifact_type),
                owner_worker_name=worker_name,
                source_task_id=task_id,
                source_step_id="" if process_task_id == task_id else process_task_id,
                storage_kind="artifact",
                storage_ref=artifact["id"],
                status=str(metadata_value.get("resource_status") or "active"),
                metadata={
                    "artifact_id": artifact["id"], "title": title, "file_name": path.name,
                    "mime_type": mime_type, "size_bytes": size, "sha256": sha256,
                },
            )
        except Exception:
            self.db.execute("DELETE FROM artifacts WHERE id=?", (artifact["id"],))
            path.unlink(missing_ok=True)
            raise
        artifact["resource_id"] = resource["id"]
        artifact["metadata"]["resource_id"] = resource["id"]
        self.db.execute(
            "UPDATE artifacts SET metadata_json=? WHERE id=?",
            (json_dumps(artifact["metadata"]), artifact["id"]),
        )
        self.events.publish(
            task_id, "artifact.created", worker_name,
            {"artifact": artifact, "artifact_id": artifact["id"], "resource_id": resource["id"]},
        )
        return artifact

    def list(self, task_id: str) -> list[dict]:
        rows = self.db.fetchall("SELECT * FROM artifacts WHERE task_id=? ORDER BY created_at", (task_id,))
        for row in rows:
            row["dependency_ids"] = json_loads(row.pop("dependency_ids_json"), [])
            row["metadata"] = json_loads(row.pop("metadata_json"), {})
        return rows

    def list_project(self, project_id: str) -> list[dict]:
        rows = self.db.fetchall(
            "SELECT * FROM artifacts WHERE project_id=? ORDER BY created_at", (project_id,),
        )
        return [self._decode(row) for row in rows]

    def get(self, artifact_id: str, project_id: str = "") -> dict | None:
        row = self.db.fetchone("SELECT * FROM artifacts WHERE id=?", (artifact_id,))
        if row and project_id and row["project_id"] != project_id:
            raise ValueError("Artifact does not belong to this project")
        return self._decode(row) if row else None

    def manifest(self, artifact_id: str, project_id: str) -> dict[str, Any]:
        artifact = self.get(artifact_id, project_id)
        if not artifact:
            raise KeyError(f"Artifact not found: {artifact_id}")
        return {
            key: artifact[key]
            for key in (
                "id", "project_id", "task_id", "process_task_id", "worker_name",
                "artifact_type", "title", "file_name", "relative_path", "mime_type",
                "size_bytes", "sha256", "dependency_ids", "metadata", "created_at",
            )
        }

    def validated_path(self, artifact_id: str, project_id: str) -> Path:
        artifact = self.get(artifact_id, project_id)
        if not artifact:
            raise KeyError(f"Artifact not found: {artifact_id}")
        path = Path(artifact["absolute_path"]).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as error:
            raise ValueError("Artifact path is outside the artifact store") from error
        if not path.is_file():
            raise ValueError("Artifact file is unavailable")
        digest, size = sha256_file(path)
        if digest != artifact["sha256"] or size != artifact["size_bytes"]:
            raise ValueError("Artifact integrity check failed")
        return path

    def read_text(self, artifact_id: str, project_id: str, *, offset: int = 0, limit: int = 16_384) -> dict[str, Any]:
        artifact = self.get(artifact_id, project_id)
        if not artifact:
            raise KeyError(f"Artifact not found: {artifact_id}")
        mime_type = str(artifact["mime_type"]).lower()
        text_like = mime_type.startswith("text/") or mime_type in {
            "application/json", "application/ld+json", "application/xml",
            "application/yaml", "application/x-yaml",
        }
        if not text_like:
            raise ValueError("Artifact is binary and cannot be read as text")
        offset = max(0, int(offset))
        limit = min(max(1, int(limit)), self.MAX_TEXT_PAGE_CHARS)
        content = self.validated_path(artifact_id, project_id).read_text(encoding="utf-8")
        page = content[offset:offset + limit]
        next_offset = offset + len(page)
        return {
            "artifact_id": artifact_id,
            "content": page,
            "offset": offset,
            "next_offset": next_offset,
            "total_chars": len(content),
            "eof": next_offset >= len(content),
            "mime_type": artifact["mime_type"],
        }

    @staticmethod
    def _decode(row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        item["dependency_ids"] = json_loads(item.pop("dependency_ids_json"), [])
        item["metadata"] = json_loads(item.pop("metadata_json"), {})
        item["resource_id"] = str(item["metadata"].get("resource_id") or "")
        return item
