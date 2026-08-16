from __future__ import annotations

import asyncio
import json
from typing import Any

from ...catalog.models import CanonicalProduct
from ...compliance.us_apparel import ComplianceResult
from ...governance.consistency import consistency_markdown, review_catalog
from ...platforms.base import ListingDraft
from ...util import json_dumps
from ._base import BoundBusinessToolkit


class GovernanceToolkit(BoundBusinessToolkit):
    """Review durable catalog resources and optionally create an export package."""

    async def review_catalog_release(
        self,
        create_export_package: bool = False,
        product_resource_ids: list[str] | None = None,
        compliance_resource_ids: list[str] | None = None,
        listing_resource_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Validate cross-platform consistency; create a package only when requested and ready."""
        return await asyncio.to_thread(
            self._review_catalog_release,
            create_export_package,
            product_resource_ids,
            compliance_resource_ids,
            listing_resource_ids,
        )

    def _review_catalog_release(
        self,
        create_export_package: bool,
        product_resource_ids: list[str] | None,
        compliance_resource_ids: list[str] | None,
        listing_resource_ids: list[str] | None,
    ) -> dict[str, Any]:
        context = self._context()
        self._progress("正在解析商品、合规、平台草稿和审批资源。", "input_resolution")
        return self._execute(
            "review_catalog_release",
            self._review,
            context,
            bool(create_export_package),
            product_resource_ids or [],
            compliance_resource_ids or [],
            listing_resource_ids or [],
        )

    def _review(
        self,
        context: Any,
        create_export_package: bool,
        product_resource_ids: list[str],
        compliance_resource_ids: list[str],
        listing_resource_ids: list[str],
    ) -> dict[str, Any]:
        product_input = self.app.project_context.resolve_inputs(
            context,
            resource_types=("product_collection", "canonical_product"),
            explicit_resource_ids=product_resource_ids or None,
        )
        compliance_input = self.app.project_context.resolve_inputs(
            context,
            resource_types=("compliance_result",),
            explicit_resource_ids=compliance_resource_ids or None,
        )
        listing_input = self.app.project_context.resolve_inputs(
            context,
            resource_types=("listing_draft", "shopify_listing", "ebay_listing"),
            explicit_resource_ids=listing_resource_ids or None,
        )
        if product_input["no_input"]:
            raise ValueError("没有可用于治理审核的规范商品资源")
        if listing_input["no_input"]:
            raise ValueError("没有可用于治理审核的平台草稿资源")

        products = [
            CanonicalProduct.model_validate(item.get("data", item))
            for item in self.app.project_context.get_canonical_products(
                context,
                resource_ids=product_input["resource_ids"],
            )
        ]
        listings = [
            ListingDraft.model_validate(item.get("data", item))
            for item in self.app.project_context.get_listing_drafts(
                context,
                resource_ids=listing_input["resource_ids"],
            )
        ]
        compliance: list[ComplianceResult] = []
        for resource in compliance_input["resources"]:
            if resource.get("storage_kind") != "artifact":
                continue
            page = self.app.project_context.read_artifact_text(
                context,
                resource_id=resource["id"],
                offset=0,
                limit=65_536,
            )
            payload = json.loads(page["content"] or "{}")
            compliance.extend(
                ComplianceResult.model_validate(item)
                for item in payload.get("results", [])
            )
        pending = self.app.project_context.get_pending_approvals(context)
        self._progress("正在校验事实一致性、规则结论、证据版本和交付阻塞项。", "governance_review")
        shopify = [item for item in listings if item.platform == "shopify"]
        ebay = [item for item in listings if item.platform == "ebay_us"]
        decision = review_catalog(
            products,
            compliance,
            shopify,
            ebay,
            len(pending),
            {item.platform for item in listings},
        )
        dependencies = list(dict.fromkeys([
            *product_input["resource_ids"],
            *compliance_input["resource_ids"],
            *listing_input["resource_ids"],
        ]))
        consistency = self.app.artifacts.create_text(
            context.task_id,
            self.worker_name,
            "catalog_consistency_report",
            "catalog_consistency_report",
            content=consistency_markdown(decision),
            extension="md",
            mime_type="text/markdown",
            dependencies=dependencies,
        )
        review = self.app.artifacts.create_text(
            context.task_id,
            self.worker_name,
            "release_decision",
            "release_decision",
            content=json_dumps(decision.model_dump()),
            extension="json",
            mime_type="application/json",
            dependencies=[consistency["resource_id"], *dependencies],
        )
        output_resource_ids = [consistency["resource_id"], review["resource_id"]]
        package = None
        if decision.ready_for_export and create_export_package:
            sku_matrix = self.app.exporter.create_sku_matrix(
                context.task_id,
                products,
                [review["resource_id"]],
            )
            artifact_ids = [
                str(resource["storage_ref"])
                for resource in [*compliance_input["resources"], *listing_input["resources"]]
                if resource.get("storage_kind") == "artifact"
            ]
            artifact_ids.extend([consistency["id"], review["id"], sku_matrix["id"]])
            package = self.app.exporter.create_package(
                context.task_id,
                artifact_ids,
                decision.model_dump(),
            )
            output_resource_ids.extend([sku_matrix["resource_id"], package["resource_id"]])

        status = {
            "approved": "completed",
            "needs_confirmation": "waiting_approval",
            "blocked": "blocked",
        }[decision.status]
        summary = (
            f"治理审核结论为“{decision.status}”，发现 {len(decision.findings)} 项一致性问题，"
            f"{'已生成导出包' if package else '当前未生成导出包'}。"
        )
        self._progress(summary, "completed")
        return {
            "summary": summary,
            "key_counts": {
                "findings": len(decision.findings),
                "pending_approvals": len(pending),
                "packages": 1 if package else 0,
            },
            "output_resource_ids": output_resource_ids,
            "status": status,
        }

    def get_tools(self) -> list[Any]:
        return self._tools(self.review_catalog_release)
