from __future__ import annotations

import html
from typing import Any

from ..catalog.models import CanonicalProduct
from ..platform.artifacts import ArtifactService
from ..platform.database import Database
from ..platform.events import EventStore
from ..platform.skills import SkillRegistry
from ..platforms.ebay_us import build_ebay_draft
from ..platforms.shopify import build_shopify_draft, shopify_csv
from ..util import json_dumps, utc_now
from ..platform.model_runtime import AgentModelRuntime
from ..graph.service import CatalogGraphService
from ..graph.models import GraphNode, GraphEdge
from ..util import stable_id


class ListingOperationsAgent:
    name = "listing_operations_agent"
    description = "Creates localized Shopify and eBay US drafts from canonical product versions."

    def __init__(self, db: Database, artifacts: ArtifactService, events: EventStore, skills: SkillRegistry, model_runtime: AgentModelRuntime, graph: CatalogGraphService) -> None:
        self.db = db
        self.artifacts = artifacts
        self.events = events
        self.skills = skills
        self.model_runtime = model_runtime
        self.graph = graph

    def run(self, task_id: str, products: list[dict[str, Any]], dependencies: list[str]) -> dict[str, Any]:
        selected_skills = [self.skills.get(name) for name in ("product-localization-en-us", "shopify-listing", "ebay-us-listing")]
        skill_instructions = [skill.load() for skill in selected_skills]
        active_skills = [skill.name for skill in selected_skills]
        self.events.publish(task_id, "worker.started", self.name, {"skills": active_skills, "skill_instruction_count": len(skill_instructions), "model": self.model_runtime.readiness("worker")})
        product_models = [CanonicalProduct.model_validate(product) for product in products]
        shopify = [build_shopify_draft(product) for product in product_models]
        ebay = [build_ebay_draft(product) for product in product_models]
        self._enhance_localization(task_id, product_models, shopify, ebay)
        now = utc_now()
        for draft in [*shopify, *ebay]:
            self.db.execute(
                """INSERT INTO listings(id,product_id,platform,version,derived_from_product_version,platform_rule_version,status,data_json,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,data_json=excluded.data_json,updated_at=excluded.updated_at""",
                (draft.id, draft.product_id, draft.platform, 1, draft.derived_from_product_version,
                 draft.platform_rule_version, draft.status, json_dumps(draft.model_dump()), now, now),
            )
            platform_id = "platform_shopify" if draft.platform == "shopify" else "platform_ebay_us"
            self.graph.add_node(GraphNode(id=platform_id, node_type="Platform", state="confirmed", data={"name": draft.platform}))
            self.graph.add_node(GraphNode(id=draft.id, node_type="Listing", data={"platform": draft.platform, "status": draft.status, "version": 1}))
            self.graph.add_edge(GraphEdge(id=stable_id("edge", draft.id, "DERIVED_FROM", draft.product_id), source_id=draft.id, relation_type="DERIVED_FROM", target_id=draft.product_id))
            self.graph.add_edge(GraphEdge(id=stable_id("edge", draft.product_id, "LISTED_ON", platform_id), source_id=draft.product_id, relation_type="LISTED_ON", target_id=platform_id))
        shopify_artifact = self.artifacts.create_text(
            task_id, self.name, "shopify_listing", "shopify_listing", content=shopify_csv(shopify),
            extension="csv", mime_type="text/csv", dependencies=dependencies,
        )
        ebay_artifact = self.artifacts.create_text(
            task_id, self.name, "ebay_listing", "ebay_listing", content=json_dumps({"listings": [draft.model_dump() for draft in ebay]}),
            extension="json", mime_type="application/json", dependencies=dependencies,
        )
        localization = self.artifacts.create_text(
            task_id, self.name, "localization_notes", "localization_notes", content=_localization_markdown(shopify, ebay),
            extension="md", mime_type="text/markdown", dependencies=dependencies,
        )
        result = {
            "shopify": [draft.model_dump() for draft in shopify],
            "ebay": [draft.model_dump() for draft in ebay],
            "artifact_ids": [shopify_artifact["id"], ebay_artifact["id"], localization["id"]],
        }
        self.events.publish(task_id, "worker.completed", self.name, {"shopify_count": len(shopify), "ebay_count": len(ebay)})
        return result

    def _enhance_localization(self, task_id: str, products: list[CanonicalProduct], shopify: list, ebay: list) -> None:
        if not self.model_runtime.readiness("worker")["configured"]:
            return
        compact = [{
            "product_id": product.id, "title": product.title, "description": product.description,
            "category": product.category, "garment_type": product.garment_type,
            "materials": product.materials, "fiber_content": product.fiber_content,
            "origin": product.country_of_origin, "claims": product.claims,
        } for product in products]
        try:
            payload = self.model_runtime.complete_json(
                "worker",
                "You are the listing_operations_agent using the product-localization-en-us skill. Return JSON with an items array. For each product_id provide title and description in concise en-US. Preserve all facts exactly, add no claims, certifications, materials, origins, measurements, or product capabilities.",
                json_dumps({"products": compact}),
            )
            by_id = {str(item.get("product_id")): item for item in payload.get("items", []) if isinstance(item, dict)}
            for draft in [*shopify, *ebay]:
                item = by_id.get(draft.product_id)
                if not item:
                    continue
                title = str(item.get("title") or "").strip()
                description = str(item.get("description") or "").strip()
                if title:
                    draft.title = title[:80] if draft.platform == "ebay_us" else title
                if description:
                    draft.description = description
                if draft.platform == "shopify" and draft.data.get("rows"):
                    draft.data["rows"][0]["Title"] = draft.title
                    draft.data["rows"][0]["Body (HTML)"] = f"<p>{html.escape(draft.description)}</p>" if draft.description else ""
                if draft.platform == "ebay_us":
                    draft.data["title"] = draft.title
                    draft.data["description"] = draft.description
            self.events.publish(task_id, "agent.model_completed", self.name, {"operation": "en_us_localization", "product_count": len(by_id)})
        except Exception as exc:
            self.events.publish(task_id, "agent.model_fallback", self.name, {"operation": "en_us_localization", "error": str(exc)[:500]})


def _localization_markdown(shopify: list, ebay: list) -> str:
    lines = ["# en-US Localization Notes", "", "All localized content is derived from canonical product facts. Missing facts remain explicit Listing gaps.", ""]
    for left, right in zip(shopify, ebay):
        lines.extend([
            f"## Product `{left.product_id}`", "",
            f"- Shopify title: {left.title}", f"- eBay title: {right.title}",
            f"- Shopify gaps: {len(left.gaps)}", f"- eBay gaps: {len(right.gaps)}", "",
        ])
    return "\n".join(lines)
