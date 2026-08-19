# AgentTeams Native Worker and Web Workspace Implementation Plan

> **For agentic workers:** Execute this plan in the current session with the repository's existing conventions. Do not use TDD. Complete the functionality first, then run the final integration verification at the end.

**Goal:** Turn the cross-border catalog governance app into an AgentTeams-native system with durable Manager/Worker roles, shared task context, artifact-backed handoffs, and a browser Web workspace as the first release UI.

**Architecture:** The separately maintained `../AgentTeams` installation is the collaboration runtime. Its Controller owns Worker/Team/Manager resources; its Manager and TeamHarness own project/task planning, Matrix rooms, Worker delegation, shared files, and human intervention. Python/FastAPI owns cross-border domain truth: Product/SKU, taxonomy, compliance, listing drafts, approvals, and local Artifact projections. The Web workspace reads authoritative platform state and AgentTeams-derived state; it does not invent its own task model or become a second source of truth.

**Deployment note:** First release runs on a single machine or simple Compose-style local setup. Do not add Kubernetes manifests, cluster bootstrap, or operator deployment work in this release. Revisit K8s only after the single-node system is stable and scaling pressure is real.

**Tech Stack:** Python 3.11+, FastAPI, AgentTeams runtime, SQLite, React, Vite, TypeScript.

## Global Constraints

- First release supports womenswear, the United States, Shopify, and eBay US only.
- First release exports files and never publishes products automatically.
- No Electron in the first release.
- No local Worker scheduler, fake AgentTeams queue, or copied Manager/Worker runtime. The integration requester uses the official AgentTeams Matrix/TeamHarness entry points and only projects their documented completion markers.
- No K8s in the first release; use local processes or Compose-style orchestration only.
- Skills remain reusable capability packages, not orchestration engines.
- Taxonomy validation, graph/schema validation, evidence-span validation, and release-state transitions remain deterministic platform steps.
- Do not use TDD; implement completely and run only the final integrated verification.

## Task 1: Connect the external AgentTeams runtime boundary

**Files:**
- Create: `src/crossborder_cowork/agentteams/`
- Modify: `src/crossborder_cowork/application.py`
- Modify: `src/crossborder_cowork/platform/`
- Modify: `src/crossborder_cowork/config.py`

**Interfaces:**
- Produces: AgentTeams Manager/Worker bootstrap, shared task context access, Worker registry, and task lifecycle hooks.

- [x] Verify the official AgentTeams Controller, Manager, Matrix and TeamHarness services are reachable before accepting tasks.
- [x] Submit requester messages to the Manager DM using the Matrix API and preserve project/task IDs.
- [x] Read Worker membership from the official Controller API; do not use local role registration as runtime truth.
- [x] Map only TeamHarness `TASK_COMPLETED` / `TASK_BLOCKED` markers into the local task projection.

## Task 2: Define the cross-system context and artifact contracts

**Files:**
- Create: `src/crossborder_cowork/platform/task_context.py`
- Create: `src/crossborder_cowork/platform/artifacts.py`
- Modify: `src/crossborder_cowork/platform/database.py`
- Modify: `src/crossborder_cowork/platform/events.py`

**Interfaces:**
- Produces: shared task manifest, dependency manifest, artifact manifest, and recovery-friendly task snapshots.

- [x] Store only compact summaries, stable IDs, and resource references in task context.
- [x] Persist artifact ownership, versions, hashes, and upstream dependencies.
- [x] Store AgentTeams room/event identifiers in the local task result so recovery works after Web backend restart.
- [x] Keep TeamHarness shared paths as external references; never pretend a local file exists until it is downloaded or mounted.
- [x] Keep all file and artifact writes behind platform services.

## Task 3: Define the four business Worker roles and their Skills

