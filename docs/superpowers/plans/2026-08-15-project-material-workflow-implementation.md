# Project Material Workflow Implementation Plan

> **For agentic workers:** Execute this plan task-by-task in the current session. Repository instructions prohibit TDD for this project; implement the complete workflow first, then run the final integration verification in Task 6.

**Goal:** Build a project-first workflow where users manage reusable source materials, explicitly import an example catalog, select materials for a task, and reliably run the Workforce without connecting to a stale backend.

**Architecture:** Introduce platform-owned `project_materials` and `task_materials` records and a focused material service. Project materials are durable inputs; tasks bind immutable material references and project their validated paths into workflow input. The desktop gains a real project home, while Electron owns an isolated backend port and verifies the backend identity before loading the UI.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, Electron 33, React 18, TypeScript, Vite.

## Global Constraints

- New projects contain no tasks and no materials by default.
- Example data is imported only after the user clicks “导入示例数据”.
- Tasks cannot run without at least one material from the same project.
- Internal Agent, Tool, Skill, Artifact and event protocol identifiers remain stable.
- First release exports Shopify/eBay files and does not publish automatically.
- Implement functionality before running final integration verification; do not use TDD.

---

### Task 1: Project Material Persistence and Example Fixture

**Files:**
- Modify: `src/crossborder_cowork/platform/database.py`
- Create: `src/crossborder_cowork/platform/materials.py`
- Modify: `src/crossborder_cowork/config.py`
- Create: `examples/womenswear-us/womenswear-catalog.csv`
- Create: `examples/womenswear-us/README.md`

**Interfaces:**
- Produces `ProjectMaterialService.list(project_id)`, `store_upload(...)`, `import_example(project_id)`, `bind_task(task_id, project_id, material_ids)`, and `task_paths(task_id)`.
- Material writes use a generated ID, sanitized basename, SHA-256, atomic persistence, and same-project validation.

- [ ] Add `project_materials` and `task_materials` tables plus indexes to the platform schema.
- [ ] Add `project_material_dir` and `example_dir` settings that work in development and packaged resources.
- [ ] Implement material persistence, SHA-256 deduplication per project, task binding and integrity checks.
- [ ] Add a complete two-product womenswear CSV and a field guide.

### Task 2: Project and Task API Contracts

**Files:**
- Modify: `src/crossborder_cowork/app.py`
- Modify: `src/crossborder_cowork/application.py`
- Modify: `src/crossborder_cowork/platform/tasks.py`
- Modify: `src/crossborder_cowork/workflow.py`

**Interfaces:**
- `TaskCreate.material_ids: list[str]` is required for executable desktop tasks.
- Project material endpoints return public metadata without absolute paths.
- `/health` returns `app_id`, `app_version`, `protocol_name`, and `protocol_version`.

- [ ] Register the material service in `CrossborderApplication`.
- [ ] Add project detail, material list/upload/import/download endpoints.
- [ ] Bind selected material IDs during task creation and project validated paths into `input.source_paths`.
- [ ] Reject a run synchronously with HTTP 409 when bindings are empty or invalid, without marking the task failed.
- [ ] Keep task attachment upload backward compatible by storing uploads as project materials before binding.
- [ ] Return application and event-protocol identity from health.

### Task 3: Desktop API and Project Home

**Files:**
- Modify: `desktop/src/api.ts`
- Create: `desktop/src/pages/Project/ProjectHome.tsx`
- Modify: `desktop/src/main.tsx`
- Modify: `desktop/src/styles.css`

**Interfaces:**
- `api.projectMaterials`, `api.uploadProjectMaterials`, `api.importExampleMaterials`, and `api.createTask(projectId, objective, materialIds)`.
- `ProjectHome` receives the selected project and emits `onOpenTask(taskId)` after successful create-and-run.

- [ ] Add typed material and health contracts.
- [ ] Build a project overview with material counts, source/origin metadata, selection controls, upload and explicit example import.
- [ ] Disable task execution until objective and material selection are valid.
- [ ] Make project selection open the project home; task selection alone opens a task workspace.
- [ ] Keep recent tasks visible and allow returning to the project home.

### Task 4: Event Protocol and Backend Process Isolation

**Files:**
- Modify: `desktop/electron/main.ts`
- Modify: `desktop/src/api.ts`
- Modify: `desktop/src/pages/Project/Workspace.tsx`

**Interfaces:**
- Electron supplies runtime API URL through `apiBaseUrl` in the window URL.
- Backend identity must match `crossborder-catalog-cowork` and Product Event protocol version `1`.

- [ ] Allocate a free loopback port for each Electron backend process and pass it in `CROSSBORDER_COWORK_PORT`.
- [ ] Validate the health identity before loading the desktop window and show a startup failure page when invalid.
- [ ] Read runtime API URL before the compile-time fallback.
- [ ] Validate Product Event envelopes and surface protocol mismatch separately from malformed payloads.
- [ ] Recover sequence gaps from a fresh snapshot without recursive duplicate connections.

### Task 5: Documentation and Packaging

**Files:**
- Modify: `README.md`
- Modify: `desktop/package.json`
- Modify: `.gitignore`

**Interfaces:**
- README documents the project-first workflow and the exact sample file path.
- Packaged app includes `examples/` as read-only resources.

- [ ] Add examples to Electron `extraResources`.
- [ ] Document upload, example import, material selection, task execution, approvals and export download.
- [ ] Document installed material storage and clarify that example data is opt-in.

### Task 6: Final Integration Verification

**Files:**
- Create: `tests/test_project_material_workflow.py`
- Modify: `tests/test_catalog_listing_integration.py` only if the public task creation helper changes.

**Interfaces:**
- Verifies project creation without tasks, example import deduplication, cross-project rejection, task binding, preflight rejection and successful sample workflow.

- [ ] Run `python -m pytest tests/test_project_material_workflow.py tests/test_catalog_listing_integration.py tests/test_production_scenario_acceptance.py -q --color=no --tb=short` and require zero failures.
- [ ] Run `npm run type-check` and `npm run build` in `desktop` and require exit code 0.
- [ ] Start the development app and verify project creation, explicit example import, material selection, task creation, workflow navigation and generated artifacts in the rendered UI.
- [ ] Run `git diff --check` and inspect the final diff for accidental protocol-ID or domain-scope changes.
