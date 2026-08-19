from __future__ import annotations

"""Shared task-space access for AgentTeams workers.

This service deliberately composes the existing Task, Resource, Artifact and
Approval stores.  It returns IDs and compact summaries only; workers fetch
domain payloads through the authorised domain APIs.
"""

from typing import Any

from ..agentteams.models import TaskContextRef


class TaskContext:
    def __init__(self, service: "TaskContextService", ref: TaskContextRef) -> None:
        self.service = service
        self.ref = ref

    @property
    def task_id(self) -> str:
        return self.ref.task_id

    @property
    def project_id(self) -> str:
        return self.ref.project_id

    def manifest(self) -> dict[str, Any]:
        return self.service.manifest(self.ref)

    def dependency_manifest(self) -> list[dict[str, Any]]:
        return self.service.dependencies(self.ref)

    def snapshot(self) -> dict[str, Any]:
        return self.service.snapshot(self.ref)


class TaskContextService:
    """Build recoverable AgentTeams context from platform-owned persistence."""

    def __init__(self, tasks: Any, resources: Any, artifacts: Any, approvals: Any) -> None:
        self.tasks = tasks
        self.resources = resources
        self.artifacts = artifacts
        self.approvals = approvals

    def for_task(
        self,
        task_id: str,
        *,
        worker_id: str = "",
        process_task_id: str = "",
        external_process_task_id: str = "",
    ) -> TaskContext:
        task = self.tasks.get_task(task_id)
        if external_process_task_id and not process_task_id:
            process_task_id = self.tasks.resolve_step_id(task_id, external_process_task_id) or ""
        if process_task_id:
            step = next((item for item in task.get("steps") or [] if item["id"] == process_task_id), None)
            if step is None:
                raise ValueError("Process task does not belong to the requested task")
            external_process_task_id = external_process_task_id or str(step.get("external_id") or "")
        return TaskContext(
            self,
            TaskContextRef(
                task_id=task_id,
                project_id=str(task["project_id"]),
                worker_id=worker_id,
                process_task_id=process_task_id,
                external_process_task_id=external_process_task_id,
            ),
        )

    def snapshot_for_task(
        self,
        task_id: str,
        *,
        worker_id: str = "",
        process_task_id: str = "",
        external_process_task_id: str = "",
    ) -> dict[str, Any]:
        """Return a recoverable snapshot without exposing a local runtime object."""
        return self.for_task(
            task_id,
            worker_id=worker_id,
            process_task_id=process_task_id,
            external_process_task_id=external_process_task_id,
        ).snapshot()

    def manifest(self, ref: TaskContextRef) -> dict[str, Any]:
        task = self.tasks.get_task(ref.task_id)
        if str(task["project_id"]) != ref.project_id:
            raise ValueError("Task does not belong to the requested project")
        input_data = dict(task.get("input") or {})
        resources = self.resources.list(ref.project_id, source_task_id=ref.task_id)
        artifacts = self.artifacts.list(ref.task_id)
        approvals = self.approvals.list(ref.task_id)
        return {
            "task": {
                "id": task["id"],
                "project_id": task["project_id"],
                "objective": task["objective"],
                "status": task["status"],
                "current_step": task.get("current_step") or "",
                "created_at": task.get("created_at"),
                "updated_at": task.get("updated_at"),
            },
            "context": ref.public_dict(),
            "input": {
                "material_ids": list(input_data.get("material_ids") or []),
                "selected_resource_ids": list(
                    input_data.get("selected_resource_ids")
                    or input_data.get("resource_ids")
                    or []
                ),
                "source_paths": list(input_data.get("source_paths") or []),
            },
            "dependencies": self.dependencies(ref),
            "resources": [self._resource_manifest(item) for item in resources],
            "artifacts": [self._artifact_manifest(item) for item in artifacts],
            "approvals": [self._approval_manifest(item) for item in approvals],
        }

    def dependencies(self, ref: TaskContextRef) -> list[dict[str, Any]]:
        task = self.tasks.get_task(ref.task_id)
        result: list[dict[str, Any]] = []
        for step in task.get("steps") or []:
            if ref.process_task_id and step["id"] == ref.process_task_id:
                continue
            item = {
                "step_id": step["id"],
                "worker_name": step.get("worker_name") or "",
                "title": step.get("title") or "",
                "status": step.get("status") or "queued",
                "dependencies": list(step.get("dependencies") or []),
            }
            step_result = dict(step.get("result") or {})
            item["summary"] = str(step_result.get("summary") or "")
            item["output_resource_ids"] = list(step_result.get("output_resource_ids") or [])
            item["artifact_ids"] = list(step_result.get("artifact_ids") or [])
            result.append(item)
        return result

    def snapshot(self, ref: TaskContextRef) -> dict[str, Any]:
        manifest = self.manifest(ref)
        return {
            "context": manifest["context"],
            "task": manifest["task"],
            "dependency_manifest": manifest["dependencies"],
            "artifact_manifest": manifest["artifacts"],
            "resource_ids": [item["id"] for item in manifest["resources"]],
            "approval_ids": [item["id"] for item in manifest["approvals"]],
        }

    @staticmethod
    def _resource_manifest(resource: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": resource["id"],
            "resource_type": resource["resource_type"],
            "logical_key": resource["logical_key"],
            "version": resource["version"],
            "status": resource["status"],
            "owner_worker_name": resource.get("owner_worker_name") or "",
            "source_task_id": resource.get("source_task_id") or "",
            "source_step_id": resource.get("source_step_id") or "",
            "storage_kind": resource.get("storage_kind") or "",
            "storage_ref": resource.get("storage_ref") or "",
            "metadata": dict(resource.get("metadata") or {}),
        }

    @staticmethod
    def _artifact_manifest(artifact: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": artifact["id"],
            "artifact_type": artifact["artifact_type"],
            "title": artifact["title"],
            "worker_name": artifact.get("worker_name") or "",
            "process_task_id": artifact.get("process_task_id") or "",
            "relative_path": artifact.get("relative_path") or "",
            "mime_type": artifact.get("mime_type") or "",
            "size_bytes": artifact.get("size_bytes") or 0,
            "sha256": artifact.get("sha256") or "",
            "dependency_ids": list(artifact.get("dependency_ids") or []),
            "resource_id": artifact.get("resource_id") or "",
            "created_at": artifact.get("created_at"),
        }

    @staticmethod
    def _approval_manifest(approval: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": approval["id"],
            "approval_type": approval["approval_type"],
            "title": approval["title"],
            "status": approval["status"],
            "payload": dict(approval.get("payload") or {}),
            "created_at": approval.get("created_at"),
            "decided_at": approval.get("decided_at"),
        }
