import type {
  Artifact,
  ProductEvent,
  ProjectResource,
  TaskDetail,
  TaskStep,
} from '../api';
import { agentLabel, stepLabel, toolLabel } from '../lib/crossborderLabels';

export type ActivityKind = 'progress' | 'handoff' | 'tool' | 'artifact' | 'waiting' | 'error' | 'result';
export type StreamState = 'connecting' | 'live' | 'reconnecting' | 'closed';

export interface ActivityItem {
  id: string;
  sender: string;
  text: string;
  kind: ActivityKind;
}

export interface HandoffItem {
  id: string;
  from: string;
  to: string;
  title: string;
}

export interface ToolSummary {
  id: string;
  label: string;
  status: 'running' | 'completed' | 'failed';
}

export interface ProjectedStep {
  id: string;
  sequence: number;
  workerName: string;
  title: string;
  status: string;
  summary: string;
  dependencies: string[];
  outputResourceIds: string[];
  progressLines: string[];
  tools: ToolSummary[];
  artifacts: Artifact[];
}

export interface TaskWorkspaceProjection {
  lastSequence: number;
  hasGap: boolean;
  steps: ProjectedStep[];
  artifacts: Artifact[];
  activity: ActivityItem[];
  handoffs: HandoffItem[];
  currentStep: ProjectedStep | null;
  participatingAgents: string[];
  toolCapabilities: string[];
  progressPercent: number;
  resources: ProjectResource[];
}

type RawMessage = {
  event_id?: string;
  sender?: string;
  content?: { body?: string; msgtype?: string };
};

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String).filter(Boolean) : [];
}

function text(...values: unknown[]): string {
  const found = values.find((value) => typeof value === 'string' && value.trim());
  return typeof found === 'string' ? found.trim() : '';
}

function valueTrim(value: string): string {
  return value.trim().replace(/\s+/g, ' ');
}

function looksLikeRawPayload(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return true;
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) return true;
  if (/"event_type"|"tool_call_id"|"payload_json"|"origin_server_ts"|"room_id"/.test(trimmed)) return true;
  if (/^m\./.test(trimmed) || trimmed.includes('"msgtype"')) return true;
  return false;
}

function textFromBody(body: string): string {
  const value = body.trim();
  if (!value || looksLikeRawPayload(value)) {
    try {
      const parsed = JSON.parse(value) as unknown;
      if (parsed && typeof parsed === 'object') {
        const payload = record(parsed);
        for (const key of ['message', 'summary', 'content', 'text', 'result', 'answer', 'description', 'objective']) {
          const candidate = text(payload[key]);
          if (candidate && !looksLikeRawPayload(candidate)) return valueTrim(candidate);
        }
      }
    } catch {
      /* plain text may still be usable */
    }
    return '';
  }
  return valueTrim(value);
}

function senderLabel(sender: string): string {
  const normalized = sender.replace(/^@/, '').split(':')[0].replace(/\./g, '_').replace(/^worker_/, '');
  if (!normalized) return '任务协调器';
  if (normalized.includes('manager') || normalized.includes('coordinator') || normalized.includes('planner')) {
    return '任务协调器';
  }
  return agentLabel(normalized);
}

const TOOL_METHOD_PREFERRED = new Set([
  'list_skills', 'load_skill', 'read_skill_resource', 'list_project_resources',
  'inspect_task_materials', 'summarize_canonical_products', 'summarize_listing_drafts',
  'read_artifact_text', 'list_pending_approvals', 'build_canonical_catalog',
  'evaluate_us_apparel_compliance', 'create_listing_drafts', 'review_catalog_release',
]);

function toolDisplay(payload: Record<string, unknown>): string {
  const method = text(payload.method_name);
  const toolkit = text(payload.toolkit_name, payload.message);
  if (method && TOOL_METHOD_PREFERRED.has(method)) return toolLabel(method);
  if (toolkit.startsWith('Skill · ')) return `加载技能：${toolkit.slice('Skill · '.length)}`;
  if (toolkit) return toolkit;
  if (method) return toolLabel(method);
  return '业务工具';
}

function pushActivity(items: ActivityItem[], seen: Set<string>, item: ActivityItem): void {
  const key = `${item.kind}|${item.sender}|${item.text}`;
  if (!item.text || seen.has(key)) return;
  seen.add(key);
  items.push(item);
}

