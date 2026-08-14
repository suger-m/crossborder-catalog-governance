from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ..catalog.models import CanonicalProduct, CatalogConflict
from ..taxonomy.registry import TaxonomyRegistry
from ..util import stable_id


FindingStatus = Literal["pass", "needs_evidence", "needs_confirmation", "blocked"]


class ComplianceFinding(BaseModel):
    id: str
    product_id: str
    scope: Literal["us_legal", "shopify_policy", "ebay_policy"]
    rule_id: str
    title: str
    status: FindingStatus
    message: str
    fact_field: str = ""
    fact_value: Any = None
    rule_source_url: str = ""
    evidence_fact_ids: list[str] = Field(default_factory=list)


class ComplianceResult(BaseModel):
    product_id: str
    legal: list[ComplianceFinding] = Field(default_factory=list)
    shopify: list[ComplianceFinding] = Field(default_factory=list)
    ebay: list[ComplianceFinding] = Field(default_factory=list)

    @property
    def release_blocked(self) -> bool:
        return any(item.status == "blocked" for item in [*self.legal, *self.shopify, *self.ebay])


class UsApparelComplianceService:
    def __init__(self, taxonomy: TaxonomyRegistry) -> None:
        self.taxonomy = taxonomy

    def evaluate(self, product: CanonicalProduct, conflicts: list[CatalogConflict] | None = None) -> ComplianceResult:
        conflicts = conflicts or []
        legal = [
            self._required(product, "fiber_content", "us.requirement.fiber_content"),
            self._required(product, "country_of_origin", "us.requirement.country_origin"),
            self._required(product, "care_instructions", "us.requirement.care_label"),
            self._required(product, "manufacturer", "us.requirement.manufacturer_identity", missing_status="needs_confirmation"),
            self._size_finding(product),
        ]
        for conflict in conflicts:
            if conflict.product_id == product.id:
                legal.append(self._conflict_finding(product, conflict))
        legal.extend(self._claim_findings(product))
        shopify = self._shopify_policy(product)
        ebay = self._ebay_policy(product)
        return ComplianceResult(product_id=product.id, legal=legal, shopify=shopify, ebay=ebay)

    def _required(self, product: CanonicalProduct, field: str, rule_id: str, missing_status: FindingStatus = "blocked") -> ComplianceFinding:
        node = self.taxonomy.get_node(rule_id, "v1")
        value = getattr(product, field)
        fact_ids = [fact.id for fact in product.facts if fact.field_name == field]
        status: FindingStatus = "pass" if str(value or "").strip() else missing_status
        return ComplianceFinding(
            id=stable_id("finding", product.id, "us_legal", rule_id), product_id=product.id,
            scope="us_legal", rule_id=rule_id, title=node["label"], status=status,
            message=(f"{node['label']} is present." if status == "pass" else f"{node['label']} is missing."),
            fact_field=field, fact_value=value, rule_source_url=node.get("source_url", ""), evidence_fact_ids=fact_ids,
        )

    def _size_finding(self, product: CanonicalProduct) -> ComplianceFinding:
        sizes = [sku.size for sku in product.skus if sku.size]
        status: FindingStatus = "pass" if sizes and len(sizes) == len(product.skus) else "needs_evidence"
        return ComplianceFinding(
            id=stable_id("finding", product.id, "us_legal", "us.requirement.size_accuracy"),
            product_id=product.id, scope="us_legal", rule_id="us.requirement.size_accuracy",
            title="Size Information", status=status,
            message="All SKUs contain size information." if status == "pass" else "One or more SKUs lack size information.",
            fact_field="skus.size", fact_value=sizes,
        )

    def _conflict_finding(self, product: CanonicalProduct, conflict: CatalogConflict) -> ComplianceFinding:
        rule_id = {
            "country_of_origin": "us.requirement.country_origin",
            "fiber_content": "us.requirement.fiber_content",
            "manufacturer": "us.requirement.manufacturer_identity",
        }.get(conflict.field_name, "us.requirement.size_accuracy")
        node = self.taxonomy.get_node(rule_id, "v1")
        return ComplianceFinding(
            id=stable_id("finding", product.id, "conflict", conflict.id), product_id=product.id,
            scope="us_legal", rule_id=rule_id, title=f"Conflicting {node['label']}",
            status="needs_confirmation", message=conflict.message, fact_field=conflict.field_name,
            fact_value=conflict.values, rule_source_url=node.get("source_url", ""), evidence_fact_ids=conflict.fact_ids,
        )

    def _claim_findings(self, product: CanonicalProduct) -> list[ComplianceFinding]:
        findings: list[ComplianceFinding] = []
        claim_text = " ".join(product.claims)
        for match in self.taxonomy.match("us-apparel-compliance", claim_text):
            if match.get("dimension") != "claim_risk":
                continue
            status = str(match.get("severity") or "needs_evidence")
            findings.append(ComplianceFinding(
                id=stable_id("finding", product.id, "claim", match["id"]), product_id=product.id,
                scope="us_legal", rule_id=match["id"], title=match["label"], status=status,
                message=f"Claim requires review: {match['matched_text']}", fact_field="claims",
                fact_value=product.claims,
            ))
        return findings

    def _shopify_policy(self, product: CanonicalProduct) -> list[ComplianceFinding]:
        checks = [
            ("shopify.field.title", bool(product.title), "Product title is required."),
            ("shopify.field.body_html", bool(product.description), "Product description is recommended for a complete listing."),
            ("shopify.field.variant_sku", all(sku.external_id for sku in product.skus), "Every variant requires a SKU."),
        ]
        return [ComplianceFinding(
            id=stable_id("finding", product.id, "shopify", rule_id), product_id=product.id,
            scope="shopify_policy", rule_id=rule_id, title=self.taxonomy.get_node(rule_id)["label"],
            status="pass" if ok else ("blocked" if rule_id != "shopify.field.body_html" else "needs_evidence"),
            message=("Requirement satisfied." if ok else message),
        ) for rule_id, ok, message in checks]

    def _ebay_policy(self, product: CanonicalProduct) -> list[ComplianceFinding]:
        checks = [
            ("ebay.specific.brand", bool(product.manufacturer), "Brand/manufacturer is required."),
            ("ebay.specific.color", all(sku.color for sku in product.skus), "Every variation requires color."),
            ("ebay.specific.material", bool(product.materials or product.fiber_content), "Material is required."),
        ]
        return [ComplianceFinding(
            id=stable_id("finding", product.id, "ebay", rule_id), product_id=product.id,
            scope="ebay_policy", rule_id=rule_id, title=self.taxonomy.get_node(rule_id)["label"],
            status="pass" if ok else "needs_evidence", message="Requirement satisfied." if ok else message,
        ) for rule_id, ok, message in checks]


def compliance_markdown(results: list[ComplianceResult]) -> str:
    lines = ["# US Apparel Compliance Report", "", "This report separates US legal requirements from marketplace policy checks.", ""]
    labels = (("US legal compliance", "legal"), ("Shopify policy", "shopify"), ("eBay US policy", "ebay"))
    for result in results:
        lines.extend([f"## Product `{result.product_id}`", ""])
        for heading, field in labels:
            lines.extend([f"### {heading}", "", "| Status | Requirement | Finding |", "|---|---|---|"])
            for item in getattr(result, field):
                lines.append(f"| {item.status} | {item.title} | {item.message} |")
            lines.append("")
    return "\n".join(lines)
