---
name: womenswear-classification
description: Use when canonical womenswear evidence must be mapped to the registered product taxonomy or when classification candidates and unresolved values need review.
---

# Womenswear Classification

Classification is part of canonical catalog construction. The Agent selects this Skill for taxonomy judgment; deterministic platform code performs formal node and evidence validation.

## Boundaries

- Use only nodes registered in `womenswear-product@v1`.
- Prefer direct evidence, aliases, and hierarchy matches over broad semantic guesses.
- Do not create a new formal label during task execution.
- Unknown or ambiguous values remain unresolved.
- `node_id`, taxonomy version, confidence, source, and evidence span must survive validation before persistence.

Read [references/mapping-policy.md](references/mapping-policy.md) when choosing between exact, hierarchical, ambiguous, or unresolved mappings.
