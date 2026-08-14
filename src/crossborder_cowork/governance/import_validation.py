from __future__ import annotations

from decimal import Decimal, InvalidOperation

from pydantic import BaseModel

from ..platforms.base import ListingDraft


class ChannelValidationIssue(BaseModel):
    platform: str
    product_id: str
    field: str
    message: str


def validate_shopify_draft(draft: ListingDraft) -> list[ChannelValidationIssue]:
    issues: list[ChannelValidationIssue] = []
    rows = draft.data.get("rows", [])
    if draft.platform != "shopify":
        issues.append(_issue(draft, "platform", "Shopify draft has an invalid platform identifier."))
    if not rows:
        return [*issues, _issue(draft, "rows", "Shopify import requires at least one variant row.")]
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        prefix = f"rows[{index}]"
        sku = str(row.get("Variant SKU") or "").strip()
        if not sku:
            issues.append(_issue(draft, f"{prefix}.Variant SKU", "Shopify Variant SKU is required."))
        elif sku in seen:
            issues.append(_issue(draft, f"{prefix}.Variant SKU", f"Duplicate Shopify Variant SKU: {sku}."))
        seen.add(sku)
        if not str(row.get("Handle") or "").strip():
            issues.append(_issue(draft, f"{prefix}.Handle", "Shopify Handle is required."))
        if not str(row.get("Option1 Value") or "").strip():
            issues.append(_issue(draft, f"{prefix}.Option1 Value", "Shopify size option is required."))
        if not str(row.get("Option2 Value") or "").strip():
            issues.append(_issue(draft, f"{prefix}.Option2 Value", "Shopify color option is required."))
        if not _valid_decimal(row.get("Variant Price")):
            issues.append(_issue(draft, f"{prefix}.Variant Price", "Shopify Variant Price must be a non-negative decimal."))
        inventory = str(row.get("Variant Inventory Qty") or "").strip()
        if inventory and not _valid_integer(inventory):
            issues.append(_issue(draft, f"{prefix}.Variant Inventory Qty", "Shopify inventory must be a non-negative integer."))
        if str(row.get("Published") or "").upper() != "FALSE" or str(row.get("Status") or "").casefold() != "draft":
            issues.append(_issue(draft, f"{prefix}.Status", "First-release Shopify output must remain an unpublished draft."))
    return issues


def validate_ebay_draft(draft: ListingDraft) -> list[ChannelValidationIssue]:
    issues: list[ChannelValidationIssue] = []
    data = draft.data
    variations = data.get("variations", [])
    if draft.platform != "ebay_us" or data.get("marketplaceId") != "EBAY_US":
        issues.append(_issue(draft, "marketplaceId", "eBay draft must target EBAY_US."))
    category = data.get("category") or {}
    if not str(category.get("id") or "").strip():
        issues.append(_issue(draft, "category.id", "eBay category ID is required."))
    title = str(data.get("title") or "").strip()
    if not title or len(title) > 80:
        issues.append(_issue(draft, "title", "eBay title is required and must not exceed 80 characters."))
    if str(data.get("status") or "").casefold() != "draft":
        issues.append(_issue(draft, "status", "First-release eBay output must remain a draft."))
    specifics = data.get("itemSpecifics") or {}
    for field in ("Brand", "Department", "Material", "Country/Region of Manufacture"):
        if not str(specifics.get(field) or "").strip():
            issues.append(_issue(draft, f"itemSpecifics.{field}", f"eBay Item Specific {field} is required."))
    if not variations:
        return [*issues, _issue(draft, "variations", "eBay import requires at least one variation.")]
    seen: set[str] = set()
    for index, variation in enumerate(variations, start=1):
        prefix = f"variations[{index}]"
        sku = str(variation.get("sku") or "").strip()
        if not sku:
            issues.append(_issue(draft, f"{prefix}.sku", "eBay variation SKU is required."))
        elif sku in seen:
            issues.append(_issue(draft, f"{prefix}.sku", f"Duplicate eBay variation SKU: {sku}."))
        seen.add(sku)
        variant_specifics = variation.get("specifics") or {}
        if not str(variant_specifics.get("Size") or "").strip():
            issues.append(_issue(draft, f"{prefix}.specifics.Size", "eBay variation size is required."))
        if not str(variant_specifics.get("Color") or "").strip():
            issues.append(_issue(draft, f"{prefix}.specifics.Color", "eBay variation color is required."))
        if not _valid_decimal(variation.get("price")):
            issues.append(_issue(draft, f"{prefix}.price", "eBay variation price must be a non-negative decimal."))
        if not _valid_integer(variation.get("quantity")):
            issues.append(_issue(draft, f"{prefix}.quantity", "eBay variation quantity must be a non-negative integer."))
    return issues


def _valid_decimal(value: object) -> bool:
    try:
        return Decimal(str(value)) >= 0
    except (InvalidOperation, TypeError, ValueError):
        return False


def _valid_integer(value: object) -> bool:
    if isinstance(value, bool) or value in (None, ""):
        return False
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return False
    return parsed >= 0 and str(parsed) == str(value).strip()


def _issue(draft: ListingDraft, field: str, message: str) -> ChannelValidationIssue:
    return ChannelValidationIssue(platform=draft.platform, product_id=draft.product_id, field=field, message=message)
