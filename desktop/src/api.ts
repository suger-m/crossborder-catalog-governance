export interface Project { id: string; name: string; created_at: string; updated_at: string }
export interface Task { id: string; project_id: string; objective: string; status: string; updated_at: string }

const baseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, { headers: { 'Content-Type': 'application/json' }, ...init });
  if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string }>('/health'),
  projects: () => request<{ items: Project[] }>('/api/projects'),
  createProject: (name: string) => request<{ project: Project }>('/api/projects', { method: 'POST', body: JSON.stringify({ name }) }),
  tasks: (projectId?: string) => request<{ items: Task[] }>(`/api/tasks${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''}`),
  createTask: (projectId: string, objective: string) => request<{ task: Task }>('/api/tasks', { method: 'POST', body: JSON.stringify({ project_id: projectId, objective }) }),
  modelSettings: () => request<Record<string, unknown>>('/api/model-settings'),
};
