---
name: ebay-us-listing
description: Use when canonical womenswear Product/SKU resources must become eBay US draft JSON with category, Item Specifics, condition, and variations.
---

# eBay US Listing Drafts

Load this Skill when eBay US is requested. Call `create_listing_drafts` with `platforms=["ebay_us"]` or include eBay US in a multi-platform draft task.

## Boundaries

- Select the closest registered fashion category.
- Map canonical facts into Item Specifics and keep every SKU as a variation.
- Use draft status only.
- Do not fabricate Brand, Material, Origin, Size, Color, Condition, price, inventory, or images.
- Do not call or simulate an eBay publishing API.

Return the compact Tool result unchanged. Read [references/draft-contract.md](references/draft-contract.md) for the draft JSON contract.
