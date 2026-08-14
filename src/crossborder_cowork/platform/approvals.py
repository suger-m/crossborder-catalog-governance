from __future__ import annotations

from typing import Any

from ..util import json_dumps, json_loads, new_id, utc_now
from .database import Database
from .events import EventStore


class ApprovalService:
    def __init__(self, db: Database, events: EventStore) -> None:
        self.db = db
        self.events = events

    def create(self, task_id: str, approval_type: str, title: str, description: str, payload: dict[str, Any]) -> dict:
        if not self.db.fetchone("SELECT id FROM tasks WHERE id=?", (task_id,)):
            raise KeyError(f"Task not found: {task_id}")
        existing = self.db.fetchone(
            "SELECT * FROM approvals WHERE task_id=? AND approval_type=? AND payload_json=? AND status='pending'",
            (task_id, approval_type, json_dumps(payload)),
        )
        if existing:
            return self._decode(existing)
        approval = {
            "id": new_id("apr"), "task_id": task_id, "approval_type": approval_type,
            "title": title, "description": description, "payload": payload,
            "status": "pending", "decision": {}, "created_at": utc_now(), "decided_at": None,
        }
        self.db.execute(
            "INSERT INTO approvals VALUES(?,?,?,?,?,?,?,?,?,?)",
            (approval["id"], task_id, approval_type, title, description, json_dumps(payload), "pending", "{}", approval["created_at"], None),
        )
        self.events.publish(task_id, "approval.requested", "human_approval", {"approval": approval})
        return approval

    def decide(self, approval_id: str, status: str, decision: dict[str, Any]) -> dict:
        if status not in {"approved", "rejected"}:
            raise ValueError("Approval status must be approved or rejected")
        decided_at = utc_now()
        self.db.execute(
            "UPDATE approvals SET status=?,decision_json=?,decided_at=? WHERE id=? AND status='pending'",
            (status, json_dumps(decision), decided_at, approval_id),
        )
        approval = self.get(approval_id)
        if not approval:
            raise KeyError(approval_id)
        self.events.publish(approval["task_id"], "approval.decided", "human_approval", {"approval": approval})
        return approval

    def get(self, approval_id: str) -> dict | None:
        row = self.db.fetchone("SELECT * FROM approvals WHERE id=?", (approval_id,))
        return self._decode(row) if row else None

    def list(self, task_id: str) -> list[dict]:
        return [self._decode(row) for row in self.db.fetchall("SELECT * FROM approvals WHERE task_id=? ORDER BY created_at", (task_id,))]

    @staticmethod
    def _decode(row: dict) -> dict:
        row = dict(row)
        row["payload"] = json_loads(row.pop("payload_json"), {})
        row["decision"] = json_loads(row.pop("decision_json"), {})
        return row
