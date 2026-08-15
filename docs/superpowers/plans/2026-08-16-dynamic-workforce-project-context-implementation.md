# Dynamic Workforce and Project Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. This repository explicitly does not use TDD for this project: complete all functionality first, then run only the final integration verification in Task 7.

**Goal:** Replace the fixed sequential runner with native CAMEL Workforce dynamic 1..N Agent execution, persist project-owned resources for cross-task reuse, and make Product Events the authoritative source for real-time Agent, tool, file, and workspace UI state.

**Architecture:** CAMEL `WorkforceMode.AUTO_DECOMPOSE` receives the user objective plus a compact project resource manifest and assigns dynamically created subtasks to four custom `Worker` nodes. Business data remains in project-scoped SQLite facts and immutable Artifacts; CAMEL Task results contain only a concise summary and `output_resource_ids`. A platform Tool Executor and Workforce callback persist lifecycle events, which are projected to Eigent-compatible Product Events and reduced directly by the desktop UI.

**Tech Stack:** Python 3.11+, CAMEL AI 0.2.90, FastAPI, SQLite, Pydantic 2, React 18, TypeScript, Electron, Vite.

## Global Constraints

- First release supports womenswear, the United States, Shopify, and eBay US only.
- First release exports listing packages and never publishes automatically.
- `camel-ai>=0.2.90,<0.3` is a required product dependency.
- The Planner and Human Approval are platform capabilities, not business Agents.
- Worker selection is dynamic; a valid task may contain one Agent or several Agents.
- Product, SKU, Listing, Artifact, material, and resource reads must be isolated by `project_id`.
- CAMEL Task result strings must never carry complete Product, Listing, compliance, or file payloads.
- Frontend state must come from task snapshots plus Product Events; do not add a frontend stream adapter or synthesize calls from static capabilities.
- Tool UI shows only Chinese tool name and running/completed/failed state, without duration, arguments, raw return JSON, or stack traces.
- Agent progress is public work summary, not hidden chain-of-thought.
- Complete implementation before testing; run only the final integration verification in Task 7.
- Preserve unrelated `.codex_tmp/`, `docs/submissions/`, and `提交材料/` files.

---

### Task 1: Add project-owned resource persistence

**Files:**
- Modify: `src/crossborder_cowork/platform/database.py`
- Create: `src/crossborder_cowork/platform/resources.py`
- Modify: `src/crossborder_cowork/platform/artifacts.py`
- Modify: `src/crossborder_cowork/graph/service.py`
- Modify: `src/crossborder_cowork/graph/store.py`
- Modify: `migrations/001_catalog_graph.sql`
- Modify: `src/crossborder_cowork/application.py`

**Interfaces:**
- Produce `ProjectResourceService.create(...)`, `list(project_id, ...)`, `resolve(...)`, `activate(...)`, and `get(resource_id, project_id)`.
- Produce resource records with `id`, `project_id`, `resource_type`, `logical_key`, `owner_worker_name`, `source_task_id`, `source_step_id`, `storage_kind`, `storage_ref`, `version`, `status`, and `metadata`.
- Add `project_id` and `process_task_id` ownership to Artifact records and project-aware Product/Listing queries.

- [ ] Extend the platform schema with `project_resources`, resource lookup indexes, `task_step_dependencies`, and additive `project_id`/`process_task_id` columns required by existing tables. Use idempotent SQLite migration helpers for existing databases rather than destructive table replacement.
- [ ] Implement resource state validation for `candidate`, `active`, `superseded`, `blocked`, and `rejected`; activating a new version must supersede the previous active row with the same project/type/logical key in one transaction.
- [ ] Update Artifact creation so it derives `project_id` from the owning task, records `process_task_id`, creates an Artifact resource pointer, and publishes an `artifact.created` event containing both IDs.
- [ ] Scope graph writes and stable Product/SKU IDs by project. Update all Product list/detail methods so a caller supplies either `project_id` or a task whose project is resolved server-side.
- [ ] Register `ProjectResourceService` in `CrossborderApplication` and keep complete resource payloads out of `tasks.result_json` and `task_steps.result_json`.
- [ ] Commit this deliverable with `feat: add project resource persistence`.

### Task 2: Add project context tools and deterministic tool execution

