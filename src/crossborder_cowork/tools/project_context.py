from __future__ import annotations

from typing import Any

from ..platform.execution_context import current_execution_context
from ..platform.project_context import ProjectContextService
from ..platform.registry import ToolRegistry
from ..platform.tool_executor import ToolExecutor


PROJECT_CONTEXT_TOOL_LABELS = {
    "list_project_resources": "查看项目资源",
    "get_canonical_products": "读取规范商品",
    "get_product_facts": "读取商品事实",
    "get_listing_drafts": "读取平台草稿",
    "get_artifact_manifest": "查看文件信息",
    "read_artifact_text": "读取文件内容",
    "get_pending_approvals": "查看待审批事项",
}


def register_project_context_tools(registry: ToolRegistry) -> None:
    for name, label in PROJECT_CONTEXT_TOOL_LABELS.items():
        registry.register(name, label, {"label": label, "kind": "project_context"})


class ProjectContextTools:
    """Agent-facing, audited access to persistent project resources."""

    def __init__(self, service: ProjectContextService, executor: ToolExecutor) -> None:
        self.service = service
        self.executor = executor

    def list_project_resources(
        self,
        resource_types: list[str] | None = None,
        statuses: list[str] | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        return self._execute(
            "list_project_resources", self.service.list_project_resources,
            resource_types=resource_types, statuses=statuses, limit=limit,
        )

    def get_canonical_products(
        self,
        product_ids: list[str] | None = None,
        resource_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return self._execute(
            "get_canonical_products", self.service.get_canonical_products,
            product_ids=product_ids, resource_ids=resource_ids,
        )

    def get_product_facts(self, product_ids: list[str] | None = None) -> list[dict[str, Any]]:
        return self._execute(
            "get_product_facts", self.service.get_product_facts, product_ids=product_ids,
        )

    def get_listing_drafts(
        self,
        platforms: list[str] | None = None,
        resource_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return self._execute(
            "get_listing_drafts", self.service.get_listing_drafts,
            platforms=platforms, resource_ids=resource_ids,
        )

    def get_artifact_manifest(
        self, artifact_id: str = "", resource_id: str = "",
    ) -> dict[str, Any]:
        return self._execute(
            "get_artifact_manifest", self.service.get_artifact_manifest,
            artifact_id, resource_id=resource_id,
        )

    def read_artifact_text(
        self,
        artifact_id: str = "",
        resource_id: str = "",
        offset: int = 0,
        limit: int = 16_384,
    ) -> dict[str, Any]:
        return self._execute(
            "read_artifact_text", self.service.read_artifact_text,
            artifact_id, resource_id=resource_id, offset=offset, limit=limit,
        )

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        return self._execute(
            "get_pending_approvals", self.service.get_pending_approvals,
        )

    def _execute(self, tool_name: str, method: Any, *args: Any, **kwargs: Any) -> Any:
        context = current_execution_context()
        assert context is not None
        return self.executor.execute(
            tool_name, context, method, context, *args, **kwargs,
        )
