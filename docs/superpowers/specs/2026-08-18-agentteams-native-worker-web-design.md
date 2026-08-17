# AgentTeams 原生 Worker 与 Web 工作区设计

## 1. 目标

将跨境商品目录治理项目改造成以 AgentTeams 为协同基础的多智能体系统，并以浏览器 Web 工作区作为第一版操作和调试入口。

本次重构解决的是 Agent 协同运行模型，不是重新实现商品治理领域能力。AgentTeams 负责 Manager、Worker、任务上下文、Skill、共享工作空间和人工介入；现有 Python 领域服务继续负责 Product/SKU、Taxonomy、合规、Listing、Artifact 和数据校验。

第一版不再以 Electron 为产品运行入口，不保留旧 `eigent` Product Event 协议，也不建立新的自定义事件适配层。

## 2. 设计结论

### 2.1 AgentTeams 适合作为协同基础

本项目有四个稳定业务角色、跨步骤资源依赖、人工审批、证据沉淀和独立运行需求，适合使用 AgentTeams 的 Manager/Worker 模型：

```text
Human
  -> Manager
  -> 选择或组合 Worker
  -> 共享任务上下文
  -> Skill / Tool 执行
  -> Artifact 和结果验证
  -> 审批、修订或完成
```

AgentTeams 不接管商品领域规则，也不替代平台侧的 Schema、Taxonomy、证据和发布状态校验。

### 2.2 不采用的做法

以下做法不进入新架构：

- 只修改 `protocol_name`，把自定义事件称为 AgentTeams 协议。
- 在 Python `run_task()` 中临时创建 Planner、Coordinator 和业务 Worker。
- 通过 `CAMEL Task.result` 或 Python 函数返回值传递完整业务数据。
- 通过前端 reducer 根据日志文本推断 Agent、工具、文件和状态。
- 保留 Electron 作为产品运行入口。
- 为了读取历史数据继续维护 `eigent` 与新协议双写、双读。
- 让 Worker 直接修改 SQLite、Artifact 目录或任意本地文件。

## 3. 总体架构

```text
                         浏览器 Web 工作区
                    /          |            \
                   /           |             \
          AgentTeams API   共享任务空间     领域 API
              |             / Artifact       |
              v                |             v
          Controller           |       Crossborder Domain Service
              |                |       (Python / FastAPI)
        +-----+------+         |       Product/SKU/合规/Listing
        |            |         |       Artifact/审批/校验
        v            v         v
     Manager      Workers  <-> Task Context
                       |
              Skills + 受控领域工具
```

### 3.1 AgentTeams 层

AgentTeams 原生组件承担：

- Manager 和 Worker 的持久身份。
- Worker 的模型、Skill、权限和运行时配置。
- Manager 的任务理解、拆解、分配、重试和状态推进。
- Worker 的任务领取、协作消息和共享任务目录。
- 人工在任务进行中的追加要求、审批和中断。
- Worker 工作空间和任务 Artifact 的持久化边界。

AgentTeams 的 Matrix、Controller 和对象存储是协同基础设施。Web 工作区可以使用自研页面展示这些状态，不要求把 Element Web 作为最终业务界面。

### 3.2 跨境领域服务层

Python 服务保留以下能力：

- 解析 Excel、CSV、PDF、图片说明和商品文件。
- 建立 Canonical Product、SKU、Variant 和商品图谱。
- 执行 Taxonomy 映射、Schema 校验和证据跨度校验。
- 执行美国服装法规、Shopify 和 eBay US 规则检查。
- 生成本地化 Listing 草稿和导出包。
- 创建不可变 Artifact、计算 SHA-256、记录版本和依赖。
- 管理审批对象、风险状态和发布就绪状态。

领域服务不负责选择 Worker，也不负责把一个用户目标拆成固定流程。

## 4. Worker 设计

### 4.1 Worker 是 AgentTeams 原生资源

四个业务角色作为持久 Worker 注册，由 AgentTeams Controller 创建和管理：

