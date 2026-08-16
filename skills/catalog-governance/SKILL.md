---
name: catalog-governance
description: Use when existing catalog, compliance, approval, and channel-draft resources need release review or an approved export package.
---

# Catalog Governance

Use this Skill for standalone review or as the final role in a larger Workforce task. Call `review_catalog_release`; set `create_export_package` only when the task explicitly asks for a package.

## Boundaries

- Treat the active canonical Product version as the only fact source.
- Reject stale Listing drafts and channel differences in SKU, material, origin, size, claims, or measurements.
- Pending Human Approval prevents release.
- A hard legal or policy finding blocks release.
- Review may run for Shopify only, eBay US only, or both, based on available/requested drafts.
- Only an approved review may create a SKU matrix and Listing package.
- Export is not publishing.

Return the compact Tool result unchanged. Read [references/review-checklist.md](references/review-checklist.md) before interpreting release status.
