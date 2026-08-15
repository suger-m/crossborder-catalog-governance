import type { TaskStep } from '../api';
import { stepLabel } from './crossborderLabels';
export const WORKERS = [
  { worker_name: 'catalog_steward_agent', title: '构建规范 Product/SKU 商品目录', label: '商品目录专员' },
  { worker_name: 'compliance_specialist_agent', title: '执行美国法规与平台合规检查', label: '合规专员' },
  { worker_name: 'listing_operations_agent', title: '生成 Shopify 和 eBay 美国站本地化草稿', label: '商品刊登专员' },
  { worker_name: 'governance_reviewer_agent', title: '审核一致性并生成导出包', label: '治理审核员' },
] as const;
export function workflowSteps(steps: TaskStep[] | undefined): Array<TaskStep & { label: string }> { return WORKERS.map((worker, index) => { const persisted = steps?.find((step) => step.worker_name === worker.worker_name); return { id: persisted?.id || `planned-${worker.worker_name}`, sequence: persisted?.sequence || index + 1, worker_name: worker.worker_name, title: stepLabel(persisted?.title || worker.title), status: persisted?.status || 'queued', result: persisted?.result || {}, label: worker.label }; }); }
