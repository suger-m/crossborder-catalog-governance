import type { CoworkWorkspaceType } from '@/types';

export type CoworkWorkerId =
  | 'planner'
  | 'catalog_steward_agent'
  | 'compliance_specialist_agent'
  | 'listing_operations_agent'
  | 'governance_reviewer_agent';

export type CoworkWorkerDef = {
  id: CoworkWorkerId;
  label: string;
  workspaceType: CoworkWorkspaceType;
  code: string;
  tools: string[];
  /** When true, included in authStore worker list / ExpandedInputBox agents. */
  inAuthList?: boolean;
};

export const COWORK_WORKER_DEFS: CoworkWorkerDef[] = [
  {
    id: 'planner',
    label: 'Task Planner',
    workspaceType: 'developer_agent',
    code: 'PL',
    tools: ['list_skills', 'load_skill'],
    inAuthList: false,
  },
  {
    id: 'catalog_steward_agent',
    label: 'Catalog Steward',
    workspaceType: 'browser_agent',
    code: 'RW',
    tools: ['inspect_product', 'classify_product', 'build_sku_graph'],
    inAuthList: true,
  },
  {
    id: 'compliance_specialist_agent',
    label: 'Compliance Specialist',
    workspaceType: 'document_agent',
    code: 'AW',
    tools: ['load_compliance_skill', 'check_us_apparel', 'validate_marketplace_policy'],
    inAuthList: true,
  },
  {
    id: 'listing_operations_agent',
    label: 'Listing Operations',
    workspaceType: 'document_agent',
    code: 'RV',
    tools: ['load_localization_skill', 'build_shopify_draft', 'build_ebay_draft'],
    inAuthList: true,
  },
  {
    id: 'governance_reviewer_agent',
    label: 'Governance Reviewer',
    workspaceType: 'document_agent',
    code: 'GR',
    tools: ['validate_evidence', 'review_release_readiness', 'request_human_approval'],
    inAuthList: true,
  },
];

export const COWORK_WORKER_MENU_ORDER: string[] = [
  'catalog_steward_agent',
  'compliance_specialist_agent',
  'listing_operations_agent',
  'governance_reviewer_agent',
];

export const COWORK_WORKER_LABELS: Record<string, string> = {
  planner: 'Task Planner',
  coordinator: 'Coordinator',
  catalog_steward_agent: 'Catalog Steward',
  compliance_specialist_agent: 'Compliance Specialist',
  listing_operations_agent: 'Listing Operations',
  governance_reviewer_agent: 'Governance Reviewer',
};

export const COWORK_WORKER_CODES: Record<string, string> = Object.fromEntries(
  COWORK_WORKER_DEFS.flatMap((def) => {
    const entries: Array<[string, string]> = [[def.id, def.code]];
    return entries;
  })
);

export const COWORK_WORKER_TO_WORKSPACE_TYPE: Record<string, CoworkWorkspaceType> = Object.fromEntries(
  COWORK_WORKER_DEFS.flatMap((def) => {
    const entries: Array<[string, CoworkWorkspaceType]> = [[def.id, def.workspaceType]];
    if (def.id === 'planner') entries.push(['coordinator', def.workspaceType]);
    return entries;
  })
);

export function normalizeCoworkWorkerId(name?: string): string {
  if (!name) return 'worker';
  const normalized = name.replace(/^worker_/, '');
  return normalized === 'reviewer_worker' ? 'reviewer' : normalized;
}

export function coworkWorkerLabel(name?: string): string {
  const normalized = (name || '').replace(/^worker_/, '');
  const key = normalized;
  return COWORK_WORKER_LABELS[key] || COWORK_WORKER_LABELS[normalized] || normalized || 'Worker';
}

export function buildAuthWorkerList(): Agent[] {
  return COWORK_WORKER_DEFS.filter((def) => def.inAuthList !== false && def.id !== 'planner').map((def) => ({
    agent_id: `worker_${def.id}`,
    name: def.id,
    type: def.workspaceType,
    status: 'pending',
    tasks: [],
    log: [],
    tools: [...def.tools],
  }));
}
