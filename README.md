# Cross-border Catalog Cowork

Cross-border Catalog Cowork is a multi-agent desktop workspace for governing womenswear catalogs for the United States, Shopify, and eBay US. It turns source product files into a traceable Canonical Product/SKU graph, separates US legal compliance from marketplace policy checks, creates localized channel drafts, reviews cross-platform consistency, and exports an auditable listing package.

The first release creates Shopify and eBay US import packages. It does not call marketplace APIs or publish products automatically.

## Capabilities

- Import CSV, Excel, JSON, PDF, Markdown, text, and image metadata.
- Preserve every source as a SHA-256 Artifact and attach facts to source locations and excerpts.
- Build stable Product, SKU, Category, Material, Claim, Certification, Market, Platform, Listing, and SourceDocument graph records.
- Validate assignments against versioned womenswear, US compliance, Shopify, and eBay US taxonomies.
- Detect missing or conflicting fiber content, origin, care, manufacturer, size, claims, and platform attributes.
- Resolve conflicts and missing required facts through inline Human Approval.
- Generate en-US Shopify CSV and eBay US JSON drafts without fabricating missing data.
- Verify SKU, size, material, origin, version, and evidence consistency across channels.
- Export canonical JSON, SKU matrix, reports, Listing files, review decision, hashes, and manifest as `listing_package.zip`.
- Display tasks, Worker progress, Product Graph, issues, Listings, approvals, model settings, and every Artifact in the Electron workspace.

## Business Agents

The Workforce contains four durable roles:

1. `catalog_steward_agent` owns canonical Product/SKU facts and classification candidates.
2. `compliance_specialist_agent` checks US apparel law and marketplace policy without changing product facts.
3. `listing_operations_agent` localizes verified facts and creates Shopify/eBay drafts.
4. `governance_reviewer_agent` checks blockers, evidence, versions, channel consistency, and export readiness.

Planner, Human Approval, Artifact/Event persistence, schema validation, graph writes, CSV/JSON/XLSX formatting, hashing, and ZIP creation are platform capabilities. Platform and market variations are loaded as Agent Skills from `skills/` rather than being implemented as extra Agents.

## Development setup

Requirements:

- Python 3.11+
- Node.js 20+
- npm

Install once:

```powershell
python -m pip install -e ".[dev]"
cd desktop
npm install
```

After installation, one command starts both the FastAPI backend and Electron/Vite desktop:

```powershell
cd desktop
npm run dev
```

The desktop starts `python -m crossborder_cowork.app` automatically. The API listens on `http://127.0.0.1:8000`, and the Vite UI uses `http://127.0.0.1:7777`.

To run only the backend:

```powershell
python -m crossborder_cowork.app
```

## Model configuration

The system works deterministically without a model. When an OpenAI-compatible model is configured, business Agents may use it for constrained language work such as en-US localization; deterministic validation remains authoritative and failures fall back safely.

Desktop settings take precedence over environment variables. Environment fallback order matches the existing cowork project:

```text
COWORK_PLANNER_* / COWORK_WORKER_* / COWORK_REVIEWER_*
→ COWORK_LLM_*
→ LLM_*
→ OPENAI_API_KEY for the key only
```

Common variables:

```dotenv
LLM_MODEL_PLATFORM=openai
LLM_MODEL=your-model
LLM_API_KEY=your-key
LLM_BASE_URL=https://api.example.com/v1
LLM_TEMPERATURE=0.1
```

Set `CROSSBORDER_DISABLE_LLM=1` to force deterministic execution. API responses never return the configured API key.

## Workflow

```text
Source product files
→ Catalog Steward: parse, normalize, classify, detect conflicts
→ platform schema/taxonomy/evidence validation
→ Human Approval for conflicts or missing required facts
→ Canonical Product/SKU Graph
→ Compliance Specialist: US law + Shopify/eBay policy checks
→ Listing Operations: en-US Shopify/eBay drafts
→ Governance Reviewer: consistency, versions, blockers, release readiness
→ deterministic listing_package.zip export
```

## Final verification

Run only after the complete feature set is implemented:

```powershell
python -m pytest tests/test_catalog_listing_integration.py -q --color=no --tb=short
cd desktop
npm run type-check
npm run build
```

The integration fixture contains two products, eight SKUs, conflicting country-of-origin evidence, and missing fiber content. The test confirms both Human Approval paths and verifies that Shopify and eBay outputs preserve the same SKU, size, material, and origin facts.

## Packaging

Windows, from Windows:

```powershell
cd desktop
npm run package:win
```

macOS Apple Silicon or Intel, from the corresponding macOS runner:

```bash
cd desktop
npm run package:mac-arm64
npm run package:mac-x64
```

The packaging scripts build a native one-file Python backend, include taxonomies, project Skills, and migrations, then package Electron. Installed applications store SQLite data, model settings, uploads, and Artifacts under Electron's per-user application data directory. GitHub Actions builds Windows, macOS arm64, and macOS x64 packages.

## Runtime data

In source development, runtime data is stored under `runtime/`. In an installed application it is stored under Electron `userData`:

- `data/crossborder.sqlite3`: projects, tasks, graph, listings, approvals, events, and Artifact metadata.
- `artifacts/<task-id>/`: reports, channel files, SKU matrix, and listing package.
- `uploads/<task-id>/`: task source files.
- `settings.json`: desktop model configuration metadata.

Canonical Product is the only authoritative product fact source. Channel drafts are read-only projections and cannot directly overwrite canonical facts.
