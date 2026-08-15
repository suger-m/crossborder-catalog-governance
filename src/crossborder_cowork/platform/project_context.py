from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from ..graph.service import CatalogGraphService
from ..util import json_loads
from .approvals import ApprovalService
from .artifacts import ArtifactService
from .database import Database
from .execution_context import ExecutionContext
from .resources import ProjectResourceService


class ProjectContextService:
    """Resolve compact project state and perform ownership-safe, on-demand reads."""

    def __init__(
        self,
        db: Database,
        resources: ProjectResourceService,
        artifacts: ArtifactService,
        graph: CatalogGraphService,
        approvals: ApprovalService,
    ) -> None:
        self.db = db
        self.resources = resources
        self.artifacts = artifacts
        self.graph = graph
        self.approvals = approvals

    def planner_manifest(self, task_id: str) -> dict[str, Any]:
        task = self._task(task_id)
        project_id = str(task["project_id"])
        resources = self.resources.list(project_id, limit=1000)
        active = [resource for resource in resources if resource["status"] == "active"]
        input_data = json_loads(task.get("input_json"), {})
        selected_ids = self._ids(
            input_data.get("selected_resource_ids") or input_data.get("resource_ids") or []
        )
        selected = [self.resources.get(resource_id, project_id) for resource_id in selected_ids]
        material_count = self.db.fetchone(
            "SELECT COUNT(*) AS count FROM project_materials WHERE project_id=?", (project_id,),
        )
        task_material_count = self.db.fetchone(
            "SELECT COUNT(*) AS count FROM task_materials WHERE task_id=?", (task_id,),
        )
        return {
            "project_id": project_id,
            "task_id": task_id,
            "counts": {
                "resources": len(resources),
                "active_resources": len(active),
                "materials": int((material_count or {}).get("count") or 0),
                "selected_materials": int((task_material_count or {}).get("count") or 0),
                "by_type": dict(sorted(Counter(item["resource_type"] for item in active).items())),
                "by_status": dict(sorted(Counter(item["status"] for item in resources).items())),
            },
            "selected_resources": [self._manifest_item(item) for item in selected],
            "active_resources": [self._manifest_item(item) for item in active],
        }

    def resolve_inputs(
        self,
        context: ExecutionContext,
        *,
        resource_types: Iterable[str] | None = None,
        explicit_resource_ids: Iterable[str] | None = None,
        upstream_step_ids: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        self._validate_context(context)
        requested_types = self._ids(resource_types or [])
        task = self._task(context.task_id)
        input_data = json_loads(task.get("input_json"), {})
        explicit_ids = self._ids(
            explicit_resource_ids
            if explicit_resource_ids is not None
            else input_data.get("selected_resource_ids") or input_data.get("resource_ids") or []
        )
        selected: list[dict[str, Any]] = []
        sources: list[str] = []
        remaining_types = set(requested_types)
        if explicit_ids:
            explicit = self.resources.resolve(
                context.project_id,
                resource_types=requested_types,
                explicit_resource_ids=explicit_ids,
            )
            selected.extend(explicit)
            if explicit:
                sources.append("explicit")
                remaining_types.difference_update(item["resource_type"] for item in explicit)
            if not requested_types:
                return self._resolution("explicit", selected, requested_types)

        dependency_ids = self._ids(upstream_step_ids or self._dependency_step_ids(context))
        upstream_resource_ids: list[str] = []
        for step_id in dependency_ids:
            row = self.db.fetchone(
                "SELECT task_id,result_json FROM task_steps WHERE id=?", (step_id,),
            )
            if not row or row["task_id"] != context.task_id:
                raise ValueError("Upstream step does not belong to this task")
            result = json_loads(row.get("result_json"), {})
            upstream_resource_ids.extend(self._ids(result.get("output_resource_ids") or []))
        if upstream_resource_ids and remaining_types:
            upstream = self.resources.resolve(
                context.project_id,
                resource_types=remaining_types,
                explicit_resource_ids=upstream_resource_ids,
            )
            if upstream:
                selected.extend(upstream)
                sources.append("upstream")
                remaining_types.difference_update(item["resource_type"] for item in upstream)
        if dependency_ids and remaining_types:
            upstream = self.resources.resolve(
                context.project_id,
                resource_types=remaining_types,
                upstream_step_ids=dependency_ids,
            )
            if upstream:
                selected.extend(upstream)
                if "upstream" not in sources:
                    sources.append("upstream")
                remaining_types.difference_update(item["resource_type"] for item in upstream)

        active = self.resources.resolve(context.project_id, resource_types=remaining_types or None) if remaining_types else []
        if active:
            selected.extend(active)
            sources.append("project_active")
        source = "+".join(sources) if sources else "none"
        unique = {item["id"]: item for item in selected}
        return self._resolution(source, list(unique.values()), requested_types)

    def list_project_resources(
        self,
        context: ExecutionContext,
        *,
        resource_types: Iterable[str] | None = None,
        statuses: Iterable[str] | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        self._validate_context(context)
        return self.resources.list(
            context.project_id, resource_types=resource_types, statuses=statuses, limit=limit,
        )

    def get_canonical_products(
        self,
        context: ExecutionContext,
        *,
        product_ids: Iterable[str] | None = None,
        resource_ids: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        self._validate_context(context)
        ids = self._ids(product_ids or [])
        for resource in self._owned_resources(context, resource_ids):
            if resource["storage_kind"] == "database" and resource["resource_type"] in {
                "canonical_product", "product", "product_collection",
            }:
                ids.extend(self._ids(resource["metadata"].get("product_ids") or [resource["storage_ref"]]))
        ids = self._ids(ids)
        if ids:
            products = [self.graph.get_product(product_id, project_id=context.project_id) for product_id in ids]
            return [product for product in products if product]
        return self.graph.list_products(project_id=context.project_id)

    def get_product_facts(
        self,
        context: ExecutionContext,
        *,
        product_ids: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        self._validate_context(context)
        return self.graph.list_product_facts(context.project_id, product_ids)

    def get_listing_drafts(
        self,
        context: ExecutionContext,
        *,
        platforms: Iterable[str] | None = None,
        resource_ids: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        self._validate_context(context)
        requested = set(self._ids(platforms or []))
        resource_listing_ids: set[str] = set()
        for resource in self._owned_resources(context, resource_ids):
            if resource["storage_kind"] == "database" and resource["resource_type"] in {
                "listing", "listing_draft", "shopify_listing", "ebay_listing",
            }:
                resource_listing_ids.update(
                    self._ids(resource["metadata"].get("listing_ids") or [resource["storage_ref"]])
                )
        rows = self.graph.list_listings(context.project_id, requested or None)
        if resource_listing_ids:
            rows = [row for row in rows if row["id"] in resource_listing_ids]
        return rows

    def get_artifact_manifest(
        self, context: ExecutionContext, artifact_id: str = "", *, resource_id: str = "",
    ) -> dict[str, Any]:
        self._validate_context(context)
        resolved_id = self._artifact_id(context, artifact_id=artifact_id, resource_id=resource_id)
        return self.artifacts.manifest(resolved_id, context.project_id)

    def read_artifact_text(
        self,
        context: ExecutionContext,
        artifact_id: str = "",
        *,
        resource_id: str = "",
        offset: int = 0,
        limit: int = 16_384,
    ) -> dict[str, Any]:
        self._validate_context(context)
        resolved_id = self._artifact_id(context, artifact_id=artifact_id, resource_id=resource_id)
        return self.artifacts.read_text(
            resolved_id, context.project_id, offset=offset, limit=limit,
        )

    def get_pending_approvals(self, context: ExecutionContext) -> list[dict[str, Any]]:
        self._validate_context(context)
        rows = self.db.fetchall(
            """SELECT approval.* FROM approvals approval
               JOIN tasks task ON task.id=approval.task_id
               WHERE task.project_id=? AND approval.status='pending'
               ORDER BY approval.created_at""",
            (context.project_id,),
        )
        return [self.approvals._decode(row) for row in rows]

    def _owned_resources(
        self, context: ExecutionContext, resource_ids: Iterable[str] | None,
    ) -> list[dict[str, Any]]:
        return [
            self.resources.get(resource_id, context.project_id)
            for resource_id in self._ids(resource_ids or [])
        ]

    def _artifact_id(self, context: ExecutionContext, *, artifact_id: str, resource_id: str) -> str:
        if resource_id:
            resource = self.resources.get(resource_id, context.project_id)
            if resource["storage_kind"] != "artifact":
                raise ValueError("Project resource does not reference an Artifact")
            return str(resource["storage_ref"])
        if not artifact_id:
            raise ValueError("artifact_id or resource_id is required")
        artifact = self.artifacts.get(artifact_id, context.project_id)
        if not artifact:
            raise KeyError(f"Artifact not found: {artifact_id}")
        return artifact_id

    def _dependency_step_ids(self, context: ExecutionContext) -> list[str]:
        if context.process_task_id == context.task_id:
            return []
        rows = self.db.fetchall(
            """SELECT dependency.depends_on_step_id FROM task_step_dependencies dependency
               JOIN task_steps step ON step.id=dependency.depends_on_step_id
               WHERE dependency.step_id=? AND step.task_id=?""",
            (context.process_task_id, context.task_id),
        )
        return [str(row["depends_on_step_id"]) for row in rows]

    def _validate_context(self, context: ExecutionContext) -> None:
        task = self._task(context.task_id)
        if task["project_id"] != context.project_id:
            raise ValueError("Execution context does not belong to this project")
        if context.process_task_id == context.task_id:
            return
        step = self.db.fetchone(
            "SELECT task_id,worker_name FROM task_steps WHERE id=?", (context.process_task_id,),
        )
        if not step or step["task_id"] != context.task_id or step["worker_name"] != context.worker_name:
            raise ValueError("Execution context does not own this process task")

    def _task(self, task_id: str) -> dict[str, Any]:
        task = self.db.fetchone("SELECT * FROM tasks WHERE id=?", (task_id,))
        if not task:
            raise KeyError(f"Task not found: {task_id}")
        return task

    @staticmethod
    def _manifest_item(resource: dict[str, Any]) -> dict[str, Any]:
        return {
            key: resource[key]
            for key in (
                "id", "resource_type", "logical_key", "version", "status",
                "owner_worker_name", "source_task_id", "source_step_id",
            )
        }

    @classmethod
    def _resolution(
        cls, source: str, resources: list[dict[str, Any]], requested_types: list[str],
    ) -> dict[str, Any]:
        found_types = {resource["resource_type"] for resource in resources}
        return {
            "source": source,
            "resources": resources,
            "resource_ids": [resource["id"] for resource in resources],
            "requested_types": requested_types,
            "missing_types": [item for item in requested_types if item not in found_types],
            "no_input": not resources,
        }

    @staticmethod
    def _ids(values: Iterable[Any]) -> list[str]:
        if isinstance(values, str):
            values = [values]
        return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
