from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


GraphState = Literal["candidate", "confirmed", "rejected", "superseded"]


class GraphNode(BaseModel):
    id: str
    node_type: str
    state: GraphState = "candidate"
    version: int = 1
    data: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source_id: str
    relation_type: str
    target_id: str
    state: GraphState = "candidate"
    version: int = 1
    data: dict[str, Any] = Field(default_factory=dict)


ALLOWED_NODE_TYPES = {
    "Product", "SKU", "Variant", "Category", "Attribute", "Material", "Claim",
    "Certification", "Market", "Regulation", "Platform", "PlatformCategory",
    "PlatformAttribute", "Listing", "ListingVersion", "MediaAsset", "SourceDocument",
}

ALLOWED_RELATIONS = {
    "HAS_SKU", "HAS_VARIANT_VALUE", "BELONGS_TO", "USES_MATERIAL", "MAKES_CLAIM",
    "REQUIRES", "TARGETS", "ENFORCES", "LISTED_ON", "DERIVED_FROM",
    "REQUIRES_ATTRIBUTE", "SUPERSEDES", "SUPPORTED_BY",
}
