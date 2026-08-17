export interface Project { id: string; name: string; created_at: string; updated_at: string }
export interface ProjectMaterial { id: string; project_id: string; file_name: string; relative_path: string; mime_type: string; size_bytes: number; sha256: string; origin: 'upload' | 'example' | string; metadata: Record<string, unknown>; created_at: string }
export interface HealthStatus { status: string; app_id: string; app_version: string; protocol_name: 'agentteams' | string; protocol_version: number }
export interface TaskStepResult { summary?: string; key_counts?: Record<string, number>; output_resource_ids?: string[]; [key: string]: unknown }
export interface TaskStep { id: string; sequence: number; worker_name: string; title: string; status: string; dependencies?: string[]; result: TaskStepResult }
export interface Task { id: string; project_id: string; objective: string; status: string; current_step?: string; input?: Record<string, unknown>; result?: TaskResult; error?: string; updated_at: string; steps?: TaskStep[] }
export interface Artifact { id: string; project_id: string; worker_name: string; process_task_id: string; artifact_type: string; title: string; file_name: string; relative_path: string; mime_type: string; size_bytes: number; sha256: string; metadata: Record<string, unknown>; created_at: string }
export interface ArtifactPreview { artifact: Artifact; content: string | null; offset: number; next_offset: number | null; truncated: boolean }
export interface ProjectResource {
  id: string;
  project_id: string;
  resource_type: string;
  logical_key: string;
  version: number;
  status: 'candidate' | 'active' | 'superseded' | 'blocked' | 'rejected' | string;
  owner_worker_name: string;
  source_task_id: string;
  source_step_id: string;
  artifact_id?: string;
  entity_id?: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
}
export interface Approval { id: string; approval_type: string; title: string; description: string; payload: Record<string, unknown>; status: 'pending' | 'approved' | 'rejected' | string }
export interface Finding { id: string; product_id: string; title?: string; message: string; status?: string; severity?: string; scope?: string; field?: string; platforms?: string[] }
export interface ListingDraft { id: string; product_id: string; platform: 'shopify' | 'ebay_us' | string; title: string; description: string; category: string; derived_from_product_version: number; platform_rule_version: string; data: Record<string, unknown>; gaps: Array<{ field: string; reason: string; severity: string }> }
export interface TaskResult {
  summary?: string;
  key_counts?: Record<string, number>;
  output_resource_ids?: string[];
  completed_at?: string;
}
export interface TaskDetail { task: Task; events: TaskEvent[]; artifacts: Artifact[]; approvals: Approval[]; resources?: ProjectResource[] }
export interface TaskEvent { sequence: number; event_type: string; worker_name: string; payload: Record<string, unknown>; created_at: string }
export interface ProductEvent {
  id: string;
  task_id: string;
  run_id: string;
  sequence: number;
  protocol_name: 'agentteams' | string;
  protocol_version: number;
  action: string;
  payload_json: Record<string, unknown>;
  source_kind: string;
  source_event_id: string;
  source_ordinal: number;
  created_at: string;
}
export type AgentWorkspaceState = 'not_started' | 'running' | 'empty' | 'failed' | 'completed';
export interface AgentWorkspace {
  project_id: string;
  worker_name: string;
  state: AgentWorkspaceState;
  steps: TaskStep[];
  resources: ProjectResource[];
  artifacts: Artifact[];
  products?: ProductSummary[];
  listings?: ListingDraft[];
  findings?: Finding[];
  approvals?: Approval[];
  summary?: string;
  error?: string;
}
export interface ProductSummary { id: string; external_id: string; title: string; version: number; status: string; data: CanonicalProduct }
export interface ProductDetail extends ProductSummary { graph: { nodes: GraphNode[]; edges: GraphEdge[] } }
export interface GraphNode { id: string; node_type: string; state: string; version: number; data: Record<string, unknown> }
export interface GraphEdge { id: string; source_id: string; target_id: string; relation_type: string }
export interface SourceEvidence { source_document_id: string; file_name: string; location: string; text: string }
export interface ProductFact { id: string; field_name: string; value: unknown; state: string; confidence: number; evidence: SourceEvidence }
export interface CanonicalSku { id: string; external_id: string; color: string; size: string; barcode: string; price: string; inventory?: number; facts: ProductFact[] }
export interface CanonicalProduct { id: string; external_id: string; title: string; description: string; category: string; garment_type: string; materials: string[]; fiber_content: string; care_instructions: string; country_of_origin: string; manufacturer: string; claims: string[]; images: string[]; tags: string[]; skus: CanonicalSku[]; facts: ProductFact[]; version: number; status: string }
export interface ModelSettings { source: string; model_platform: string; model_type: string; api_url: string; extra_params: Record<string, unknown>; has_api_key: boolean; version: number; updated_at: string }
export interface ModelSettingsPayload { source: string; model_platform: string; model_type: string; api_key?: string; api_url: string; extra_params: Record<string, unknown> }
export interface SkillSummary { name: string; description: string }
export interface SkillDetail { name: string; content: string }
export type ModelRoleStatus = Record<string, { configured?: boolean; source?: string; model_platform?: string; model_type?: string; ok?: boolean; error?: string }>;

