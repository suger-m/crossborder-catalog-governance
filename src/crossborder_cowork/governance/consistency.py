from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..catalog.models import CanonicalProduct
from ..compliance.us_apparel import ComplianceResult
from ..platforms.base import ListingDraft
from ..util import stable_id


class GovernanceFinding(BaseModel):
    id: str
    product_id: str
    severity: Literal["info", "confirmation", "blocking"]
    field: str
    message: str
    platforms: list[str] = Field(default_factory=list)


class GovernanceDecision(BaseModel):
    status: Literal["approved", "needs_confirmation", "blocked"]
    ready_for_export: bool
    findings: list[GovernanceFinding] = Field(default_factory=list)


def review_catalog(products: list[CanonicalProduct], compliance: list[ComplianceResult], shopify: list[ListingDraft], ebay: list[ListingDraft], pending_approvals: int = 0) -> GovernanceDecision:
    findings: list[GovernanceFinding] = []
    compliance_by_product = {item.product_id: item for item in compliance}
    shopify_by_product = {item.product_id: item for item in shopify}
    ebay_by_product = {item.product_id: item for item in ebay}
    for product in products:
        legal = compliance_by_product.get(product.id)
        if legal:
            for item in [*legal.legal, *legal.shopify, *legal.ebay]:
                if item.status == "blocked":
                    findings.append(_finding(product.id, "blocking", item.fact_field or item.rule_id, item.message, [item.scope]))
                elif item.status == "needs_confirmation":
                    findings.append(_finding(product.id, "confirmation", item.fact_field or item.rule_id, item.message, [item.scope]))
        left = shopify_by_product.get(product.id)
        right = ebay_by_product.get(product.id)
        if not left or not right:
            findings.append(_finding(product.id, "blocking", "listing", "Both Shopify and eBay US drafts are required.", ["shopify", "ebay_us"]))
            continue
        if left.derived_from_product_version != product.version or right.derived_from_product_version != product.version:
            findings.append(_finding(product.id, "blocking", "version", "A Listing draft was derived from a superseded product version.", [left.platform, right.platform]))
        shopify_rows = left.data.get("rows", [])
        shopify_skus = {row.get("Variant SKU") for row in shopify_rows}
        ebay_skus = {variation.get("sku") for variation in right.data.get("variations", [])}
        canonical_skus = {sku.external_id for sku in product.skus}
        if shopify_skus != canonical_skus or ebay_skus != canonical_skus:
            findings.append(_finding(product.id, "blocking", "sku", "Channel SKU sets do not match the canonical product.", ["shopify", "ebay_us"]))
        material = ", ".join(product.materials) or product.fiber_content
        shopify_materials = {row.get("Metafield: custom.material [single_line_text_field]", "") for row in shopify_rows}
        ebay_material = right.data.get("itemSpecifics", {}).get("Material", "")
        if shopify_materials != {material} or ebay_material != material:
            findings.append(_finding(product.id, "blocking", "material", "Channel material facts do not match the canonical product.", ["shopify", "ebay_us"]))
        shopify_origins = {row.get("Metafield: custom.country_of_origin [single_line_text_field]", "") for row in shopify_rows}
        ebay_origin = right.data.get("itemSpecifics", {}).get("Country/Region of Manufacture", "")
        if shopify_origins != {product.country_of_origin} or ebay_origin != product.country_of_origin:
            findings.append(_finding(product.id, "blocking", "country_of_origin", "Channel origin facts do not match the canonical product.", ["shopify", "ebay_us"]))
    if pending_approvals:
        findings.append(_finding("catalog", "confirmation", "approval", f"{pending_approvals} Human Approval request(s) remain pending.", []))
    if any(item.severity == "blocking" for item in findings):
        return GovernanceDecision(status="blocked", ready_for_export=False, findings=findings)
    if any(item.severity == "confirmation" for item in findings):
        return GovernanceDecision(status="needs_confirmation", ready_for_export=False, findings=findings)
    return GovernanceDecision(status="approved", ready_for_export=True, findings=findings)


def _finding(product_id: str, severity: str, field: str, message: str, platforms: list[str]) -> GovernanceFinding:
    return GovernanceFinding(
        id=stable_id("gov", product_id, severity, field, message), product_id=product_id,
        severity=severity, field=field, message=message, platforms=platforms,
    )


def consistency_markdown(decision: GovernanceDecision) -> str:
    lines = ["# Catalog Consistency Report", "", f"Decision: **{decision.status}**", "", "| Severity | Product | Field | Message |", "|---|---|---|---|"]
    for item in decision.findings:
        lines.append(f"| {item.severity} | {item.product_id} | {item.field} | {item.message} |")
    if not decision.findings:
        lines.append("| info | catalog | all | Canonical and channel facts are consistent. |")
    return "\n".join(lines) + "\n"
