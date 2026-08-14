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

- `product_catalog_agent`：读取商品资料，建立 Product/SKU/Variant 候选事实。
- `product_classification_agent`：映射内部类目、标准类目、美国市场分类和平台类目。
- `us_compliance_agent`：检查美国服装标签、材料、原产地、声明和必要证明。
- `shopify_listing_agent`：生成 Shopify Product/Variant/Option 数据和导入文件。
- `ebay_us_listing_agent`：映射 eBay 类目、Item Specifics、Variation 和 Listing 内容。
- `localization_agent`：负责英文表达、单位转换、尺码表达和本地化内容。
- `catalog_governance_agent`：检查跨 SKU、跨平台、跨版本的一致性。
- `compliance_reviewer`：执行最终合规与材料完整性审核。
- `export_agent`：整理上架包，不直接发布。

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
-> Product Catalog Agent 抽取候选事实
-> 平台归一、去重和 schema 校验
-> 用户确认关键冲突
-> Canonical Product Graph
-> 分类、美国合规和平台适配并行
-> Localization Agent 生成英文内容
-> Catalog Governance Agent 检查跨平台一致性
-> Compliance Reviewer 执行发布闸门
-> Export Agent 生成上架包
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

