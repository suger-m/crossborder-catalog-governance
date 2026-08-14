from __future__ import annotations

import csv
import html
import io
import re

from ..catalog.models import CanonicalProduct
from ..util import stable_id
from .base import ListingDraft, ListingGap, localize_en_us


SHOPIFY_HEADERS = [
    "Handle", "Title", "Body (HTML)", "Vendor", "Product Category", "Type", "Tags", "Published",
    "Option1 Name", "Option1 Value", "Option2 Name", "Option2 Value", "Variant SKU", "Variant Price",
    "Variant Inventory Qty", "Image Src", "Metafield: custom.material [single_line_text_field]",
    "Metafield: custom.country_of_origin [single_line_text_field]", "Status",
]


def make_handle(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", localize_en_us(value).casefold()).strip("-")
    return value or "product"


def build_shopify_draft(product: CanonicalProduct) -> ListingDraft:
    title = localize_en_us(product.title)
    description = localize_en_us(product.description)
    category = localize_en_us(product.category or product.garment_type or "Women’s Apparel")
    gaps: list[ListingGap] = []
    if not description:
        gaps.append(ListingGap(field="Body (HTML)", reason="Canonical description is missing."))
    if not product.manufacturer:
        gaps.append(ListingGap(field="Vendor", reason="Canonical manufacturer/vendor is missing."))
    if not product.images and not any(sku.image_urls for sku in product.skus):
        gaps.append(ListingGap(field="Image Src", reason="No product images were supplied."))
    rows: list[dict[str, str]] = []
    handle = make_handle(f"{product.external_id}-{title}")
    for index, sku in enumerate(product.skus):
        images = sku.image_urls or product.images
        rows.append({
            "Handle": handle,
            "Title": title if index == 0 else "",
            "Body (HTML)": f"<p>{html.escape(description)}</p>" if index == 0 and description else "",
            "Vendor": product.manufacturer if index == 0 else "",
            "Product Category": category if index == 0 else "",
            "Type": localize_en_us(product.garment_type or product.category) if index == 0 else "",
            "Tags": ", ".join(localize_en_us(tag) for tag in product.tags) if index == 0 else "",
            "Published": "FALSE", "Option1 Name": "Size", "Option1 Value": sku.size or "One Size",
            "Option2 Name": "Color", "Option2 Value": localize_en_us(sku.color or "Default"),
            "Variant SKU": sku.external_id, "Variant Price": sku.price,
            "Variant Inventory Qty": "" if sku.inventory is None else str(sku.inventory),
            "Image Src": images[0] if images else "",
            "Metafield: custom.material [single_line_text_field]": ", ".join(product.materials) or product.fiber_content,
            "Metafield: custom.country_of_origin [single_line_text_field]": product.country_of_origin,
            "Status": "draft",
        })
    return ListingDraft(
        id=stable_id("listing", product.id, "shopify", product.version), product_id=product.id,
        platform="shopify", derived_from_product_version=product.version, platform_rule_version="shopify-product@v1",
        title=title, description=description, category=category,
        data={"handle": handle, "rows": rows}, gaps=gaps,
    )


def shopify_csv(drafts: list[ListingDraft]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=SHOPIFY_HEADERS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for draft in drafts:
        writer.writerows(draft.data.get("rows", []))
    return stream.getvalue()
