import type { Artifact, ProductEvent, ProjectResource, TaskDetail, TaskStep } from '../api';
import type { CoworkArtifact, CoworkTask, CoworkTaskDetail } from '../types';
import type { Task } from '../store/chatStore';
import { agentLabel, localizedMessage, stepLabel } from '../lib/crossborderLabels';

interface WorkerDefinition {
  id: string;
  name: string;
  type: AgentNameType;
  tools: string[];
}

interface ReducedTool {
  id: string;
  name: string;
  method: string;
  status: AgentStatus;
}

interface ReducedStep {
  id: string;
  sequence: number;
  workerName: string;
  content: string;
  status: TaskInfo['status'];
  summary: string;
  dependencies: string[];
  outputResourceIds: string[];
  progressLines: string[];
  tools: Map<string, ReducedTool>;
  artifacts: Map<string, Artifact>;
}

export interface ReducedWorkspaceState {
  lastSequence: number;
  hasGap: boolean;
  steps: ReducedStep[];
  artifacts: Artifact[];
  messages: Message[];
}

export const WORKERS: WorkerDefinition[] = [
  { id: 'catalog_steward_agent', name: '商品目录专员', type: 'developer_agent', tools: ['inspect_product', 'classify_product', 'build_sku_graph'] },
  { id: 'compliance_specialist_agent', name: '合规专员', type: 'document_agent', tools: ['load_compliance_skill', 'check_us_apparel', 'validate_marketplace_policy'] },
  { id: 'listing_operations_agent', name: '商品刊登专员', type: 'document_agent', tools: ['load_localization_skill', 'build_shopify_draft', 'build_ebay_draft'] },
  { id: 'governance_reviewer_agent', name: '治理审核员', type: 'document_agent', tools: ['validate_evidence', 'review_release_readiness', 'request_human_approval'] },
];

const WORKER_BY_ID = new Map(WORKERS.map((worker) => [worker.id, worker]));

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String).filter(Boolean) : [];
}

function text(...values: unknown[]): string {
  const found = values.find((value) => typeof value === 'string' && value.trim());
  return typeof found === 'string' ? found.trim() : '';
}

function stepStatus(value?: string): TaskInfo['status'] {
  const normalized = String(value || '').toLowerCase();
  if (['running', 'started'].includes(normalized)) return 'running';
  if (['completed', 'done', 'succeeded'].includes(normalized)) return 'completed';
  if (['failed', 'error'].includes(normalized)) return 'failed';
  if (['blocked', 'waiting_approval'].includes(normalized)) return 'blocked';
  return 'waiting';
}

function agentStatus(steps: ReducedStep[]): AgentStatus {
  if (steps.some((step) => step.status === 'running')) return 'running';
  if (steps.some((step) => step.status === 'failed' || step.status === 'blocked')) return 'failed';
  if (steps.length > 0 && steps.every((step) => step.status === 'completed')) return 'completed';
  return 'pending';
}

function workspaceState(steps: ReducedStep[]): Agent['workspaceState'] {
  if (steps.length === 0) return 'not_started';
  if (steps.some((step) => step.status === 'running')) return 'running';
  if (steps.some((step) => step.status === 'failed' || step.status === 'blocked')) return 'failed';
  const hasOutput = steps.some((step) => step.summary || step.outputResourceIds.length || step.artifacts.size);
  return hasOutput ? 'completed' : 'empty';
}

function artifactFile(artifact: Artifact): FileInfo {
  return {
    name: artifact.file_name,
    type: artifact.mime_type,
    path: artifact.relative_path || artifact.file_name,
    artifact_id: artifact.id,
    artifact_type: artifact.artifact_type,
    mime_type: artifact.mime_type,
    size_bytes: artifact.size_bytes,
    sha256: artifact.sha256,
    project_id: artifact.project_id,
    worker_task_id: artifact.process_task_id,
    agent_id: artifact.worker_name,
  };
}

function seedStep(step: TaskStep): ReducedStep {
  return {
    id: step.id,
    sequence: step.sequence,
    workerName: step.worker_name,
    content: step.title,
    status: stepStatus(step.status),
    summary: text(step.result?.summary),
    dependencies: strings(step.dependencies),
    outputResourceIds: strings(step.result?.output_resource_ids),
    progressLines: [],
    tools: new Map(),
    artifacts: new Map(),
  };
}

