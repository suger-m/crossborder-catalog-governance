from __future__ import annotations

import asyncio
from typing import Any

from ._base import BoundBusinessToolkit


class ProjectContextToolkit(BoundBusinessToolkit):
    """Compact, ownership-safe project context available to business Agents."""

    async def list_project_resources(
        self,
        resource_types: list[str] | None = None,
        statuses: list[str] | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """List reusable project resources without loading their full payloads."""
        return await asyncio.to_thread(
            self._list_project_resources, resource_types, statuses, limit,
        )

    def _list_project_resources(
        self,
        resource_types: list[str] | None,
        statuses: list[str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        rows = self._execute(
            "list_project_resources",
            self.app.project_context.list_project_resources,
            self._context(),
            resource_types=resource_types,
            statuses=statuses,
            limit=limit,
        )
        return [_resource_summary(row) for row in rows]

    async def inspect_task_materials(self) -> list[dict[str, Any]]:
        """Inspect metadata for files explicitly bound to the current task."""
        return await asyncio.to_thread(self._inspect_task_materials)

    def _inspect_task_materials(self) -> list[dict[str, Any]]:
        context = self._context()
        rows = self._execute(
            "inspect_task_materials",
            self.app.materials.task_materials,
            context.task_id,
        )
        return [
            {
                "id": row["id"],
                "file_name": row["file_name"],
                "mime_type": row["mime_type"],
                "size_bytes": row["size_bytes"],
                "origin": row["origin"],
            }
            for row in rows
        ]

    async def summarize_canonical_products(
        self,
        resource_ids: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Read compact Product/SKU summaries for planning a domain operation."""
        return await asyncio.to_thread(
            self._summarize_canonical_products, resource_ids, limit,
        )

    def _summarize_canonical_products(
        self,
        resource_ids: list[str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        rows = self._execute(
            "summarize_canonical_products",
            self.app.project_context.get_canonical_products,
            self._context(),
            resource_ids=resource_ids,
        )
        summaries = []
        for row in rows[:max(1, min(int(limit), 200))]:
            product = row.get("data", row)
            summaries.append({
                "product_id": product.get("id", row.get("id", "")),
                "external_id": product.get("external_id", ""),
                "title": product.get("title", ""),
                "category": product.get("category", ""),
                "garment_type": product.get("garment_type", ""),
                "version": product.get("version", 1),
                "status": product.get("status", ""),
                "sku_count": len(product.get("skus") or []),
                "missing_fields": [
                    field
                    for field in (
                        "description", "fiber_content", "care_instructions",
                        "country_of_origin", "manufacturer",
                    )
                    if not product.get(field)
                ],
            })
        return summaries

    async def summarize_listing_drafts(
        self,
        platforms: list[str] | None = None,
        resource_ids: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Read compact Shopify/eBay draft summaries without returning full channel payloads."""
        return await asyncio.to_thread(
            self._summarize_listing_drafts, platforms, resource_ids, limit,
        )

    def _summarize_listing_drafts(
        self,
        platforms: list[str] | None,
        resource_ids: list[str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        rows = self._execute(
            "summarize_listing_drafts",
            self.app.project_context.get_listing_drafts,
            self._context(),
            platforms=platforms,
            resource_ids=resource_ids,
        )
        summaries = []
        for row in rows[:max(1, min(int(limit), 200))]:
            draft = row.get("data", row)
            summaries.append({
                "listing_id": draft.get("id", row.get("id", "")),
                "product_id": draft.get("product_id", ""),
                "platform": draft.get("platform", ""),
                "title": draft.get("title", ""),
                "status": draft.get("status", ""),
                "derived_from_product_version": draft.get("derived_from_product_version", 1),
                "gap_count": len(draft.get("gaps") or []),
            })
        return summaries

    async def read_artifact_text(
        self,
        artifact_id: str = "",
        resource_id: str = "",
        offset: int = 0,
        limit: int = 16_384,
    ) -> dict[str, Any]:
        """Read one validated page from a text Artifact owned by this project."""
        return await asyncio.to_thread(
            self._read_artifact_text, artifact_id, resource_id, offset, limit,
        )

    def _read_artifact_text(
        self,
        artifact_id: str,
        resource_id: str,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        return self._execute(
            "read_artifact_text",
            self.app.project_context.read_artifact_text,
            self._context(),
            artifact_id,
            resource_id=resource_id,
            offset=offset,
            limit=limit,
        )

    async def list_pending_approvals(self) -> list[dict[str, Any]]:
        """List pending Human Approval requests using compact business fields."""
        return await asyncio.to_thread(self._list_pending_approvals)

    def _list_pending_approvals(self) -> list[dict[str, Any]]:
        rows = self._execute(
            "list_pending_approvals",
            self.app.project_context.get_pending_approvals,
            self._context(),
        )
        return [
            {
                "id": row["id"],
                "approval_type": row["approval_type"],
                "title": row["title"],
                "description": row["description"],
                "status": row["status"],
            }
            for row in rows
        ]

    def get_tools(self, names: tuple[str, ...]) -> list[Any]:
        return self._tools(*(getattr(self, name) for name in names))


def _resource_summary(resource: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(resource.get("metadata") or {})
    return {
        "id": resource["id"],
        "resource_type": resource["resource_type"],
        "logical_key": resource["logical_key"],
        "version": resource["version"],
        "status": resource["status"],
        "owner_worker_name": resource["owner_worker_name"],
        "source_task_id": resource["source_task_id"],
        "source_step_id": resource["source_step_id"],
        "metadata": _compact_metadata(metadata),
    }


def _compact_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "product_ids", "product_count", "conflict_count", "platform",
        "listing_ids", "artifact_id", "title", "file_name", "mime_type",
        "size_bytes", "sha256", "member_count",
    }
    result: dict[str, Any] = {}
    for key, value in metadata.items():
        if key not in allowed:
            continue
        if isinstance(value, list):
            result[key] = value[:20]
            if len(value) > 20:
                result[f"{key}_total"] = len(value)
        else:
            result[key] = value
    return result
