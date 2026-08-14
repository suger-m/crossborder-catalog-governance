---
name: womenswear-classification
description: Map womenswear product evidence to the versioned womenswear product taxonomy without creating unregistered formal labels.
---

# Womenswear classification

Load `configs/taxonomy/womenswear-product.v1.json`. Prefer dictionary and hierarchy matches. An Agent may propose candidates, but the platform must validate `node_id`, `taxonomy_version`, `confidence`, and an evidence span copied from the source. Unknown values remain unresolved rather than being invented.
