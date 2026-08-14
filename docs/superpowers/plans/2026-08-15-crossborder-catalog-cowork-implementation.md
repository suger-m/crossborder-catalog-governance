# Cross-border Catalog Cowork Implementation Plan

> **For agentic workers:** Execute this plan task-by-task in the current session. Do not use TDD or create per-step test suites; implement the complete feature set first, then run the final integration verification defined in Task 9.

**Goal:** Build an independent multi-agent desktop application that converts womenswear product files into a canonical product graph, US compliance result, Shopify listing package, and eBay US listing package.

**Architecture:** Start from a clean repository and extract only the generic CAMEL Workforce, skill, approval, artifact, event, model configuration, and Electron workspace patterns from `D:/vibe/e-commerce-cowork-p6-cowork`. Keep all cross-border business logic under a separate `crossborder` package. Store graph nodes and edges in SQLite and retain source text/artifacts for traceability.

**Tech Stack:** Python 3.11+, FastAPI, CAMEL Workforce, SQLite, LanceDB, Electron, React, TypeScript.

## Global Constraints

- First release supports womenswear, the United States, Shopify, and eBay US only.
- First release exports files and never performs automatic platform publishing.
- Canonical Product is the only authoritative product fact source.
- US legal compliance and marketplace policy compliance remain separate.
- LLM output cannot directly become a formal taxonomy node or graph edge without platform validation.
- Business capability variations must be implemented as Agent Skills before adding new Agent roles.
- Skills use progressive disclosure and may bundle scripts, references, and assets following the Agent Skills specification.
- Medium-risk writes and future platform publication require Human Approval.
- Do not copy demand-insight, comment-modeling, Demand Signal, Demand Cube, or Opportunity Radar code from the source repository.
- Run only final integration tests after implementation, matching the user's requested development process.

---

### Task 1: Bootstrap the independent application

**Files:**
- Create: `pyproject.toml`
- Create: `src/crossborder_cowork/__init__.py`
- Create: `src/crossborder_cowork/app.py`
- Create: `src/crossborder_cowork/platform/`
- Create: `desktop/`
- Create: `.gitignore`
- Create: `README.md`

**Interfaces:**
- Consumes: generic Workforce, approval, artifact and event patterns from the existing project.
- Produces: `build_application(base_dir: Path) -> CrossborderApplication` and a desktop shell that can create and observe tasks.

- [ ] Copy only generic model configuration, task lifecycle, Worker/Tool/Skill registry, Human Approval, Artifact, Product Event and Electron workspace modules.
- [ ] Rename Python imports to `crossborder_cowork` and remove retrieval-demand assumptions.
- [ ] Configure `python -m crossborder_cowork.app` to start the API and serve desktop-compatible task endpoints.
- [ ] Configure `desktop/package.json` with `dev`, `type-check`, `build`, and Electron packaging scripts.
- [ ] Document one-command development startup in `README.md`.

### Task 2: Add canonical product schemas and graph storage

**Files:**
- Create: `src/crossborder_cowork/catalog/models.py`
- Create: `src/crossborder_cowork/catalog/schemas.py`
- Create: `src/crossborder_cowork/graph/store.py`
- Create: `src/crossborder_cowork/graph/models.py`
- Create: `src/crossborder_cowork/graph/service.py`
- Create: `migrations/001_catalog_graph.sql`

**Interfaces:**
- Produces: `CanonicalProduct`, `CanonicalSku`, `ProductFact`, `GraphNode`, `GraphEdge`, and `CatalogGraphService.upsert_candidate_graph(...)`.

- [ ] Define immutable IDs for Product, SKU, Variant, SourceDocument and ListingVersion.
- [ ] Create SQLite tables `products`, `skus`, `product_facts`, `graph_nodes`, `graph_edges`, `graph_evidence`, and `graph_versions`.
- [ ] Validate node types, relation types, taxonomy versions and source evidence before graph writes.
- [ ] Store candidate, confirmed, rejected and superseded graph states separately.
- [ ] Expose graph summary and product detail endpoints for the desktop application.