| Worker | 职责 | 主要 Skills | 主要领域工具 |
|---|---|---|---|
| `catalog-steward-worker` | 建立和维护 Product/SKU 候选事实 | 商品接入、女装分类 | 解析素材、建立规范商品、读取项目资源 |
| `compliance-specialist-worker` | 检查美国市场和渠道合规 | 美国服装合规、Shopify 政策、eBay US 政策 | 执行合规检查、读取商品事实、创建问题清单 |
| `listing-operations-worker` | 生成渠道 Listing 草稿 | 英文 本地化、Shopify Listing、eBay US Listing | 生成草稿、校验字段、创建导出 Artifact |
| `governance-reviewer-worker` | 检查一致性、证据和发布就绪状态 | 目录治理 | 读取全部结果、检查冲突、生成审核结论 |

Worker 的身份、说明、Skill、模型和权限由 AgentTeams 配置持久保存。一次任务只决定是否分配某个 Worker，不重新创建 Worker。

### 4.2 Worker 运行时

第一版统一使用 AgentTeams 支持的 QwenPaw Worker 运行时。选择理由：

- AgentTeams 原生支持。
- Skill 以 Markdown 和脚本资源为核心，与现有项目 Skill 结构一致。
- Python 领域服务可以通过稳定的 HTTP 工具契约暴露，不需要把领域代码复制到 Node Worker。
- 后续可以按角色切换 OpenClaw 或 Hermes，不改变 Worker 的身份和任务上下文契约。

这不表示要把整个项目迁移到 QwenPaw。QwenPaw 只负责 AgentTeams Worker 运行；商品领域服务仍然由 Python/FastAPI 提供。

### 4.3 Worker 与领域服务的连接

Worker 不直接导入 Python 模块，不直接访问 SQLite，也不直接写 Artifact 目录。Worker 通过 Skill 使用受控领域能力：

```text
Worker
  -> Skill 判断当前任务需要的能力
  -> 受控领域工具客户端
  -> FastAPI 领域接口
  -> Schema 校验、业务执行和审计
  -> 返回紧凑结果及 Artifact/Resource ID
```

每个领域工具必须提供：

- 工具名称和用途。
- 输入 JSON Schema。
- 输出 JSON Schema。
- `project_id`、`task_id`、`worker_id` 和幂等键。
- 可读取的 Artifact/Resource 依赖。
- 权限边界和调用失败结构。
- 重试和幂等规则。
- 审计记录。

MCP 不是第一版硬性依赖。领域 API 先使用等价的受控 HTTP 工具契约，后续迁移到 MCP 时只替换连接协议，不改变 Skill、输入输出 Schema 和领域实现。

## 5. Manager 与任务流程

### 5.1 Manager 的职责

Manager 是 AgentTeams 的任务拥有者，负责：

- 接收用户目标。
- 判断是单 Worker 任务、多个 Worker 协作任务，还是只读查询。
- 读取项目资源摘要和现有任务上下文。
- 选择已有 Worker，建立真实依赖。
- 传递 Artifact 和资源引用，不复制完整业务数据。
- 根据 Worker 结果决定继续、重试、修订、审批或结束。
- 向用户说明任务状态、阻塞原因和需要审批的动作。

Manager 不执行商品解析、合规规则或 Listing 字段生成。

### 5.2 任务上下文

每个 AgentTeams 任务使用共享任务空间作为跨 Worker 的持久上下文：

```text
shared/tasks/{task-id}/
├── meta.json
├── plan.md
├── context/
│   ├── input-manifest.json
│   ├── dependency-manifest.json
│   └── decisions.json
├── artifacts/
│   └── ...
└── workers/
    └── {worker-name}/
        ├── result.json
        └── notes.md
```

`result.json` 只保存紧凑结果：

```json
{
  "status": "completed",
  "summary": "已建立 12 个商品候选，发现 3 个待确认字段",
  "key_counts": {
    "products": 12,
    "conflicts": 3
  },
  "output_resource_ids": ["resource_123"],
  "artifact_ids": ["artifact_456"],
  "next_actions": ["等待人工确认材质字段"]
}
```

下游 Worker 通过 `dependency-manifest.json` 和领域 API 按需读取具体内容，不依赖某个上一步 Python 进程是否仍然存在。

### 5.3 动态任务示例

仅整理已有商品事实：

```text
Manager -> catalog-steward-worker
```

执行美国合规审核：

```text
Manager -> compliance-specialist-worker
```

生成完整导出包：

```text
Manager
  -> catalog-steward-worker
  -> compliance-specialist-worker
  -> listing-operations-worker
  -> governance-reviewer-worker
```

是否执行四个 Worker 由 Manager 根据目标和上下文决定，不由平台固定编排。

