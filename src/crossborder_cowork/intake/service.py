from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..catalog.models import (
    CanonicalProduct, CanonicalSku, CatalogBatch, CatalogConflict, ProductFact,
    SourceEvidence, TaxonomyAssignment,
)
from ..taxonomy.registry import TaxonomyRegistry
from ..util import new_id, stable_id
from .parsers import ParsedDocument, ParsedRecord, parse_document


LIST_FIELDS = {"materials", "images", "tags", "claims", "certifications"}
PRODUCT_FIELDS = {
    "title", "description", "category", "garment_type", "materials", "fiber_content",
    "care_instructions", "country_of_origin", "manufacturer", "claims", "certifications", "images", "tags",
}
CONFLICT_FIELDS = {"country_of_origin", "fiber_content", "manufacturer"}


def split_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in re.split(r"[,;，；|]", str(value or "")) if item.strip()]


class IntakeService:
    def __init__(self, taxonomy: TaxonomyRegistry) -> None:
        self.taxonomy = taxonomy

    def parse(self, paths: list[Path]) -> CatalogBatch:
        documents = [parse_document(path) for path in paths]
        groups: dict[str, list[ParsedRecord]] = defaultdict(list)
        for document in documents:
            for record in document.records:
                key = str(record.values.get("product_id") or record.values.get("title") or "").strip()
                if not key:
                    key = f"UNASSIGNED-{record.source_document_id[-8:]}"
                groups[key].append(record)

        products: list[CanonicalProduct] = []
        conflicts: list[CatalogConflict] = []
        for external_id, records in groups.items():
            product, product_conflicts = self._build_product(external_id, records)
            products.append(product)
            conflicts.extend(product_conflicts)
        return CatalogBatch(
            products=products,
            conflicts=conflicts,
            source_documents=[{
                "id": doc.id, "file_name": doc.path.name, "absolute_path": str(doc.path),
                "mime_type": doc.mime_type, "record_count": len(doc.records),
            } for doc in documents],
        )

    def _build_product(self, external_id: str, records: list[ParsedRecord]) -> tuple[CanonicalProduct, list[CatalogConflict]]:
        product_id = stable_id("prod", external_id)
        facts: list[ProductFact] = []
        field_values: dict[str, list[tuple[Any, ProductFact]]] = defaultdict(list)
        for record in records:
            for field, value in record.values.items():
                if field not in PRODUCT_FIELDS:
                    continue
                fact = self._fact(product_id, field, value, record)
                facts.append(fact)
                field_values[field].append((value, fact))

        resolved: dict[str, Any] = {}
        conflicts: list[CatalogConflict] = []
        for field, values in field_values.items():
            unique: list[Any] = []
            for value, _ in values:
                normalized = tuple(split_values(value)) if field in LIST_FIELDS else str(value).strip().casefold()
                if not any((tuple(split_values(item)) if field in LIST_FIELDS else str(item).strip().casefold()) == normalized for item in unique):
                    unique.append(value)
            if field in CONFLICT_FIELDS and len(unique) > 1:
                conflicts.append(CatalogConflict(
                    id=stable_id("conflict", product_id, field, *[str(item) for item in unique]), product_id=product_id, field_name=field,
                    values=unique, fact_ids=[fact.id for _, fact in values],
                    message=f"Conflicting {field.replace('_', ' ')} values require confirmation.",
                ))
            if field in LIST_FIELDS:
                resolved[field] = list(dict.fromkeys(item for value in unique for item in split_values(value)))
            else:
                resolved[field] = str(unique[0]) if unique else ""

        skus: list[CanonicalSku] = []
        seen_skus: set[str] = set()
        for record in records:
            color = str(record.values.get("color") or "").strip()
            size = str(record.values.get("size") or "").strip()
            sku_external = str(record.values.get("sku") or f"{external_id}-{color or 'NA'}-{size or 'NA'}").strip()
            sku_id = stable_id("sku", product_id, sku_external)
            if sku_id in seen_skus:
                continue
            seen_skus.add(sku_id)
            inventory_raw = record.values.get("inventory")
            try:
                inventory = int(inventory_raw) if inventory_raw not in (None, "") else None
            except (TypeError, ValueError):
                inventory = None
            skus.append(CanonicalSku(
                id=sku_id, external_id=sku_external, product_id=product_id,
                color=color, size=size, barcode=str(record.values.get("barcode") or ""),
                price=str(record.values.get("price") or ""), inventory=inventory,
                image_urls=split_values(record.values.get("images")),
            ))

        title = str(resolved.get("title") or external_id)
        category_text = " ".join([str(resolved.get("category") or ""), str(resolved.get("garment_type") or ""), title])
        category_matches = self.taxonomy.match("womenswear-product", category_text)
        category = str(resolved.get("category") or (category_matches[0]["label"] if category_matches else "Women’s Apparel"))
        product = CanonicalProduct(
            id=product_id, external_id=external_id, title=title,
            description=str(resolved.get("description") or ""), category=category,
            garment_type=str(resolved.get("garment_type") or ""),
            materials=resolved.get("materials", []), fiber_content=str(resolved.get("fiber_content") or ""),
            care_instructions=str(resolved.get("care_instructions") or ""),
            country_of_origin=str(resolved.get("country_of_origin") or ""),
            manufacturer=str(resolved.get("manufacturer") or ""), claims=resolved.get("claims", []),
            certifications=resolved.get("certifications", []), images=resolved.get("images", []),
            tags=resolved.get("tags", []), skus=skus, facts=facts,
        )
        return product, conflicts

    def _fact(self, product_id: str, field: str, value: Any, record: ParsedRecord) -> ProductFact:
        text_value = str(value)
        assignment = None
        matches = self.taxonomy.match("womenswear-product", text_value)
        if matches:
            match = matches[0]
            assignment = TaxonomyAssignment(
                node_id=match["id"], taxonomy_version="v1", source="dictionary",
                confidence=float(match["confidence"]), evidence_span=str(match["matched_text"]),
            )
        return ProductFact(
            id=stable_id("fact", product_id, field, record.source_document_id, record.location, text_value),
            field_name=field, value=value, confidence=1.0,
            evidence=SourceEvidence(
                source_document_id=record.source_document_id, file_name=record.file_name,
                location=record.location, text=record.evidence_text,
            ),
            taxonomy=assignment,
        )
