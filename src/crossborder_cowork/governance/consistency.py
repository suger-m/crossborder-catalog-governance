from __future__ import annotations

from typing import Iterable, Literal

from pydantic import BaseModel, Field

from ..catalog.models import CanonicalProduct
from ..compliance.us_apparel import ComplianceResult
from ..platforms.base import ListingDraft
from ..util import stable_id
from .import_validation import validate_ebay_draft, validate_shopify_draft


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


def review_catalog(
    products: list[CanonicalProduct],
    compliance: list[ComplianceResult],
    shopify: list[ListingDraft],
    ebay: list[ListingDraft],
    pending_approvals: int = 0,
    required_platforms: Iterable[str] | None = None,
) -> GovernanceDecision:
    findings: list[GovernanceFinding] = []
    platforms = set(required_platforms or ("shopify", "ebay_us"))
    if not platforms or not platforms.issubset({"shopify", "ebay_us"}):
        raise ValueError("Governance review requires Shopify and/or eBay US scope")
    compliance_by_product = {item.product_id: item for item in compliance}
    shopify_by_product = {item.product_id: item for item in shopify}
    ebay_by_product = {item.product_id: item for item in ebay}
    for product in products:
        legal = compliance_by_product.get(product.id)
        if legal:
            scoped_compliance = [*legal.legal]
            if "shopify" in platforms:
                scoped_compliance.extend(legal.shopify)
            if "ebay_us" in platforms:
                scoped_compliance.extend(legal.ebay)
            for item in scoped_compliance:
                if item.status == "blocked":
                    findings.append(_finding(product.id, "blocking", item.fact_field or item.rule_id, item.message, [item.scope]))
                elif item.status == "needs_confirmation":
                    findings.append(_finding(product.id, "confirmation", item.fact_field or item.rule_id, item.message, [item.scope]))
        left = shopify_by_product.get(product.id)
        right = ebay_by_product.get(product.id)
        missing_platforms = [
            platform
            for platform, draft in (("shopify", left), ("ebay_us", right))
            if platform in platforms and draft is None
        ]
        if missing_platforms:
            findings.append(_finding(
                product.id,
                "blocking",
                "listing",
                f"Required Listing draft is missing for: {', '.join(missing_platforms)}.",
                missing_platforms,
            ))
            continue
        canonical_skus = {sku.external_id for sku in product.skus}
        material = ", ".join(product.materials) or product.fiber_content
        selected_drafts = [
            draft
            for platform, draft in (("shopify", left), ("ebay_us", right))
            if platform in platforms and draft is not None
        ]
        for draft in selected_drafts:
            if draft.derived_from_product_version != product.version:
                findings.append(_finding(product.id, "blocking", "version", "A Listing draft was derived from a superseded product version.", [draft.platform]))
            if draft.platform == "shopify":
                rows = draft.data.get("rows", [])
                if {row.get("Variant SKU") for row in rows} != canonical_skus:
                    findings.append(_finding(product.id, "blocking", "sku", "Channel SKU set does not match the canonical product.", [draft.platform]))
                if {row.get("Metafield: custom.material [single_line_text_field]", "") for row in rows} != {material}:
                    findings.append(_finding(product.id, "blocking", "material", "Channel material facts do not match the canonical product.", [draft.platform]))
                if {row.get("Metafield: custom.country_of_origin [single_line_text_field]", "") for row in rows} != {product.country_of_origin}:
                    findings.append(_finding(product.id, "blocking", "country_of_origin", "Channel origin facts do not match the canonical product.", [draft.platform]))
                issues = validate_shopify_draft(draft)
            else:
                if {variation.get("sku") for variation in draft.data.get("variations", [])} != canonical_skus:
                    findings.append(_finding(product.id, "blocking", "sku", "Channel SKU set does not match the canonical product.", [draft.platform]))
                if draft.data.get("itemSpecifics", {}).get("Material", "") != material:
                    findings.append(_finding(product.id, "blocking", "material", "Channel material facts do not match the canonical product.", [draft.platform]))
                if draft.data.get("itemSpecifics", {}).get("Country/Region of Manufacture", "") != product.country_of_origin:
                    findings.append(_finding(product.id, "blocking", "country_of_origin", "Channel origin facts do not match the canonical product.", [draft.platform]))
                issues = validate_ebay_draft(draft)
            for issue in issues:
                findings.append(_finding(product.id, "blocking", issue.field, issue.message, [issue.platform]))
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
