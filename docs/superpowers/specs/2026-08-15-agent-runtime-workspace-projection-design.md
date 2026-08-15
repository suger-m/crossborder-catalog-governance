# Agent 运行过程与工作区投影设计

## 1. 背景与目标

当前桌面端存在三个相互关联的问题：

1. Agent 卡片没有真实工具调用记录，只能显示静态工具名称或空区域。
2. 子任务的完整结构化结果被序列化为 Markdown，导致“完成报告”区域出现大段 JSON。
3. 右下角 Agent 工作区读取顶层任务结果，而不是所属步骤的数据和产物，点击后经常显示 `0`、`无` 或空白内容。

这些问题来自同一个架构缺口：Worker 的实际业务操作没有经过统一 Tool 边界，后端 Product Event 也没有形成工具、工作摘要、步骤结果和 Artifact 的完整投影。

本次改造目标是让后端 Product Event 成为唯一 UI 状态源。桌面端不伪造工具调用，不从静态工具列表猜测运行状态，也不再把机器结果当作正式报告。

## 2. 用户体验

Agent 子任务卡片主要展示逐条出现的公开工作摘要，例如：

```text
正在读取供应商商品资料并识别 Product/SKU 层级。
发现两个原产地值存在冲突，保留两份来源证据并请求确认。
其余商品事实已通过 taxonomy 校验，开始写入规范商品图谱。
```

工作摘要是面向用户的过程说明和决策依据，不是模型隐藏推理。摘要不得包含内部思维链、原始提示词、完整工具参数、完整工具返回或异常堆栈。

工具区域只展示真实发生的确定性业务操作及其状态：

```text
工具
✓ 解析商品素材
✓ 校验商品分类
✓ 写入商品图谱
```

工具区域不显示耗时、参数或返回结果。需要长期查看的业务结果必须写入 Artifact，并从文件区或 Agent 专属工作区打开。

## 3. 不采用的方案

### 3.1 前端合成工具调用

不根据 Agent 的静态 `tools` 列表或步骤结果生成虚假的调用记录。静态列表只能表示能力，不能证明本次任务实际执行过该工具，也无法可靠表达失败、重试和刷新恢复。

### 3.2 Worker 手工拼装 UI 事件

不要求每个 Worker 重复实现 `activate_toolkit`、`deactivate_toolkit` 等 Eigent UI 事件。业务 Worker 只发布平台领域事件，Product Event 投影由后端统一完成。

### 3.3 完整结果作为完成报告

不再将 `step.result` 直接 `JSON.stringify` 后送入 Markdown 组件。结构化步骤结果属于机器状态，不是用户报告。

## 4. 运行架构

确定性业务操作通过统一 Tool Registry 和 Tool Executor 执行：

```text
Worker
  -> 发布 agent.progress
  -> Tool Registry 解析 Tool
  -> Tool Executor
       -> tool_call.started
       -> 执行确定性业务服务
       -> tool_call.succeeded / tool_call.failed
  -> 发布 agent.progress
  -> Artifact Service 生成文件
  -> artifact.created
  -> Worker 返回结构化步骤结果
```

Tool 是确定性执行边界，不改变现有 Agent、Skill、Tool 职责：

- Agent 决定要完成的业务目标，并按需加载 Skill。
- Skill 提供操作程序、规则和参考资料。
- Tool 调用解析、校验、图谱写入、合规计算、文件生成和导出等确定性代码。
- taxonomy 校验、schema 校验、证据范围校验和交付状态转换继续由平台代码负责。

第一版需要覆盖实际业务操作，而不是只记录每个 Agent 的粗粒度阶段。

### 4.1 商品目录专员

- 导入源文件
- 解析商品素材
- 规范商品事实
- 校验女性服装分类
- 写入 Product/SKU 图谱
- 生成商品目录产物
- 创建事实冲突审批

### 4.2 合规专员

- 加载美国服装合规 Skill
- 加载 Shopify 商品政策 Skill
- 加载 eBay 美国站政策 Skill
- 执行美国服装法规检查
- 执行 Shopify 政策检查
- 执行 eBay 美国站政策检查
- 生成合规报告
- 创建缺失事实审批

### 4.3 商品刊登专员

- 加载英文商品本地化 Skill
- 加载 Shopify Listing Skill
- 加载 eBay Listing Skill
- 生成 Shopify 草稿
- 生成 eBay 美国站草稿
- 执行受约束的英文内容本地化
- 写入 Listing 图谱
- 生成平台草稿产物

### 4.4 治理审核员

- 加载商品治理 Skill
- 校验跨平台事实一致性
- 校验证据和版本
- 计算交付就绪状态
- 生成治理审核报告
- 生成 SKU 矩阵
- 在满足条件时生成导出包

## 5. 平台事件契约

### 5.1 工具调用事件

Tool Executor 自动发布以下持久化平台事件：

- `tool_call.started`
- `tool_call.succeeded`
- `tool_call.failed`

共同字段：

```json
{
  "tool_call_id": "tcall_...",
  "worker_name": "catalog_steward_agent",
  "process_task_id": "step_...",
  "tool_name": "parse_product_materials",
  "tool_label": "解析商品素材",
  "status": "running"
}
```

后端可持久化紧凑输入摘要、紧凑输出摘要、错误信息、开始时间、结束时间和关联 Artifact ID，用于审计和恢复；Product Event 给桌面端的默认可见字段只包含调用标识、归属、中文名称和状态。

同一次调用的开始和结束事件必须使用相同的 `tool_call_id`。重试创建新的调用 ID，避免把两次执行错误地合并。

