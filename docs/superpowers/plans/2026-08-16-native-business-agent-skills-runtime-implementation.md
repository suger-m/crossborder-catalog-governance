# Native Business Agent Skills Runtime Implementation Plan

> **For agentic workers:** Execute inline in this repository. Do not dispatch separate review or test agents. Run only the final integrated verification after implementation.

**Goal:** Replace fixed Python business runners with Eigent-style CAMEL ChatAgents that autonomously activate scoped Skills and call only project-context and role-domain Tools.

**Architecture:** Keep `ResourceAwareWorkforce`, Product Events, project resources, Artifacts and approval services. Replace the custom direct-call `BusinessWorker` with a lightweight native `SingleAgentWorker` extension that runs a real ChatAgent and supplies the CAMEL process task identity. Extend CAMEL `SkillToolkit` for repository/user discovery and per-role visibility; expose deterministic business services through focused FunctionTools.

**Tech Stack:** Python 3.11+, CAMEL Workforce/ChatAgent/SkillToolkit, FastAPI, SQLite, existing Product Event and Artifact services.

## Global Constraints

- Do not use TDD; implement completely and run final integration verification once.
- Do not add TerminalToolkit, SearchToolkit, browser, MCP, arbitrary file-write, shell, or marketplace publishing tools.
- Keep four durable business Agents; Planner and Human Approval remain platform capabilities.
- Formal taxonomy, graph, evidence, resource, approval and release validation remain platform code.
- Backend Product Events remain the authoritative UI state.

---

### Task 1: Replace the minimal Skill registry with a CAMEL-based runtime

**Files:**
- Modify: `src/crossborder_cowork/platform/skills.py`
- Modify: `src/crossborder_cowork/config.py`
- Modify: `src/crossborder_cowork/application.py`

- [ ] Extend CAMEL `SkillToolkit` with project/user roots, role-scoped `allowed_skills`, Skill activation events and project task identity.
- [ ] Preserve REST list/detail APIs through a catalog facade backed by the same runtime.
- [ ] Remove regex frontmatter parsing and use CAMEL's YAML parser/discovery.

### Task 2: Expose project context and domain operations as model-callable Toolkits

**Files:**
- Create: `src/crossborder_cowork/agent/toolkits/project_context.py`
- Create: `src/crossborder_cowork/agent/toolkits/catalog.py`
- Create: `src/crossborder_cowork/agent/toolkits/compliance.py`
- Create: `src/crossborder_cowork/agent/toolkits/listing.py`
- Create: `src/crossborder_cowork/agent/toolkits/governance.py`
- Modify: `src/crossborder_cowork/platform/tool_executor.py`

- [ ] Bind root task, project, process task and worker identity to every toolkit call.
- [ ] Wrap existing deterministic services without giving the model direct database or filesystem access.
- [ ] Return resource IDs and compact summaries rather than full cross-Agent payloads.

### Task 3: Create the four business ChatAgent factories

**Files:**
- Create: `src/crossborder_cowork/agent/factory.py`
- Create: `src/crossborder_cowork/agent/prompts.py`
- Modify: `src/crossborder_cowork/platform/model_runtime.py`

- [ ] Build one scoped ChatAgent per durable business role.
- [ ] Register only SkillToolkit, ProjectContextToolkit and the role's domain Toolkit.
- [ ] Instruct the model to list/load relevant Skills, reuse project resources and return the compact result contract.
- [ ] Explicitly prohibit Terminal, Search, browser, MCP and publishing capabilities.

### Task 4: Replace direct-call BusinessWorker with native ChatAgent execution

**Files:**
- Replace: `src/crossborder_cowork/workforce/worker.py`
- Modify: `src/crossborder_cowork/workforce/runtime.py`
- Modify: `src/crossborder_cowork/workforce/callback.py`

- [ ] Extend CAMEL `SingleAgentWorker` only to bind `process_task_id` and project execution context around native ChatAgent execution.
- [ ] Register business ChatAgents with Workforce using the Eigent/CAMEL single-agent worker pattern.
- [ ] Keep resource-aware quality validation outside the Agent execution path.

### Task 5: Remove fixed business orchestration

**Files:**
- Modify: `src/crossborder_cowork/workers/catalog_steward.py`
- Modify: `src/crossborder_cowork/workers/compliance_specialist.py`
- Modify: `src/crossborder_cowork/workers/listing_operations.py`
- Modify: `src/crossborder_cowork/workers/governance_reviewer.py`
- Modify: `src/crossborder_cowork/application.py`

- [ ] Move reusable deterministic operations into domain Toolkits.
- [ ] Remove fixed Skill selection and `run_for_workforce()` execution sequences.
- [ ] Remove obsolete legacy runner methods after confirming there are no callers.

### Task 6: Upgrade the nine project Skills into real capability packages

**Files:**
- Modify: `skills/*/SKILL.md`
- Create as needed: `skills/*/references/`
- Create as needed: `skills/*/assets/`

- [ ] Add activation scenarios, boundaries, available resources, edge cases and output expectations.
- [ ] Keep reusable platform schemas and policy references in on-demand files.
- [ ] Do not duplicate deterministic platform implementations as Skill scripts.

### Task 7: Product Events and desktop Skill observability

**Files:**
- Modify: `src/crossborder_cowork/platform/product_events.py`
- Modify: `desktop/src/state/crossborderWorkspaceState.ts`
- Modify relevant task/Agent workspace components only if backend events require projection changes.

- [ ] Project `skill.activated` and Skill resource-read events into existing Agent activity views.
- [ ] Show Skill name and state without hidden reasoning or raw JSON.

### Task 8: Final integrated verification and documentation

**Files:**
- Modify: `tests/test_dynamic_workforce_project_context_integration.py`
- Modify: `README.md`

- [ ] Verify full delivery, standalone governance and single-platform Listing through real ChatAgent Worker boundaries.
- [ ] Verify Skill activation, resource ownership, Tool authorization, no Terminal/Search tools, independent Artifact previews and no automatic publishing.
- [ ] Run `python -m compileall -q src` and `python -m pytest -q --color=no --tb=short`.
- [ ] Run `npm run type-check` and `npm run build` in `desktop/`.