**Files:**
- Create: `src/crossborder_cowork/platform/execution_context.py`
- Create: `src/crossborder_cowork/platform/tool_executor.py`
- Create: `src/crossborder_cowork/platform/project_context.py`
- Create: `src/crossborder_cowork/tools/project_context.py`
- Modify: `src/crossborder_cowork/platform/registry.py`
- Modify: `src/crossborder_cowork/application.py`

**Interfaces:**
- Produce immutable `ExecutionContext(task_id, project_id, process_task_id, worker_name)` carried by `contextvars`.
- Produce `ToolExecutor.execute(tool_name, context, fn, *args, **kwargs)` with one stable `tool_call_id` for start and terminal events.
- Produce `ProjectContextService.planner_manifest(task_id)`, `resolve_inputs(...)`, and authorized paged read methods.
- Register `list_project_resources`, `get_canonical_products`, `get_product_facts`, `get_listing_drafts`, `get_artifact_manifest`, `read_artifact_text`, and `get_pending_approvals`.

- [ ] Implement strict project ownership checks for every context read; a foreign-project resource ID must fail with a protocol-safe error before any file or database access.
- [ ] Resolve inputs in this exact order: explicit selected resource IDs, direct upstream `output_resource_ids`, active project resources, then an explicit no-input result.
- [ ] Generate a compact Planner manifest containing resource ID/type/logical key/version/status/owner and counts, never full Artifact text or Product JSON.
- [ ] Wrap deterministic business calls with `tool_call.started`, `tool_call.succeeded`, and `tool_call.failed`; persist audit summaries but expose only ID, Chinese label, Worker, process task, and status to Product Events.
- [ ] Page Markdown/text Artifact reads by offset and limit, reject binary MIME types, validate on-disk path/hash/size through Artifact Service, and cap each response.
- [ ] Store Worker-to-Tool authorization metadata in `WorkerRegistry`; reject unauthorized execution in `ToolExecutor`.
- [ ] Commit this deliverable with `feat: add project context tool execution`.

### Task 3: Replace the fixed runner with native CAMEL Workforce

