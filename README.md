# 跨境商品目录协同工作台

这是一个面向美国市场、Shopify 和 eBay 美国站的跨境女装商品目录治理 Web 工作台。它把供应商资料整理为可追溯的商品与库存单位信息，分别执行美国法规和平台政策检查，生成本地化渠道草稿，完成跨渠道一致性审核，并导出可审计的上架资料包。

第一版只生成 Shopify 和 eBay 美国站的导入文件，不调用平台发布接口，也不会自动发布商品。

## 主要能力

- 导入 CSV、Excel、JSON、PDF、Markdown、文本和图片资料。
- 为每份原始资料保存 SHA-256 文件凭证，并把商品事实关联到来源位置和原文片段。
- 建立稳定的商品、库存单位、分类、材质、声明、认证、市场、平台、渠道草稿和来源文档关系图。
- 按版本化的女装分类、美国合规、Shopify 和 eBay 美国站分类体系校验映射。
- 发现纤维成分、原产地、洗护、制造商、尺码、宣传声明及平台属性的缺失或冲突。
- 通过人工审批处理冲突和必填事实缺失，并保留版本记录。
- 基于已核验事实生成美式英语 Shopify 表格草稿和 eBay 美国站 JSON 草稿，不编造缺失信息。
- 检查 SKU、尺码、材质、原产地、版本和证据在不同渠道之间的一致性。
- 将规范化 JSON、SKU 矩阵、报告、渠道文件、审核决定、哈希和清单导出为 `listing_package.zip`。
- 在 Web 工作台展示任务、智能体进度、商品关系图、问题、渠道草稿、审批、模型设置及全部文件凭证。

## 业务智能体

AgentTeams 协作层会根据目标动态选择一个或多个持久业务角色，不要求每次都执行完整流程：

1. `catalog_steward_agent`：维护规范商品和 SKU 事实，提出分类候选。
2. `compliance_specialist_agent`：检查美国服装法规和平台政策，不修改商品事实。
3. `listing_operations_agent`：将已核验事实本地化，并生成 Shopify、eBay 草稿。
4. `governance_reviewer_agent`：检查阻塞项、证据、版本、渠道一致性和导出就绪状态。

规划、人工审批、文件凭证与事件持久化、模式校验、关系图写入、CSV/JSON/XLSX 格式化、哈希计算和 ZIP 打包都是平台能力，不单独创建业务智能体。平台或市场差异通过 `skills/` 下的按需技能包提供，而不是继续增加智能体数量。

每个业务角色都是持久化的 AgentTeams Worker，按需读取项目资源清单并分配最少必要的任务；智能体只发现和加载自己可见的技能包，按需读取项目上下文，再选择受授权的确定性领域工具。只做审核的目标可以只运行审核智能体，完整交付目标才会按依赖关系运行目录、合规、渠道草稿和治理审核。

业务智能体不提供终端、通用搜索、浏览器、MCP、任意文件系统、脚本执行或平台发布能力。技能包参考资料通过受限的文本读取工具访问；所有会改变状态的操作都必须经过项目或领域工具，并由平台完成模式、分类、证据、授权和发布状态校验。

## 开发环境

需要：

- Python 3.11 或更高版本
- Node.js 20 或更高版本
- npm 10 或更高版本

首次安装：

```powershell
python -m pip install -e ".[dev]"
cd web
npm install
```

终端一启动 AgentTeams 服务：

```powershell
# 首次使用或 AgentTeams 尚未运行时，先启动官方 AgentTeams 服务。
# 该脚本调用 D:\vibe\AgentTeams 的官方安装器，并通过官方 agt 接口声明 Worker。
.\scripts\start_agentteams.ps1

# 在同一终端启动本项目 Web 后端（后端会自动读取官方 env 文件）
$env:PYTHONPATH = "src"
python -m crossborder_cowork.app
```

AgentTeams 由官方安装器和 Docker Desktop 提供；本项目只做服务探活、请求提交和结果投影，不会在 FastAPI 进程内启动或模拟 Manager/Worker。嵌入式 AgentTeams 默认只把 Matrix 网关映射到宿主机，启动脚本会额外创建两个只做 TCP 转发的本地端口，让后端读取 AgentTeams 官方接口：

