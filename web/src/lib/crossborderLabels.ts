export const AGENT_LABELS: Record<string, string> = {
  planner: '任务规划器',
  coordinator: '任务协调器',
  catalog_steward_agent: '商品目录专员',
  compliance_specialist_agent: '合规专员',
  listing_operations_agent: '商品刊登专员',
  governance_reviewer_agent: '治理审核员',
};

export const TOOL_LABELS: Record<string, string> = {
  list_skills: '查看可用技能',
  load_skill: '加载技能',
  read_skill_resource: '读取技能资料',
  list_project_resources: '查看项目资源',
  inspect_task_materials: '查看任务素材',
  summarize_canonical_products: '查看规范商品摘要',
  summarize_listing_drafts: '查看平台草稿摘要',
  read_artifact_text: '读取文件内容',
  list_pending_approvals: '查看待审批事项',
  build_canonical_catalog: '建立规范商品目录',
  evaluate_us_apparel_compliance: '执行美国服装合规检查',
  create_listing_drafts: '生成平台草稿',
  review_catalog_release: '执行目录治理审核',
};

export const SKILL_LABELS: Record<string, string> = {
  'product-catalog': '商品目录治理',
  'womenswear-classification': '女装商品分类',
  'us-apparel-compliance': '美国服装合规',
  'shopify-product-policy': 'Shopify 商品政策',
  'ebay-us-fashion-policy': 'eBay 美国站时尚品类政策',
  'product-localization-en-us': '美国市场商品本地化',
  'shopify-listing': 'Shopify 刊登草稿',
  'ebay-us-listing': 'eBay 美国站刊登草稿',
  'catalog-governance': '商品目录治理审核',
};

export const SKILL_DESCRIPTIONS: Record<string, string> = {
  'product-catalog': '规范商品与 SKU 事实，保留来源证据和版本关系。',
  'womenswear-classification': '按照女装分类体系生成受控分类候选。',
  'us-apparel-compliance': '检查美国服装标签、原产地及声明要求。',
  'shopify-product-policy': '校验 Shopify 商品字段与平台政策要求。',
  'ebay-us-fashion-policy': '校验 eBay 美国站时尚品类字段与政策要求。',
  'product-localization-en-us': '将规范商品事实转化为美国市场表达。',
  'shopify-listing': '根据规范商品事实生成 Shopify 导入草稿。',
  'ebay-us-listing': '根据规范商品事实生成 eBay 美国站草稿。',
  'catalog-governance': '审核事实一致性、证据完整性与交付就绪状态。',
};

export const STEP_LABELS: Record<string, string> = {
  'Build canonical Product/SKU catalog': '构建规范 Product/SKU 商品目录',
  'Evaluate US and marketplace compliance': '执行美国法规与平台合规检查',
  'Create localized Shopify and eBay drafts': '生成 Shopify 和 eBay 美国站本地化草稿',
  'Review consistency and export package': '审核一致性并生成导出包',
};

export const STATUS_LABELS: Record<string, string> = {
  checking: '检查中',
  online: '在线',
  degraded: '等待 AgentTeams',
  offline: '离线',
  queued: '等待执行',
  planned: '已规划',
  waiting: '等待执行',
  pending: '待处理',
  open: '待处理',
  running: '执行中',
  completed: '已完成',
  done: '已完成',
  failed: '失败',
  blocked: '已阻塞',
  waiting_approval: '等待审批',
  cancelled: '已取消',
  skipped: '已跳过',
  connecting: '连接中',
  reconnecting: '重新连接中',
  live: '实时连接',
  closed: '已断开',
  ready: '就绪',
  configured: '已配置',
  draft: '草稿',
  confirmed: '已确认',
};

export function agentLabel(value = ''): string {
  const normalized = value.replace(/^worker_/, '');
  return AGENT_LABELS[normalized] || value || '业务智能体';
}

export function toolLabel(value = ''): string {
  return TOOL_LABELS[value] || value.replace(/[_-]+/g, ' ') || '工具调用';
}

export function skillLabel(value = ''): string {
  return SKILL_LABELS[value] || value;
}

export function stepLabel(value = ''): string {
  return STEP_LABELS[value] || value;
}

export function statusLabel(value = ''): string {
  return STATUS_LABELS[value.toLowerCase()] || value.replace(/_/g, ' ');
}

export function localizedMessage(value: unknown): string {
  const message = value instanceof Error ? value.message : String(value || '');
  if (message === 'Failed to fetch') return '无法连接到后端服务。';
  if (message.includes('No source files supplied')) return '尚未提供源文件。请至少上传一个商品目录文件后再运行。';
  if (message.includes('Product not found')) return '未找到对应商品。';
  if (message.includes('Approval not found')) return '未找到对应审批记录。';
  if (message.includes('Artifact not found')) return '未找到对应生成文件。';
  return message;
}
