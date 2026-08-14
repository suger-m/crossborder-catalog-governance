import type { TaskStep } from '../api';
export const WORKERS = [
  { worker_name: 'catalog_steward_agent', title: 'Build canonical Product/SKU catalog', label: 'Catalog Steward' },
  { worker_name: 'compliance_specialist_agent', title: 'Evaluate US and marketplace compliance', label: 'Compliance Specialist' },
  { worker_name: 'listing_operations_agent', title: 'Create localized Shopify and eBay drafts', label: 'Listing Operations' },
  { worker_name: 'governance_reviewer_agent', title: 'Review consistency and export package', label: 'Governance Reviewer' },
] as const;
export function workflowSteps(steps: TaskStep[] | undefined): Array<TaskStep & { label: string }> { return WORKERS.map((worker, index) => { const persisted = steps?.find((step) => step.worker_name === worker.worker_name); return { id: persisted?.id || `planned-${worker.worker_name}`, sequence: persisted?.sequence || index + 1, worker_name: worker.worker_name, title: persisted?.title || worker.title, status: persisted?.status || 'queued', result: persisted?.result || {}, label: worker.label }; }); }
