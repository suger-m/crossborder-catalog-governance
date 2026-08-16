# Shopify Draft Checks

- Product title is present.
- Each Variant has a canonical SKU.
- Product and Variant facts trace to the active canonical Product version.
- Material and country-of-origin fields match canonical facts.
- Missing body, Vendor, image, price, or inventory remains an explicit gap.
- `Published` is false and the output remains a draft/import file.
