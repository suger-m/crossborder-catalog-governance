# 跨境商品合规与海外平台上架治理设计

## 1. 产品目标

建立一个由多智能体协作的跨境商品治理平台。企业上传商品 Excel、图片、说明书和资质文件后，系统建立唯一的 Canonical Product/SKU 图谱，完成美国服装合规检查，并生成 Shopify 与 eBay US 的上架包。

第一版不自动登录或发布商品，不处理订单、库存、价格、采购和供应商。

## 2. 第一版范围

- 商品品类：女性服装。
- 目标市场：美国。
- 渠道：Shopify、eBay US。
- 输入：Excel/CSV、图片、PDF、Markdown、JSON。
- 输出：标准商品档案、SKU 矩阵、问题清单、合规报告、渠道 Listing、导入文件和审核报告。
- 发布方式：仅导出；后续版本再通过 Human Approval 接平台 API。

## 3. 核心原则

1. Canonical Product 是唯一商品事实源。
2. 国家法规合规与平台规则检查分离。
3. Agent 只能提出候选标签和关系，平台负责 schema、taxonomy 和证据校验。
4. 所有 Listing 都必须能追溯到商品事实和规则依据。
5. 不同平台 Listing 可以有不同表达，但不能包含冲突的事实。
6. 高风险修改、覆盖商品事实和对外发布必须经过 Human Approval。

## 4. 多智能体团队

第一版只保留四个稳定业务角色：

- `catalog_steward_agent`：维护 Product/SKU/Variant 候选事实，按需加载商品接入和女性服装分类 Skills。
- `compliance_specialist_agent`：按需加载美国服装法规、Shopify 政策和 eBay US 政策 Skills，输出相互独立的合规结论。
- `listing_operations_agent`：按需加载英文本地化、Shopify Listing 和 eBay US Listing Skills，生成渠道草稿。
- `governance_reviewer_agent`：检查商品事实、合规阻塞、跨平台一致性、证据、版本和发布状态。

Planner、Human Approval 和文件导出属于平台能力，不作为业务 Agent。

Skills 采用 Agent Skills 渐进加载机制：启动时只暴露名称和描述；Agent 判断匹配后加载完整 `SKILL.md`；脚本、参考资料和模板仅在技能执行需要时读取。

## 5. 领域模型

核心节点：

- Product
- SKU
- Variant
- Category
- Attribute
- Material
- Claim
- Certification
- Market
- Regulation
- Platform
- PlatformCategory
- PlatformAttribute
- Listing
- ListingVersion
- MediaAsset
- SourceDocument

核心关系：

- Product `HAS_SKU` SKU
- SKU `HAS_VARIANT_VALUE` Attribute
- Product `BELONGS_TO` Category
- Product `USES_MATERIAL` Material
- Product `MAKES_CLAIM` Claim
- Product `REQUIRES` Certification
- Product `TARGETS` Market
- Market `ENFORCES` Regulation
- Product `LISTED_ON` Platform
- Listing `DERIVED_FROM` Product/SKU
- PlatformCategory `REQUIRES_ATTRIBUTE` PlatformAttribute
- ListingVersion `SUPERSEDES` ListingVersion
- Fact/Edge `SUPPORTED_BY` SourceDocument

## 6. Taxonomy

第一版包含四套独立 taxonomy：

1. `womenswear-product`：服装类目、款式、材料、尺寸、颜色、场景和适用人群。
2. `us-apparel-compliance`：美国服装标签、原产地、材料声明、洗护和风险声明。
3. `shopify-product`：Product、Variant、Option、Tag、Collection 和导入字段。
4. `ebay-us-fashion`：eBay 类目、Item Specifics、Condition、Variation 和政策要求。

所有正式标签必须包含 `node_id`、`taxonomy_version`、`source`、`confidence` 和 `evidence_span`。

## 7. 数据处理链路

```text
商品文件
-> 文件解析和原始 Artifact
-> Catalog Steward Agent 抽取、分类候选事实
-> 平台归一、去重和 schema 校验
-> 用户确认关键冲突
-> Canonical Product Graph
-> Compliance Specialist Agent 检查美国法规和平台政策
-> Listing Operations Agent 生成本地化 Shopify/eBay 草稿
-> Governance Reviewer Agent 执行一致性和发布审核
-> 平台导出工具生成上架包
```

## 8. Artifact 类型

- `canonical_product.json`
- `sku_matrix.xlsx`
- `source_manifest.json`
- `classification_result.json`
- `us_compliance_report.md`
- `shopify_listing.csv`
- `ebay_listing.json`
- `localization_notes.md`
- `catalog_consistency_report.md`
- `release_review.json`
- `listing_package.zip`

## 9. 技术架构

- 后端：Python、FastAPI、CAMEL Workforce。
- 桌面端：Electron、React、TypeScript。
- 结构化存储：SQLite。
- 图数据第一版：SQLite `graph_nodes`、`graph_edges`、`graph_evidence`、`graph_versions`。
- 文档和语义索引：LanceDB，仅用于查找商品原文、规则和平台说明。
- Skills：项目级 `skills/`，由 Worker 动态发现、加载和执行。
- Artifact：文件持久化、SHA-256、版本和上游依赖。

## 10. 验收标准

用户上传一组女性服装商品资料后，系统能够：

1. 生成稳定的 Product/SKU/Variant 标识。
2. 识别缺失、冲突和无法确认的商品属性。
3. 建立带证据来源的商品图谱。
4. 输出美国服装合规检查结果。
5. 生成 Shopify CSV 和 eBay US Listing JSON。
6. 检查两个渠道的商品事实是否一致。
7. 阻止存在硬性合规问题的商品进入可发布状态。
8. 在桌面工作空间展示任务、图谱摘要、问题和全部文件。
