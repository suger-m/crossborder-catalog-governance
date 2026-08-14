from __future__ import annotations

from .models import CanonicalProduct


REQUIRED_PRODUCT_FIELDS = ("external_id", "title")


def validate_product(product: CanonicalProduct) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_PRODUCT_FIELDS:
        if not str(getattr(product, field, "") or "").strip():
            errors.append(f"Missing required product field: {field}")
    if not product.skus:
        errors.append("Product must contain at least one SKU")
    sku_ids = [sku.id for sku in product.skus]
    if len(sku_ids) != len(set(sku_ids)):
        errors.append("Product contains duplicate SKU IDs")
    return errors
