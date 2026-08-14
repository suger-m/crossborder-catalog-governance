from __future__ import annotations

from typing import Any

from ..util import json_dumps, json_loads, new_id, utc_now
from .database import Database


class EventStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def publish(self, task_id: str, event_type: str, source: str, payload: dict[str, Any]) -> dict:
        event = {
            "id": new_id("evt"),
            "task_id": task_id,
            "event_type": event_type,
            "source": source,
            "payload": payload,
            "created_at": utc_now(),
        }
        with self.db.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO events(id,task_id,event_type,source,payload_json,created_at) VALUES(?,?,?,?,?,?)",
                (event["id"], task_id, event_type, source, json_dumps(payload), event["created_at"]),
            )
            event["sequence"] = cursor.lastrowid
        return event

    def list_after(self, task_id: str, after: int = 0, limit: int = 200) -> list[dict]:
        rows = self.db.fetchall(
            "SELECT * FROM events WHERE task_id=? AND sequence>? ORDER BY sequence LIMIT ?",
            (task_id, after, limit),
        )
        for row in rows:
            row["payload"] = json_loads(row.pop("payload_json"), {})
            row["worker_name"] = row["source"]
        return rows
