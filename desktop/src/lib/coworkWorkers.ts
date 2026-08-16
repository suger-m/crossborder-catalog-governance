import type { CoworkWorkspaceType } from '@/types';
import { AGENT_LABELS } from './crossborderLabels';

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
    label: '任务规划器',
    workspaceType: 'developer_agent',
    code: 'PL',
    tools: [],
    inAuthList: false,
  },
  {
    id: 'catalog_steward_agent',
    label: '商品目录专员',
    workspaceType: 'developer_agent',
    code: 'CS',
    tools: ['list_skills', 'load_skill', 'read_skill_resource', 'list_project_resources', 'inspect_task_materials', 'build_canonical_catalog'],
    inAuthList: true,
  },
  {
    id: 'compliance_specialist_agent',
    label: '合规专员',
    workspaceType: 'document_agent',
    code: 'CO',
    tools: ['list_skills', 'load_skill', 'read_skill_resource', 'list_project_resources', 'summarize_canonical_products', 'list_pending_approvals', 'evaluate_us_apparel_compliance'],
    inAuthList: true,
  },
  {
    id: 'listing_operations_agent',
    label: '商品刊登专员',
    workspaceType: 'document_agent',
    code: 'LO',
    tools: ['list_skills', 'load_skill', 'read_skill_resource', 'list_project_resources', 'summarize_canonical_products', 'create_listing_drafts'],
    inAuthList: true,
  },
  {
    id: 'governance_reviewer_agent',
    label: '治理审核员',
    workspaceType: 'document_agent',
    code: 'GR',
    tools: ['list_skills', 'load_skill', 'read_skill_resource', 'list_project_resources', 'summarize_canonical_products', 'summarize_listing_drafts', 'read_artifact_text', 'list_pending_approvals', 'review_catalog_release'],
    inAuthList: true,
  },
];

export const COWORK_WORKER_MENU_ORDER: string[] = [
  'catalog_steward_agent',
  'compliance_specialist_agent',
  'listing_operations_agent',
  'governance_reviewer_agent',
];

export const COWORK_WORKER_LABELS: Record<string, string> = AGENT_LABELS;

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
  return COWORK_WORKER_LABELS[key] || COWORK_WORKER_LABELS[normalized] || normalized || '业务智能体';
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