### Task 3: Add taxonomy packages

**Files:**
- Create: `configs/taxonomy/womenswear-product.v1.json`
- Create: `configs/taxonomy/us-apparel-compliance.v1.json`
- Create: `configs/taxonomy/shopify-product.v1.json`
- Create: `configs/taxonomy/ebay-us-fashion.v1.json`
- Create: `src/crossborder_cowork/taxonomy/registry.py`
- Create: `src/crossborder_cowork/taxonomy/validator.py`

**Interfaces:**
- Produces: `TaxonomyRegistry.get_node(node_id, version)` and `validate_assignment(assignment, evidence_text)`.

- [ ] Define womenswear category, garment type, material, color, size, fit, occasion and target-user hierarchies.
- [ ] Define US apparel labeling, origin, care, fiber-content, claim and evidence requirements.
- [ ] Define Shopify Product/Variant/Option/Collection/Tag fields.
- [ ] Define eBay US fashion category, Item Specifics, Condition and Variation fields.
- [ ] Reject unknown node IDs, missing taxonomy versions and evidence spans not contained in source text.

### Task 4: Implement the Catalog Steward Agent and catalog Skills

**Files:**
- Create: `src/crossborder_cowork/intake/parsers.py`
- Create: `src/crossborder_cowork/intake/service.py`
- Create: `src/crossborder_cowork/workers/catalog_steward.py`
- Create: `skills/product-catalog/SKILL.md`
- Create: `skills/womenswear-classification/SKILL.md`
- Create: `src/crossborder_cowork/tools/product_intake.py`

**Interfaces:**
- Consumes: uploaded Excel/CSV, JSON, PDF, Markdown and image metadata.
- Produces: `source_manifest.json`, candidate `CanonicalProduct`, candidate SKUs, taxonomy assignments and a conflict list.

- [ ] Parse tabular product fields without sending complete workbooks to the LLM.
- [ ] Persist original files as source artifacts with SHA-256.
- [ ] Extract candidate facts with source file, sheet/page, row and text span.
- [ ] Normalize units, colors, sizes, materials and identifiers using taxonomy rules first.
- [ ] Route unresolved conflicts to Human Approval instead of silently selecting a value.
- [ ] Let `catalog_steward_agent` discover and activate product-catalog or womenswear-classification Skills instead of defining separate Agents.

### Task 5: Implement the Compliance Specialist Agent and compliance Skills

**Files:**
- Create: `src/crossborder_cowork/workers/compliance_specialist.py`
- Create: `src/crossborder_cowork/compliance/us_apparel.py`
- Create: `skills/us-apparel-compliance/SKILL.md`
- Create: `skills/shopify-product-policy/SKILL.md`
- Create: `skills/ebay-us-fashion-policy/SKILL.md`
- Create: `src/crossborder_cowork/tools/compliance.py`

**Interfaces:**
- Produces: independent US legal, Shopify policy and eBay policy results with statuses `pass`, `needs_evidence`, `needs_confirmation`, or `blocked`.

- [ ] Evaluate fiber content, care instruction, origin, manufacturer/importer identity, sizing and marketing claims separately.
- [ ] Attach every compliance finding to a product fact and rule evidence reference.
- [ ] Block release when a hard requirement is missing or contradicted.
- [ ] Keep platform policy findings out of the US legal compliance result.
- [ ] Let one compliance role activate the appropriate legal or marketplace-policy Skill instead of adding a new Agent per jurisdiction or platform.

### Task 6: Implement the Listing Operations Agent and channel Skills

