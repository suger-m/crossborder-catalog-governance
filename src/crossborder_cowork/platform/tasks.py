from __future__ import annotations

from typing import Any

from ..util import json_dumps, json_loads, new_id, utc_now
from .database import Database
from .events import EventStore


TASK_STATUSES = {"queued", "running", "waiting_approval", "blocked", "paused", "completed", "failed", "cancelled"}


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

    def create_step_from_workforce(
        self,
        task_id: str,
        process_task_id: str,
        title: str,
        *,
        worker_name: str = "workforce",
        dependencies: list[str] | None = None,
    ) -> dict[str, Any]:
        """Persist a CAMEL task without translating its task identifier."""
        self.get_task(task_id)
        process_task_id = str(process_task_id).strip()
        title = str(title).strip()
        if not process_task_id or not title:
            raise ValueError("Workforce task ID and title are required")
        existing = self.db.fetchone("SELECT * FROM task_steps WHERE id=?", (process_task_id,))
        if existing:
            if existing["task_id"] != task_id:
                raise ValueError(f"Workforce task ID already belongs to another task: {process_task_id}")
        else:
            row = self.db.fetchone(
                "SELECT COALESCE(MAX(sequence), 0) AS sequence FROM task_steps WHERE task_id=?",
                (task_id,),
            )
            sequence = int((row or {}).get("sequence") or 0) + 1
            self.db.execute(
                "INSERT INTO task_steps(id,task_id,sequence,worker_name,title,status,result_json,started_at,completed_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (process_task_id, task_id, sequence, worker_name, title, "queued", "{}", None, None),
            )
        if dependencies is not None:
            self.set_step_dependencies(task_id, process_task_id, dependencies)
        return self.get_step(process_task_id)

    def get_step(self, step_id: str) -> dict[str, Any]:
        row = self.db.fetchone("SELECT * FROM task_steps WHERE id=?", (step_id,))
        if not row:
            raise KeyError(f"Step not found: {step_id}")
        step = self._decode_step(row)
        dependencies = self.db.fetchall(
            "SELECT depends_on_step_id FROM task_step_dependencies WHERE step_id=? ORDER BY depends_on_step_id",
            (step_id,),
        )
        step["dependencies"] = [item["depends_on_step_id"] for item in dependencies]
        return step

    def set_step_dependencies(self, task_id: str, step_id: str, dependencies: list[str]) -> dict[str, Any]:
        step = self.get_step(step_id)
        if step["task_id"] != task_id:
            raise ValueError(f"Step does not belong to task {task_id}: {step_id}")
        dependency_ids = list(dict.fromkeys(str(item).strip() for item in dependencies if str(item).strip()))
        if step_id in dependency_ids:
            raise ValueError(f"Workforce dependency cycle at {step_id}")
        for dependency_id in dependency_ids:
            dependency = self.get_step(dependency_id)
            if dependency["task_id"] != task_id:
                raise ValueError(f"Dependency does not belong to task {task_id}: {dependency_id}")
        graph: dict[str, set[str]] = {}
        for row in self.db.fetchall(
            """SELECT d.step_id,d.depends_on_step_id FROM task_step_dependencies d
               JOIN task_steps s ON s.id=d.step_id WHERE s.task_id=?""",
            (task_id,),
        ):
            graph.setdefault(row["step_id"], set()).add(row["depends_on_step_id"])
        graph[step_id] = set(dependency_ids)
        if self._has_dependency_cycle(graph):
            raise ValueError("Workforce dependency graph must be acyclic")
        now = utc_now()
        with self.db.connect() as conn:
            conn.execute("DELETE FROM task_step_dependencies WHERE step_id=?", (step_id,))
            conn.executemany(
                "INSERT INTO task_step_dependencies(step_id,depends_on_step_id,created_at) VALUES(?,?,?)",
                [(step_id, dependency_id, now) for dependency_id in dependency_ids],
            )
        return self.get_step(step_id)

    def assign_workforce_step(
        self,
        task_id: str,
        step_id: str,
        worker_name: str,
        dependencies: list[str] | None = None,
    ) -> dict[str, Any]:
        worker_name = str(worker_name).strip()
        if not worker_name:
            raise ValueError("Workforce worker name is required")
        self.create_step_from_workforce(task_id, step_id, step_id)
        if dependencies is not None:
            self.set_step_dependencies(task_id, step_id, dependencies)
        self.db.execute("UPDATE task_steps SET worker_name=? WHERE id=?", (worker_name, step_id))
        return self.get_step(step_id)

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
        decoded_steps = []
        for step in steps:
            decoded = self._decode_step(step)
            dependencies = self.db.fetchall(
                "SELECT depends_on_step_id FROM task_step_dependencies WHERE step_id=? ORDER BY depends_on_step_id",
                (decoded["id"],),
            )
            decoded["dependencies"] = [item["depends_on_step_id"] for item in dependencies]
            decoded_steps.append(decoded)
        task["steps"] = decoded_steps
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

    def update_input(self, task_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        self.get_task(task_id)
        timestamp = utc_now()
        self.db.execute(
            "UPDATE tasks SET input_json=?,updated_at=? WHERE id=?",
            (json_dumps(input_data), timestamp, task_id),
        )
        return self.get_task(task_id)

    def update_step(
        self,
        step_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        *,
        emit_event: bool = True,
    ) -> dict[str, Any]:
        allowed = {"queued", "running", "completed", "failed", "blocked", "waiting_approval"}
        if status not in allowed:
            raise ValueError(f"Invalid step status: {status}")
        row = self.db.fetchone("SELECT * FROM task_steps WHERE id=?", (step_id,))
        if not row:
            raise KeyError(f"Step not found: {step_id}")
        now = utc_now()
        started = row.get("started_at") or (now if status == "running" else None)
        completed = now if status in {"completed", "failed", "blocked"} else (None if status == "running" else row.get("completed_at"))
        self.db.execute(
            "UPDATE task_steps SET status=?,result_json=?,started_at=?,completed_at=? WHERE id=?",
            (status, json_dumps(result or {}), started, completed, step_id),
        )
        task_id = row["task_id"]
        if status == "running":
            self.db.execute(
                "UPDATE tasks SET current_step=?,updated_at=? WHERE id=?",
                (step_id, now, task_id),
            )
        elif status in {"completed", "failed", "blocked", "waiting_approval"}:
            self.db.execute(
                "UPDATE tasks SET current_step='',updated_at=? WHERE id=? AND current_step=?",
                (now, task_id, step_id),
            )
        if emit_event:
            self.events.publish(task_id, "task.step_changed", "platform", {
                "step_id": step_id, "status": status, "result": result or {},
            })
        return self.get_task(task_id)

    @staticmethod
    def _has_dependency_cycle(graph: dict[str, set[str]]) -> bool:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            for dependency in graph.get(node, set()):
                if visit(dependency):
                    return True
            visiting.remove(node)
            visited.add(node)
            return False

        return any(visit(node) for node in graph)

    def detail(
        self,
        task_id: str,
        artifacts: Any,
        approvals: Any,
        resources: Any | None = None,
    ) -> dict[str, Any]:
        task = self.get_task(task_id)
        detail = {
            "task": task,
            "events": self.events.list_after(task_id),
            "artifacts": artifacts.list(task_id),
            "approvals": approvals.list(task_id),
        }
        if resources is not None:
            detail["resources"] = resources.list(
                task["project_id"], source_task_id=task_id,
            )
        return detail

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
