---
name: product-catalog
description: Use when task-bound womenswear files must become canonical Product/SKU facts with source evidence, conflict candidates, and reusable project resources.
---

# Product Catalog Intake

Use this Skill when the goal includes importing, normalizing, rebuilding, or checking a canonical catalog from files bound to the current task.

## Boundaries

- Use `inspect_task_materials` before intake when the available inputs are unclear.
- Use `build_canonical_catalog` for parsing, evidence capture, graph persistence, conflict detection, and Product/SKU resource creation.
- Preserve every original file as a source Artifact.
- Never fabricate missing product facts or silently resolve conflicting authoritative fields.
- Keep product-level facts separate from SKU-level color, size, barcode, price, inventory, and images.
- Human Approval owns unresolved authoritative conflicts.

## Expected Result

Return the compact result from `build_canonical_catalog` unchanged. The authoritative outputs are project resource IDs, not a rewritten copy of the catalog in chat.

Read [references/canonical-fields.md](references/canonical-fields.md) when field ownership or Product/SKU boundaries matter.
