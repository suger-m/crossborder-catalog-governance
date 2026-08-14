# AGENTS.md

## Scope

These instructions apply to the entire repository.

## Product Scope

The first release builds a cross-border womenswear catalog governance application for the United States, Shopify, and eBay US. It exports listing packages and does not publish products automatically.

## Agent, Skill, and Tool Boundaries

- An Agent represents a durable business role with its own responsibility, decision boundary, inputs, and artifacts.
- A Skill is an on-demand package of procedural knowledge and resources. Do not create a new Agent merely because a platform, country, file format, or workflow variation needs different instructions.
- A Tool performs deterministic work such as parsing files, validating schemas, writing graph records, formatting CSV/JSON, hashing artifacts, or creating ZIP files.
- Skills follow progressive disclosure: expose name and description during discovery, load `SKILL.md` only when selected, and load bundled scripts/references/assets only when needed.
- Prefer model-driven skill activation. Do not implement brittle keyword routing when the assigned Agent can select the appropriate visible Skill from the task objective.
- Skill scripts execute only through allowlisted Tool boundaries with risk controls and Human Approval where required.
- Taxonomy validation, graph schema validation, evidence-span validation, and release-state transitions must remain platform code, not free-form LLM behavior.

## First-release Business Agents

- `catalog_steward_agent`: owns canonical Product/SKU facts and classification candidates.
- `compliance_specialist_agent`: applies US apparel and marketplace-policy Skills without changing product facts.
- `listing_operations_agent`: loads localization, Shopify, and eBay Skills to create channel drafts.
- `governance_reviewer_agent`: checks fact consistency, compliance blockers, evidence, versions, and release readiness.

The Planner and Human Approval service are platform capabilities, not business Agents.

## Agent Skills References

Use these sources when designing or implementing the Skill runtime or project Skills:

- [Agent Skills overview](https://agentskills.io/home)
- [Agent Skills specification](https://agentskills.io/specification)
- [Skill creation quickstart](https://agentskills.io/skill-creation/quickstart)
- [Best practices for skill creators](https://agentskills.io/skill-creation/best-practices)
- [Optimizing skill descriptions](https://agentskills.io/skill-creation/optimizing-descriptions)
- [Evaluating skill output quality](https://agentskills.io/skill-creation/evaluating-skills)
- [Using scripts in skills](https://agentskills.io/skill-creation/using-scripts)
- [Adding Agent Skills support](https://agentskills.io/client-implementation/adding-skills-support)
- [Complete documentation index](https://agentskills.io/llms.txt)

## Local Architecture References

When reusing generic Workforce, approval, artifact, event, desktop workspace, or model-configuration patterns, inspect the existing repository at:

- `D:/vibe/e-commerce-cowork-p6-cowork`
- `D:/vibe/_reference/camel`
- `D:/vibe/_reference/eigent`

Do not copy demand-insight, comment-modeling, Demand Signal, Demand Cube, Opportunity Radar, or other domain-specific modules.

## Development Process

- Current design: `docs/superpowers/specs/2026-08-15-crossborder-catalog-cowork-design.md`
- Current plan: `docs/superpowers/plans/2026-08-15-crossborder-catalog-cowork-implementation.md`
- Do not use TDD for this project. Complete the planned functionality, then run the final integration verification.
- Do not add automatic Shopify or eBay publishing in the first release.