**Files:**
- Create: `src/crossborder_cowork/workforce/__init__.py`
- Create: `src/crossborder_cowork/workforce/callback.py`
- Create: `src/crossborder_cowork/workforce/worker.py`
- Create: `src/crossborder_cowork/workforce/runtime.py`
- Modify: `src/crossborder_cowork/platform/tasks.py`
- Modify: `src/crossborder_cowork/workflow.py`
- Modify: `src/crossborder_cowork/platform/model_runtime.py`
- Modify: `src/crossborder_cowork/app.py`
- Modify: `src/crossborder_cowork/application.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produce `CrossborderWorkforceRuntime.run(task_id) -> dict[str, Any]`.
- Produce four CAMEL `Worker` subclasses through one reusable `BusinessWorker` wrapper with stable node IDs equal to business Worker names.
- Produce `CrossborderWorkforceCallback` implementing every CAMEL 0.2.90 callback method.
- Add dynamic `TaskService.create_step_from_workforce(...)`, dependency persistence, and idempotent lifecycle updates.

- [ ] Move `camel-ai>=0.2.90,<0.3` into required dependencies and build CAMEL model backends from the existing desktop/environment role configurations without persisting credentials.
- [ ] Construct one `Workforce(mode=WorkforceMode.AUTO_DECOMPOSE)` per run with native coordinator/task agents, the four custom Worker children, strict business-role descriptions, and the project resource manifest appended to the root objective.
- [ ] In `TaskCreatedEvent`, persist the CAMEL task using the exact CAMEL `task_id`; in assignment/start/completion/failure callbacks persist Worker, dependencies, state, compact summary, and `output_resource_ids` without generating parallel IDs.
- [ ] Validate each assignment against registered Worker IDs, acyclic dependencies, project-owned referenced resources, Tool/Skill authorization, and the no-publishing rule. Invalid plans fail visibly instead of falling back to the old four-step runner.
- [ ] Implement `BusinessWorker._process_task` so it creates `ExecutionContext`, resolves declared inputs from `ProjectContextService`, invokes the matching business Agent, stores only a compact Task result string, and returns CAMEL `TaskState.DONE` or `FAILED`.
- [ ] Remove `DEFAULT_STEPS` and direct `.run()` sequencing from `CatalogWorkflow`; task creation no longer creates four placeholder steps and task execution no longer requires new material when active project resources satisfy the objective.
- [ ] Preserve approval decisions in SQLite. Approval rerun starts a new Workforce run using explicit affected resource IDs; correctness must not depend on an in-memory CAMEL snapshot.
- [ ] Commit this deliverable with `feat: run tasks with dynamic camel workforce`.

### Task 4: Refactor business Agents to resource inputs and compact outputs

**Files:**
- Modify: `src/crossborder_cowork/workers/catalog_steward.py`
- Modify: `src/crossborder_cowork/workers/compliance_specialist.py`
- Modify: `src/crossborder_cowork/workers/listing_operations.py`
- Modify: `src/crossborder_cowork/workers/governance_reviewer.py`
- Modify: `src/crossborder_cowork/export/package.py`
- Modify: `src/crossborder_cowork/platform/approvals.py`

**Interfaces:**
- Each Agent accepts `ExecutionContext` plus resolved resource IDs/material IDs, reads payloads through platform services, and returns `{summary, key_counts, output_resource_ids, status}`.
- Each formal narrative output is a `text/markdown` Artifact; JSON/CSV/ZIP remain machine resources.

- [ ] Add concise Chinese `agent.progress` events at meaningful boundaries: input inspection, validation findings, draft/report generation, and final decision. Do not emit model reasoning or raw payloads.
- [ ] Route each deterministic operation through `ToolExecutor` with Chinese labels such as `解析商品素材`, `校验商品分类`, `检查美国服装合规`, `生成 Shopify 草稿`, and `审核交付一致性`.
- [ ] Catalog Agent writes canonical Product/SKU and conflict resources; compliance Agent resolves canonical Product resources and writes findings/report resources; listing Agent resolves canonical Product resources and writes platform draft resources; governance Agent resolves the exact requested active/upstream resources and writes review/export resources.
- [ ] Generate formal Markdown reports for compliance and governance. Do not turn a serialized result dictionary into Markdown.
- [ ] Make all Artifact dependencies resource-based and preserve source task/step provenance. Do not select dependencies by newest timestamp.
- [ ] Ensure a standalone Agent returns a clear missing-input result when no compatible resource exists; Workforce may replan but the Agent must not fabricate empty business output.
- [ ] Commit this deliverable with `refactor: make agents consume project resources`.

### Task 5: Make Product Events the complete runtime projection

**Files:**
- Modify: `src/crossborder_cowork/platform/product_events.py`
- Modify: `src/crossborder_cowork/platform/events.py`
- Modify: `src/crossborder_cowork/platform/tasks.py`
- Modify: `src/crossborder_cowork/platform/artifacts.py`
- Modify: `src/crossborder_cowork/app.py`

**Interfaces:**
- Project `workforce.task_created/decomposed/assigned/started/completed/failed`, `agent.progress`, `tool_call.*`, and `artifact.created` into Eigent protocol version 1.
- Maintain `assign_task.task_id == activate_agent.process_task_id == toolkit.process_task_id == write_file.process_task_id == task_state.task_id`.

- [ ] Add idempotent Product Event drafts for dynamic task creation/decomposition, assignment, Agent activation/deactivation, task state, progress, toolkit activation/deactivation, and file writes.
- [ ] Use CAMEL `task_steps.id` directly as `process_task_id`; never prefix it, translate it, or recover ownership from Agent names.
- [ ] Include `tool_call_id` and one of `running/completed/failed` in tool payloads. Do not include duration, arguments, return JSON, or stack traces in visible payload fields.
- [ ] Include `artifact_id`, `process_task_id`, `worker_name`, MIME type, file name, size, and download identity in each `write_file` event so multiple files remain independently addressable.
- [ ] Extend task detail snapshots with project resource manifests and step-owned resources so refresh recovery produces the same state as a live stream.
- [ ] Keep legacy tasks readable without synthesizing absent tool calls or assigning artifacts by fuzzy Worker-name matching.
- [ ] Commit this deliverable with `feat: project workforce lifecycle events`.

### Task 6: Reduce authoritative events into Agent cards and resource workspaces

**Files:**
- Modify: `desktop/src/api.ts`
- Modify: `desktop/src/types.ts`
- Rewrite: `desktop/src/state/crossborderWorkspaceState.ts`
- Modify: `desktop/src/components/ChatBox/TaskBox/TaskItem.tsx`
- Modify: `desktop/src/components/ChatBox/TaskBox/TaskCard.tsx`
- Modify: `desktop/src/components/ChatBox/TaskBox/StreamingTaskList.tsx`
- Modify: `desktop/src/pages/Project/Workspace.tsx`
- Modify: `desktop/src/components/ProductGraph/ProductGraph.tsx`
- Modify: `desktop/src/components/ProductIssues/ProductIssues.tsx`
- Modify: `desktop/src/components/ListingWorkspace/ListingWorkspace.tsx`
- Modify: `desktop/src/components/WorkFlow/index.tsx`
- Modify: `desktop/src/styles.css`

**Interfaces:**
- Produce a pure reducer keyed by `process_task_id`, `tool_call_id`, and `artifact_id`.
- Produce Agent workspace view models with explicit `not_started`, `running`, `empty`, `failed`, and `completed` states.
- Add Artifact text preview API support while retaining download for all file types.

- [ ] Seed reducer state from the task snapshot, then apply Product Events strictly by sequence. Ignore duplicate sequence numbers and reconnect on gaps; do not concatenate a second snapshot onto already applied events.
- [ ] Build dynamic task cards from `assign_task`/task snapshots. Show public progress entries one line at a time and tool rows containing only Chinese name plus state.
- [ ] Set `task.report` only from compact completion summary or Markdown Artifact content. Remove all `JSON.stringify(step.result)` report generation.
- [ ] Assign files to a step only by `process_task_id` and to a Worker workspace only through the owning step/resource metadata. Remove `artifact.worker_name === step.worker_name` as the ownership rule.
- [ ] Query Product, compliance, Listing, governance, approval, and Artifact data by `project_id`/resource ID for each workspace instead of reading shared `detail.task.result`.
- [ ] Add inline text/Markdown Artifact preview fetched by Artifact ID; JSON/CSV may show bounded structured/text preview, while XLSX/ZIP/image binaries show metadata and download. Clicking different files must always fetch their own content.
- [ ] Keep all user-visible Agent, tool, status, directory, and capability labels in Chinese; internal IDs remain stable English identifiers.
- [ ] Commit this deliverable with `feat: render agent runtime from product events`.

### Task 7: Run final integration verification and commit

**Files:**
- Modify: `tests/test_catalog_listing_integration.py`
- Modify: `tests/test_production_scenario_acceptance.py`
- Modify: `tests/test_project_material_workflow.py`
- Create: `tests/test_dynamic_workforce_project_context_integration.py`
- Modify: `README.md` only if startup/runtime behavior changed for users.

**Interfaces:**
- Verify both single-Agent resource reuse and multi-Agent full delivery through public application/API boundaries.

- [ ] Run a full delivery objective from imported womenswear materials and assert that CAMEL creates dynamic steps, applicable branches execute, every lifecycle uses the same process task ID, real tool events exist, and Markdown/report Artifacts are independently readable.
- [ ] Run a second task in the same project with objective `审核已有 eBay 草稿`; assert only the governance role is assigned and it reads active Listing/compliance resources without new uploaded materials.
- [ ] Create a second project containing the same source SKU and assert Product, Listing, Artifact, and resource queries never return the first project's records.
- [ ] Assert visible tool payloads contain no duration/arguments/raw results, step reports contain no serialized machine JSON, and refresh snapshot plus replay yields the same reduced state as the live event sequence.
- [ ] Run `python -m pytest -q --color=no --tb=short` from the repository root and require zero failures.
- [ ] Run `npm run type-check` from `desktop` and require exit code 0.
- [ ] Run `npm run build` from `desktop` and require exit code 0.
- [ ] Start the backend and desktop development servers, exercise project creation, material import, full task execution, standalone review, Agent workspace switching, multiple file previews, and page refresh; capture any runtime error before stopping both processes.
- [ ] Run `git diff --check`, inspect `git status --short`, and commit only task-related files with `feat: add dynamic workforce project context`.
