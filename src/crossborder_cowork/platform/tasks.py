from __future__ import annotations

from typing import Any

from ..util import json_dumps, json_loads, new_id, utc_now
from .database import Database
from .events import EventStore


TASK_STATUSES = {"queued", "running", "paused", "completed", "failed", "cancelled"}


class TaskService:
    """Deterministic project/task persistence; worker execution arrives in later tasks."""

    def __init__(self, db: Database, events: EventStore) -> None:
        self.db = db
        self.events = events

    def create_project(self, name: str) -> dict[str, Any]:
        name = str(name).strip()
        if not name:
            raise ValueError("Project name is required")
        timestamp = utc_now()
        project = {"id": new_id("prj"), "name": name, "created_at": timestamp, "updated_at": timestamp}
        self.db.execute("INSERT INTO projects VALUES(?,?,?,?)", tuple(project.values()))
        return project

    def list_projects(self) -> list[dict[str, Any]]:
        return self.db.fetchall("SELECT * FROM projects ORDER BY updated_at DESC, created_at DESC")

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        return self.db.fetchone("SELECT * FROM projects WHERE id=?", (project_id,))

    def create_task(
        self, project_id: str, objective: str, input_data: dict[str, Any] | None = None, steps: list[dict[str, str]] | None = None
    ) -> dict[str, Any]:
        if not self.get_project(project_id):
            raise KeyError(f"Project not found: {project_id}")
        objective = str(objective).strip()
        if not objective:
            raise ValueError("Task objective is required")
        timestamp = utc_now()
        task = {
            "id": new_id("tsk"), "project_id": project_id, "objective": objective, "status": "queued",
            "current_step": "", "input": input_data or {}, "result": {}, "error": "",
            "created_at": timestamp, "updated_at": timestamp,
        }
        self.db.execute(
            "INSERT INTO tasks(id,project_id,objective,status,current_step,input_json,result_json,error,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (task["id"], project_id, objective, "queued", "", json_dumps(task["input"]), "{}", "", timestamp, timestamp),
        )
        for sequence, step in enumerate(steps or [], start=1):
            self._add_step(task["id"], sequence, step)
        self.events.publish(task["id"], "task.created", "platform", {"task": self._task_public(task)})
        return self.get_task(task["id"])

    def _add_step(self, task_id: str, sequence: int, step: dict[str, str]) -> None:
        title = str(step.get("title") or "").strip()
        if not title:
            raise ValueError("Task step title is required")
        worker_name = str(step.get("worker_name") or "platform").strip() or "platform"
        self.db.execute(
            "INSERT INTO task_steps(id,task_id,sequence,worker_name,title,status,result_json,started_at,completed_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (new_id("step"), task_id, sequence, worker_name, title, "queued", "{}", None, None),
        )

    def list_tasks(self, project_id: str | None = None) -> list[dict[str, Any]]:
        if project_id:
            rows = self.db.fetchall("SELECT * FROM tasks WHERE project_id=? ORDER BY created_at DESC", (project_id,))
        else:
            rows = self.db.fetchall("SELECT * FROM tasks ORDER BY created_at DESC")
        return [self._decode_task(row) for row in rows]

    def get_task(self, task_id: str) -> dict[str, Any]:
        row = self.db.fetchone("SELECT * FROM tasks WHERE id=?", (task_id,))
        if not row:
            raise KeyError(f"Task not found: {task_id}")
        task = self._decode_task(row)
        steps = self.db.fetchall("SELECT * FROM task_steps WHERE task_id=? ORDER BY sequence", (task_id,))
        task["steps"] = [self._decode_step(step) for step in steps]
        return task

    def update_status(self, task_id: str, status: str, result: dict[str, Any] | None = None, error: str = "") -> dict[str, Any]:
        if status not in TASK_STATUSES:
            raise ValueError(f"Invalid task status: {status}")
        task = self.get_task(task_id)
        timestamp = utc_now()
        self.db.execute(
            "UPDATE tasks SET status=?,result_json=?,error=?,updated_at=? WHERE id=?",
            (status, json_dumps(result if result is not None else task["result"]), str(error), timestamp, task_id),
        )
        updated = self.get_task(task_id)
        self.events.publish(task_id, "task.status_changed", "platform", {"task": self._task_public(updated)})
        return updated

    def detail(self, task_id: str, artifacts: Any, approvals: Any) -> dict[str, Any]:
        task = self.get_task(task_id)
        return {
            "task": task,
            "events": self.events.list_after(task_id),
            "artifacts": artifacts.list(task_id),
            "approvals": approvals.list(task_id),
        }

    @staticmethod
    def _decode_task(row: dict[str, Any]) -> dict[str, Any]:
        task = dict(row)
        task["input"] = json_loads(task.pop("input_json"), {})
        task["result"] = json_loads(task.pop("result_json"), {})
        return task

    @staticmethod
    def _decode_step(row: dict[str, Any]) -> dict[str, Any]:
        step = dict(row)
        step["result"] = json_loads(step.pop("result_json"), {})
        return step

    @staticmethod
    def _task_public(task: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in task.items() if key not in {"input", "result", "steps"}}
