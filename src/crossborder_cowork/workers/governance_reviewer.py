from __future__ import annotations

from typing import Any

from ..catalog.models import CanonicalProduct
from ..compliance.us_apparel import ComplianceResult
from ..export.package import ExportPackageService
from ..governance.consistency import consistency_markdown, review_catalog
from ..platform.artifacts import ArtifactService
from ..platform.events import EventStore
from ..platform.skills import SkillRegistry
from ..platforms.base import ListingDraft
from ..util import json_dumps


class GovernanceReviewerAgent:
    name = "governance_reviewer_agent"
    description = "审核商品事实、合规阻塞项、证据、版本、一致性和交付就绪状态。"

    def __init__(self, artifacts: ArtifactService, events: EventStore, skills: SkillRegistry, exporter: ExportPackageService) -> None:
        self.artifacts = artifacts
        self.events = events
        self.skills = skills
        self.exporter = exporter

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
