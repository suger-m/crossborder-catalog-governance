from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Any, Iterable

from ..util import json_dumps, json_loads, new_id, safe_name, sha256_file, utc_now
from .database import Database


ALLOWED_SUFFIXES = {".csv", ".json", ".jsonl", ".md", ".txt", ".xlsx", ".pdf", ".png", ".jpg", ".jpeg", ".webp"}
MAX_MATERIAL_BYTES = 50 * 1024 * 1024


class ProjectMaterialService:
    """Own durable project inputs and validated task-to-material bindings."""

    def __init__(self, db: Database, root: Path, example_root: Path) -> None:
        self.db = db
        self.root = Path(root).resolve()
        self.example_root = Path(example_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def list(self, project_id: str) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT * FROM project_materials WHERE project_id=? ORDER BY created_at, file_name",
            (project_id,),
        )
        return [self._public(row) for row in rows]

    def get(self, material_id: str) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT * FROM project_materials WHERE id=?", (material_id,))
        return self._decode(row) if row else None

    def validate_project_materials(self, project_id: str, material_ids: Iterable[str]) -> list[dict[str, Any]]:
        ordered_ids = list(dict.fromkeys(str(item).strip() for item in material_ids if str(item).strip()))
        if not ordered_ids:
            raise ValueError("Select at least one project material")
        placeholders = ",".join("?" for _ in ordered_ids)
        rows = self.db.fetchall(
            f"SELECT * FROM project_materials WHERE project_id=? AND id IN ({placeholders})",
            (project_id, *ordered_ids),
        )
        by_id = {row["id"]: row for row in rows}
        if any(item not in by_id for item in ordered_ids):
            raise ValueError("One or more selected materials do not belong to this project")
        return [self._decode(by_id[item]) for item in ordered_ids]

    def store_bytes(
        self,
        project_id: str,
        file_name: str,
        content: bytes,
        *,
        origin: str = "upload",
        mime_type: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.db.fetchone("SELECT id FROM projects WHERE id=?", (project_id,)):
            raise KeyError(f"Project not found: {project_id}")
        display_name = Path(str(file_name).replace("\\", "/")).name.strip()
        suffix = Path(display_name).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise ValueError(f"Unsupported material type: {suffix or 'unknown'}")
        display_name = "".join(character for character in display_name if ord(character) >= 32)[:180]
        clean_name = f"{safe_name(Path(display_name).stem, 'material')}{suffix}"
        if not content:
            raise ValueError("Material file is empty")
        if len(content) > MAX_MATERIAL_BYTES:
            raise ValueError("Material file exceeds the 50 MB limit")

        material_id = new_id("mat")
        folder = (self.root / project_id / material_id).resolve()
        folder.relative_to(self.root)
        folder.mkdir(parents=True, exist_ok=False)
        destination = folder / clean_name
        temporary = folder / f".{clean_name}.tmp"
        try:
            temporary.write_bytes(content)
            digest, size = sha256_file(temporary)
            existing = self.db.fetchone(
                "SELECT * FROM project_materials WHERE project_id=? AND sha256=?",
                (project_id, digest),
            )
            if existing:
                temporary.unlink(missing_ok=True)
                folder.rmdir()
                return self._public(existing)
            os.replace(temporary, destination)
            created_at = utc_now()
            relative_path = destination.relative_to(self.root).as_posix()
            row = {
                "id": material_id,
                "project_id": project_id,
                "file_name": display_name or clean_name,
                "absolute_path": str(destination),
                "relative_path": relative_path,
                "mime_type": mime_type or mimetypes.guess_type(clean_name)[0] or "application/octet-stream",
                "size_bytes": size,
                "sha256": digest,
                "origin": origin,
                "metadata_json": metadata or {},
                "created_at": created_at,
            }
            self.db.execute(
                """INSERT INTO project_materials(
                       id,project_id,file_name,absolute_path,relative_path,mime_type,
                       size_bytes,sha256,origin,metadata_json,created_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    row["id"], row["project_id"], row["file_name"], row["absolute_path"],
                    row["relative_path"], row["mime_type"], row["size_bytes"], row["sha256"],
                    row["origin"], json_dumps(row["metadata_json"]), row["created_at"],
                ),
            )
            return self._public(row)
        except Exception:
            temporary.unlink(missing_ok=True)
            if destination.exists():
                destination.unlink()
            if folder.exists() and not any(folder.iterdir()):
                folder.rmdir()
            raise

    def import_example(self, project_id: str) -> list[dict[str, Any]]:
        source = self.example_root / "womenswear-us" / "womenswear-catalog.csv"
        if not source.is_file():
            raise FileNotFoundError(f"Example material is unavailable: {source}")
        material = self.store_bytes(
            project_id,
            source.name,
            source.read_bytes(),
            origin="example",
            mime_type="text/csv",
            metadata={"example_set": "womenswear-us", "description": "美国市场女装商品目录示例"},
        )
        return [material]

    def bind_task(
        self,
        task_id: str,
        project_id: str,
        material_ids: Iterable[str],
        *,
        replace: bool = True,
    ) -> list[dict[str, Any]]:
        ordered_ids = list(dict.fromkeys(str(item).strip() for item in material_ids if str(item).strip()))
        if not ordered_ids:
            raise ValueError("Select at least one project material")
        task = self.db.fetchone("SELECT id,project_id FROM tasks WHERE id=?", (task_id,))
        if not task or task["project_id"] != project_id:
            raise ValueError("Task does not belong to the selected project")
        rows = self.validate_project_materials(project_id, ordered_ids)
        by_id = {row["id"]: row for row in rows}
        now = utc_now()
        with self.db.connect() as conn:
            if replace:
                conn.execute("DELETE FROM task_materials WHERE task_id=?", (task_id,))
            current = conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS sequence FROM task_materials WHERE task_id=?",
                (task_id,),
            ).fetchone()
            start = int(current["sequence"] or 0)
            for offset, material_id in enumerate(ordered_ids, start=1):
                conn.execute(
                    "INSERT OR IGNORE INTO task_materials(task_id,material_id,sequence,created_at) VALUES(?,?,?,?)",
                    (task_id, material_id, start + offset, now),
                )
        return [self._public(by_id[item]) for item in ordered_ids]

    def task_materials(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            """SELECT material.* FROM task_materials binding
               JOIN project_materials material ON material.id=binding.material_id
               WHERE binding.task_id=? ORDER BY binding.sequence""",
            (task_id,),
        )
        return [self._decode(row) for row in rows]

    def task_paths(self, task_id: str) -> list[str]:
        paths: list[str] = []
        for material in self.task_materials(task_id):
            path = Path(material["absolute_path"]).resolve()
            try:
                path.relative_to(self.root)
            except ValueError as error:
                raise ValueError("Material path is outside the project material store") from error
            if not path.is_file():
                raise ValueError(f"Project material is unavailable: {material['file_name']}")
            digest, size = sha256_file(path)
            if digest != material["sha256"] or size != material["size_bytes"]:
                raise ValueError(f"Project material integrity check failed: {material['file_name']}")
            paths.append(str(path))
        return paths

    @staticmethod
    def _decode(row: dict[str, Any]) -> dict[str, Any]:
        value = dict(row)
        raw_metadata = value.pop("metadata_json", {})
        value["metadata"] = raw_metadata if isinstance(raw_metadata, dict) else json_loads(raw_metadata, {})
        return value

    @classmethod
    def _public(cls, row: dict[str, Any]) -> dict[str, Any]:
        value = cls._decode(row)
        value.pop("absolute_path", None)
        return value
