# 生产级真实场景验收设计

## 1. 目标

为第一版跨境女装商品治理链路增加一套可重复的生产仿真验收。验收资料模拟真实供应商交付，而不是把现有 CSV 简单扩行。系统必须能够处理多文件、中文字段、Unicode 差异、货币与库存格式、补充说明、媒体文件、事实冲突和缺失事实，并生成可校验的 Shopify 与 eBay US 导入包。

这套验收不能被描述为真实企业数据或真实平台发布测试。它验证的是接近生产资料的完整数据链路；真实 Shopify/eBay 测试店导入仍属于外部验收。

## 2. 输入资料包

一次任务同时输入以下文件：

- `supplier-catalog.xlsx`：两款女性服装、多个颜色和尺码、中文/英文字段、全角字符、带货币符号价格和带单位库存。
- `label-specification.pdf`：补充标签事实，并为其中一款商品制造真实原产地冲突。
- `media-and-certifications.json`：商品图片 URL、认证和标签等产品级补充事实。
- `lookbook-front.png`：真实二进制图片文件，用于验证源文件 Artifact 的保存、哈希和文件空间展示。

资料包包含至少 2 个 Product、10 个真实 SKU、1 个原产地冲突和 1 个缺失纤维成分。

## 3. 接入层改造

接入层增加以下确定性归一能力：

1. 对表头和字符串执行 Unicode NFKC 归一，兼容全角字符和常见空白。
2. 将 `PRC`、`CN`、`中国` 等原产地别名归一为正式值，避免同义值产生虚假冲突。
3. 对纤维成分进行稳定比较，忽略大小写、空白和常见分隔符差异。
4. 将 `$59.90`、`US$ 59.90` 等价格归一为无货币符号的小数文本。
5. 将 `1,200 pcs`、`25件` 等库存归一为非负整数。
6. 只有包含 SKU、颜色、尺码、条码、价格或库存等变体字段的记录才生成 SKU。PDF/JSON 产品级补充记录不得产生 `NA-NA` 虚假 SKU。
7. 如果商品只有产品级记录且完全没有变体记录，才生成一个稳定的单品 SKU。

## 4. 渠道导入校验

Governance Reviewer 在批准导出前调用确定性校验器：

- Shopify：Handle、Variant SKU、价格、库存、尺码、颜色、草稿状态和 SKU 唯一性。
- eBay US：Marketplace、类目 ID、80 字符标题限制、Item Specifics、Variation SKU、价格、数量、尺码、颜色和 SKU 唯一性。
- 任一导入约束失败都生成 blocking finding，阻止 `listing_package.zip`。
- 校验器不调用平台 API，也不包含发布凭据。

## 5. Artifact 与导出验收

验收必须验证：

- 每个输入源文件都有独立 `source_document` Artifact、SHA-256 和正确大小。
- Source Manifest 能列出全部输入文件和记录数。
- Human Approval 产生的事实带 `human_approval:<id>` 证据来源。
- Shopify 与 eBay 的 SKU、尺寸、颜色、材料、原产地和价格与 Canonical Product 一致。
- ZIP 内每个成员的实际 SHA-256 和字节数与 `manifest.json` 一致。
- ZIP 不包含 API Key、访问令牌或发布动作。

## 6. 安装包验收

Windows 打包后启动冻结的 Python 后端，使用打包后的 `resources` 目录和独立 runtime 目录，验证：

- `/health` 返回成功。
- 4 套 Taxonomy 和 9 个项目 Skills 可发现。
- Planner、Worker、Reviewer 能按旧项目兼容顺序读取环境变量或桌面设置。

自动验收不操作真实 Shopify/eBay 店铺，也不执行发布。

## 7. 测试策略

遵循项目约束，不为每个归一函数建立 TDD 或独立测试套件。全部实现完成后只运行：

1. 现有基础端到端集成测试。
2. 新增生产仿真端到端验收测试。
3. Electron type-check、生产构建和 Windows 打包。
4. 打包后端资源烟测。

验收失败时修复根因，并重新执行完整最终验收。
