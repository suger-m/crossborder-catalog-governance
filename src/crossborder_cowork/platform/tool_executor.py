from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from ..util import new_id
from .database import Database
from .events import EventStore
from .execution_context import ExecutionContext, use_execution_context
from .registry import ToolRegistry, WorkerRegistry


T = TypeVar("T")


class ToolAuthorizationError(PermissionError):
    pass


class ToolExecutor:
    """Run deterministic Tools with one durable lifecycle identity."""

    def __init__(
        self,
        db: Database,
        events: EventStore,
        workers: WorkerRegistry,
        tools: ToolRegistry,
    ) -> None:
        self.db = db
        self.events = events
        self.workers = workers
        self.tools = tools

    def execute(
        self,
        tool_name: str,
        context: ExecutionContext,
        fn: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        self._validate_context(context)
        tool = self.tools.get(tool_name)
        if not self.workers.is_tool_authorized(context.worker_name, tool_name):
            raise ToolAuthorizationError(
                f"Worker {context.worker_name} is not authorized to use Tool {tool_name}"
            )
        tool_call_id = new_id("toolcall")
        common = {
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "tool_label": str(tool.metadata.get("label") or tool.description or tool.name),
            "worker_name": context.worker_name,
            "process_task_id": context.process_task_id,
        }
        self.events.publish(
            context.task_id,
            "tool_call.started",
            context.worker_name,
            {**common, "status": "running", "audit_summary": self._call_summary(args, kwargs)},
        )
        try:
            with use_execution_context(context):
                result = fn(*args, **kwargs)
        except Exception as error:
            self.events.publish(
                context.task_id,
                "tool_call.failed",
                context.worker_name,
                {
                    **common,
                    "status": "failed",
                    "audit_summary": f"{type(error).__name__}: {str(error)[:300]}",
                },
            )
            raise
        self.events.publish(
            context.task_id,
            "tool_call.succeeded",
            context.worker_name,
            {**common, "status": "completed", "audit_summary": self._result_summary(result)},
        )
        return result

    def _validate_context(self, context: ExecutionContext) -> None:
        task = self.db.fetchone("SELECT project_id FROM tasks WHERE id=?", (context.task_id,))
        if not task or task["project_id"] != context.project_id:
            raise ToolAuthorizationError("Execution context does not belong to this project")
        self.workers.get(context.worker_name)
        if context.process_task_id == context.task_id:
            return
        step = self.db.fetchone(
            "SELECT task_id,worker_name FROM task_steps WHERE id=?", (context.process_task_id,),
        )
        if not step or step["task_id"] != context.task_id:
            raise ToolAuthorizationError("Execution step does not belong to this task")
        if step["worker_name"] != context.worker_name:
            raise ToolAuthorizationError("Execution step is assigned to a different Worker")

    @staticmethod
    def _call_summary(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        return f"调用参数 {len(args) + len(kwargs)} 项"

    @staticmethod
    def _result_summary(result: Any) -> str:
        if result is None:
            return "工具执行完成"
        if isinstance(result, dict):
            return f"返回 {len(result)} 个字段"
        if isinstance(result, (list, tuple, set)):
            return f"返回 {len(result)} 条记录"
        return f"返回 {type(result).__name__}"
