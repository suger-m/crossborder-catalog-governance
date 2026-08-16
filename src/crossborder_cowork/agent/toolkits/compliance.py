from __future__ import annotations

import asyncio
from typing import Any

from ...catalog.models import CanonicalProduct, CatalogConflict
from ...compliance.us_apparel import compliance_markdown
from ...util import json_dumps
from ._base import BoundBusinessToolkit


class ComplianceToolkit(BoundBusinessToolkit):
    """Deterministic US apparel and marketplace-policy evaluation."""

    async def evaluate_us_apparel_compliance(
        self,
        product_resource_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Evaluate canonical products and persist human-readable and machine results."""
        return await asyncio.to_thread(
            self._evaluate_us_apparel_compliance, product_resource_ids,
        )

    def _evaluate_us_apparel_compliance(
        self,
        product_resource_ids: list[str] | None,
    ) -> dict[str, Any]:
        context = self._context()
        self._progress("正在解析规范商品和待确认事实。", "input_resolution")
        return self._execute(
            "evaluate_us_apparel_compliance",
            self._evaluate,
            context,
            product_resource_ids or [],
        )

    def _evaluate(
        self,
        context: Any,
        product_resource_ids: list[str],
    ) -> dict[str, Any]:
        resolution = self.app.project_context.resolve_inputs(
            context,
            resource_types=("product_collection", "canonical_product"),
            explicit_resource_ids=product_resource_ids or None,
        )
        if resolution["no_input"]:
            raise ValueError("没有可用于合规检查的规范商品资源")
        products_raw = self.app.project_context.get_canonical_products(
            context,
            resource_ids=resolution["resource_ids"],
        )
        products = [
            CanonicalProduct.model_validate(item.get("data", item))
            for item in products_raw
        ]
        pending = self.app.project_context.get_pending_approvals(context)
        conflicts = [
            CatalogConflict.model_validate(item["payload"])
            for item in pending
            if item.get("approval_type") == "catalog_conflict"
            and isinstance(item.get("payload"), dict)
        ]
        self._progress(
            f"正在检查 {len(products)} 个商品的美国法规与平台政策要求。",
            "compliance_check",
        )
        results = [self.app.compliance_service.evaluate(product, conflicts) for product in products]
        approvals = []
        for result in results:
            for finding in result.legal:
                if finding.status == "blocked" and finding.fact_field and finding.fact_value in (None, "", []):
                    approvals.append(self.app.approvals.create(
                        context.task_id,
                        "missing_required_fact",
                        f"补充 {finding.title}",
                        f"{finding.title} 是交付前必须确认的商品事实。",
                        {
                            "product_id": finding.product_id,
                            "field_name": finding.fact_field,
                            "rule_id": finding.rule_id,
                        },
                    ))
        blocked_count = sum(
            1
            for result in results
            for finding in [*result.legal, *result.shopify, *result.ebay]
            if finding.status == "blocked"
        )
        report = self.app.artifacts.create_text(
            context.task_id,
            self.worker_name,
            "us_compliance_report",
            "us_compliance_report",
            content=compliance_markdown(results),
            extension="md",
            mime_type="text/markdown",
            dependencies=resolution["resource_ids"],
        )
        machine = self.app.artifacts.create_text(
            context.task_id,
            self.worker_name,
            "compliance_result",
            "compliance_result",
            content=json_dumps({"results": [result.model_dump() for result in results]}),
            extension="json",
            mime_type="application/json",
            dependencies=[report["resource_id"]],
        )
        release_blocked = any(result.release_blocked for result in results)
        summary = (
            f"已完成 {len(results)} 个商品的合规检查，发现 {blocked_count} 项阻塞问题，"
            f"新增 {len(approvals)} 项待确认事实。"
        )
        self._progress(summary, "completed")
        return {
            "summary": summary,
            "key_counts": {
                "products": len(results),
                "blocked_findings": blocked_count,
                "approvals": len(approvals),
            },
            "output_resource_ids": [report["resource_id"], machine["resource_id"]],
            "status": "blocked" if release_blocked else "completed",
        }

    def get_tools(self) -> list[Any]:
        return self._tools(self.evaluate_us_apparel_compliance)
