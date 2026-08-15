from __future__ import annotations

from typing import Any

from ..catalog.models import CanonicalProduct, CatalogConflict
from ..compliance.us_apparel import UsApparelComplianceService, compliance_markdown
from ..platform.artifacts import ArtifactService
from ..platform.events import EventStore
from ..platform.skills import SkillRegistry
from ..platform.approvals import ApprovalService
from ..platform.execution_context import ExecutionContext
from ..platform.project_context import ProjectContextService
from ..platform.resources import ProjectResourceService
from ..platform.tool_executor import ToolExecutor
from ..util import json_dumps


class ComplianceSpecialistAgent:
    name = "compliance_specialist_agent"
    description = "在不修改商品事实的前提下，应用美国服装法规与平台政策技能。"

    def __init__(
        self,
        service: UsApparelComplianceService,
        artifacts: ArtifactService,
        events: EventStore,
        skills: SkillRegistry,
        approvals: ApprovalService,
        project_context: ProjectContextService | None = None,
        resources: ProjectResourceService | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        self.service = service
        self.artifacts = artifacts
        self.events = events
        self.skills = skills
        self.approvals = approvals
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
            raise RuntimeError("Compliance Specialist Workforce services are not configured")
        selected_skills = [self.skills.get(name) for name in (
            "us-apparel-compliance", "shopify-product-policy", "ebay-us-fashion-policy",
        )]
        for skill in selected_skills:
            skill.load()
        self._progress(context, "正在读取规范商品事实并确定本次合规检查范围。", "input_resolution")
        resolution = self.project_context.resolve_inputs(
            context,
            resource_types=("product_collection", "canonical_product"),
        )
        if resolution["no_input"]:
            raise ValueError("没有可用于合规检查的规范商品资源")
        products_raw = self.tool_executor.execute(
            "get_canonical_products",
            context,
            self.project_context.get_canonical_products,
            context,
            resource_ids=resolution["resource_ids"],
        )
        products = [item.get("data", item) for item in products_raw]
        product_models = [CanonicalProduct.model_validate(product) for product in products]
        pending = self.tool_executor.execute(
            "get_pending_approvals",
            context,
            self.project_context.get_pending_approvals,
            context,
        )
        conflict_models = [
            CatalogConflict.model_validate(item["payload"])
            for item in pending
            if item.get("approval_type") == "catalog_conflict" and isinstance(item.get("payload"), dict)
        ]
        self._progress(context, f"正在检查 {len(product_models)} 个商品的美国法规与平台政策要求。", "compliance_check")
        results = self.tool_executor.execute(
            "check_product_compliance",
            context,
            lambda: [self.service.evaluate(product, conflict_models) for product in product_models],
        )
        approval_items = []
        for result in results:
            for finding in result.legal:
                if finding.status == "blocked" and finding.fact_field and finding.fact_value in (None, "", []):
                    approval_items.append(self.approvals.create(
                        context.task_id, "missing_required_fact", f"补充 {finding.title}",
                        f"{finding.title} 是交付前必须确认的商品事实。",
                        {"product_id": finding.product_id, "field_name": finding.fact_field, "rule_id": finding.rule_id},
                    ))
        blocked_count = sum(
            1
            for result in results
            for finding in [*result.legal, *result.shopify, *result.ebay]
            if finding.status == "blocked"
        )
        markdown = compliance_markdown(results)
        report = self.artifacts.create_text(
            context.task_id, self.name, "us_compliance_report", "us_compliance_report",
            content=markdown, extension="md", mime_type="text/markdown",
            dependencies=resolution["resource_ids"],
        )
        machine = self.artifacts.create_text(
            context.task_id, self.name, "compliance_result", "compliance_result",
            content=json_dumps({"results": [result.model_dump() for result in results]}),
            extension="json", mime_type="application/json", dependencies=[report["resource_id"]],
        )
        release_blocked = any(result.release_blocked for result in results)
        summary = (
            f"已完成 {len(results)} 个商品的合规检查，发现 {blocked_count} 项阻塞问题"
            f"，新增 {len(approval_items)} 项待确认事实。"
        )
        self._progress(context, summary, "completed")
        return {
            "summary": summary,
            "key_counts": {
                "products": len(results), "blocked_findings": blocked_count,
                "approvals": len(approval_items),
            },
            "output_resource_ids": [report["resource_id"], machine["resource_id"]],
            "status": "blocked" if release_blocked else "completed",
        }

    def _progress(self, context: ExecutionContext, message: str, phase: str) -> None:
        self.events.publish(context.task_id, "agent.progress", self.name, {
            "worker_name": self.name,
            "process_task_id": context.process_task_id,
            "message": message,
            "phase": phase,
        })

    def run(self, task_id: str, products: list[dict[str, Any]], conflicts: list[dict[str, Any]], dependencies: list[str]) -> dict[str, Any]:
        selected_skills = [self.skills.get(name) for name in ("us-apparel-compliance", "shopify-product-policy", "ebay-us-fashion-policy")]
        skill_instructions = [skill.load() for skill in selected_skills]
        active_skills = [skill.name for skill in selected_skills]
        self.events.publish(task_id, "worker.started", self.name, {"skills": active_skills, "skill_instruction_count": len(skill_instructions)})
        product_models = [CanonicalProduct.model_validate(product) for product in products]
        conflict_models = [CatalogConflict.model_validate(conflict) for conflict in conflicts]
        results = [self.service.evaluate(product, conflict_models) for product in product_models]
        approval_items = []
        for result in results:
            for finding in result.legal:
                if finding.status == "blocked" and finding.fact_field and finding.fact_value in (None, "", []):
                    approval_items.append(self.approvals.create(
                        task_id, "missing_required_fact", f"Provide {finding.title}",
                        f"{finding.title} is required before release.",
                        {"product_id": finding.product_id, "field_name": finding.fact_field, "rule_id": finding.rule_id},
                    ))
        markdown = compliance_markdown(results)
        report = self.artifacts.create_text(
            task_id, self.name, "us_compliance_report", "us_compliance_report",
            content=markdown, extension="md", mime_type="text/markdown", dependencies=dependencies,
        )
        machine = self.artifacts.create_text(
            task_id, self.name, "compliance_result", "compliance_result",
            content=json_dumps({"results": [result.model_dump() for result in results]}),
            extension="json", mime_type="application/json", dependencies=[report["id"]],
        )
        payload = {
            "results": [result.model_dump() for result in results],
            "release_blocked": any(result.release_blocked for result in results),
            "artifact_ids": [report["id"], machine["id"]],
            "approvals": approval_items,
        }
        self.events.publish(task_id, "worker.completed", self.name, {"release_blocked": payload["release_blocked"]})
        return payload