```text
Matrix 网关：       http://127.0.0.1:18080
Controller API：    http://127.0.0.1:18090  -> Controller:8090
共享对象存储：      http://127.0.0.1:19000  -> Controller:9000
```

这两个转发器不保存项目、任务或 Worker 状态；任务状态仍由 AgentTeams Controller、Matrix 和 TeamHarness 共享存储负责。可用以下接口确认它已经就绪：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/agentteams/health
```

终端二启动 Web 工作台：

```powershell
cd web
npm run dev
```

浏览器打开 `http://127.0.0.1:7777`。Web 只读取后端的项目、任务、事件、资源、审批和文件状态，不维护第二套任务状态。

本项目不会复制或内置 AgentTeams Controller、Manager、Matrix、Worker runtime 或 TeamHarness。`start_agentteams.ps1` 只调用 `D:\vibe\AgentTeams\install\agentteams-install.ps1`，再通过官方 `agt apply` 创建或更新跨境 Worker。跨境后端通过 AgentTeams 的 Matrix Manager 入口提交请求，再根据 Controller 可用的工作流接口或 TeamHarness 在官方共享存储中写入的 `meta.json`/交付物恢复本地任务投影。AgentTeams 的默认资源要求为至少 2 核 4 GB 内存，Windows 需要 Docker Desktop 正常运行。

如果模型变量使用本项目的命名，启动脚本会映射：`LLM_API_KEY` → `AGENTTEAMS_LLM_API_KEY`、`LLM_BASE_URL` → `AGENTTEAMS_OPENAI_BASE_URL`、`LLM_MODEL` → `AGENTTEAMS_DEFAULT_MODEL`。官方安装器生成的 `%USERPROFILE%\\agentteams-manager.env` 会被后端自动读取，不需要手工复制管理员密码。`provision_agentteams.ps1` 会通过官方 `agt apply` 声明式创建四个业务 Worker，并把本项目的 Skill 包复制到 Manager 工作区；Worker 通过角色限定的 `/mcp/{role}` 平台入口调用确定性业务工具。跨境后端连接地址可通过 `AGENTTEAMS_MATRIX_URL`、`AGENTTEAMS_CONTROLLER_PUBLIC_URL`、`AGENTTEAMS_FS_PUBLIC_URL`、`AGENTTEAMS_ADMIN_USER`、`AGENTTEAMS_ADMIN_PASSWORD` 和 `AGENTTEAMS_MATRIX_DOMAIN` 配置。`start_agentteams.ps1` 会在本地部署中自动设置 Controller 与共享存储的公开转发地址；如果你使用外部 AgentTeams 部署，则需要自行提供这些地址。

验证整条本地依赖链：

```powershell
.\scripts\verify_agentteams.ps1
```

验证脚本会同时检查 FastAPI、Matrix 版本接口、Controller Worker 列表和 AgentTeams 就绪状态；如果 Controller 尚未暴露或共享服务未就绪，会明确返回失败原因。

只启动后端：

```powershell
python -m crossborder_cowork.app
```

## 模型配置

执行任务需要配置兼容 OpenAI 接口的模型。AgentTeams 任务规划会使用模型辅助理解目标并选择智能体；领域工具仍由平台确定性执行，模型输出不能绕过分类、关系图、证据、授权和发布状态校验。

Web 设置页保存的模型配置优先于环境变量。环境变量的回退顺序为：

```text
COWORK_PLANNER_* / COWORK_WORKER_* / COWORK_REVIEWER_*
→ COWORK_LLM_*
→ LLM_*
→ 仅密钥字段使用 OPENAI_API_KEY
```

常用配置：

```dotenv
LLM_MODEL_PLATFORM=openai
LLM_MODEL=your-model
LLM_API_KEY=your-key
LLM_BASE_URL=https://api.example.com/v1
LLM_TEMPERATURE=0.1
```

只有在查看数据或执行平台诊断时才设置 `CROSSBORDER_DISABLE_LLM=1`。此时需要模型能力的 AgentTeams 任务会拒绝执行。接口不会返回已保存的密钥。

