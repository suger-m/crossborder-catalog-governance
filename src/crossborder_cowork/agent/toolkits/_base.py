from __future__ import annotations

from typing import Any, Callable, TypeVar

from camel.toolkits import FunctionTool

from ...platform.execution_context import ExecutionContext, current_execution_context


T = TypeVar("T")


class BoundBusinessToolkit:
    """Bind Agent tool calls to one validated project execution context."""

    def __init__(self, app: Any, worker_name: str) -> None:
        self.app = app
        self.worker_name = worker_name

    def _context(self) -> ExecutionContext:
        context = current_execution_context()
        assert context is not None
        if context.worker_name != self.worker_name:
            raise PermissionError("Agent execution context belongs to another business role")
        return context

    def _execute(
        self,
        tool_name: str,
        fn: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        return self.app.tool_executor.execute(
            tool_name,
            self._context(),
            fn,
            *args,
            **kwargs,
        )

    def _progress(self, message: str, phase: str) -> None:
        context = self._context()
        self.app.events.publish(context.task_id, "agent.progress", self.worker_name, {
            "worker_name": self.worker_name,
            "process_task_id": context.process_task_id,
            "message": message,
            "phase": phase,
        })

    @staticmethod
    def _tools(*methods: Callable[..., Any]) -> list[FunctionTool]:
        return [FunctionTool(method) for method in methods]
