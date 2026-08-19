from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TaskContextRef:
    """A compact, serialisable handle passed between Manager and Workers."""

    task_id: str
    project_id: str
    worker_id: str = ""
    process_task_id: str = ""
    external_process_task_id: str = ""

    def __post_init__(self) -> None:
        for field_name in ("task_id", "project_id"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"TaskContextRef.{field_name} is required")

    def public_dict(self) -> dict[str, str]:
        return {
            "task_id": self.task_id,
            "project_id": self.project_id,
            "worker_id": self.worker_id,
            "process_task_id": self.process_task_id,
            "external_process_task_id": self.external_process_task_id,
        }