function seedStep(step: TaskStep): ProjectedStep {
  return {
    id: step.id,
    sequence: step.sequence,
    workerName: step.worker_name,
    title: step.title,
    status: step.status,
    summary: text(step.result?.summary),
    dependencies: strings(step.dependencies),
    outputResourceIds: strings(step.result?.output_resource_ids),
    progressLines: [],
    tools: [],
    artifacts: [],
  };
}

function projectFromEvents(events: ProductEvent[], stepsById: Map<string, TaskStep>): ActivityItem[] {
  const items: ActivityItem[] = [];
  const seen = new Set<string>();
  const ordered = [...events].sort((left, right) => left.sequence - right.sequence);

  for (const event of ordered) {
    const payload = record(event.payload_json);
    const worker = text(payload.worker_name, payload.agent_id, payload.agent);
    const sender = senderLabel(worker);
    const stepId = text(payload.process_task_id, payload.task_id);
    const step = stepId ? stepsById.get(stepId) : undefined;
    const stepTitle = stepLabel(text(payload.content, payload.message, step?.title));

    switch (event.action) {
      case 'assign_task':
      case 'create_agent':
        pushActivity(items, seen, {
          id: `${event.id}:handoff`,
          sender: '任务协调器',
          text: stepTitle ? `已交接给${sender}：${stepTitle}` : `已交接给${sender}`,
          kind: 'handoff',
        });
        break;
      case 'activate_agent':
        pushActivity(items, seen, {
          id: `${event.id}:start`,
          sender,
          text: stepTitle ? `开始处理：${stepTitle}` : '开始处理当前步骤',
          kind: 'handoff',
        });
        break;
      case 'agent_progress': {
        const message = text(payload.message);
        if (message && !looksLikeRawPayload(message)) {
          pushActivity(items, seen, { id: event.id, sender, text: valueTrim(message), kind: 'progress' });
        }
        break;
      }
      case 'activate_toolkit':
        pushActivity(items, seen, {
          id: `${event.id}:tool`,
          sender,
          text: toolDisplay(payload),
          kind: 'tool',
        });
        break;
      case 'deactivate_toolkit':
        if (String(payload.status || '').toLowerCase() === 'failed') {
          pushActivity(items, seen, {
            id: `${event.id}:tool-fail`,
            sender,
            text: `${toolDisplay(payload)} 未成功`,
            kind: 'error',
          });
        }
        break;
      case 'write_file': {
        // File-level writes are represented by the Artifact/result panels.
        // Repeating every path in the main activity stream makes the real
        // workflow disappear under implementation noise.
        break;
      }
      case 'ask':
        pushActivity(items, seen, {
          id: `${event.id}:ask`,
          sender: sender || '任务协调器',
          text: text(payload.question, record(payload.approval).title, record(payload.approval).description) || '需要人工审批后才能继续',
          kind: 'waiting',
        });
        break;
      case 'human_response':
        pushActivity(items, seen, {
          id: `${event.id}:human`,
          sender: '人工审批',
          text: '审批决定已回写，任务可继续执行',
          kind: 'result',
        });
        break;
      case 'task_state': {
        const summary = text(payload.summary, payload.result, payload.message);
        const state = String(payload.state || '').toUpperCase();
        if (summary && step) {
          pushActivity(items, seen, {
            id: `${event.id}:state`,
            sender,
            text: summary,
            kind: state.includes('FAIL') ? 'error' : state.includes('WAIT') || state.includes('BLOCK') ? 'waiting' : 'result',
          });
        }
        break;
      }
      case 'deactivate_agent': {
        const summary = text(payload.message, payload.summary);
        if (summary && !looksLikeRawPayload(summary)) {
          const state = String(payload.state || '').toUpperCase();
          pushActivity(items, seen, {
            id: `${event.id}:done`,
            sender,
            text: summary,
            kind: state.includes('FAIL') ? 'error' : 'result',
          });
        }
        break;
      }
      case 'to_sub_tasks': {
        const subTasks = Array.isArray(payload.sub_tasks) ? payload.sub_tasks : [];
        pushActivity(items, seen, {
          id: `${event.id}:plan`,
          sender: '任务协调器',
          text: subTasks.length ? `动态计划已形成，共 ${subTasks.length} 个步骤` : '动态计划已更新',
          kind: 'progress',
        });
        break;
      }
      case 'activity': {
        const message = text(payload.message, payload.summary);
        if (message && !looksLikeRawPayload(message)) {
          pushActivity(items, seen, { id: event.id, sender: sender || '任务协调器', text: valueTrim(message), kind: 'progress' });
        }
        break;
      }
      case 'error':
        pushActivity(items, seen, {
          id: event.id,
          sender: sender || '任务协调器',
          text: text(payload.summary, payload.message) || '任务执行失败',
          kind: 'error',
        });
        break;
      case 'end':
        pushActivity(items, seen, {
          id: event.id,
          sender: '任务协调器',
          text: text(payload.summary, payload.message) || '任务已结束',
          kind: 'result',
        });
        break;
      default:
        break;
    }
  }
  return items;
}

