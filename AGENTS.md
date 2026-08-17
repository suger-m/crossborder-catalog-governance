# AGENTS.md

## Scope

These instructions apply to the entire repository.

## Product Scope

The first release builds a cross-border womenswear catalog governance application for the United States, Shopify, and eBay US. It exports listing packages and does not publish products automatically.

## Runtime Architecture

- AgentTeams is the collaboration runtime and the authoritative source for Manager, Worker, assignment, task, and execution state.
- The AgentTeams Controller creates and manages persistent Manager and Worker resources. Do not recreate business Workers inside the FastAPI process or per task run.
- Use the AgentTeams Manager for task understanding, dynamic decomposition, Worker selection, dependency management, retries, human intervention, and final consolidation.
- Use QwenPaw as the first-release Manager and Worker runtime unless a later approved design assigns a different AgentTeams-supported runtime to a specific role.
- Shared AgentTeams task workspaces and Artifact manifests carry cross-Worker context. Do not pass complete business payloads through Python return values, transient process memory, or custom UI events.
- The Python/FastAPI application is the cross-border domain service. It owns Product/SKU facts, taxonomy and schema validation, compliance rules, Listing generation, Artifact integrity, approvals, and audit records.
- React, TypeScript, and Vite provide the first-release Web workspace. Do not add Electron, desktop packaging, preload processes, or desktop-only state.
- Do not use CAMEL Workforce as the task orchestrator. Do not add or restore `BusinessAgentWorker`, Workforce callbacks, Product Event projections, Eigent-compatible protocols, or frontend event reducers that infer Worker state from logs.
- The Web workspace reads AgentTeams state, shared task context, and domain APIs directly. Start with explicit state APIs or polling; do not invent a second real-time event protocol.

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
- First-release business Workers must not receive TerminalToolkit, SearchToolkit, browser, arbitrary filesystem, shell, or marketplace publishing capabilities. MCP is not required for the first release. Domain capabilities use an authenticated, schema-validated HTTP Tool contract that can later be exposed through MCP without redesigning the Skill or business implementation.
- Worker domain Tool calls must include `project_id`, AgentTeams `task_id`, `worker_id`, dependency identifiers, and an idempotency key. The platform must validate role authorization and write an audit record before returning resource or Artifact identifiers.
- Taxonomy validation, graph schema validation, evidence-span validation, and release-state transitions must remain platform code, not free-form LLM behavior.

## First-release Manager and Business Workers

- The AgentTeams Manager owns the user objective, task plan, Worker selection, dependencies, execution state, retries, approvals, and final result. It must choose the minimum necessary set of Workers and may assign a task to one Worker only.
- `catalog-steward-worker`: owns canonical Product/SKU fact candidates, source evidence, conflicts, and classification candidates. It may propose facts but cannot bypass platform taxonomy, schema, or evidence validation.
- `compliance-specialist-worker`: applies US apparel, Shopify, and eBay US policy Skills to confirmed or explicitly identified candidate facts. It must not silently change canonical product facts.
- `listing-operations-worker`: applies localization, Shopify, and eBay US Listing Skills to create channel drafts and export inputs. It must not publish products or invent missing commercial facts.
- `governance-reviewer-worker`: checks fact consistency, compliance blockers, evidence, versions, pending approvals, and release readiness. It may run independently for a review-only objective.

Human Approval remains a platform capability, not a business Worker. An approval pauses or revises the active AgentTeams task context and must retain the original task, approval, resource-version, and Artifact relationships.

## State and Context Ownership

- AgentTeams task state is the source of truth for planning, assignments, Worker activity, blocking, retry, and completion.
- The shared task workspace is the source of truth for `meta.json`, `plan.md`, dependency manifests, Worker result summaries, and cross-Worker Artifact references.
- The domain service is the source of truth for Product/SKU data, taxonomy assignments, graph records, compliance findings, Listing drafts, approvals, and Artifact integrity.
- Worker result files must remain compact and contain status, summary, key counts, output resource IDs, Artifact IDs, and requested next actions.
- A downstream Worker reads upstream resources by manifest and identifier. It must not depend on the upstream Worker process, a Python object, or a copied prompt containing the entire upstream result.
- The Web workspace is a presentation and interaction layer only. It must not synthesize missing tasks, Tool calls, Worker ownership, file ownership, or completion state.

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

Use the following repository as the primary reference for Manager, Worker, shared task workspace, AgentTeams Skills, lifecycle, Matrix communication, Controller resources, and local deployment:

- `../AgentTeams`

The existing Python code in this repository remains the reference for cross-border domain services. Do not use Eigent or CAMEL as an orchestration or UI-event reference. Do not copy demand-insight, comment-modeling, Demand Signal, Demand Cube, Opportunity Radar, or other unrelated domain modules.

## Development Process

- Current design: `docs/superpowers/specs/2026-08-18-agentteams-native-worker-web-design.md`
- Do not use TDD for this project. Complete the planned functionality, then run the final integration verification.
- Do not keep parallel orchestration or UI implementations for compatibility. Replace the old runtime in explicit stages, then remove the retired CAMEL Workforce, Product Event, Electron, and desktop-only code.
- Verify the final integrated system with a real womenswear catalog scenario covering dynamic Worker selection, cross-Worker Artifact dependencies, approval pause/resume, independent governance review, browser refresh, and task recovery.
- Do not add automatic Shopify or eBay publishing in the first release.

