# Production Scenario Acceptance Implementation Plan

> **For agentic workers:** Execute this plan task-by-task in the current session. Do not use TDD or create per-component test suites. Complete all implementation work, then run the final integration verification in Task 5.

**Goal:** Add a repeatable production-realistic multi-file acceptance workflow and fix the ingestion, channel validation, artifact, and packaging issues it exposes.

**Architecture:** Generate a deterministic supplier-style fixture at integration-test runtime, pass it through the existing four-role workflow, and validate both structured drafts and serialized artifacts. Keep normalization and marketplace import checks in deterministic platform code; Human Approval remains the only way to resolve conflicting or missing authoritative facts.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, OpenPyXL, pypdf, ReportLab for fixture generation, Electron, React, TypeScript, PyInstaller.

## Global Constraints

- First release supports womenswear, the United States, Shopify, and eBay US only.
- First release exports files and never performs automatic platform publishing.
- Canonical Product remains the only authoritative product fact source.
- Do not send complete workbooks or source documents to the LLM.
- Taxonomy, evidence, graph, import-schema, and release-state validation remain deterministic platform code.
- Do not add per-feature unit tests or TDD; run only the final integrated acceptance commands.

---

### Task 1: Build the production-realistic fixture factory

**Files:**
- Create: `tests/fixtures/womenswear-us-realistic/build_fixture.py`
- Create: `tests/fixtures/womenswear-us-realistic/cc0-dress.jpg`
- Create: `tests/fixtures/womenswear-us-realistic/SOURCE.md`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `build_fixture(target: Path) -> list[Path]` returning an XLSX, PDF, JSON, and PNG input bundle.

- [ ] Pin a CC0-1.0 dress image to an immutable Clothing Dataset Small commit with URL and SHA-256 provenance.
- [ ] Generate two womenswear products and at least ten enriched variant rows in a multi-sheet XLSX using Chinese and English field aliases.
- [ ] Include full-width values, currency symbols, inventory units, blank optional cells, images, claims, and certifications.
- [ ] Generate a searchable PDF with product-level facts and a deliberate origin conflict.
- [ ] Generate JSON product-level media/certification facts and a valid PNG source file.
- [ ] Add ReportLab only to the development dependency group used by final integration verification.

### Task 2: Harden multi-file product ingestion

**Files:**
- Modify: `src/crossborder_cowork/intake/parsers.py`
- Modify: `src/crossborder_cowork/intake/service.py`

**Interfaces:**
- Produces: normalized field keys and values, stable conflict comparison, normalized price/inventory, and SKU creation only from variant-bearing records.

- [ ] Apply Unicode NFKC normalization to headers and string cells.
- [ ] Normalize country aliases and stable fiber-content comparison before conflict creation.
- [ ] Normalize price strings and non-negative inventory values.
- [ ] Prevent PDF/JSON product supplement records from creating phantom SKUs.
- [ ] Generate a single fallback SKU only when a product has no variant-bearing records.
- [ ] Preserve every normalized fact's original source location and evidence text.

### Task 3: Add deterministic channel import validation

**Files:**
- Create: `src/crossborder_cowork/governance/import_validation.py`
- Modify: `src/crossborder_cowork/governance/consistency.py`
- Modify: `src/crossborder_cowork/workers/governance_reviewer.py`

**Interfaces:**
- Produces: `validate_shopify_draft(draft) -> list[ChannelValidationIssue]` and `validate_ebay_draft(draft) -> list[ChannelValidationIssue]`.

- [ ] Validate required identifiers, draft state, SKU uniqueness, sizes, colors, prices, inventory/quantity, eBay title length, marketplace and category.
- [ ] Convert validation issues into blocking Governance Findings tied to the affected Product and platform.
- [ ] Prevent package creation when serialized channel data would fail deterministic import checks.
- [ ] Keep publishing credentials and API calls out of the validator.

### Task 4: Add package integrity verification and production acceptance

**Files:**
- Create: `src/crossborder_cowork/export/verification.py`
- Create: `tests/test_production_scenario_acceptance.py`
- Modify: `README.md`

**Interfaces:**
- Produces: `verify_listing_package(path: Path) -> dict` with member count and verified manifest details.

- [ ] Run the full fixture through Catalog Steward, compliance, listing, governance and both Human Approval paths.
- [ ] Assert exactly two Products and the expected real SKU sets without phantom SKUs.
- [ ] Verify source Artifact hashes and Source Manifest coverage for all four input files.
- [ ] Verify Human Approval evidence, graph versions, channel facts and deterministic import validation.
- [ ] Verify every ZIP member hash and size against the manifest and scan exported text for credential/publishing fields.
- [ ] Document the production acceptance command and its honest boundary from a real marketplace test-store import.

### Task 5: Final integration verification, packaging, and commit

**Files:**
- Create: `scripts/smoke_packaged_backend.ps1`
- Modify: `.github/workflows/build.yml`

**Interfaces:**
- Verifies the source workflow and installed backend resources.

- [ ] Run `python -m pytest tests/test_catalog_listing_integration.py tests/test_production_scenario_acceptance.py -q --color=no --tb=short` and require zero failures.
- [ ] Run `npm run type-check` and `npm run build` in `desktop` and require exit code 0.
- [ ] Build the PyInstaller backend and Windows NSIS/ZIP package.
- [ ] Run the packaged backend smoke script and require health, 4 Taxonomies, 9 Skills, and configured model-role readiness when environment variables are present.
- [ ] Add the production acceptance test to GitHub Actions before desktop packaging.
- [ ] Run secret and diff checks, commit the completed acceptance implementation, and retain generated packages only in ignored directories.