function projectFromMessages(messages: RawMessage[]): ActivityItem[] {
  const items: ActivityItem[] = [];
  const seen = new Set<string>();
  messages.forEach((message, index) => {
    const body = textFromBody(message.content?.body || '');
    if (!body) return;
    pushActivity(items, seen, {
      id: message.event_id || `message-${index}`,
      sender: senderLabel(message.sender || ''),
      text: body,
      kind: /审批|等待人工|blocked|waiting/i.test(body) ? 'waiting'
        : /失败|error|exception/i.test(body) ? 'error'
        : /交接|delegat|handoff|assigned|已分配/i.test(body) ? 'handoff'
        : /完成|报告|生成|导出/i.test(body) ? 'result'
        : 'progress',
    });
  });
  return items;
}

function mergeActivity(events: ProductEvent[], messages: RawMessage[], steps: TaskStep[]): ActivityItem[] {
  const stepsById = new Map(steps.map((step) => [step.id, step]));
  const fromEvents = projectFromEvents(events, stepsById);
  const fromMessages = projectFromMessages(messages);
  const merged: ActivityItem[] = [...fromEvents];
  const seen = new Set(fromEvents.map((item) => `${item.kind}|${item.sender}|${item.text}`));
  for (const item of fromMessages) {
    const key = `${item.kind}|${item.sender}|${item.text}`;
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(item);
  }
  // Tools and file writes are already summarized in the capability and
  // delivery areas. Keep the central stream for decisions, handoffs,
  // progress, waits, errors and final results only.
  return merged
    .filter((item) => item.kind !== 'tool' && item.kind !== 'artifact')
    .slice(-20);
}

function projectHandoffs(steps: ProjectedStep[], events: ProductEvent[]): HandoffItem[] {
  const fromSteps: HandoffItem[] = [];
  for (let index = 1; index < steps.length; index += 1) {
    const previous = steps[index - 1];
    const current = steps[index];
    if (previous.workerName === current.workerName) continue;
    fromSteps.push({
      id: `step-handoff-${current.id}`,
      from: previous.workerName,
      to: current.workerName,
      title: stepLabel(current.title),
    });
  }
  if (fromSteps.length) return fromSteps;

  const fromEvents: HandoffItem[] = [];
  let lastWorker = '';
  const ordered = [...events].sort((left, right) => left.sequence - right.sequence);
  for (const event of ordered) {
    if (event.action !== 'assign_task' && event.action !== 'activate_agent') continue;
    const payload = record(event.payload_json);
    const worker = text(payload.worker_name, payload.agent_id);
    if (!worker || worker === lastWorker) continue;
    fromEvents.push({
      id: `${event.id}:chain`,
      from: lastWorker || 'coordinator',
      to: worker,
      title: stepLabel(text(payload.content, payload.message)) || agentLabel(worker),
    });
    lastWorker = worker;
  }
  return fromEvents;
}

export function isProductEvent(value: unknown): value is ProductEvent {
  if (!value || typeof value !== 'object') return false;
  const event = value as Partial<ProductEvent>;
  return typeof event.id === 'string'
    && typeof event.sequence === 'number'
    && event.protocol_name === 'agentteams'
    && event.protocol_version === 1
    && typeof event.action === 'string'
    && Boolean(event.payload_json && typeof event.payload_json === 'object');
}

export function contiguousEvents(events: ProductEvent[], cursor: number): ProductEvent[] | null {
  const additions = events.filter((event) => event.sequence > cursor).sort((left, right) => left.sequence - right.sequence);
  let expected = cursor + 1;
  for (const event of additions) {
    if (event.sequence !== expected) return null;
    expected += 1;
  }
  return additions;
}

export function activityKindLabel(kind: ActivityKind): string {
  if (kind === 'handoff') return '交接';
  if (kind === 'tool') return '工具';
  if (kind === 'artifact') return '产物';
  if (kind === 'waiting') return '审批';
  if (kind === 'error') return '异常';
  if (kind === 'result') return '结果';
  return '进展';
}

