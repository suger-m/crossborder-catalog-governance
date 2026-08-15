export type CoworkTaskStatus =
  | 'pending'
  | 'planned'
  | 'running'
  | 'waiting_approval'
  | 'waiting_human_input'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | string;

export interface CoworkTask {
  id: string;
  objective: string;
  status: CoworkTaskStatus;
  kind?: 'task' | 'chat';
  scenario?: string;
  risk_level?: string;
  created_at?: string;
  updated_at?: string;
  error_message?: string;
  result_json?: Record<string, unknown>;
}

export interface CoworkArtifact {
  id: string;
  project_id: string;
  cowork_task_id: string;
  run_id: string;
  worker_task_id: string;
  artifact_type: 'evidence_bundle' | 'analysis_report_markdown' | 'review_report_markdown' | string;
  title: string;
  file_name: string;
  absolute_path: string;
  relative_path: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  cited_evidence_ids: string[];
  inspected_evidence_count: number;
  metadata: Record<string, unknown>;
  status: string;
  created_at: string;
}

export interface CoworkEvidencePreviewItem {
  evidence_id: string;
  rank?: number;
  chunk_role?: string;
  chunk_text?: string;
  document_id?: string;
  source_platform?: string;
  source_type?: string;
  published_at?: string;
  final_score?: number;
  learned_score?: number;
  quality_score?: number;
  engagement_score?: number;
  tags?: string[];
  hashtags?: string[];
  size_labels?: string[];
  matched_routes?: string[];
  route_scores?: Record<string, number>;
  expanded_from?: string;
  parent_query?: string;
}

export interface CoworkEvidencePreview {
  artifact_id: string;
  title: string;
  status: string;
  query: string;
  total_evidence_count: number;
  returned_count: number;
  omitted_count: number;
  source_breakdown: Array<{ source: string; count: number }>;
  time_range: Record<string, string>;
  route_counts: Record<string, number>;
  retrieval_log_id: string;
  retrieval_summary: {
    returned_count?: number;
    total_result_count?: number;
    omitted_count?: number;
    truncated?: boolean;
    truncation_reasons?: string[];
  };
  evidence: CoworkEvidencePreviewItem[];
}

export interface CoworkProject {
  id: string;
  name: string;
  description?: string;
  status?: 'active' | 'archived' | string;
  metadata?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
  task_count?: number;
  message_count?: number;
}

export interface CoworkChatMessage {
  id: string;
  project_id: string;
  role: 'user' | 'assistant' | string;
  content: string;
  metadata?: Record<string, unknown>;
  created_at?: string;
}

export interface CoworkChatResponse {
  project_id: string;
  mode: string;
  user_message?: CoworkChatMessage;
  assistant_message?: CoworkChatMessage;
  messages: CoworkChatMessage[];
  context_too_long?: {
    message: string;
    current_length?: number;
    max_length?: number;
  };
}

export interface CoworkSubmissionIntent {
  intent: 'chat' | 'task';
  source: 'model' | 'attachment' | 'fallback' | string;
  model?: string;
}

export interface CoworkSubmitResponse {
  project_id: string;
  mode: 'simple_chat' | 'automation_task' | 'context_too_long' | string;
  intent: CoworkSubmissionIntent;
  task?: CoworkTaskDetail;
  start_error?: string;
  user_message?: CoworkChatMessage;
  assistant_message?: CoworkChatMessage;
  messages?: CoworkChatMessage[];
  context_too_long?: {
    message: string;
    current_length?: number;
    max_length?: number;
  };
}

export interface CoworkInputAttachment {
  fileName: string;
  filePath: string;
  extension?: string;
  file?: File;
}

export interface WorkerTask {
  id: string;
  run_id?: string;
  cowork_task_id?: string;
  worker_id?: string;
  worker_name?: string;
  parent_task_id?: string;
  content?: string;
  status?: string;
  result_summary?: string;
  output_json?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
  artifacts?: CoworkArtifact[];
}

export interface WorkforceEvent {
  id: string;
  run_id?: string;
  cowork_task_id?: string;
  event_type: string;
  source?: string;
  worker_id?: string;
  worker_name?: string;
  worker_task_id?: string;
  payload_json?: Record<string, unknown>;
  created_at?: string;
}

export interface ToolCall {
  id: string;
  run_id?: string;
  cowork_task_id?: string;
  worker_task_id?: string;
  worker_id?: string;
  worker_name?: string;
  tool_name: string;
  status: string;
  input_json?: Record<string, unknown>;
  output_json?: Record<string, unknown>;
  error_message?: string;
  created_at?: string;
  finished_at?: string;
}

export interface HumanInterrupt {
  id: string;
  run_id?: string;
  cowork_task_id?: string;
  worker_task_id?: string;
  worker_id?: string;
  interrupt_type?: string;
  prompt?: string;
  status: string;
  request_json?: Record<string, unknown>;
  response_json?: Record<string, unknown>;
  decision_comment?: string;
  created_at?: string;
  resolved_at?: string;
}

