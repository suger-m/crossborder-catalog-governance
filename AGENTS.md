# AGENTS.md

## Scope

These instructions apply to the entire repository.

## Product Scope

The first release builds a cross-border womenswear catalog governance application for the United States, Shopify, and eBay US. It exports listing packages and does not publish products automatically.

## Collaboration Responsibilities

- Use the current AgentTeams design and runtime as the reference for multi-agent identity, delegation, shared context, human intervention, and lifecycle management. Do not recreate a competing orchestration model without an approved design change.
- A business Agent/Worker is a durable role with a clear responsibility, decision boundary, inputs, outputs, and artifact ownership. Do not create a new business role merely for a platform, country, file format, or workflow variation.
- The Manager or other platform coordinator owns task decomposition, delegation, dependencies, retries, approvals, and consolidation. Business Agents own domain decisions within their assigned boundary.
- Cross-agent context must be passed through the platform's approved task context and artifact/resource references. Do not rely on transient process memory or unstructured log parsing.
- The Web or other client is a presentation and interaction layer. It must consume authoritative platform and domain state instead of inventing Worker, Tool, file, or task state.
- Keep orchestration, domain logic, and presentation responsibilities separate. A change to one layer must not silently become a second implementation of another layer.

## Agent, Skill, and Tool Boundaries

- An Agent represents a durable business role with its own responsibility, decision boundary, inputs, and artifacts.
- A Skill is an on-demand package of procedural knowledge and resources. Do not create a new Agent merely because a platform, country, file format, or workflow variation needs different instructions.
- A Tool performs deterministic work such as parsing files, validating schemas, writing graph records, formatting CSV/JSON, hashing artifacts, or creating ZIP files.
- A Skill is not a workflow orchestrator, a fixed process, an Agent, or a Tool allowlist. Activating a Skill adds its specialized instructions and available resources to the assigned Agent's context; the Agent remains the task owner and retains control over reasoning and execution.
- After activating a Skill, an Agent may use only the parts relevant to the current objective, read referenced knowledge or assets, execute bundled scripts when useful, combine the Skill with platform Tools, or complete the task without calling a Tool. Activating a Skill does not require running every procedure or resource bundled with it.
- The optional `allowed-tools` Skill metadata is not the semantic definition of a Skill and must not be treated as a mandatory workflow. It may be used by a compatible client as a permission hint only.
- Skills follow progressive disclosure: expose name and description during discovery, load `SKILL.md` only when selected, and load bundled scripts/references/assets only when needed.
- Prefer model-driven skill activation. Do not implement brittle keyword routing when the assigned Agent can select the appropriate visible Skill from the task objective.
- When a Skill's bundled script performs executable or state-changing work, the platform must run it through an allowlisted execution boundary with risk controls and Human Approval where required. This is a host-platform security constraint; it does not make the Skill a Tool orchestrator.
- First-release business Agents must not receive TerminalToolkit, SearchToolkit, browser, arbitrary filesystem, shell, or marketplace publishing capabilities unless a current approved design explicitly changes that boundary.
- External capability access must use an approved Tool/connector contract with explicit input/output schemas, authorization, failure handling, idempotency, and auditability. Do not make a Skill a hidden workflow orchestrator or permission bypass.
- Taxonomy validation, graph schema validation, evidence-span validation, and release-state transitions must remain platform code, not free-form LLM behavior.

## First-release Manager and Business Agents

- `catalog_steward_agent`: owns canonical Product/SKU fact candidates, source evidence, conflicts, and classification candidates. It may propose facts but cannot bypass platform taxonomy, schema, or evidence validation.
- `compliance_specialist_agent`: applies US apparel, Shopify, and eBay US policy Skills to confirmed or explicitly identified candidate facts. It must not silently change canonical product facts.
- `listing_operations_agent`: applies localization, Shopify, and eBay US Listing Skills to create channel drafts and export inputs. It must not publish products or invent missing commercial facts.
- `governance_reviewer_agent`: checks fact consistency, compliance blockers, evidence, versions, pending approvals, and release readiness. It may run independently for a review-only objective.

Planner, Manager, Human Approval, artifact storage, and export are platform capabilities, not additional business Agents unless a current approved design explicitly says otherwise.

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

Use the following repository as the primary reference for AgentTeams collaboration concepts and runtime behavior:

- `../AgentTeams`

The existing domain code in this repository remains the reference for cross-border business behavior. Do not copy unrelated domain modules or reintroduce retired architecture solely for visual or naming compatibility.

## Development Process

- Read the relevant current design and implementation plan under `docs/superpowers/` before changing architecture or cross-layer contracts.
- Do not use TDD for this project. Complete the planned functionality, then run the final integration verification.
- Do not keep parallel implementations solely for compatibility. Retire obsolete code only after the current design and its migration plan identify it as obsolete.
- Verify the final integrated system with a real womenswear catalog scenario covering multi-agent delegation, cross-agent resource dependencies, approval behavior, independent governance review, and recovery after interruption.
- Do not add automatic Shopify or eBay publishing in the first release.