const runtimeApiUrl = new URLSearchParams(window.location.search).get('apiBaseUrl');
const baseUrl = (runtimeApiUrl || import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${baseUrl}${path}`, { ...init, headers });
  if (!response.ok) {
    const text = await response.text();
    let detail = text;
    try {
      const parsed = JSON.parse(text) as { detail?: unknown };
      detail = typeof parsed.detail === 'string' ? parsed.detail : JSON.stringify(parsed.detail || parsed);
    } catch { /* Keep the response body as-is. */ }
    throw new Error(`${response.status}: ${detail}`);
  }
  return (await response.json()) as T;
}
export const api = {
  health: () => request<HealthStatus>('/health'), projects: () => request<{ items: Project[] }>('/api/projects'),
  createProject: (name: string) => request<{ project: Project }>('/api/projects', { method: 'POST', body: JSON.stringify({ name }) }),
  projectMaterials: (projectId: string) => request<{ items: ProjectMaterial[] }>(`/api/projects/${encodeURIComponent(projectId)}/materials`),
  uploadProjectMaterials: (projectId: string, files: File[]) => { const body = new FormData(); files.forEach((file) => body.append('files', file)); return request<{ items: ProjectMaterial[] }>(`/api/projects/${encodeURIComponent(projectId)}/materials`, { method: 'POST', body }); },
  importExampleMaterials: (projectId: string) => request<{ items: ProjectMaterial[] }>(`/api/projects/${encodeURIComponent(projectId)}/materials/import-example`, { method: 'POST' }),
  projectMaterialDownloadUrl: (materialId: string) => `${baseUrl}/api/project-materials/${encodeURIComponent(materialId)}/download`,
  tasks: (projectId?: string) => request<{ items: Task[] }>(`/api/tasks${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''}`),
  createTask: (projectId: string, objective: string, materialIds: string[]) => request<{ task: Task }>('/api/tasks', { method: 'POST', body: JSON.stringify({ project_id: projectId, objective, material_ids: materialIds }) }),
  task: (taskId: string) => request<TaskDetail>(`/api/tasks/${encodeURIComponent(taskId)}`),
  productEvents: (taskId: string, afterSequence = 0) => request<{ items: ProductEvent[]; latest_sequence: number; protocol_name: 'agentteams' | string; protocol_version: number }>(`/api/tasks/${encodeURIComponent(taskId)}/product-events?after_sequence=${afterSequence}&protocol_version=1`),
  uploadSources: (taskId: string, files: File[]) => { const body = new FormData(); files.forEach((file) => body.append('files', file)); return request<{ task_id: string; source_paths: string[] }>(`/api/tasks/${encodeURIComponent(taskId)}/sources`, { method: 'POST', body }); },
  runTask: (taskId: string) => request<{ task_id: string; status: string }>(`/api/tasks/${encodeURIComponent(taskId)}/run`, { method: 'POST' }),
  products: (taskId?: string) => request<{ items: ProductSummary[] }>(`/api/products${taskId ? `?task_id=${encodeURIComponent(taskId)}` : ''}`),
  projectProducts: (projectId: string) => request<{ items: ProductSummary[] }>(`/api/projects/${encodeURIComponent(projectId)}/products`),
  product: (productId: string) => request<ProductDetail>(`/api/products/${encodeURIComponent(productId)}`),
  projectResources: (projectId: string, filters: { resourceType?: string; status?: string } = {}) => {
    const params = new URLSearchParams();
    if (filters.resourceType) params.set('resource_type', filters.resourceType);
    if (filters.status) params.set('status', filters.status);
    const query = params.size ? `?${params.toString()}` : '';
    return request<{ items: ProjectResource[] }>(`/api/projects/${encodeURIComponent(projectId)}/resources${query}`);
  },
  projectListings: (projectId: string, platform = '') => request<{ items: ListingDraft[] }>(`/api/projects/${encodeURIComponent(projectId)}/listings${platform ? `?platform=${encodeURIComponent(platform)}` : ''}`),
  agentWorkspace: (projectId: string, workerName: string) => request<AgentWorkspace>(`/api/projects/${encodeURIComponent(projectId)}/workspace/${encodeURIComponent(workerName)}`),
  approve: (approvalId: string, payload: Record<string, unknown>) => request<{ task: Task }>(`/api/approvals/${encodeURIComponent(approvalId)}/approve`, { method: 'POST', body: JSON.stringify(payload) }),
  reject: (approvalId: string, payload: Record<string, unknown> = {}) => request<{ approval: Approval }>(`/api/approvals/${encodeURIComponent(approvalId)}/reject`, { method: 'POST', body: JSON.stringify(payload) }),
  modelSettings: () => request<ModelSettings>('/api/model-settings'),
  saveModelSettings: (payload: ModelSettingsPayload) => request<ModelSettings>('/api/model-settings', { method: 'PUT', body: JSON.stringify(payload) }),
  modelReadiness: () => request<ModelRoleStatus>('/api/model-settings/readiness'),
  modelSmoke: () => request<ModelRoleStatus>('/api/model-settings/smoke', { method: 'POST' }),
  skills: () => request<{ items: SkillSummary[] }>('/api/skills'),
  skill: (name: string) => request<SkillDetail>(`/api/skills/${encodeURIComponent(name)}`),
  artifactDownloadUrl: (artifactId: string) => `${baseUrl}/api/artifacts/${encodeURIComponent(artifactId)}/download`,
  artifactPreview: (artifactId: string, offset = 0, limit = 65536) => request<ArtifactPreview>(`/api/artifacts/${encodeURIComponent(artifactId)}/preview?offset=${Math.max(0, offset)}&limit=${Math.max(1, limit)}`),
  productEventStreamUrl: (taskId: string, afterSequence = 0) => `${baseUrl}/api/tasks/${encodeURIComponent(taskId)}/product-events/stream?after_sequence=${afterSequence}&protocol_version=1`,
};
