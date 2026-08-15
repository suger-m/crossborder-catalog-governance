from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any, Awaitable, Callable, List, Optional

from camel.societies.workforce.worker import Worker
from camel.tasks import Task
from camel.tasks.task import TaskState

from ..platform.execution_context import ExecutionContext, use_execution_context


class BusinessWorker(Worker):
    """CAMEL Worker boundary for one durable cross-border business Agent."""

    def __init__(self, app: Any, platform_task_id: str, agent: Any) -> None:
        super().__init__(description=agent.description, node_id=agent.name)
        self.app = app
        self.platform_task_id = platform_task_id
        self.agent = agent

    async def _process_task(
        self,
        task: Task,
        dependencies: List[Task],
        stream_callback: Optional[Callable[[Any], Optional[Awaitable[None]]]] = None,
    ) -> TaskState:
        del stream_callback
        platform_task = self.app.tasks.get_task(self.platform_task_id)
        context = ExecutionContext(
            task_id=self.platform_task_id,
            project_id=platform_task["project_id"],
            process_task_id=task.id,
            worker_name=self.agent.name,
        )
        input_data = platform_task.get("input") or {}
        selected_ids = list(input_data.get("selected_resource_ids") or input_data.get("resource_ids") or [])
        upstream_ids = [dependency.id for dependency in dependencies]
        try:
            with use_execution_context(context):
                self.app.project_context.resolve_inputs(
                    context,
                    explicit_resource_ids=selected_ids,
                    upstream_step_ids=upstream_ids,
                )
            method = getattr(self.agent, "run_for_workforce", None)
            if not callable(method):
                raise RuntimeError(f"{self.agent.name} does not implement run_for_workforce")
            if inspect.iscoroutinefunction(method):
                with use_execution_context(context):
                    raw = await method(context, task.content, dependencies)
            else:
                raw = await asyncio.to_thread(self._call_agent, method, context, task, dependencies)
            compact = self._validate_result(raw, context.project_id)
            task.result = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
            self.app.tasks.update_step(
                task.id,
                self._step_status(compact["status"]),
                compact,
                emit_event=False,
            )
            return TaskState.FAILED if compact["status"] == "failed" else TaskState.DONE
        except Exception as exc:
            compact = {"summary": str(exc)[:1000], "key_counts": {}, "output_resource_ids": [], "status": "failed"}
            task.result = json.dumps(
                compact,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            self.app.tasks.update_step(task.id, "failed", compact, emit_event=False)
            return TaskState.FAILED

    @staticmethod
    def _call_agent(method: Callable[..., Any], context: ExecutionContext, task: Task, dependencies: List[Task]) -> Any:
        with use_execution_context(context):
            return method(context, task.content, dependencies)

    def _validate_result(self, raw: Any, project_id: str) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise TypeError(f"{self.agent.name} must return a compact result dictionary")
        summary = str(raw.get("summary") or "").strip()
        if not summary:
            raise ValueError(f"{self.agent.name} returned no summary")
        status = str(raw.get("status") or "completed").strip().lower()
        if status not in {"completed", "waiting_approval", "blocked", "failed"}:
            raise ValueError(f"Invalid Agent result status: {status}")
        resource_ids = list(dict.fromkeys(str(item) for item in raw.get("output_resource_ids", []) if str(item).strip()))
        for resource_id in resource_ids:
            self.app.resources.get(resource_id, project_id)
        counts = raw.get("key_counts") if isinstance(raw.get("key_counts"), dict) else {}
        return {
            "summary": summary[:1000],
            "key_counts": {
                str(key): value if isinstance(value, (int, float, bool)) or value is None else str(value)[:100]
                for key, value in list(counts.items())[:30]
            },
            "output_resource_ids": resource_ids[:500],
            "status": status,
        }

    @staticmethod
    def _step_status(status: str) -> str:
        if status == "waiting_approval":
            return "waiting_approval"
        if status == "blocked":
            return "blocked"
        if status == "failed":
            return "failed"
        return "completed"