## 6. 审批、失败和回滚

高风险动作包括：

- 覆盖已确认商品事实。
- 解决字段冲突。
- 将商品标记为发布就绪。
- 导出包含阻塞问题的 Listing 包。
- 未来可能增加的外部发布操作。

出现高风险动作时，Worker 写入审批请求并暂停当前任务。用户审批后，Manager 继续原任务上下文或创建明确标记为修订版本的任务，不复制一份无法关联的普通任务。

所有修订都记录：

- 原任务 ID。
- 审批 ID。
- 被修改的资源版本。
- 修改前后值。
- 执行 Worker。
- 新 Artifact 和校验结果。

领域服务负责校验回滚内容，Manager 负责决定是否触发回滚或重新执行。

## 7. Web 工作区

第一版仅提供浏览器 Web 工作区，React + Vite，不再维护 Electron 主进程、Preload、桌面打包和桌面专用状态。

工作区包含：

1. 项目与任务：项目、当前任务、任务目标和任务计划。
2. Agent 协作：Manager、Worker、当前状态、分配关系和阻塞原因。
3. 共享上下文：计划、依赖、Artifact、结果摘要和版本。
4. 商品图谱：Product、SKU、Variant、冲突和证据。
5. 合规与 Listing：检查结果、草稿和导出包。
6. 审批中心：待审批事项、审批前后差异和恢复状态。

Web 直接读取：

- AgentTeams Controller 的 Manager/Worker/Task 状态。
- 共享任务空间中的计划和 Artifact manifest。
- 跨境领域 API 的商品、合规、Listing、审批数据。

Web 不根据日志文字推断状态，不维护固定四步流程，也不把领域数据转换成另一套 UI 事件协议。第一版可使用轮询；实时更新在明确需要后直接接入 AgentTeams 原生消息或任务状态，不新增自定义事件投影层。

## 8. 数据和技术栈边界

### 保留

- Python、FastAPI、Pydantic。
- SQLite 作为本地开发存储，后续可替换为 PostgreSQL。
- 现有商品图谱、Taxonomy、合规、Listing、Artifact 和审批服务。
- 项目级 Skills 和领域工具 Schema。
- React、TypeScript、Vite 作为 Web 前端。

### 退出主链路

- CAMEL Workforce 作为任务编排器。
- `BusinessAgentWorker`、`CrossborderWorkforceCallback`。
- `ProductEventStore` 和旧 `eigent` 事件协议。
- Electron 运行时和桌面打包配置。
- 前端根据事件 reducer 还原 Agent 状态的逻辑。

### 新增

- AgentTeams Controller 配置和 Worker 资源。
- AgentTeams Manager 与 QwenPaw Worker 运行配置。
- 共享任务空间和 Artifact manifest 契约。
- 领域工具 HTTP 契约及按 Worker 身份鉴权。
- React/Vite Web 工作区。

## 9. 验证标准

第一版必须通过一个真实商品目录场景验证：

1. 浏览器创建项目并上传女性服装素材。
2. Manager 根据目标只选择必要 Worker。
3. Catalog Worker 写入规范商品和 Artifact。
4. Compliance Worker 读取上游 Artifact，生成合规结果。
5. Listing Worker 只在存在合规输入时生成渠道草稿。
6. Governance Worker 可以单独运行，也可以作为完整任务的最后一步运行。
7. 任一 Worker 失败后，Manager 能显示失败原因并重新执行该 Worker。
8. 高风险冲突进入审批，审批后原任务上下文可恢复。
9. Web 能显示每个 Worker 的真实状态、结果、Artifact 和审批，不依赖日志猜测。
10. 任务重启后仍可从共享任务空间恢复，不依赖原 Python 进程内存。

## 10. 迁移策略

迁移按以下顺序进行：

1. 定义 AgentTeams Worker、Task Context、Artifact manifest 和领域工具契约。
2. 将四个业务角色注册为 AgentTeams Worker，先完成单 Worker 独立运行。
3. 接入 Manager 动态拆解和真实依赖。
4. 将领域服务改为可被 Worker 调用的受控接口。
5. 建立共享任务空间读写和恢复机制。
6. 建立 Web 工作区，直接读取 AgentTeams 和领域状态。
7. 移除 CAMEL Workforce、Electron、ProductEventStore 及旧桌面状态代码。
8. 进行最终集成场景验证和运行证据留存。

