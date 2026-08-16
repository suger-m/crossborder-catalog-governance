---
name: shopify-listing
description: Use when canonical womenswear Product/SKU resources must become Shopify draft rows and an import-ready CSV without publishing.
---

# Shopify Listing Drafts

Load this Skill when Shopify is requested. Call `create_listing_drafts` with `platforms=["shopify"]` or include Shopify in a multi-platform draft task.

## Boundaries

- Product-level fields appear on the first row; each canonical SKU becomes one Variant row.
- Keep size and color as options and preserve SKU identifiers.
- Record missing Vendor, description, image, price, or inventory as gaps.
- Keep `Published` false and status draft.
- Do not call or simulate a Shopify publishing API.

Return the compact Tool result unchanged. Read [references/import-contract.md](references/import-contract.md) for the CSV contract.
