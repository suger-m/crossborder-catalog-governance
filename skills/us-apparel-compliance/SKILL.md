---
name: us-apparel-compliance
description: Use when canonical womenswear products need US fiber, origin, care, manufacturer, sizing, claim, or certification review before drafting or export.
---

# US Apparel Compliance

Load this Skill for US legal and evidence review. Use `evaluate_us_apparel_compliance` to evaluate durable canonical resources and persist both a readable report and machine result.

## Boundaries

- Keep US legal conclusions separate from Shopify and eBay policy checks.
- Treat canonical Product facts as read-only inputs.
- Preserve versioned rule IDs and official source URLs.
- Missing fiber content, country of origin, or care instructions blocks release.
- Conflicting authoritative facts require Human Approval.
- Claims such as organic, antibacterial, sustainability, or certification claims require supporting evidence.
- Do not infer legal compliance from marketplace acceptance.

Return the compact result from the compliance Tool unchanged. Read [references/release-gates.md](references/release-gates.md) for release-state rules.
