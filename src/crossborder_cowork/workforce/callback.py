from __future__ import annotations

import json
import re
from typing import Any

from camel.societies.workforce.events import (
    AllTasksCompletedEvent,
    LogEvent,
    TaskAssignedEvent,
    TaskCompletedEvent,
    TaskCreatedEvent,
    TaskDecomposedEvent,
    TaskFailedEvent,
    TaskStartedEvent,
    TaskUpdatedEvent,
    WorkerCreatedEvent,
    WorkerDeletedEvent,
)
from camel.societies.workforce.workforce_callback import WorkforceCallback


_PUBLISHING_ACTION = re.compile(
    r"(?:自动|直接|立即|实际|正式)(?:发布|上架)|(?:发布|上架)(?:到|至)(?:\s*)(?:shopify|ebay)|publish\s+(?:live|to)",
    re.IGNORECASE,
)


class CrossborderWorkforceCallback(WorkforceCallback):
    """Persist native CAMEL lifecycle callbacks against one product task."""

    def __init__(self, app: Any, task_id: str) -> None:
        self.app = app
        self.task_id = task_id
        self._created_metadata: dict[str, dict[str, Any]] = {}

    def _emit(self, event_type: str, event: Any) -> None:
        payload = event.model_dump(mode="json")
        self.app.events.publish(self.task_id, event_type, "camel_workforce", payload)

    def _validate_resource_ids(self, metadata: dict[str, Any] | None) -> None:
        if not metadata or not hasattr(self.app, "resources"):
            return
        project_id = self.app.tasks.get_task(self.task_id)["project_id"]
        resource_ids = metadata.get("resource_ids") or metadata.get("selected_resource_ids") or []
        for resource_id in resource_ids:
            self.app.resources.get(str(resource_id), project_id)

    def _validate_assignment(self, event: TaskAssignedEvent) -> None:
        worker = self.app.workers.get(event.worker_id)
        step = self.app.tasks.get_step(event.task_id)
        if _requests_publishing(step["title"]):
            raise ValueError("First release cannot automatically publish Shopify or eBay listings")
        metadata = dict(worker.metadata or {})
        for tool_name in metadata.get("authorized_tools", metadata.get("tools", [])):
            self.app.tools.get(str(tool_name))
        for skill_name in metadata.get("skills", []):
            self.app.skills.get(str(skill_name))
        self._validate_resource_ids(self._created_metadata.get(event.task_id))

    def log_message(self, event: LogEvent) -> None:
        self._emit("workforce.log", event)

    def log_task_created(self, event: TaskCreatedEvent) -> None:
        if event.task_id == self.task_id:
            return
        metadata = dict(event.metadata or {})
        self._created_metadata[event.task_id] = metadata
        self._validate_resource_ids(metadata)
        self.app.tasks.create_step_from_workforce(
            self.task_id,
            event.task_id,
            event.description,
            worker_name="workforce",
        )
        self._emit("workforce.task_created", event)

    def log_task_decomposed(self, event: TaskDecomposedEvent) -> None:
        self._emit("workforce.task_decomposed", event)

    def log_task_assigned(self, event: TaskAssignedEvent) -> None:
        if event.task_id == self.task_id:
            self._emit("workforce.root_assigned", event)
            return
        self._validate_assignment(event)
        self.app.tasks.assign_workforce_step(
            self.task_id,
            event.task_id,
            event.worker_id,
            list(event.dependencies or []),
        )
        self._emit("workforce.task_assigned", event)

    def log_task_started(self, event: TaskStartedEvent) -> None:
        if event.task_id == self.task_id:
            self._emit("workforce.root_started", event)
            return
        self.app.tasks.assign_workforce_step(self.task_id, event.task_id, event.worker_id)
        self.app.tasks.update_step(event.task_id, "running", emit_event=False)
        self._emit("workforce.task_started", event)

    def log_task_updated(self, event: TaskUpdatedEvent) -> None:
        if event.task_id == self.task_id:
            self._emit("workforce.root_updated", event)
            return
        if event.worker_id:
            self.app.tasks.assign_workforce_step(self.task_id, event.task_id, event.worker_id)
        self._emit("workforce.task_updated", event)

    def log_task_completed(self, event: TaskCompletedEvent) -> None:
        if event.task_id == self.task_id:
            self._emit("workforce.root_completed", event)
            return
        persisted = self.app.tasks.get_step(event.task_id).get("result") or {}
        result = persisted if persisted.get("summary") else _compact_result(event.result_summary)
        self.app.tasks.update_step(event.task_id, _step_status(result), result, emit_event=False)
        self._emit("workforce.task_completed", event)

    def log_task_failed(self, event: TaskFailedEvent) -> None:
        if event.task_id == self.task_id:
            self._emit("workforce.root_failed", event)
            return
        persisted = self.app.tasks.get_step(event.task_id).get("result") or {}
        result = persisted if persisted.get("summary") else {
            "summary": str(event.error_message)[:1000],
            "key_counts": {},
            "output_resource_ids": [],
            "status": "failed",
        }
        self.app.tasks.update_step(event.task_id, "failed", result, emit_event=False)
        self._emit("workforce.task_failed", event)

    def log_worker_created(self, event: WorkerCreatedEvent) -> None:
        # Initial business workers are registered platform roles. CAMEL-created
        # generic workers are rejected instead of silently expanding authority.
        self.app.workers.get(event.worker_id)
        self._emit("workforce.worker_created", event)

    def log_worker_deleted(self, event: WorkerDeletedEvent) -> None:
        self._emit("workforce.worker_deleted", event)

    def log_all_tasks_completed(self, event: AllTasksCompletedEvent) -> None:
        self._emit("workforce.all_tasks_completed", event)


def _compact_result(raw: str | None) -> dict[str, Any]:
    value: Any = None
    if raw:
        try:
            value = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            value = None
    if not isinstance(value, dict):
        return {"summary": str(raw or "任务已完成")[:1000], "key_counts": {}, "output_resource_ids": [], "status": "completed"}
    counts = value.get("key_counts") if isinstance(value.get("key_counts"), dict) else {}
    resource_ids = value.get("output_resource_ids") if isinstance(value.get("output_resource_ids"), list) else []
    return {
        "summary": str(value.get("summary") or "任务已完成")[:1000],
        "key_counts": {
            str(key): item if isinstance(item, (int, float, bool)) or item is None else str(item)[:100]
            for key, item in list(counts.items())[:30]
        },
        "output_resource_ids": list(dict.fromkeys(str(item) for item in resource_ids if str(item).strip()))[:500],
        "status": str(value.get("status") or "completed")[:50],
    }


def _step_status(result: dict[str, Any]) -> str:
    status = str(result.get("status") or "completed").lower()
    if status in {"waiting_approval", "needs_confirmation"}:
        return "waiting_approval"
    if status == "blocked":
        return "blocked"
    if status == "failed":
        return "failed"
    return "completed"


def _requests_publishing(content: str) -> bool:
    for match in _PUBLISHING_ACTION.finditer(content):
        clause_start = max(
            content.rfind(separator, 0, match.start())
            for separator in ("。", "，", ",", "；", ";", "\n")
        )
        prefix = content[clause_start + 1:match.start()].lower()
        if any(negation in prefix for negation in (
            "不", "禁止", "严禁", "无需", "无须", "never", "not ", "do not", "don't", "must not",
        )):
            continue
        return True
    return False
