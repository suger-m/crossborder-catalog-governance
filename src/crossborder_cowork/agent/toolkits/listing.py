from __future__ import annotations

import asyncio
from typing import Any

from ...catalog.models import CanonicalProduct
from ...graph.models import GraphEdge, GraphNode
from ...platforms.ebay_us import build_ebay_draft
from ...platforms.shopify import build_shopify_draft, shopify_csv
from ...util import json_dumps, stable_id, utc_now
from ._base import BoundBusinessToolkit


SUPPORTED_PLATFORMS = {"shopify", "ebay_us"}


class ListingToolkit(BoundBusinessToolkit):
    """Create validated draft listings without publishing them."""

    async def create_listing_drafts(
        self,
        platforms: list[str],
        product_resource_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create Shopify and/or eBay US draft resources for canonical products."""
        return await asyncio.to_thread(
            self._create_listing_drafts, platforms, product_resource_ids,
        )

    def _create_listing_drafts(
        self,
        platforms: list[str],
        product_resource_ids: list[str] | None,
    ) -> dict[str, Any]:
        aliases = {"ebay": "ebay_us", "ebay us": "ebay_us", "ebay-us": "ebay_us"}
        selected = list(dict.fromkeys(
            aliases.get(str(item).strip().lower(), str(item).strip().lower())
            for item in platforms
            if str(item).strip()
        ))
        if not selected:
            raise ValueError("至少选择 Shopify 或 eBay US 之一")
        unsupported = set(selected) - SUPPORTED_PLATFORMS
        if unsupported:
            raise ValueError(f"不支持的平台: {', '.join(sorted(unsupported))}")
        context = self._context()
        self._progress("正在解析规范商品和目标平台范围。", "input_resolution")
        return self._execute(
            "create_listing_drafts",
            self._create,
            context,
            selected,
            product_resource_ids or [],
        )

    def _create(
        self,
        context: Any,
        platforms: list[str],
        product_resource_ids: list[str],
    ) -> dict[str, Any]:
        resolution = self.app.project_context.resolve_inputs(
            context,
            resource_types=("product_collection", "canonical_product"),
            explicit_resource_ids=product_resource_ids or None,
        )
        if resolution["no_input"]:
            raise ValueError("没有可用于生成平台草稿的规范商品资源")
        products_raw = self.app.project_context.get_canonical_products(
            context,
            resource_ids=resolution["resource_ids"],
        )
        products = [
            CanonicalProduct.model_validate(item.get("data", item))
            for item in products_raw
        ]
        labels = {"shopify": "Shopify", "ebay_us": "eBay 美国站"}
        self._progress(
            f"正在为 {len(products)} 个商品生成 {' 与 '.join(labels[item] for item in platforms)} 草稿。",
            "draft_generation",
        )
        shopify = [build_shopify_draft(product) for product in products] if "shopify" in platforms else []
        ebay = [build_ebay_draft(product) for product in products] if "ebay_us" in platforms else []

        now = utc_now()
        for draft in [*shopify, *ebay]:
            self.app.database.execute(
                """INSERT INTO listings(
                       id,project_id,process_task_id,product_id,platform,version,
                       derived_from_product_version,platform_rule_version,status,
                       data_json,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET project_id=excluded.project_id,
                       process_task_id=excluded.process_task_id,status=excluded.status,
                       data_json=excluded.data_json,updated_at=excluded.updated_at""",
                (
                    draft.id,
                    context.project_id,
                    context.process_task_id,
                    draft.product_id,
                    draft.platform,
                    1,
                    draft.derived_from_product_version,
                    draft.platform_rule_version,
                    draft.status,
                    json_dumps(draft.model_dump()),
                    now,
                    now,
                ),
            )
            platform_id = stable_id("platform", context.project_id, draft.platform)
            self.app.graph.add_node(
                GraphNode(
                    id=platform_id,
                    node_type="Platform",
                    state="confirmed",
                    data={"name": draft.platform},
                ),
                context.project_id,
            )
            self.app.graph.add_node(
                GraphNode(
                    id=draft.id,
                    node_type="Listing",
                    data={"platform": draft.platform, "status": draft.status, "version": 1},
                ),
                context.project_id,
            )
            self.app.graph.add_edge(
                GraphEdge(
                    id=stable_id("edge", context.project_id, draft.id, "DERIVED_FROM", draft.product_id),
                    source_id=draft.id,
                    relation_type="DERIVED_FROM",
                    target_id=draft.product_id,
                ),
                context.project_id,
            )
            self.app.graph.add_edge(
                GraphEdge(
                    id=stable_id("edge", context.project_id, draft.product_id, "LISTED_ON", platform_id),
                    source_id=draft.product_id,
                    relation_type="LISTED_ON",
                    target_id=platform_id,
                ),
                context.project_id,
            )

        output_resource_ids: list[str] = []
        if shopify:
            resource = self.app.resources.create(
                project_id=context.project_id,
                resource_type="listing_draft",
                logical_key="shopify",
                owner_worker_name=self.worker_name,
                source_task_id=context.task_id,
                source_step_id=(context.process_task_id if context.process_task_id != context.task_id else ""),
                storage_kind="database",
                storage_ref="shopify",
                status="active",
                metadata={"platform": "shopify", "listing_ids": [item.id for item in shopify]},
            )
            artifact = self.app.artifacts.create_text(
                context.task_id,
                self.worker_name,
                "shopify_listing",
                "shopify_listing",
                content=shopify_csv(shopify),
                extension="csv",
                mime_type="text/csv",
                dependencies=resolution["resource_ids"],
            )
            output_resource_ids.extend([resource["id"], artifact["resource_id"]])
        if ebay:
            resource = self.app.resources.create(
                project_id=context.project_id,
                resource_type="listing_draft",
                logical_key="ebay_us",
                owner_worker_name=self.worker_name,
                source_task_id=context.task_id,
                source_step_id=(context.process_task_id if context.process_task_id != context.task_id else ""),
                storage_kind="database",
                storage_ref="ebay_us",
                status="active",
                metadata={"platform": "ebay_us", "listing_ids": [item.id for item in ebay]},
            )
            artifact = self.app.artifacts.create_text(
                context.task_id,
                self.worker_name,
                "ebay_listing",
                "ebay_listing",
                content=json_dumps({"listings": [draft.model_dump() for draft in ebay]}),
                extension="json",
                mime_type="application/json",
                dependencies=resolution["resource_ids"],
            )
            output_resource_ids.extend([resource["id"], artifact["resource_id"]])
        localization = self.app.artifacts.create_text(
            context.task_id,
            self.worker_name,
            "localization_notes",
            "localization_notes",
            content=_localization_markdown(shopify, ebay),
            extension="md",
            mime_type="text/markdown",
            dependencies=resolution["resource_ids"],
        )
        gap_count = sum(len(item.gaps) for item in [*shopify, *ebay])
        output_resource_ids.append(localization["resource_id"])
        summary = (
            f"已生成 {len(shopify)} 份 Shopify 草稿和 {len(ebay)} 份 eBay 美国站草稿，"
            f"形成 {len(output_resource_ids)} 项可复用资源，保留 {gap_count} 项缺失字段。"
        )
        self._progress(summary, "completed")
        return {
            "summary": summary,
            "key_counts": {
                "shopify": len(shopify),
                "ebay_us": len(ebay),
                "output_resources": len(output_resource_ids),
                "gaps": gap_count,
            },
            "output_resource_ids": output_resource_ids,
            "status": "completed",
        }

    def get_tools(self) -> list[Any]:
        return self._tools(self.create_listing_drafts)


def _localization_markdown(shopify: list[Any], ebay: list[Any]) -> str:
    lines = [
        "# en-US Localization Notes",
        "",
        "All localized content is derived from canonical product facts. Missing facts remain explicit Listing gaps.",
        "",
    ]
    by_product: dict[str, dict[str, Any]] = {}
    for draft in [*shopify, *ebay]:
        by_product.setdefault(draft.product_id, {})[draft.platform] = draft
    for product_id, drafts in by_product.items():
        lines.extend([f"## Product `{product_id}`", ""])
        for platform, label in (("shopify", "Shopify"), ("ebay_us", "eBay")):
            draft = drafts.get(platform)
            if draft:
                lines.extend([f"- {label} title: {draft.title}", f"- {label} gaps: {len(draft.gaps)}"])
        lines.append("")
    return "\n".join(lines)
