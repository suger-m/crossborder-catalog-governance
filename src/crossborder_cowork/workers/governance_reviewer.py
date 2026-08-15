from __future__ import annotations

from typing import Any

from ..catalog.models import CanonicalProduct
from ..compliance.us_apparel import ComplianceResult
from ..export.package import ExportPackageService
from ..governance.consistency import consistency_markdown, review_catalog
from ..platform.artifacts import ArtifactService
from ..platform.events import EventStore
from ..platform.skills import SkillRegistry
from ..platform.execution_context import ExecutionContext
from ..platform.project_context import ProjectContextService
from ..platform.resources import ProjectResourceService
from ..platform.tool_executor import ToolExecutor
from ..platforms.base import ListingDraft
from ..util import json_dumps


class GovernanceReviewerAgent:
    name = "governance_reviewer_agent"
    description = "审核商品事实、合规阻塞项、证据、版本、一致性和交付就绪状态。"

    def __init__(
        self,
        artifacts: ArtifactService,
        events: EventStore,
        skills: SkillRegistry,
        exporter: ExportPackageService,
        project_context: ProjectContextService | None = None,
        resources: ProjectResourceService | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.events = events
        self.skills = skills
        self.exporter = exporter
        self.project_context = project_context
        self.resources = resources
        self.tool_executor = tool_executor

    def run_for_workforce(
        self,
        context: ExecutionContext,
        task_content: str,
        dependencies: list[Any],
    ) -> dict[str, Any]:
        if not self.project_context or not self.resources or not self.tool_executor:
            raise RuntimeError("Governance Reviewer Workforce services are not configured")
        skill = self.skills.get("catalog-governance")
        skill.load()
        self._progress(context, "正在读取本次审核所需的商品、合规与平台草稿资源。", "input_resolution")
        product_input = self.project_context.resolve_inputs(
            context, resource_types=("product_collection", "canonical_product"),
        )
        compliance_input = self.project_context.resolve_inputs(
            context, resource_types=("compliance_result",),
        )
        listing_input = self.project_context.resolve_inputs(
            context, resource_types=("listing_draft", "shopify_listing", "ebay_listing"),
        )
        if product_input["no_input"]:
            raise ValueError("没有可用于治理审核的规范商品资源")
        if listing_input["no_input"]:
            raise ValueError("没有可用于治理审核的平台草稿资源")
        products_raw = self.tool_executor.execute(
            "get_canonical_products", context, self.project_context.get_canonical_products,
            context, resource_ids=product_input["resource_ids"],
        )
        product_models = [CanonicalProduct.model_validate(item.get("data", item)) for item in products_raw]
        listing_rows = self.tool_executor.execute(
            "get_listing_drafts", context, self.project_context.get_listing_drafts,
            context, resource_ids=listing_input["resource_ids"],
        )
        listing_models = [ListingDraft.model_validate(item.get("data", item)) for item in listing_rows]
        shopify_models = [item for item in listing_models if item.platform == "shopify"]
        ebay_models = [item for item in listing_models if item.platform == "ebay_us"]
        compliance_models: list[ComplianceResult] = []
        for resource in compliance_input["resources"]:
            if resource.get("storage_kind") != "artifact":
                continue
            page = self.tool_executor.execute(
                "read_artifact_text", context, self.project_context.read_artifact_text,
                context, resource_id=resource["id"], offset=0, limit=65_536,
            )
            payload = __import__("json").loads(page["content"] or "{}")
            compliance_models.extend(
                ComplianceResult.model_validate(item) for item in payload.get("results", [])
            )
        pending = self.tool_executor.execute(
            "get_pending_approvals", context, self.project_context.get_pending_approvals, context,
        )
        self._progress(context, "正在校验跨平台事实一致性、证据版本和交付阻塞项。", "governance_review")
        decision = self.tool_executor.execute(
            "review_catalog_governance",
            context,
            review_catalog,
            product_models,
            compliance_models,
            shopify_models,
            ebay_models,
            len(pending),
            {item.platform for item in listing_models},
        )
        dependencies_ids = list(dict.fromkeys([
            *product_input["resource_ids"], *compliance_input["resource_ids"],
            *listing_input["resource_ids"],
        ]))
        consistency = self.artifacts.create_text(
            context.task_id, self.name, "catalog_consistency_report", "catalog_consistency_report",
            content=consistency_markdown(decision), extension="md", mime_type="text/markdown",
            dependencies=dependencies_ids,
        )
        review = self.artifacts.create_text(
            context.task_id, self.name, "release_decision", "release_decision",
            content=json_dumps(decision.model_dump()), extension="json", mime_type="application/json",
            dependencies=[consistency["resource_id"], *dependencies_ids],
        )
        create_package = _requests_export_package(task_content)
        output_resource_ids = [consistency["resource_id"], review["resource_id"]]
        package = None
        if decision.ready_for_export and create_package:
            sku_matrix = self.tool_executor.execute(
                "create_sku_matrix",
                context,
                self.exporter.create_sku_matrix,
                context.task_id,
                product_models,
                [review["resource_id"]],
            )
            artifacts_to_package = [
                str(resource["storage_ref"])
                for resource in [*compliance_input["resources"], *listing_input["resources"]]
                if resource.get("storage_kind") == "artifact"
            ]
            artifacts_to_package.extend([consistency["id"], review["id"], sku_matrix["id"]])
            package = self.tool_executor.execute(
                "create_listing_package",
                context,
                self.exporter.create_package,
                context.task_id,
                artifacts_to_package,
                decision.model_dump(),
            )
            output_resource_ids.extend([sku_matrix["resource_id"], package["resource_id"]])
        summary = (
            f"治理审核结论为“{decision.status}”，发现 {len(decision.findings)} 项一致性问题"
            f"，{'已生成导出包' if package else '当前未生成导出包'}。"
        )
        self._progress(context, summary, "completed")
        return {
            "summary": summary,
            "key_counts": {
                "findings": len(decision.findings), "pending_approvals": len(pending),
                "packages": 1 if package else 0,
            },
            "output_resource_ids": output_resource_ids,
            "status": "completed" if decision.ready_for_export else decision.status,
        }

    def _progress(self, context: ExecutionContext, message: str, phase: str) -> None:
        self.events.publish(context.task_id, "agent.progress", self.name, {
            "worker_name": self.name,
            "process_task_id": context.process_task_id,
            "message": message,
            "phase": phase,
        })


def _requests_export_package(task_content: str) -> bool:
    normalized = str(task_content or "").casefold()
    phrases = ("导出包", "交付包", "目录包", "listing package", "export package")
    for phrase in phrases:
        start = normalized.find(phrase)
        while start >= 0:
            clause_start = max(
                normalized.rfind(separator, 0, start)
                for separator in ("。", "，", ",", "；", ";", "\n")
            )
            prefix = normalized[clause_start + 1:start]
            if not any(negation in prefix for negation in (
                "不", "禁止", "严禁", "无需", "无须", "never", "not ", "do not", "don't", "must not",
            )):
                return True
            start = normalized.find(phrase, start + len(phrase))
    return False

    def run(self, task_id: str, products: list[dict[str, Any]], compliance: list[dict[str, Any]], shopify: list[dict[str, Any]], ebay: list[dict[str, Any]], pending_approvals: int, dependencies: list[str]) -> dict[str, Any]:
        skill = self.skills.get("catalog-governance")
        skill.load()
        self.events.publish(task_id, "worker.started", self.name, {"skills": [skill.name]})
        product_models = [CanonicalProduct.model_validate(item) for item in products]
        compliance_models = [ComplianceResult.model_validate(item) for item in compliance]
        shopify_models = [ListingDraft.model_validate(item) for item in shopify]
        ebay_models = [ListingDraft.model_validate(item) for item in ebay]
        decision = review_catalog(product_models, compliance_models, shopify_models, ebay_models, pending_approvals)
        consistency = self.artifacts.create_text(
            task_id, self.name, "catalog_consistency_report", "catalog_consistency_report",
            content=consistency_markdown(decision), extension="md", mime_type="text/markdown", dependencies=dependencies,
        )
        review = self.artifacts.create_text(
            task_id, self.name, "release_review", "release_review", content=json_dumps(decision.model_dump()),
            extension="json", mime_type="application/json", dependencies=[consistency["id"], *dependencies],
        )
        sku_matrix = self.exporter.create_sku_matrix(task_id, product_models, [review["id"]])
        artifact_ids = [consistency["id"], review["id"], sku_matrix["id"]]
        package = None
        if decision.ready_for_export:
            package = self.exporter.create_package(task_id, [*dependencies, *artifact_ids], decision.model_dump())
            artifact_ids.append(package["id"])
        result = {"decision": decision.model_dump(), "artifact_ids": artifact_ids, "package": package}
        self.events.publish(task_id, "worker.completed", self.name, {"status": decision.status, "package_created": bool(package)})
        return result