export interface CamelWorkforceState {
  latest_run?: {
    id: string;
    status: string;
    result_json?: Record<string, unknown>;
    error_message?: string;
  } | null;
  runs?: Array<Record<string, unknown>>;
  worker_tasks?: WorkerTask[];
  events?: WorkforceEvent[];
  tool_calls?: ToolCall[];
  human_interrupts?: HumanInterrupt[];
  workspace_events?: WorkforceEvent[];
}

export interface CoworkTaskDetail {
  task: CoworkTask;
  plan?: {
    steps?: Array<Record<string, unknown>>;
    [key: string]: unknown;
  } | null;
  steps?: Array<Record<string, unknown>>;
  camel_workforce?: CamelWorkforceState;
  events?: WorkforceEvent[];
  tool_calls?: ToolCall[];
  approvals?: HumanInterrupt[];
  artifacts?: CoworkArtifact[];
}

export interface TaskListResponse {
  items?: CoworkTask[];
  project_id?: string;
}

export enum TriggerType {
  Schedule = 'schedule',
  Webhook = 'webhook',
  Slack = 'slack_trigger',
}

export enum TriggerStatus {
  PendingAuth = 'pending_verification',
  Inactive = 'inactive',
  Active = 'active',
}

export enum ListenerType {
  Workforce = 'workforce',
}

export enum ExecutionType {
  Scheduled = 'scheduled',
  Webhook = 'webhook',
  Slack = 'slack',
}

export enum RequestType {
  GET = 'GET',
  POST = 'POST',
}

export enum ExecutionStatus {
  Pending = 'pending',
  Running = 'running',
  Completed = 'completed',
  Failed = 'failed',
  Cancelled = 'cancelled',
  Missed = 'missed',
}

export type Trigger = {
  id: number;
  user_id: string;
  name: string;
  project_id?: string;
  description: string;
  trigger_type: TriggerType;
  status: TriggerStatus;
  webhook_url?: string;
  custom_cron_expression?: string;
  listener_type?: ListenerType;
  webhook_method?: RequestType;
  agent_model?: string;
  task_prompt?: string;
  custom_task?: Record<string, unknown>;
  max_executions_per_hour?: number;
  max_executions_per_day?: number;
  is_single_execution: boolean;
  last_executed_at?: string;
  last_execution_status?: string;
  next_run_at?: string;
  consecutive_failures?: number;
  auto_disabled_at?: string;
  created_at?: string;
  updated_at?: string;
  execution_count?: number;
  config?: Record<string, unknown>;
};

export type TriggerInput = {
  name: string;
  description?: string;
  project_id?: string;
  trigger_type: TriggerType;
  custom_cron_expression?: string;
  webhook_url?: string;
  webhook_method?: RequestType;
  listener_type?: ListenerType;
  agent_model?: string;
  task_prompt?: string;
  custom_task?: Record<string, unknown>;
  max_executions_per_hour?: number;
  max_executions_per_day?: number;
  is_single_execution?: boolean;
  config?: Record<string, unknown>;
};

export type TriggerUpdate = {
  name?: string;
  description?: string;
  project_id?: string;
  status?: TriggerStatus;
  custom_cron_expression?: string;
  listener_type?: ListenerType;
  webhook_method?: RequestType;
  agent_model?: string;
  task_prompt?: string;
  custom_task?: Record<string, unknown>;
  max_executions_per_hour?: number;
  max_executions_per_day?: number;
  is_single_execution?: boolean;
  config?: Record<string, unknown>;
};

export interface WorkerTaskView {
  id: string;
  content: string;
  status: 'completed' | 'failed' | 'waiting' | 'running' | 'blocked' | '';
  result?: string;
  report?: string;
  toolkits: ToolCall[];
  terminal?: string[];
  fileList?: FileInfo[];
  failure_count?: number;
  reAssignTo?: string;
  sourceWorkerName?: string;
  sourceToolNames?: string[];
  isSyntheticToolTask?: boolean;
}

export type CoworkWorkspaceType =
  | 'developer_agent'
  | 'browser_agent'
  | 'document_agent'
  | 'multi_modal_agent'
  | 'social_media_agent';

export interface WorkerNodeView {
  [key: string]: unknown;
  agent_id: string;
  name: string;
  type:
    | 'retrieval_worker'
    | 'source_ingest_worker'
    | 'analysis_worker'
    | 'reviewer'
    | 'reviewer_worker'
    | 'planner'
    | 'human'
    | 'worker';
  status: 'pending' | 'running' | 'completed' | 'failed';
  tools: string[];
  tasks: WorkerTaskView[];
  log: WorkforceEvent[];
  workspace_type?: CoworkWorkspaceType;
}
