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

The Workforce can dynamically select one or more of four durable roles for each objective:

1. `catalog_steward_agent` owns canonical Product/SKU facts and classification candidates.
2. `compliance_specialist_agent` checks US apparel law and marketplace policy without changing product facts.
3. `listing_operations_agent` localizes verified facts and creates Shopify/eBay drafts.
4. `governance_reviewer_agent` checks blockers, evidence, versions, channel consistency, and export readiness.

Planner, Human Approval, Artifact/Event persistence, schema validation, graph writes, CSV/JSON/XLSX formatting, hashing, and ZIP creation are platform capabilities. Platform and market variations are loaded as Agent Skills from `skills/` rather than being implemented as extra Agents.

CAMEL Workforce receives a compact manifest of project-owned resources, decomposes the objective into the minimum necessary task graph, and assigns each task by role capability. A review-only objective can run only `governance_reviewer_agent`; a full delivery objective can run Catalog first, Compliance and Listing in parallel, and Governance after their outputs are available. Complete business payloads never pass through CAMEL result strings.

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

The desktop starts `python -m crossborder_cowork.app` automatically. Electron assigns an isolated loopback API port for this application instance, validates the backend identity and Product Event protocol, then opens the Vite UI on `http://127.0.0.1:7777`. This avoids connecting to an older process that happens to occupy port 8000.

The desktop workspace follows the same native workspace pattern as the reference cowork application: projects and tasks live in the history rail, the task workspace receives a versioned Eigent product-event stream, and Product/SKU, compliance, Listing, approval, and Artifact panels read project-owned backend resources. The UI does not parse log text, synthesize tool calls, or maintain a second business state source.

To run only the backend:

```powershell
python -m crossborder_cowork.app
```

## Model configuration

Task execution requires a configured OpenAI-compatible model because native CAMEL Workforce uses it to decompose the objective, select the necessary Agent roles, and establish dependencies. Business Tools remain deterministic, and model output cannot bypass taxonomy, graph, evidence, authorization, or release-state validation.

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

Set `CROSSBORDER_DISABLE_LLM=1` only when inspecting data or running platform-only diagnostics; Workforce tasks will reject execution while model access is disabled. API responses never return the configured API key.

## Workflow

```text
Create project (no task is created automatically)
→ upload project materials or explicitly import the sample catalog
→ enter an objective and optionally select materials or existing resources
→ CAMEL Workforce reads the compact project resource manifest
→ dynamically create and assign only the necessary 1..N Agent tasks
→ Agents read Product/Fact/Listing/Artifact data on demand through authorized Tools
→ platform schema/taxonomy/evidence validation remains authoritative
→ Human Approval persists conflicts or missing facts and creates a new resource version
→ Agent outputs become project resources and independently addressable Artifacts
→ Governance creates listing_package.zip only when the requested delivery is ready
```

## 使用方法

1. 点击左侧项目区的 `+`，输入项目名称。项目创建后会直接进入项目首页，不会自动创建任务。
2. 在“项目素材库”上传供应商的 CSV、Excel、JSON、PDF、Markdown、文本或图片资料。素材属于项目，可被多个任务复用。
3. 没有真实资料时，可点击“导入示例数据”。该操作只在用户点击后执行，不会向新项目自动注入示例。示例源文件位于 `examples/womenswear-us/womenswear-catalog.csv`。
4. 首次构建商品目录时勾选素材并输入目标；后续合规检查、Listing 生成或审核任务可以不选新素材，直接复用当前项目的 active 资源。
5. 任务工作区左侧查看 Workforce 动态生成的任务计划、逐条工作摘要和真实工具状态；未参与本次任务的智能体会明确显示“尚未执行”。底部可切换各智能体和文件工作区。
6. 如果任务要求人工确认，在审批卡片中处理冲突或补齐必要事实。审核通过后，在文件区下载 Shopify CSV、eBay JSON 和最终 `listing_package.zip`。

项目素材与任务生成文件是两类数据：素材是项目级、可复用的输入；Artifact 是任务级、不可变的输出。选择素材创建任务时，平台会保存材料绑定并校验文件哈希，任务不会依赖临时浏览器附件。

## Final verification

Run only after the complete feature set is implemented:

```powershell
python -m pytest -q --color=no --tb=short
cd desktop
npm run type-check
npm run build
```

The integration fixture contains two products, eight SKUs, conflicting country-of-origin evidence, and missing fiber content. The test confirms both Human Approval paths and verifies that Shopify and eBay outputs preserve the same SKU, size, material, and origin facts.

Production-realistic acceptance uses a pinned CC0-1.0 public dress image plus a generated supplier XLSX, searchable PDF, JSON metadata, and image source file:

```powershell
python -m pytest tests/test_catalog_listing_integration.py tests/test_production_scenario_acceptance.py -q --color=no --tb=short
```

This acceptance covers dirty field formats, multi-file fact merging, approval reruns, channel import constraints, Artifact hashes, and listing-package integrity. It is not a substitute for importing the generated files into a real Shopify development store and an eBay Sandbox account.

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

The packaging scripts build a native one-file Python backend, include taxonomies, project Skills, migrations, and the opt-in example catalog, then package Electron. Installed applications store SQLite data, model settings, project materials, and Artifacts under Electron's per-user application data directory. GitHub Actions builds Windows, macOS arm64, and macOS x64 packages.

## Runtime data

In source development, runtime data is stored under `runtime/`. In an installed application it is stored under Electron `userData`:

- `data/crossborder.sqlite3`: projects, tasks, graph, listings, approvals, events, and Artifact metadata.
- `artifacts/<task-id>/`: reports, channel files, SKU matrix, and listing package.
- `project-materials/<project-id>/<material-id>/`: reusable project source files copied from uploads or the explicit example import.
- `settings.json`: desktop model configuration metadata.

Canonical Product is the only authoritative product fact source. Channel drafts are read-only projections and cannot directly overwrite canonical facts.