function ensureStep(steps: Map<string, ReducedStep>, id: string, payload: Record<string, unknown>): ReducedStep | null {
  if (!id) return null;
  const existing = steps.get(id);
  if (existing) return existing;
  const created: ReducedStep = {
    id,
    sequence: steps.size + 1,
    workerName: text(payload.worker_name, payload.agent_id),
    content: text(payload.content, payload.title, id),
    status: stepStatus(String(payload.state || 'waiting')),
    summary: '',
    dependencies: strings(payload.dependencies),
    outputResourceIds: [],
    progressLines: [],
    tools: new Map(),
    artifacts: new Map(),
  };
  steps.set(id, created);
  return created;
}

function eventStepId(payload: Record<string, unknown>): string {
  return text(payload.process_task_id, payload.task_id);
}

function eventWorker(payload: Record<string, unknown>): string {
  return text(payload.worker_name, payload.agent_id);
}

export function reduceWorkspaceState(detail: TaskDetail, events: ProductEvent[]): ReducedWorkspaceState {
  const steps = new Map((detail.task.steps || []).map((step) => [step.id, seedStep(step)]));
  const artifacts = new Map<string, Artifact>();
  detail.artifacts.forEach((artifact) => {
    artifacts.set(artifact.id, artifact);
    if (artifact.process_task_id) steps.get(artifact.process_task_id)?.artifacts.set(artifact.id, artifact);
  });
  const messages: Message[] = [];
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
    const processTaskId = eventStepId(payload);
    const workerName = eventWorker(payload);
    const step = processTaskId === detail.task.id ? null : ensureStep(steps, processTaskId, payload);

    if (event.action === 'assign_task' && step) {
      step.workerName = workerName || step.workerName;
      step.content = text(payload.content, step.content);
      step.dependencies = strings(payload.dependencies);
      step.status = 'waiting';
    } else if (event.action === 'activate_agent' && step) {
      step.workerName = workerName || step.workerName;
      step.status = 'running';
    } else if (event.action === 'task_state' && step) {
      step.workerName = workerName || step.workerName;
      step.status = stepStatus(String(payload.state || ''));
      step.summary = text(payload.summary, payload.result, step.summary);
      step.outputResourceIds = strings(payload.output_resource_ids);
    } else if (event.action === 'deactivate_agent' && step) {
      step.status = stepStatus(String(payload.state || 'completed'));
      step.summary = text(payload.message, step.summary);
    } else if (event.action === 'agent_progress' && step) {
      const line = text(payload.message);
      if (line && step.progressLines.at(-1) !== line) step.progressLines.push(line);
    } else if ((event.action === 'activate_toolkit' || event.action === 'deactivate_toolkit') && step) {
      const toolCallId = text(payload.tool_call_id);
      if (toolCallId) {
        const current = step.tools.get(toolCallId);
        step.tools.set(toolCallId, {
          id: toolCallId,
          name: text(payload.toolkit_name, current?.name, payload.method_name, '业务工具'),
          method: text(payload.method_name, current?.method),
          status: event.action === 'activate_toolkit'
            ? 'running'
            : String(payload.status).toLowerCase() === 'failed' ? 'failed' : 'completed',
        });
      }
    } else if (event.action === 'write_file') {
      const rawArtifact = record(payload.file);
      const artifactId = text(payload.artifact_id, rawArtifact.id);
      if (artifactId) {
        const artifact = {
          ...rawArtifact,
          id: artifactId,
          process_task_id: text(rawArtifact.process_task_id, processTaskId),
          worker_name: text(rawArtifact.worker_name, workerName),
        } as unknown as Artifact;
        artifacts.set(artifactId, artifact);
        if (step) step.artifacts.set(artifactId, artifact);
      }
    }

    if (event.action === 'agent_progress' && step) {
      const line = text(payload.message);
      if (line) messages.push({ id: event.id, role: 'agent', content: line, step: 'notice', agent_id: step.workerName, task_id: processTaskId });
    }
    if (event.action === 'error' || event.action === 'end') {
      const summary = text(payload.summary, payload.message);
      if (summary) messages.push({ id: event.id, role: 'agent', content: summary, step: event.action, task_id: detail.task.id });
    }
  }

  return {
    lastSequence,
    hasGap,
    steps: Array.from(steps.values()).sort((left, right) => left.sequence - right.sequence),
    artifacts: Array.from(artifacts.values()),
    messages,
  };
}

