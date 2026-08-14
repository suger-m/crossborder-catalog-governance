from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..util import json_dumps, json_loads, new_id, safe_name, sha256_file, utc_now
from .database import Database
from .events import EventStore


class ArtifactService:
    def __init__(self, db: Database, root: Path, events: EventStore) -> None:
        self.db = db
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.events = events

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
    ) -> dict:
        artifact_id = new_id("art")
        file_name = f"{safe_name(title)}-{artifact_id[-8:]}.{extension.lstrip('.')}"
        path = self._task_root(task_id) / file_name
        path.write_bytes(content)
        return self._record(task_id, worker_name, artifact_type, title, path, mime_type, dependencies, metadata)

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
    ) -> dict:
        artifact_id = new_id("art")
        file_name = f"{safe_name(source.stem)}-{artifact_id[-8:]}{source.suffix.lower()}"
        path = self._task_root(task_id) / file_name
        shutil.copy2(source, path)
        return self._record(task_id, worker_name, artifact_type, title, path, mime_type, dependencies, metadata)

    def _record(self, task_id: str, worker_name: str, artifact_type: str, title: str, path: Path, mime_type: str, dependencies: list[str] | None, metadata: dict[str, Any] | None) -> dict:
        if not self.db.fetchone("SELECT id FROM tasks WHERE id=?", (task_id,)):
            raise KeyError(f"Task not found: {task_id}")
        sha256, size = sha256_file(path)
        artifact = {
            "id": new_id("artrec"),
            "task_id": task_id,
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
            "metadata": metadata or {},
            "created_at": utc_now(),
        }
        self.db.execute(
            "INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                artifact["id"], task_id, worker_name, artifact_type, title, path.name,
                str(path), artifact["relative_path"], mime_type, size, sha256,
                json_dumps(artifact["dependency_ids"]), json_dumps(artifact["metadata"]), artifact["created_at"],
            ),
        )
        self.events.publish(task_id, "artifact.created", worker_name, {"artifact": artifact})
        return artifact

    def list(self, task_id: str) -> list[dict]:
        rows = self.db.fetchall("SELECT * FROM artifacts WHERE task_id=? ORDER BY created_at", (task_id,))
        for row in rows:
            row["dependency_ids"] = json_loads(row.pop("dependency_ids_json"), [])
            row["metadata"] = json_loads(row.pop("metadata_json"), {})
        return rows

    def get(self, artifact_id: str) -> dict | None:
        row = self.db.fetchone("SELECT * FROM artifacts WHERE id=?", (artifact_id,))
        if row:
            row["dependency_ids"] = json_loads(row.pop("dependency_ids_json"), [])
            row["metadata"] = json_loads(row.pop("metadata_json"), {})
        return row
