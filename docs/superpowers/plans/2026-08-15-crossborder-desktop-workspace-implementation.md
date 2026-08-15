# Cross-border Desktop Workspace Implementation Plan

> **For agentic workers:** Implement inline in this session with the existing repository conventions. Do not use TDD; run the final integrated verification after implementation.

**Goal:** Replace the placeholder cross-border desktop shell with an application-internal project/task workspace modeled on the existing cowork workspace, while keeping all cross-border business data and APIs independent.

**Architecture:** Keep the cross-border API as the business boundary, but expose its workforce lifecycle through an Eigent-compatible product-event protocol. The backend remains the authoritative task/worker/artifact/approval state source; the desktop consumes the native event stream and renders workspace panels from that state rather than inventing a second UI adapter or parsing presentation text. Rebuild the React shell around a persistent left history rail, a task conversation/status workspace, and contextual product/compliance/listing/file panels. Do not reintroduce old `uiagentStoreAdapter`, `uiagentStreamAdapter`, `useCoworkUiagentStore`, or legacy runner modules.

**Tech Stack:** React 18, TypeScript, Vite, Electron, existing cross-border FastAPI API.

## Global Constraints

- The first release exports Shopify/eBay drafts and never publishes automatically.
- Cross-border Product/SKU, compliance, Listing, Approval, Artifact, and model-settings APIs remain authoritative.
- Layout and interaction may follow the existing cowork workspace, but deprecated adapters, stores, agents, and domain modules must not be copied.
- Do not use `window.prompt` or browser-native modal dialogs for core actions.
- Do not use TDD; complete implementation first and run final integrated verification.
- Agent/worker output, file mappings, active workspace, and status panels must be driven by the backend event/state protocol; no frontend-only heuristic mapping of log text is allowed.

### Task 0: Establish the native product-event boundary

**Files:**
- Create: `src/crossborder_cowork/platform/product_events.py`
- Modify: `src/crossborder_cowork/platform/database.py`
- Modify: `src/crossborder_cowork/platform/events.py`
- Modify: `src/crossborder_cowork/app.py`
- Modify: `src/crossborder_cowork/workflow.py`
- Modify: `desktop/src/api.ts`

- [ ] Add versioned `eigent` product events with stable sequence, source event ID, action, payload, and task/run identity.
- [ ] Emit native actions for worker creation/activation/deactivation, task assignment/state, toolkit calls, file writes, approvals, and terminal status from the existing deterministic workflow and Artifact service.
- [ ] Persist events idempotently and expose history plus SSE with gap/version metadata.
- [ ] Keep the existing `/api/tasks/:id` detail response as a snapshot/recovery source; the event stream is the live UI source.
- [ ] Define typed desktop event contracts matching the backend protocol without introducing a `*Adapter` or a second reducer layer.

### Task 1: Replace project creation with an in-app dialog

**Files:**
- Modify: `desktop/src/main.tsx`
- Modify: `desktop/src/styles.css`

- [ ] Add controlled modal state with project name, validation, submit/loading/error states, and Escape/backdrop close behavior.
- [ ] Change the sidebar plus button to open the modal instead of calling `window.prompt`.
- [ ] On successful creation, refresh projects, select the new project, and focus the task composer.
- [ ] Keep API errors visible inside the modal and preserve the existing `/api/projects` contract.

### Task 2: Build the cowork-style shell

**Files:**
- Modify: `desktop/src/main.tsx`
- Modify: `desktop/src/styles.css`

- [ ] Split the page into top bar, history rail, main task workspace, and contextual inspector regions.
- [ ] Add clear empty-state primary actions for creating a project and starting the first catalog task.
- [ ] Show project metadata, task status, last update, and active task count in the rail instead of only raw buttons.
- [ ] Add responsive behavior without changing API semantics.

### Task 3: Rework task workspace around execution flow

**Files:**
- Modify: `desktop/src/pages/Project/Workspace.tsx`
- Modify: `desktop/src/styles.css`

- [ ] Replace the flat tab-first presentation with an execution header, step timeline, source dropzone, activity feed, approval inbox, and contextual views.
- [ ] Keep workflow upload/run actions wired to `uploadSources` and `runTask`.
- [ ] Keep Product Graph, Compliance & Issues, Listings, Files, and Settings available as workspace views, but expose them through the same workspace navigation pattern.
- [ ] Poll task detail without resetting the active view or losing in-progress file selection.

### Task 4: Align language and affordances with catalog governance

**Files:**
- Modify: `desktop/src/main.tsx`
- Modify: `desktop/src/pages/Project/Workspace.tsx`
- Modify: `desktop/src/styles.css`
- Modify: `README.md`

- [ ] Replace implementation-oriented labels with user-facing catalog workflow labels: source intake, review facts, compliance, channel drafts, and export package.
- [ ] Add visible next-action guidance when no project, no task, no source, approval pending, or workflow completed.
- [ ] Document the in-app project/task creation flow and the single-command development startup.

### Task 5: Final integrated verification

**Files:**
- None beyond the files above.

- [ ] Run `npm run type-check` from `desktop`.
- [ ] Run `npm run build` from `desktop`.
- [ ] Run the existing backend/catalog integration tests selected for this project.
- [ ] Start the desktop development mode, verify the create-project dialog and first-task flow manually, then confirm no deprecated files are added.

---

## Self-review

- Project creation, shell, workspace flow, terminology, and verification each have an explicit task.
- No deprecated adapter/store/runner module is referenced as an implementation dependency.
- No Shopify/eBay publishing behavior is added.
- The plan uses the existing cross-border API contracts rather than inventing a second state source.
