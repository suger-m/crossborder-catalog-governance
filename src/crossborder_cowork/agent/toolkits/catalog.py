from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path
from typing import Any

from ...util import json_dumps
from ._base import BoundBusinessToolkit


class CatalogToolkit(BoundBusinessToolkit):
    """Deterministic catalog intake and canonical Product/SKU persistence."""

    async def build_canonical_catalog(self) -> dict[str, Any]:
        """Parse bound task materials and persist canonical Product/SKU resources."""
        return await asyncio.to_thread(self._build_canonical_catalog)

    def _build_canonical_catalog(self) -> dict[str, Any]:
        context = self._context()
        paths = [Path(path) for path in self.app.materials.task_paths(context.task_id)]
        if not paths:
            raise ValueError("当前任务没有绑定可处理的商品素材")

        self._progress("正在读取商品素材并识别 Product/SKU 层级。", "material_intake")
        source_artifacts = self._execute(
            "build_canonical_catalog",
            self._build,
            context,
            paths,
        )
        self._progress(source_artifacts["summary"], "completed")
        return source_artifacts

    def _build(self, context: Any, paths: list[Path]) -> dict[str, Any]:
        imported = [
            self.app.artifacts.import_file(
                context.task_id,
                self.worker_name,
                "source_document",
                path.name,
                path,
                mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            )
            for path in paths
        ]
        batch = self.app.intake.parse(paths, context.project_id)
        graph_summary = self.app.graph.upsert_candidate_graph(
            batch.products,
            context.task_id,
            context.project_id,
        )
        source_manifest = self.app.artifacts.create_text(
            context.task_id,
            self.worker_name,
            "source_manifest",
            "source_manifest",
            content=json_dumps({
                "sources": batch.source_documents,
                "artifact_ids": [artifact["id"] for artifact in imported],
            }),
            extension="json",
            mime_type="application/json",
            dependencies=[artifact["resource_id"] for artifact in imported],
        )
        canonical = self.app.artifacts.create_text(
            context.task_id,
            self.worker_name,
            "canonical_product",
            "canonical_product",
            content=json_dumps({
                "products": [product.model_dump() for product in batch.products],
                "conflicts": [conflict.model_dump() for conflict in batch.conflicts],
            }),
            extension="json",
            mime_type="application/json",
            dependencies=[source_manifest["resource_id"]],
        )
        classification = self.app.artifacts.create_text(
            context.task_id,
            self.worker_name,
            "classification_result",
            "classification_result",
            content=json_dumps({
                "taxonomy": "womenswear-product@v1",
                "assignments": [
                    {"product_id": product.id, "fact_id": fact.id, **fact.taxonomy.model_dump()}
                    for product in batch.products
                    for fact in product.facts
                    if fact.taxonomy
                ],
            }),
            extension="json",
            mime_type="application/json",
            dependencies=[canonical["resource_id"]],
        )
        approvals = [
            self.app.approvals.create(
                context.task_id,
                "catalog_conflict",
                f"确认 {conflict.field_name}",
                conflict.message,
                conflict.model_dump(),
            )
            for conflict in batch.conflicts
        ]
        collection = self.app.resources.create(
            project_id=context.project_id,
            resource_type="product_collection",
            logical_key="canonical-products",
            owner_worker_name=self.worker_name,
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
        sku_count = sum(len(product.skus) for product in batch.products)
        summary = (
            f"已建立 {len(batch.products)} 个规范商品和 {sku_count} 个 SKU，"
            f"发现 {len(batch.conflicts)} 项需要确认的事实冲突。"
        )
        return {
            "summary": summary,
            "key_counts": {
                "products": len(batch.products),
                "skus": sku_count,
                "conflicts": len(batch.conflicts),
                "approvals": len(approvals),
                "graph_nodes": sum(int(item.get("count") or 0) for item in graph_summary.get("nodes", [])),
            },
            "output_resource_ids": [
                collection["id"],
                source_manifest["resource_id"],
                canonical["resource_id"],
                classification["resource_id"],
            ],
            "status": "waiting_approval" if approvals else "completed",
        }

    def get_tools(self) -> list[Any]:
        return self._tools(self.build_canonical_catalog)
