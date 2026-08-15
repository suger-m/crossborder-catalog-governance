from __future__ import annotations

from pathlib import Path
from typing import Any

from ..graph.service import CatalogGraphService
from ..intake.service import IntakeService
from ..platform.approvals import ApprovalService
from ..platform.artifacts import ArtifactService
from ..platform.events import EventStore
from ..platform.skills import SkillRegistry
from ..platform.execution_context import ExecutionContext
from ..platform.materials import ProjectMaterialService
from ..platform.resources import ProjectResourceService
from ..platform.tool_executor import ToolExecutor
from ..util import json_dumps


class CatalogStewardAgent:
    name = "catalog_steward_agent"
    description = "负责规范 Product/SKU 商品事实和分类候选。"

    def __init__(
        self,
        intake: IntakeService,
        graph: CatalogGraphService,
        artifacts: ArtifactService,
        approvals: ApprovalService,
        events: EventStore,
        skills: SkillRegistry,
        materials: ProjectMaterialService | None = None,
        resources: ProjectResourceService | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        self.intake = intake
        self.graph = graph
        self.artifacts = artifacts
        self.approvals = approvals
        self.events = events
        self.skills = skills
        self.materials = materials
        self.resources = resources
        self.tool_executor = tool_executor

    def run_for_workforce(
        self,
        context: ExecutionContext,
        task_content: str,
        dependencies: list[Any],
    ) -> dict[str, Any]:
        if not self.materials or not self.resources or not self.tool_executor:
            raise RuntimeError("Catalog Steward Workforce services are not configured")
        paths = [Path(path) for path in self.materials.task_paths(context.task_id)]
        if not paths:
            raise ValueError("商品目录专员没有可处理的项目素材")
        self._progress(context, "正在读取所选商品素材并识别 Product/SKU 层级。", "material_intake")
        selected_skills = [self.skills.get(name) for name in ("product-catalog", "womenswear-classification")]
        for skill in selected_skills:
            skill.load()

        source_artifacts = self.tool_executor.execute(
            "import_product_materials",
            context,
            lambda: [
                self.artifacts.import_file(
                    context.task_id, self.name, "source_document", path.name, path, _mime(path)
                )
                for path in paths
            ],
        )
        batch = self.tool_executor.execute(
            "parse_product_sources",
            context,
            self.intake.parse,
            paths,
            context.project_id,
        )
        self._progress(
            context,
            f"已识别 {len(batch.products)} 个商品，正在校验分类与事实来源。",
            "fact_validation",
        )
        graph_summary = self.tool_executor.execute(
            "write_product_graph",
            context,
            self.graph.upsert_candidate_graph,
            batch.products,
            context.task_id,
            context.project_id,
        )
        source_manifest = self.artifacts.create_text(
            context.task_id, self.name, "source_manifest", "source_manifest", content=json_dumps({
                "sources": batch.source_documents,
                "artifact_ids": [artifact["id"] for artifact in source_artifacts],
            }), extension="json", mime_type="application/json",
            dependencies=[artifact["resource_id"] for artifact in source_artifacts],
        )
        canonical = self.artifacts.create_text(
            context.task_id, self.name, "canonical_product", "canonical_product", content=json_dumps({
                "products": [product.model_dump() for product in batch.products],
                "conflicts": [conflict.model_dump() for conflict in batch.conflicts],
            }), extension="json", mime_type="application/json", dependencies=[source_manifest["resource_id"]],
        )
        classification = self.artifacts.create_text(
            context.task_id, self.name, "classification_result", "classification_result", content=json_dumps({
                "taxonomy": "womenswear-product@v1",
                "assignments": [
                    {"product_id": product.id, "fact_id": fact.id, **fact.taxonomy.model_dump()}
                    for product in batch.products for fact in product.facts if fact.taxonomy
                ],
            }), extension="json", mime_type="application/json", dependencies=[canonical["resource_id"]],
        )
        approval_items = self.tool_executor.execute(
            "create_catalog_approvals",
            context,
            lambda: [
                self.approvals.create(
                    context.task_id, "catalog_conflict", f"确认 {conflict.field_name}",
                    conflict.message, conflict.model_dump(),
                )
                for conflict in batch.conflicts
            ],
        )
        collection = self.resources.create(
            project_id=context.project_id,
            resource_type="product_collection",
            logical_key="canonical-products",
            owner_worker_name=self.name,
            source_task_id=context.task_id,
            source_step_id=context.process_task_id,
            storage_kind="database",
            storage_ref=context.project_id,
            status="active",
            metadata={
                "product_ids": [product.id for product in batch.products],
                "product_count": len(batch.products),
                "conflict_count": len(batch.conflicts),
            },
        )
        output_resource_ids = [
            collection["id"], source_manifest["resource_id"], canonical["resource_id"],
            classification["resource_id"],
        ]
        summary = (
            f"已建立 {len(batch.products)} 个规范商品和 {sum(len(item.skus) for item in batch.products)} 个 SKU"
            f"，发现 {len(batch.conflicts)} 项需要确认的事实冲突。"
        )
        self._progress(context, summary, "completed")
        return {
            "summary": summary,
            "key_counts": {
                "products": len(batch.products),
                "skus": sum(len(item.skus) for item in batch.products),
                "conflicts": len(batch.conflicts),
                "approvals": len(approval_items),
            },
            "output_resource_ids": output_resource_ids,
            "status": "waiting_approval" if approval_items else "completed",
            "graph_summary": graph_summary,
        }

    def _progress(self, context: ExecutionContext, message: str, phase: str) -> None:
        self.events.publish(context.task_id, "agent.progress", self.name, {
            "worker_name": self.name,
            "process_task_id": context.process_task_id,
            "message": message,
            "phase": phase,
        })

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
