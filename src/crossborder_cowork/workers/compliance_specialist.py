from __future__ import annotations

from typing import Any

from ..catalog.models import CanonicalProduct, CatalogConflict
from ..compliance.us_apparel import UsApparelComplianceService, compliance_markdown
from ..platform.artifacts import ArtifactService
from ..platform.events import EventStore
from ..platform.skills import SkillRegistry
from ..platform.approvals import ApprovalService
from ..util import json_dumps


class ComplianceSpecialistAgent:
    name = "compliance_specialist_agent"
    description = "在不修改商品事实的前提下，应用美国服装法规与平台政策技能。"

    def __init__(self, service: UsApparelComplianceService, artifacts: ArtifactService, events: EventStore, skills: SkillRegistry, approvals: ApprovalService) -> None:
        self.service = service
        self.artifacts = artifacts
        self.events = events
        self.skills = skills
        self.approvals = approvals

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
