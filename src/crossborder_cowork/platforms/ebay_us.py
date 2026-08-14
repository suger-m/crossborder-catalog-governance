from __future__ import annotations

from ..catalog.models import CanonicalProduct
from ..util import stable_id
from .base import ListingDraft, ListingGap, localize_en_us


CATEGORY_MAP = {
    "dress": {"id": "63861", "name": "Women’s Dresses"},
    "top": {"id": "53159", "name": "Women’s Tops"},
    "t-shirt": {"id": "53159", "name": "Women’s Tops"},
    "jeans": {"id": "11554", "name": "Women’s Jeans"},
    "knit": {"id": "63866", "name": "Women’s Sweaters"},
    "cardigan": {"id": "63866", "name": "Women’s Sweaters"},
    "sports": {"id": "185082", "name": "Women’s Activewear"},
    "trench": {"id": "63862", "name": "Women’s Coats, Jackets & Vests"},
    "coat": {"id": "63862", "name": "Women’s Coats, Jackets & Vests"},
}


def ebay_category(product: CanonicalProduct) -> dict[str, str]:
    text = localize_en_us(f"{product.category} {product.garment_type} {product.title}").casefold()
    for token, category in CATEGORY_MAP.items():
        if token in text:
            return category
    return {"id": "15724", "name": "Women’s Clothing"}


def build_ebay_draft(product: CanonicalProduct) -> ListingDraft:
    title = localize_en_us(product.title)[:80]
    description = localize_en_us(product.description)
    category = ebay_category(product)
    gaps: list[ListingGap] = []
    if not product.manufacturer:
        gaps.append(ListingGap(field="Brand", reason="Canonical manufacturer/brand is missing."))
    if not product.materials and not product.fiber_content:
        gaps.append(ListingGap(field="Material", reason="Canonical material is missing.", severity="blocked"))
    if any(not sku.size or not sku.color for sku in product.skus):
        gaps.append(ListingGap(field="Variations", reason="One or more SKUs lack size or color."))
    item_specifics = {
        "Brand": product.manufacturer or "Unbranded",
        "Department": "Women",
        "Material": ", ".join(product.materials) or product.fiber_content,
        "Style": localize_en_us(product.garment_type or product.category),
        "Country/Region of Manufacture": product.country_of_origin,
        "Size Type": "Regular",
    }
    variations = [{
        "sku": sku.external_id,
        "specifics": {"Size": sku.size, "Color": localize_en_us(sku.color)},
        "price": sku.price,
        "quantity": sku.inventory,
        "images": sku.image_urls or product.images,
    } for sku in product.skus]
    data = {
        "sku": product.external_id,
        "marketplaceId": "EBAY_US",
        "category": category,
        "condition": "NEW_WITH_TAGS",
        "title": title,
        "description": description,
        "itemSpecifics": item_specifics,
        "variations": variations,
        "status": "draft",
    }
    return ListingDraft(
        id=stable_id("listing", product.id, "ebay_us", product.version), product_id=product.id,
        platform="ebay_us", derived_from_product_version=product.version, platform_rule_version="ebay-us-fashion@v1",
        title=title, description=description, category=category["name"], data=data, gaps=gaps,
    )
