from __future__ import annotations

from pathlib import Path
from typing import Any

from ..graph.service import CatalogGraphService
from ..intake.service import IntakeService
from ..platform.approvals import ApprovalService
from ..platform.artifacts import ArtifactService
from ..platform.events import EventStore
from ..platform.skills import SkillRegistry
from ..util import json_dumps


class CatalogStewardAgent:
    name = "catalog_steward_agent"
    description = "Owns canonical Product/SKU facts and classification candidates."

    def __init__(self, intake: IntakeService, graph: CatalogGraphService, artifacts: ArtifactService, approvals: ApprovalService, events: EventStore, skills: SkillRegistry) -> None:
        self.intake = intake
        self.graph = graph
        self.artifacts = artifacts
        self.approvals = approvals
        self.events = events
        self.skills = skills

    def run(self, task_id: str, paths: list[Path]) -> dict[str, Any]:
        selected_skills = [self.skills.get(name) for name in ("product-catalog", "womenswear-classification")]
        skill_instructions = [skill.load() for skill in selected_skills]
        active_skills = [skill.name for skill in selected_skills]
        self.events.publish(task_id, "worker.started", self.name, {"skills": active_skills, "skill_instruction_count": len(skill_instructions), "file_count": len(paths)})
        source_artifacts = [
            self.artifacts.import_file(task_id, self.name, "source_document", path.name, path, _mime(path))
            for path in paths
        ]
        batch = self.intake.parse(paths)
        graph_summary = self.graph.upsert_candidate_graph(batch.products, task_id)
        source_manifest = self.artifacts.create_text(
            task_id, self.name, "source_manifest", "source_manifest", content=json_dumps({
                "sources": batch.source_documents,
                "artifact_ids": [artifact["id"] for artifact in source_artifacts],
            }), extension="json", mime_type="application/json",
            dependencies=[artifact["id"] for artifact in source_artifacts],
        )
        canonical = self.artifacts.create_text(
            task_id, self.name, "canonical_product", "canonical_product", content=json_dumps({
                "products": [product.model_dump() for product in batch.products],
                "conflicts": [conflict.model_dump() for conflict in batch.conflicts],
            }), extension="json", mime_type="application/json", dependencies=[source_manifest["id"]],
        )
        classification = self.artifacts.create_text(
            task_id, self.name, "classification_result", "classification_result", content=json_dumps({
                "taxonomy": "womenswear-product@v1",
                "assignments": [
                    {"product_id": product.id, "fact_id": fact.id, **fact.taxonomy.model_dump()}
                    for product in batch.products for fact in product.facts if fact.taxonomy
                ],
            }), extension="json", mime_type="application/json", dependencies=[canonical["id"]],
        )
        approval_items = [
            self.approvals.create(
                task_id, "catalog_conflict", f"Confirm {conflict.field_name.replace('_', ' ')}",
                conflict.message, conflict.model_dump(),
            ) for conflict in batch.conflicts
        ]
        result = {
            "products": [product.model_dump() for product in batch.products],
            "conflicts": [conflict.model_dump() for conflict in batch.conflicts],
            "approvals": approval_items,
            "graph_summary": graph_summary,
            "artifact_ids": [source_manifest["id"], canonical["id"], classification["id"]],
        }
        self.events.publish(task_id, "worker.completed", self.name, {"product_count": len(batch.products), "conflict_count": len(batch.conflicts)})
        return result


def _mime(path: Path) -> str:
    import mimetypes
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"