function nativeTaskInfo(step: ReducedStep): TaskInfo {
  return {
    id: step.id,
    content: stepLabel(step.content),
    status: step.status,
    report: step.summary || undefined,
    terminal: step.progressLines,
    progressLines: step.progressLines,
    outputResourceIds: step.outputResourceIds,
    dependencies: step.dependencies,
    fileList: Array.from(step.artifacts.values()).map(artifactFile),
    toolkits: Array.from(step.tools.values()).map((tool) => ({
      toolkitId: tool.id,
      toolkitName: tool.name,
      toolkitMethods: tool.method,
      message: '',
      toolkitStatus: tool.status,
    })),
  };
}

function workerDefinition(workerName: string): WorkerDefinition {
  return WORKER_BY_ID.get(workerName) || {
    id: workerName,
    name: agentLabel(workerName),
    type: 'single_agent',
    tools: [],
  };
}

export function projectTask(detail: TaskDetail, _events: ProductEvent[]): CoworkTask {
  const task = detail.task;
  return {
    id: task.id,
    objective: task.objective,
    status: task.status,
    kind: 'task',
    created_at: task.updated_at,
    updated_at: task.updated_at,
    error_message: task.error ? localizedMessage(task.error) : '',
  };
}

function coworkArtifact(artifact: Artifact, taskId: string): CoworkArtifact {
  return {
    id: artifact.id,
    project_id: artifact.project_id,
    cowork_task_id: taskId,
    run_id: '',
    worker_task_id: artifact.process_task_id,
    artifact_type: artifact.artifact_type,
    title: artifact.title,
    file_name: artifact.file_name,
    absolute_path: '',
    relative_path: artifact.relative_path,
    mime_type: artifact.mime_type,
    size_bytes: artifact.size_bytes,
    sha256: artifact.sha256,
    cited_evidence_ids: [],
    inspected_evidence_count: 0,
    metadata: artifact.metadata || {},
    status: 'available',
    created_at: artifact.created_at,
  };
}

export function projectDetail(detail: TaskDetail, events: ProductEvent[]): CoworkTaskDetail {
  const reduced = reduceWorkspaceState(detail, events);
  const humanInterrupts = detail.approvals.map((approval) => ({
    id: approval.id,
    cowork_task_id: detail.task.id,
    worker_task_id: text(approval.payload?.process_task_id),
    prompt: approval.description,
    interrupt_type: 'approval',
    status: approval.status,
    request_json: approval.payload,
  }));
  return {
    task: projectTask(detail, events),
    steps: reduced.steps.map((step) => ({ id: step.id, worker_name: step.workerName, title: step.content, status: step.status, result: { summary: step.summary } })),
    artifacts: reduced.artifacts.map((artifact) => coworkArtifact(artifact, detail.task.id)),
    approvals: humanInterrupts,
    camel_workforce: { human_interrupts: humanInterrupts },
  };
}

export function projectNativeTask(detail: TaskDetail, events: ProductEvent[]): Task {
  const reduced = reduceWorkspaceState(detail, events);
  const workerNames = new Set(WORKERS.map((worker) => worker.id));
  reduced.steps.forEach((step) => { if (step.workerName) workerNames.add(step.workerName); });
  const taskAssigning: Agent[] = Array.from(workerNames).map((workerName) => {
    const definition = workerDefinition(workerName);
    const ownedSteps = reduced.steps.filter((step) => step.workerName === workerName);
    return {
      agent_id: workerName,
      sourceWorkerName: workerName,
      name: definition.name,
      type: definition.type,
      status: agentStatus(ownedSteps),
      workspaceState: workspaceState(ownedSteps),
      tools: [],
      tasks: ownedSteps.map(nativeTaskInfo),
      log: ownedSteps.flatMap((step) => step.progressLines.map((line) => ({
        step: 'notice' as const,
        data: { message: line, agent_name: definition.name, process_task_id: step.id },
      }))),
    };
  });
  const completed = reduced.steps.filter((step) => step.status === 'completed').length;
  const terminal = reduced.steps.filter((step) => ['completed', 'failed', 'blocked'].includes(step.status || '')).length;
  const progressValue = reduced.steps.length
    ? Math.round(((completed + Math.max(0, terminal - completed)) / reduced.steps.length) * 100)
    : detail.task.status === 'completed' ? 100 : 0;
  return {
    id: detail.task.id,
    summaryTask: detail.task.objective,
    messages: reduced.messages,
    taskInfo: reduced.steps.map(nativeTaskInfo),
    taskAssigning,
    progressValue,
    fileList: reduced.artifacts.map(artifactFile),
    activeWorkspace: 'workflow',
  };
}

export function resourcesForWorker(resources: ProjectResource[], workerName: string): ProjectResource[] {
  return resources.filter((resource) => resource.owner_worker_name === workerName);
}
