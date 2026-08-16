# 原生业务 Agent 与 Agent Skills Runtime 设计

## 1. 目标

将当前“CAMEL Workforce 动态分配任务、Python `run_for_workforce()` 固定执行”的内部结构，重构为 Eigent/CAMEL 原生的模型 Worker 模式：四个稳定业务角色均由 `ChatAgent` 承担，使用 `SingleAgentWorker` 接收 Workforce 子任务，并由 Agent 根据目标自主选择 Skill 和领域 Tool。

## 2. 参考实现

直接参考 Eigent：

- `D:/vibe/_reference/eigent/backend/app/agent/toolkit/skill_toolkit.py`
- `D:/vibe/_reference/eigent/backend/app/agent/factory/`
- `D:/vibe/_reference/eigent/backend/app/utils/single_agent_worker.py`
- `D:/vibe/_reference/eigent/backend/app/utils/workforce.py`

复用其底层模式，不复制 Browser、Developer、Document 等通用 Agent 的业务能力。

## 3. Agent 工具边界

四个业务 Agent 只获得以下能力：

1. CAMEL `SkillToolkit`：`list_skills`、`load_skill`，以及仅限已授权 Skill 包目录的 `read_skill_resource`。
2. 项目上下文 Toolkit：读取当前项目中的 Product、Listing、Approval、Artifact 和 Resource 摘要。
3. 当前角色对应的确定性领域 Tools。
4. 需要时创建 Human Approval 的受控能力。

不得注册：

- `TerminalToolkit`
- `SearchToolkit`
- Browser 工具
- MCP 通用工具
- 任意文件系统写入或命令执行工具
- Shopify/eBay 发布工具

## 4. Skill 语义

Skill 是按需加载到 Agent 上下文的能力包，不是固定工作流、Agent 或 Tool 白名单。Agent 激活 Skill 后，可以只使用与当前目标有关的指令、references、assets 或 scripts，也可以结合领域 Tool 或不调用 Tool。

平台只负责 Skill 发现、权限、加载、脚本风险边界和可观察性，不通过关键词替 Agent 选择 Skill。

## 5. 运行结构

```text
ResourceAwareWorkforce
-> 原生/轻量扩展 SingleAgentWorker
-> 业务 ChatAgent
   -> SkillToolkit
   -> ProjectContextToolkit
   -> Role Domain Toolkit
-> Project Resource / Artifact
-> ResourceAwareWorkforce 校验紧凑结果
```

轻量 `SingleAgentWorker` 扩展只负责将 CAMEL 子任务 ID 写入 Agent 的执行上下文，并保留事件身份；不得绕过 `ChatAgent.step()` 或直接调用业务 Python runner。

## 6. 业务 Agent

- 商品目录专员：可见 `product-catalog`、`womenswear-classification`；项目上下文工具为 `list_project_resources`、`inspect_task_materials`；领域工具为 `build_canonical_catalog`。
- 合规专员：可见 `us-apparel-compliance`、`shopify-product-policy`、`ebay-us-fashion-policy`；项目上下文工具为 `list_project_resources`、`summarize_canonical_products`、`list_pending_approvals`；领域工具为 `evaluate_us_apparel_compliance`。
- Listing 运营专员：可见 `product-localization-en-us`、`shopify-listing`、`ebay-us-listing`；项目上下文工具为 `list_project_resources`、`summarize_canonical_products`；领域工具为 `create_listing_drafts(platforms, product_resource_ids)`。
- 治理审核员：可见 `catalog-governance`；项目上下文工具为 `list_project_resources`、`summarize_canonical_products`、`summarize_listing_drafts`、`read_artifact_text`、`list_pending_approvals`；领域工具为 `review_catalog_release(create_export_package, ...)`。

领域工具不是“执行整个 Agent”的隐藏 runner。它们分别代表一个有明确输入、输出、授权和持久化边界的业务事务。Agent 决定是否先读项目摘要、启用哪些 Skill、选择哪个平台、是否要求导出包，以及何时调用领域工具；平台负责事务内部的 schema、图、Artifact、审批和资源一致性。

## 7. 确定性平台边界

以下能力继续保留为平台代码：taxonomy 校验、evidence span 校验、图 schema、项目隔离、Tool 授权、Artifact 哈希、资源版本、审批状态、release 状态、CSV/JSON/XLSX/ZIP 格式化和禁止自动发布。

LLM 负责选择 Skill、组织 Tool 调用、判断需要读取哪些项目资源和形成公开摘要，不直接写数据库或伪造正式资源 ID。

## 8. Skill Runtime

基于 CAMEL `SkillToolkit` 扩展项目能力：

- 扫描项目 `skills/`、`.agents/skills/` 和用户 Skills 目录。
- 项目级覆盖用户级同名 Skill。
- 使用 CAMEL/YAML 解析，不再使用正则 frontmatter 解析。
- 按 Agent 配置过滤可见 Skill，但不替 Agent 激活。
- 记录 Skill 激活和 Skill reference 读取事件；按需列出 bundled resources。
- 因业务 Agent 不具备 TerminalToolkit，Skill references 只能通过包目录受限、文本类型受限、分页读取的 `read_skill_resource` 访问。
- 不在启动时加载全部 Skill 正文。

## 9. 结果契约

业务 Agent 最终必须返回紧凑 JSON：

```json
{
  "summary": "公开工作摘要",
  "key_counts": {},
  "output_resource_ids": [],
  "status": "completed"
}
```

完整业务数据只存在于项目 Resource 和 Artifact。Workforce 在接受结果前校验项目归属、CAMEL 子任务归属和 Artifact 完整性。

## 10. 迁移与删除

删除 `BusinessWorker -> run_for_workforce()` 固定执行链路。原 `run_for_workforce()` 中的确定性操作迁移为角色领域 Toolkit；旧同步 `run()` 仅在确认无调用者后删除，不保留双执行源。

## 11. 验证

不采用 TDD。功能整体完成后执行一次最终集成验证，覆盖：完整交付、单 Agent 审核、单平台 Listing、项目资源复用、Skill 自主激活、Tool 权限拒绝、Artifact 独立预览及禁止发布。
