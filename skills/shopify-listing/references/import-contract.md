# Shopify Import Contract

The deterministic draft Tool creates CSV rows using the registered Shopify headers. Product-level values belong on the first row. Every canonical SKU becomes a Variant row with size and color options where available.

The package must keep `Published=FALSE`, `Status=draft`, stable Variant SKU values, and explicit empty fields for missing facts. It is an import draft, not a publishing request.
