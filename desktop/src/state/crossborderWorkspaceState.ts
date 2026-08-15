import type { Artifact, ProductEvent, TaskDetail, TaskStep } from '../api';
import type { CoworkArtifact, CoworkTask, CoworkTaskDetail } from '../types';
import type { Task } from '../store/chatStore';

const WORKERS = [
  { id: 'catalog_steward_agent', name: 'Catalog Steward', type: 'developer_agent' as const, tools: ['inspect_product', 'classify_product', 'build_sku_graph'] },
  { id: 'compliance_specialist_agent', name: 'Compliance Specialist', type: 'document_agent' as const, tools: ['load_compliance_skill', 'check_us_apparel', 'validate_marketplace_policy'] },
  { id: 'listing_operations_agent', name: 'Listing Operations', type: 'document_agent' as const, tools: ['load_localization_skill', 'build_shopify_draft', 'build_ebay_draft'] },
  { id: 'governance_reviewer_agent', name: 'Governance Reviewer', type: 'document_agent' as const, tools: ['validate_evidence', 'review_release_readiness', 'request_human_approval'] },
];

function status(value?: string): AgentStatus {
  if (value === 'running') return 'running';
  if (value === 'completed') return 'completed';
  if (value === 'failed') return 'failed';
  return 'pending';
}

function workerId(name?: string): string {
  const value = String(name || '').toLowerCase();
  if (value.includes('catalog') || value.includes('steward')) return 'catalog_steward_agent';
  if (value.includes('compliance')) return 'compliance_specialist_agent';
  if (value.includes('listing')) return 'listing_operations_agent';
  if (value.includes('governance') || value.includes('review')) return 'governance_reviewer_agent';
  return '';
}

function fileInfo(artifact: Artifact): FileInfo {
  return {
    name: artifact.file_name,
    type: artifact.mime_type,
    path: artifact.file_name,
    artifact_id: artifact.id,
    artifact_type: artifact.artifact_type,
    mime_type: artifact.mime_type,
    size_bytes: artifact.size_bytes,
    worker_task_id: artifact.worker_name,
  };
}

function taskInfo(step: TaskStep, artifacts: Artifact[]): TaskInfo {
  const files = artifacts.filter((artifact) => artifact.worker_name === step.worker_name).map(fileInfo);
  const result = step.result && Object.keys(step.result).length > 0 ? JSON.stringify(step.result, null, 2) : undefined;
  return {
    id: step.id,
    content: step.title,
    status: status(step.status) as TaskInfo['status'],
    report: result,
    fileList: files,
  };
}

export function projectTask(detail: TaskDetail, events: ProductEvent[]): CoworkTask {
  const task = detail.task;
  return {
    id: task.id,
    objective: task.objective,
    status: task.status,
    kind: 'task',
    created_at: task.updated_at,
    updated_at: task.updated_at,
    error_message: task.error,
    result_json: task.result as Record<string, unknown> | undefined,
  };
}

export function projectDetail(detail: TaskDetail, events: ProductEvent[]): CoworkTaskDetail {
  const task = projectTask(detail, events);
  return {
    task,
    steps: (detail.task.steps || []) as unknown as Array<Record<string, unknown>>,
    events: detail.events.map((event) => ({
      id: `${detail.task.id}:${event.sequence}`,
      event_type: event.event_type,
      worker_name: event.worker_name,
      cowork_task_id: detail.task.id,
      payload_json: event.payload,
      created_at: event.created_at,
    })),
    artifacts: detail.artifacts.map((artifact): CoworkArtifact => ({
      id: artifact.id,
      project_id: '',
      cowork_task_id: detail.task.id,
      run_id: '',
      worker_task_id: artifact.worker_name,
      artifact_type: artifact.artifact_type,
      title: artifact.title,
      file_name: artifact.file_name,
      absolute_path: '',
      relative_path: artifact.file_name,
      mime_type: artifact.mime_type,
      size_bytes: artifact.size_bytes,
      sha256: '',
      cited_evidence_ids: [],
      inspected_evidence_count: 0,
      metadata: {},
      status: 'available',
      created_at: artifact.created_at,
    })),
    approvals: detail.approvals.map((approval) => ({
      id: approval.id,
      cowork_task_id: detail.task.id,
      worker_task_id: approval.approval_type,
      prompt: approval.description,
      interrupt_type: approval.approval_type,
      status: approval.status,
      request_json: approval.payload,
    })),
  };
}

export function projectNativeTask(detail: TaskDetail, events: ProductEvent[]): Task {
  const steps = detail.task.steps || [];
  const byWorker = new Map<string, TaskInfo[]>();
  steps.forEach((step) => {
    const id = workerId(step.worker_name);
    if (!id) return;
    const list = byWorker.get(id) || [];
    list.push(taskInfo(step, detail.artifacts));
    byWorker.set(id, list);
  });
  const taskAssigning: Agent[] = WORKERS.map((worker) => {
    const workerEvents = events.filter((event) => workerId(String(event.payload_json.worker_name || event.payload_json.agent_name || '')) === worker.id);
    const tasks = byWorker.get(worker.id) || [];
    const latest = tasks[tasks.length - 1];
    const derivedStatus = latest?.status || (workerEvents.length ? 'running' : 'pending');
    return {
      agent_id: worker.id,
      sourceWorkerName: worker.id,
      name: worker.name,
      type: worker.type,
      status: derivedStatus as AgentStatus,
      tools: worker.tools,
      tasks,
      log: workerEvents.map((event) => ({
        step: event.action === 'error' ? 'error' : event.action === 'end' ? 'end' : 'notice',
        data: { message: String(event.payload_json.message || event.payload_json.summary || event.action), agent_name: worker.name },
        created_at: event.created_at,
      })) as AgentMessage[],
    };
  });
  const messages: Message[] = events.map((event) => ({
    id: event.id,
    role: event.action === 'ask' || event.action === 'human_response' ? 'agent' : 'agent',
    content: String(event.payload_json.message || event.payload_json.summary || event.payload_json.output || event.action),
    step: event.action === 'end' ? 'end' : event.action === 'error' ? 'error' : 'notice',
    agent_id: workerId(String(event.payload_json.worker_name || event.payload_json.agent_name || '')) || undefined,
    task_id: detail.task.id,
  }));
  const files = detail.artifacts.map(fileInfo);
  const completed = taskAssigning.reduce((sum, agent) => sum + agent.tasks.filter((item) => item.status === 'completed').length, 0);
  const total = Math.max(steps.length, taskAssigning.length);
  return {
    id: detail.task.id,
    summaryTask: detail.task.objective,
    messages,
    taskInfo: steps.map((step) => taskInfo(step, detail.artifacts)),
    taskAssigning,
    progressValue: total ? Math.round((completed / total) * 100) : detail.task.status === 'completed' ? 100 : 0,
    fileList: files,
    activeWorkspace: 'workflow',
  };
}

export { WORKERS };