export function artifactDirectory(artifact: Artifact): 'catalog' | 'compliance' | 'listings' | 'governance' | 'exports' | 'reports' {
  const value = `${artifact.artifact_type} ${artifact.file_name}`.toLowerCase();
  if (value.includes('export') || value.includes('package') || value.includes('zip')) return 'exports';
  if (artifact.worker_name === 'governance_reviewer_agent') return 'governance';
  if (artifact.worker_name === 'listing_operations_agent') return 'listings';
  if (artifact.worker_name === 'compliance_specialist_agent') return 'compliance';
  if (artifact.worker_name === 'catalog_steward_agent') return 'catalog';
  if (value.includes('listing') || value.includes('shopify') || value.includes('ebay')) return 'listings';
  if (value.includes('compliance') || value.includes('policy')) return 'compliance';
  if (value.includes('governance') || value.includes('review') || value.includes('approval')) return 'governance';
  if (value.includes('catalog') || value.includes('product') || value.includes('sku') || value.includes('taxonomy')) return 'catalog';
  return 'reports';
}

/** Pure UI projection. Never invents plan steps outside TaskDetail.task.steps. */
export function projectTaskWorkspace(
  detail: TaskDetail,
  events: ProductEvent[],
  messages: RawMessage[] = [],
): TaskWorkspaceProjection {
  const steps = new Map((detail.task.steps || []).map((step) => [step.id, seedStep(step)]));
  const artifacts = new Map<string, Artifact>();
  detail.artifacts.forEach((artifact) => {
    artifacts.set(artifact.id, artifact);
    if (artifact.process_task_id) steps.get(artifact.process_task_id)?.artifacts.push(artifact);
  });

  let lastSequence = 0;
  let hasGap = false;
  const ordered = [...events].sort((left, right) => left.sequence - right.sequence);
  for (const event of ordered) {
    if (event.sequence <= lastSequence) continue;
    if (event.sequence !== lastSequence + 1) {
      hasGap = true;
      break;
    }
    lastSequence = event.sequence;
    const payload = record(event.payload_json);
    const processTaskId = text(payload.process_task_id, payload.task_id);
    const step = processTaskId && processTaskId !== detail.task.id ? steps.get(processTaskId) || null : null;
    if (!step) continue;

    if (event.action === 'agent_progress') {
      const line = text(payload.message);
      if (line && !looksLikeRawPayload(line) && step.progressLines.at(-1) !== line) {
        step.progressLines.push(valueTrim(line));
      }
    } else if (event.action === 'activate_toolkit' || event.action === 'deactivate_toolkit') {
      const toolCallId = text(payload.tool_call_id);
      if (!toolCallId) continue;
      const existing = step.tools.find((tool) => tool.id === toolCallId);
      const next: ToolSummary = {
        id: toolCallId,
        label: toolDisplay(payload) || existing?.label || '业务工具',
        status: event.action === 'activate_toolkit'
          ? 'running'
          : String(payload.status).toLowerCase() === 'failed' ? 'failed' : 'completed',
      };
      if (existing) Object.assign(existing, next);
      else step.tools.push(next);
    }
  }

  const projectedSteps = Array.from(steps.values()).sort((left, right) => left.sequence - right.sequence);
  const doneCount = projectedSteps.filter((step) => ['completed', 'done'].includes(step.status)).length;
  const currentStep = projectedSteps.find((step) => step.status === 'running')
    || projectedSteps.find((step) => ['planned', 'queued', 'waiting', 'waiting_approval', 'blocked'].includes(step.status))
    || projectedSteps.find((step) => !['completed', 'done'].includes(step.status))
    || null;

  const toolCapabilities = Array.from(new Set(
    projectedSteps.flatMap((step) => step.tools.map((tool) => tool.label)).filter(Boolean),
  ));

  return {
    lastSequence,
    hasGap,
    steps: projectedSteps,
    artifacts: Array.from(artifacts.values()),
    activity: mergeActivity(events, messages, detail.task.steps || []),
    handoffs: projectHandoffs(projectedSteps, events),
    currentStep,
    participatingAgents: Array.from(new Set(projectedSteps.map((step) => step.workerName).filter(Boolean))),
    toolCapabilities,
    progressPercent: projectedSteps.length
      ? Math.round((doneCount / projectedSteps.length) * 100)
      : detail.task.status === 'completed' ? 100 : 0,
    resources: detail.resources || [],
  };
}
