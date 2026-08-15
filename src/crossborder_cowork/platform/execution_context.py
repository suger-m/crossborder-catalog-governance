from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    task_id: str
    project_id: str
    process_task_id: str
    worker_name: str

    def __post_init__(self) -> None:
        for field in ("task_id", "project_id", "process_task_id", "worker_name"):
            if not str(getattr(self, field)).strip():
                raise ValueError(f"ExecutionContext.{field} is required")


_CURRENT_EXECUTION_CONTEXT: ContextVar[ExecutionContext | None] = ContextVar(
    "crossborder_execution_context", default=None,
)


def current_execution_context(*, required: bool = True) -> ExecutionContext | None:
    context = _CURRENT_EXECUTION_CONTEXT.get()
    if required and context is None:
        raise RuntimeError("No active Agent execution context")
    return context


@contextmanager
def use_execution_context(context: ExecutionContext) -> Iterator[ExecutionContext]:
    token: Token[ExecutionContext | None] = _CURRENT_EXECUTION_CONTEXT.set(context)
    try:
        yield context
    finally:
        _CURRENT_EXECUTION_CONTEXT.reset(token)
