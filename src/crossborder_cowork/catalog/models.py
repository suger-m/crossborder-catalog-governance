from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


FactState = Literal["candidate", "confirmed", "rejected", "superseded"]


class SourceEvidence(BaseModel):
    source_document_id: str
    file_name: str
    location: str
    text: str


class TaxonomyAssignment(BaseModel):
    node_id: str
    taxonomy_version: str
    source: str
    confidence: float = Field(ge=0, le=1)
    evidence_span: str


class ProductFact(BaseModel):
    id: str
    field_name: str
    value: Any
    state: FactState = "candidate"
    confidence: float = Field(default=1.0, ge=0, le=1)
    evidence: SourceEvidence
    taxonomy: TaxonomyAssignment | None = None


class CanonicalSku(BaseModel):
    id: str
    external_id: str
    product_id: str
    color: str = ""
    size: str = ""
    barcode: str = ""
    price: str = ""
    inventory: int | None = None
    image_urls: list[str] = Field(default_factory=list)
    facts: list[ProductFact] = Field(default_factory=list)


class CanonicalProduct(BaseModel):
    id: str
    external_id: str
    title: str
    description: str = ""
    category: str = ""
    garment_type: str = ""
    materials: list[str] = Field(default_factory=list)
    fiber_content: str = ""
    care_instructions: str = ""
    country_of_origin: str = ""
    manufacturer: str = ""
    claims: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    skus: list[CanonicalSku] = Field(default_factory=list)
    facts: list[ProductFact] = Field(default_factory=list)
    version: int = 1
    status: str = "candidate"


class CatalogConflict(BaseModel):
    id: str
    product_id: str
    field_name: str
    values: list[Any]
    fact_ids: list[str]
    message: str


class CatalogBatch(BaseModel):
    products: list[CanonicalProduct]
    conflicts: list[CatalogConflict] = Field(default_factory=list)
    source_documents: list[dict[str, Any]] = Field(default_factory=list)