### 5.2 工作摘要事件

Agent 使用 `agent.progress` 发布面向用户的逐条工作摘要：

```json
{
  "worker_name": "catalog_steward_agent",
  "process_task_id": "step_...",
  "message": "发现两个原产地值存在冲突，已保留来源证据并请求确认。",
  "phase": "fact_validation"
}
```

工作摘要要求：

- 使用简洁中文。
- 说明当前动作、重要发现、业务判断或下一步。
- 不复制完整工具返回。
- 不输出原始 JSON、提示词、内部推理或异常堆栈。
- 每条事件可独立阅读，并可在刷新后按 sequence 恢复。

### 5.3 Product Event 投影

后端统一将平台事件投影为 Eigent 兼容事件：

| 平台事件 | Product Event |
| --- | --- |
| `tool_call.started` | `activate_toolkit` |
| `tool_call.succeeded` | `deactivate_toolkit`，状态为完成 |
| `tool_call.failed` | `deactivate_toolkit`，状态为失败 |
| `agent.progress` | `agent_progress` |
| `artifact.created` | `write_file` |
| `task.step_changed` | `create_agent`、`assign_task`、`activate_agent`、`task_state`、`deactivate_agent` |

投影事件必须保留 `worker_name` 和 `process_task_id`。前端按稳定 ID 直接归属，不通过 Agent 名称模糊匹配，也不通过事件文本猜测归属。

## 6. 步骤结果、摘要与报告

步骤完成后保留结构化 `step.result`，供平台状态恢复和 Agent 专属工作区使用，但它不直接成为 UI 报告。

每个步骤额外提供紧凑完成摘要，至少包含：

- 一句业务结论。
- 关键计数或状态。
- 关联 Artifact ID。

Agent 卡片的完成区域只显示紧凑摘要和生成文件入口。

正式报告必须来自 `text/markdown` Artifact，例如：

- `us_compliance_report.md`
- `localization_notes.md`
- `catalog_consistency_report.md`

Markdown Artifact 使用 Markdown 阅读器渲染。JSON、CSV、XLSX 和 ZIP 是机器产物或交付文件，只在文件工作区显示文件信息、结构化预览或下载入口。

## 7. Agent 专属工作区

右下角按钮只负责切换工作区，工作区数据通过明确的数据投影获得。

### 7.1 数据所有权

- 商品目录专员：读取规范 Product/SKU API、商品目录步骤结果及该 Worker 的 Artifact。
- 合规专员：读取合规步骤结果、待审批项及合规 Artifact。
- 商品刊登专员：读取刊登步骤结果及 Shopify/eBay Artifact。
- 治理审核员：读取治理步骤结果、交付状态、审批和导出 Artifact。
- 文件工作区：读取任务源文件与全部 Artifact，并按虚拟目录分类。

前端不得让所有 Agent 工作区共享顶层 `task.result` 后自行猜测字段。

### 7.2 状态区分

每个工作区明确区分：

- 未执行：所属步骤尚未开始。
- 运行中：已有进度事件，但结果尚未完成。
- 无业务问题：步骤完成且结果明确为空。
- 加载失败：接口或数据解析失败，并提供可读错误。
- 已完成：展示结构化业务结果和相关 Artifact。

这可以避免将“尚未产生结果”和“检查后确实为零”都显示成 `0 / 无`。

## 8. 前端状态投影

桌面端使用 Product Events 和任务快照构建以下状态：

- Agent 和子任务生命周期。
- 按 `process_task_id` 分组的 `agent.progress` 列表。
- 按 `tool_call_id` 合并的真实工具状态。
- 按 Worker 和步骤归属的 Artifact。
- 步骤紧凑完成摘要。

静态 Worker 配置只保留名称、图标、说明和能力描述，不参与推断工具是否执行。

历史任务没有新工具事件时不补造调用记录，只显示已经存在的步骤摘要和 Artifact。

## 9. 错误和恢复

- 工具失败时持久化 `tool_call.failed`，工具状态显示“失败”。
- Agent 同时发布一条可读的失败摘要；完整异常留在后端日志和审计字段。
- Product Event 按任务 sequence 有序传输，SSE 断线后从游标继续。
- 前端以 `tool_call_id` 幂等合并工具开始与结束事件。
- Artifact 事件携带所属 Worker、步骤和类型，避免多个文件打开成同一内容。
- 缺少步骤归属的数据作为协议错误记录，不使用模糊匹配静默归类。

## 10. 最终集成验证

不增加零散的小测试。功能完成后运行完整场景：

```text
创建项目
-> 导入女性服装素材
-> 创建并执行任务
-> 观察四个 Agent 的逐条工作摘要
-> 检查真实工具名称和状态
-> 确认 Agent 卡片不再出现完整 JSON
-> 分别打开四个 Agent 专属工作区
-> 打开 Markdown 报告与其他生成文件
-> 刷新页面并确认事件状态完整恢复
```

同时执行：

- 后端完整集成测试。
- 桌面端 TypeScript 类型检查。
- 桌面端生产构建。

验收要求：

1. 每个实际执行的业务 Tool 都有稳定、真实的状态记录。
2. Agent 工作摘要逐条实时显示，刷新后仍可恢复。
3. 工具区域不显示耗时、参数或结果内容。
4. Agent 卡片不再把结构化结果渲染为大段 JSON。
5. 四个 Agent 工作区展示各自真实业务数据和文件。
6. 同一任务的不同 Artifact 可独立打开，内容不会串联。
7. 历史任务兼容且不伪造工具调用。