**Files:**
- Create/modify: `src/crossborder_cowork/agentteams/`
- Create: `skills/product-catalog/SKILL.md`
- Create: `skills/us-apparel-compliance/SKILL.md`
- Create: `skills/shopify-listing/SKILL.md`
- Create: `skills/ebay-us-listing/SKILL.md`
- Create: `skills/product-localization-en-us/SKILL.md`

**Interfaces:**
- Produces: `catalog_steward_agent`, `compliance_specialist_agent`, `listing_operations_agent`, and `governance_reviewer_agent`.

- [x] Keep each Worker durable, role-scoped, and artifact-aware in the official AgentTeams runtime; do not create a local Worker scheduler or role registry.
- [x] Let Skills load progressively and only when the Worker needs them.
- [x] Expose deterministic domain tools for parsing, validation, compliance, and export.
- [x] Keep business reasoning inside the role boundary; keep deterministic checks in platform services.

## Task 4: Build the browser Web workspace (Electron excluded)

**Files:**
- Create/modify: `web/src/pages/Project/Workspace.tsx`
- Create/modify: `web/src/components/`
- Create/modify: `web/src/state/`
- Modify: `web/src/api.ts`

**Interfaces:**
- Produces: a web workspace for projects, tasks, Workers, approvals, artifacts, and files.

- [x] Read backend task state, shared context, approvals, and artifact manifests directly.
- [x] Show Worker progress, handoffs, and generated files as projected state.
- [x] Keep the view rich and operational without becoming a second truth source.
- [x] Do not add or restore an Electron shell in this release.
- [x] Preserve a clean empty state and a clear first-task flow.

## Task 5: Connect cross-border domain services to Worker actions

**Files:**
- Create/modify: `src/crossborder_cowork/catalog/`
- Create/modify: `src/crossborder_cowork/compliance/`
- Create/modify: `src/crossborder_cowork/platforms/`
- Create/modify: `src/crossborder_cowork/governance/`

**Interfaces:**
- Produces: canonical Product/SKU facts, compliance findings, channel drafts, and export packages.

- [x] Keep product truth, compliance truth, and channel draft truth separate.
- [x] Route confirmations and high-risk changes through approval.
- [x] Generate artifacts deterministically after domain checks pass.

## Task 6: Update documentation and startup guidance

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md` only if a durable rule needs clarification

**Interfaces:**
- Produces: clear startup instructions and the current architecture summary.

- [x] Document the single-node/local startup path.
- [x] Document that K8s is deferred in the first release.
- [x] Document the AgentTeams/Skills/Web boundary in plain language.

## Task 7: Final integrated verification

**Files:**
- None beyond the files above.

- [x] Start the application in local development mode.
- [x] Run one real womenswear catalog scenario end to end.
- [x] Verify Worker delegation, shared context, approvals, artifact creation, and Web projection.
- [x] Verify no Electron path, no custom event adapter, no local Worker scheduler, and no K8s dependency entered the first release.
- [x] Run the final integration commands for the backend and web app.

## Risks

- A UI-only implementation can drift back into a second state source if task context and artifacts are not kept authoritative.
- A deployment story that reaches for K8s too early will slow debugging and obscure the real runtime boundary.
- Worker design can get too generic if the four business roles are not kept durable and distinct.

## Self-review

- The plan keeps AgentTeams as the collaboration base and Python/FastAPI as the domain truth source.
- The plan explicitly defers K8s, Electron, and auto-publishing.
- Every major design decision has an implementation task and a verification step.

## Runtime note

The currently published QwenPaw Manager image logs a warning that its optional
task-trace sync layer has no `AGENTTEAMS_WORKER_NAME` when running as a Manager.
This does not change the authoritative execution path: the Manager still uses
AgentTeams `projectflow`, Matrix, TeamHarness shared state, and Worker rooms;
the Web requester never treats that warning as a local scheduling signal. A
future AgentTeams image can remove the warning by injecting a Manager trace
identity at the Controller layer; the cross-border application does not patch
the Manager container or create a replacement taskflow implementation.