## 使用流程

```text
创建项目（不会自动创建任务）
→ 上传项目素材，或由用户明确导入示例目录
→ 输入目标，可选定素材或复用项目已有资源
→ AgentTeams 读取项目资源清单
→ 仅创建并分配当前目标需要的一个或多个智能体任务
→ 智能体发现并加载可见技能包
→ 智能体按需读取商品、渠道草稿、审批和文件凭证上下文
→ 智能体选择角色对应的确定性工具，写入持久项目资源
→ 平台完成模式、分类、证据和授权校验
→ 人工审批处理冲突或缺失事实，并生成新的资源版本
→ 智能体输出成为项目资源和可独立访问的文件凭证
→ 只有达到交付条件时，治理审核才生成 listing_package.zip
```

## 操作说明

1. 点击左侧项目区的“+”，输入项目名称。创建后直接进入项目首页，不会自动创建任务。
2. 在“项目素材库”上传供应商的 CSV、Excel、JSON、PDF、Markdown、文本或图片资料。素材属于项目，可被多个任务复用。
3. 没有真实资料时，点击“导入示例数据”。该操作只在用户主动点击后执行；示例文件为 `examples/womenswear-us/womenswear-catalog.csv`。
4. 首次构建商品目录时选择素材并输入目标；后续合规检查、渠道草稿生成或治理审核可以直接复用项目当前有效资源。
5. 在任务工作区左侧查看 AgentTeams 动态生成的任务计划、逐条工作摘要和实际工具状态。未参与本次任务的智能体会显示“尚未执行”。底部可切换智能体和文件工作区。
6. 如果任务需要人工确认，在审批卡片中处理冲突或补齐必要事实。审核通过后，可在文件区下载 Shopify 表格、eBay 数据文件和最终 `listing_package.zip`。

项目素材与任务生成文件是两类数据：素材是项目级、可复用的输入；文件凭证是任务级、不可变的输出。选择素材创建任务时，平台会保存素材绑定并校验文件哈希，任务不会依赖临时浏览器附件。

## 集成验证

完整功能实现后再执行：

```powershell
python -m pytest -q --color=no --tb=short
npm run type-check --prefix web
npm run build --prefix web
```

集成场景覆盖动态项目资源、商品事件投影、技能包激活、规范目录生成、美国合规、单平台和双平台草稿、独立治理审核、文件预览、资料包完整性和项目隔离。不包含 Shopify 或 eBay 自动发布，也不能替代将生成草稿手动导入平台测试环境。

## 打包

第一版提供本地 Python 服务和浏览器 Web 工作台，不包含 Electron 安装包。AgentTeams 使用其官方本地 Docker 部署；本项目不再维护另一套 Compose、Controller 或 Worker runtime。Kubernetes 仍由 AgentTeams 官方部署方式负责，本项目不新增 K8s 资源。

## 运行边界

- Web 是第一版唯一界面；Electron 目录和 Electron 打包链不再参与运行。
- AgentTeams Manager 自己决定是否拆分目标、调用哪些 Worker 以及是否只运行单个审核角色；FastAPI 不维护本地 Worker 队列，也不把固定四阶段当作执行器。
- FastAPI 的本地 SQLite、Artifact 元数据和 Web 展示是业务域的持久投影；AgentTeams 的 Controller、Matrix、TeamHarness 共享目录和 Worker 结果是协作运行时的权威来源。
- 本项目只读取 AgentTeams 共享对象来恢复阶段报告和交付物，不把外部对象伪装成尚未下载的本地文件；下载后的文件才会进入本地 Artifact 预览。

## 运行数据位置

运行数据位于 `runtime/`：

- `data/crossborder.sqlite3`：项目、任务、关系图、渠道草稿、审批、事件和文件凭证元数据。
- `artifacts/<task-id>/`：报告、渠道文件、SKU 矩阵和上架资料包。
- `project-materials/<project-id>/<material-id>/`：从上传或明确导入的示例目录复制的项目素材。
- `settings.json`：Web 设置页保存的模型配置元数据。

规范商品事实是唯一权威来源。渠道草稿只是只读投影，不能直接覆盖规范商品事实。