**Files:**
- Create: `src/crossborder_cowork/platforms/base.py`
- Create: `src/crossborder_cowork/platforms/shopify.py`
- Create: `src/crossborder_cowork/platforms/ebay_us.py`
- Create: `src/crossborder_cowork/workers/listing_operations.py`
- Create: `skills/product-localization-en-us/SKILL.md`
- Create: `skills/shopify-listing/SKILL.md`
- Create: `skills/ebay-us-listing/SKILL.md`

**Interfaces:**
- Produces: normalized `ListingDraft`, Shopify CSV rows and eBay US JSON records derived from canonical product versions.

- [ ] Generate Shopify Product, Handle, Option, Variant, Image, Tag and Collection mappings.
- [ ] Generate eBay category, Item Specifics, Condition, Variation, title and description mappings.
- [ ] Record unsupported or missing platform attributes instead of fabricating values.
- [ ] Store `derived_from_product_version` and `platform_rule_version` on every ListingDraft.
- [ ] Do not add API credentials or platform publishing calls in the first release.
- [ ] Let `listing_operations_agent` activate localization, Shopify, and eBay Skills independently and run Shopify/eBay drafts in parallel when dependencies permit.

### Task 7: Implement the Governance Reviewer Agent and deterministic export

**Files:**
- Create: `src/crossborder_cowork/workers/governance_reviewer.py`
- Create: `src/crossborder_cowork/governance/consistency.py`
- Create: `src/crossborder_cowork/export/package.py`
- Create: `skills/catalog-governance/SKILL.md`

**Interfaces:**
- Produces: localized content, consistency findings, release decision and `listing_package.zip`.

- [ ] Compare product, SKU, material, origin, claims and dimensions across Shopify and eBay drafts.
- [ ] Reject stale drafts derived from superseded product versions.
- [ ] Require reviewer status `approved` before export status becomes `ready`.
- [ ] Package source manifest, canonical JSON, SKU matrix, compliance report, Shopify CSV, eBay JSON and review report using deterministic export code rather than an Export Agent.

### Task 8: Build the desktop product workspace

**Files:**
- Create: `desktop/src/pages/Project/Workspace.tsx`
- Create: `desktop/src/components/ProductGraph/`
- Create: `desktop/src/components/ProductIssues/`
- Create: `desktop/src/components/ListingWorkspace/`
- Create: `desktop/src/components/ApprovalCard/`
- Create: `desktop/src/lib/workers.ts`

**Interfaces:**
- Consumes: task detail, product graph summary, artifacts, findings and approvals.
- Produces: a project workspace showing Workflow, Product Graph, Compliance, Listings and Files.

- [ ] Display task plans and Worker progress through the backend event stream.
- [ ] Display canonical Product/SKU facts and their source evidence.
- [ ] Display blocking, confirmation and informational findings separately.
- [ ] Display Shopify and eBay drafts without allowing direct edits that bypass canonical facts.
- [ ] Place Human Approval actions inline in the task workspace.
- [ ] Allow downloading individual artifacts and the final listing package.

### Task 9: Final integration verification and packaging

**Files:**
- Create: `tests/fixtures/womenswear-us/`
- Create: `tests/test_catalog_listing_integration.py`
- Create: `.github/workflows/build.yml`

**Interfaces:**
- Verifies the complete upload-to-export workflow.

- [ ] Add one fixture containing at least two products, multiple sizes/colors, product images, one missing fiber-content value and one conflicting origin value.
- [ ] Run the complete task through Catalog Steward, Compliance Specialist, Listing Operations and Governance Reviewer Agents, followed by deterministic export.
- [ ] Confirm the conflicting origin creates Human Approval and the missing fiber content blocks release until resolved.
- [ ] Confirm Shopify and eBay outputs contain the same SKU, material, origin and size facts.
- [ ] Run `python -m pytest tests/test_catalog_listing_integration.py -q --color=no --tb=short` and require zero failures.
- [ ] Run `npm run type-check` and `npm run build` in `desktop` and require exit code 0.
- [ ] Build the Windows installer locally and configure GitHub Actions to produce macOS arm64 and x64 artifacts.
