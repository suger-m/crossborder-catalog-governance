# 跨境商品目录协同工作台

这是一个面向美国市场、Shopify 和 eBay 美国站的跨境女装商品目录治理桌面应用。它把供应商资料整理为可追溯的商品与库存单位信息，分别执行美国法规和平台政策检查，生成本地化渠道草稿，完成跨渠道一致性审核，并导出可审计的上架资料包。

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
- 在桌面工作台展示任务、智能体进度、商品关系图、问题、渠道草稿、审批、模型设置及全部文件凭证。

## 业务智能体

Workforce（基于 AgentTeams 的协同执行引擎）会根据目标动态选择一个或多个持久业务角色，不要求每次都执行完整流程：

1. `catalog_steward_agent`：维护规范商品和 SKU 事实，提出分类候选。
2. `compliance_specialist_agent`：检查美国服装法规和平台政策，不修改商品事实。
3. `listing_operations_agent`：将已核验事实本地化，并生成 Shopify、eBay 草稿。
4. `governance_reviewer_agent`：检查阻塞项、证据、版本、渠道一致性和导出就绪状态。

规划、人工审批、文件凭证与事件持久化、模式校验、关系图写入、CSV/JSON/XLSX 格式化、哈希计算和 ZIP 打包都是平台能力，不单独创建业务智能体。平台或市场差异通过 `skills/` 下的按需技能包提供，而不是继续增加智能体数量。

每个业务角色都是真正的 CAMEL `ChatAgent`，由 `SingleAgentWorker` 承载。Workforce 先读取项目资源清单，拆分为最少必要的任务并按角色能力分配；智能体只发现和加载自己可见的技能包，按需读取项目上下文，再选择受授权的确定性领域工具。只做审核的目标可以只运行审核智能体，完整交付目标才会按依赖关系运行目录、合规、渠道草稿和治理审核。

业务智能体不提供终端、通用搜索、浏览器、MCP、任意文件系统、脚本执行或平台发布能力。技能包参考资料通过受限的文本读取工具访问；所有会改变状态的操作都必须经过项目或领域工具，并由平台完成模式、分类、证据、授权和发布状态校验。

## 开发环境

需要：

- Python 3.11 或更高版本
- Node.js 20 或更高版本
- npm

首次安装：

```powershell
python -m pip install -e ".[dev]"
cd desktop
npm install
```

启动后端和桌面端：

```powershell
cd desktop
npm run dev
```

桌面端会自动启动 `python -m crossborder_cowork.app`。Electron 会为当前应用实例分配独立的本机回环端口，并校验后端身份和商品事件协议，然后打开前端页面。这样不会误连接到占用固定端口的旧进程。

只启动后端：

```powershell
python -m crossborder_cowork.app
```

## 模型配置

执行任务需要配置兼容 OpenAI 接口的模型。CAMEL Workforce 使用模型拆分目标、选择智能体并建立依赖；领域工具仍由平台确定性执行，模型输出不能绕过分类、关系图、证据、授权和发布状态校验。

桌面端设置优先于环境变量。环境变量的回退顺序为：

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

只有在查看数据或执行平台诊断时才设置 `CROSSBORDER_DISABLE_LLM=1`。此时 Workforce 任务会拒绝执行。接口不会返回已保存的密钥。

## 使用流程

```text
创建项目（不会自动创建任务）
→ 上传项目素材，或由用户明确导入示例目录
→ 输入目标，可选定素材或复用项目已有资源
→ Workforce 读取项目资源清单
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
5. 在任务工作区左侧查看 Workforce 动态生成的任务计划、逐条工作摘要和实际工具状态。未参与本次任务的智能体会显示“尚未执行”。底部可切换智能体和文件工作区。
6. 如果任务需要人工确认，在审批卡片中处理冲突或补齐必要事实。审核通过后，可在文件区下载 Shopify 表格、eBay 数据文件和最终 `listing_package.zip`。

项目素材与任务生成文件是两类数据：素材是项目级、可复用的输入；文件凭证是任务级、不可变的输出。选择素材创建任务时，平台会保存素材绑定并校验文件哈希，任务不会依赖临时浏览器附件。

## 集成验证

完整功能实现后再执行：

```powershell
python -m pytest -q --color=no --tb=short
cd desktop
npm run type-check
npm run build
```

集成场景覆盖动态项目资源、商品事件投影、技能包激活、规范目录生成、美国合规、单平台和双平台草稿、独立治理审核、文件预览、资料包完整性和项目隔离。不包含 Shopify 或 eBay 自动发布，也不能替代将生成草稿手动导入平台测试环境。

## 打包

在 Windows 上打包：

```powershell
cd desktop
npm run package:win
```

在对应的 macOS 构建环境上打包苹果芯片或英特尔芯片版本：

```bash
cd desktop
npm run package:mac-arm64
npm run package:mac-x64
```

打包脚本会构建独立的 Python 后端，包含分类体系、项目技能包、数据库迁移和可选示例目录，再交由 Electron 打包。GitHub Actions 可以构建 Windows、macOS arm64 和 macOS x64 安装包。

## 运行数据位置

源码开发时，运行数据位于 `runtime/`。安装后的应用使用 Electron 的用户数据目录：

- `data/crossborder.sqlite3`：项目、任务、关系图、渠道草稿、审批、事件和文件凭证元数据。
- `artifacts/<task-id>/`：报告、渠道文件、SKU 矩阵和上架资料包。
- `project-materials/<project-id>/<material-id>/`：从上传或明确导入的示例目录复制的项目素材。
- `settings.json`：桌面端模型配置元数据。

规范商品事实是唯一权威来源。渠道草稿只是只读投影，不能直接覆盖规范商品事实。
