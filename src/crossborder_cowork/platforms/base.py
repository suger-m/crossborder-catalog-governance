from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ListingGap(BaseModel):
    field: str
    reason: str
    severity: Literal["info", "needs_evidence", "blocked"] = "needs_evidence"


class ListingDraft(BaseModel):
    id: str
    product_id: str
    platform: Literal["shopify", "ebay_us"]
    derived_from_product_version: int
    platform_rule_version: str
    status: str = "draft"
    title: str
    description: str
    category: str
    data: dict[str, Any] = Field(default_factory=dict)
    gaps: list[ListingGap] = Field(default_factory=list)


GLOSSARY = {
    "连衣裙": "Dress", "长裙": "Maxi Dress", "上衣": "Top", "T恤": "T-Shirt",
    "牛仔裤": "Jeans", "直筒": "Straight Leg", "针织": "Knit", "开衫": "Cardigan",
    "运动文胸": "Sports Bra", "风衣": "Trench Coat", "女士": "Women’s",
    "黑色": "Black", "白色": "White", "蓝色": "Blue", "米色": "Beige",
}


def localize_en_us(value: str) -> str:
    result = str(value or "").strip()
    for source, target in sorted(GLOSSARY.items(), key=lambda item: len(item[0]), reverse=True):
        result = result.replace(source, target)
    return " ".join(result.split())
