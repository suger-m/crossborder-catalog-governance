import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ChevronDown, Plus, RefreshCw, Settings } from 'lucide-react';
import { api, type Project, type Task } from './api';
import { SettingsCenter } from './components/settings/SettingsCenter';
import { localizedMessage, statusLabel } from './lib/crossborderLabels';
import { useProjectBundle } from './hooks/useProjectBundle';
import { useTaskLive } from './hooks/useTaskLive';
import { OverviewView } from './views/OverviewView';
import { CatalogView } from './views/CatalogView';
import { WorkbenchView } from './views/WorkbenchView';
import { ResultsView } from './views/ResultsView';
import './styles.css';

type AppSection = 'overview' | 'catalog' | 'workbench' | 'results';

function CreateProjectDialog({
  open,
  busy,
  error,
  onClose,
  onCreate,
}: {
  open: boolean;
  busy: boolean;
  error: string;
  onClose: () => void;
  onCreate: (name: string) => Promise<void>;
}) {
  const [name, setName] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setName('');
      window.setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [busy, onClose, open]);

  if (!open) return null;

  return (
    <div
      className="dialog-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <form
        className="project-dialog"
        onSubmit={(event) => {
          event.preventDefault();
          if (name.trim()) void onCreate(name.trim());
        }}
      >
        <div className="dialog-heading">
          <div>
            <h2>创建项目</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} disabled={busy} aria-label="关闭">×</button>
        </div>
        <p className="dialog-copy muted">用于管理女装资料、商品事实、合规检查和导出包。</p>
        <label className="dialog-field">
          <span>项目名称</span>
          <input ref={inputRef} value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：夏季女装美国市场" maxLength={120} />
        </label>
        {error && <p className="error">{error}</p>}
        <div className="dialog-actions">
          <button type="button" onClick={onClose} disabled={busy}>取消</button>
          <button className="primary" type="submit" disabled={busy || !name.trim()}>{busy ? '创建中…' : '创建项目'}</button>
        </div>
      </form>
    </div>
  );
}

function ProjectSwitcher({
  projects,
  selected,
  onSelect,
  onCreate,
}: {
  projects: Project[];
  selected: Project | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    window.addEventListener('mousedown', onPointer);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('mousedown', onPointer);
      window.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div className="project-switcher" ref={ref}>
      <button
        type="button"
        className="project-switcher-trigger"
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => setOpen((current) => !current)}
      >
        <span>{selected?.name || '选择项目'}</span>
        <ChevronDown size={16} />
      </button>
      {open ? (
        <div className="project-switcher-menu" role="listbox">
          {projects.map((project) => (
            <button
              key={project.id}
              type="button"
              role="option"
              aria-selected={selected?.id === project.id}
              className={selected?.id === project.id ? 'selected' : ''}
              onClick={() => {
                onSelect(project.id);
                setOpen(false);
              }}
            >
              {project.name}
            </button>
          ))}
          <button
            type="button"
            className="project-switcher-create"
            onClick={() => {
              setOpen(false);
              onCreate();
            }}
          >
            <Plus size={15} /> 新建项目
          </button>
        </div>
      ) : null}
    </div>
  );
}

function App() {
  const [health, setHealth] = useState('checking');
  const [projects, setProjects] = useState<Project[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [selectedTask, setSelectedTask] = useState<string | null>(null);
  const [section, setSection] = useState<AppSection>('overview');
  const [message, setMessage] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogBusy, setDialogBusy] = useState(false);
  const [dialogError, setDialogError] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [preferredArtifactId, setPreferredArtifactId] = useState('');
  const refreshRequestRef = useRef(0);

  const { bundle, loading: bundleLoading, error: bundleError, refresh: refreshBundle } = useProjectBundle(selectedProject?.id || null);

  async function refreshTasksOnly() {
    if (!selectedProject) return;
    const nextTasks = (await api.tasks(selectedProject.id)).items;
    setTasks(nextTasks);
  }

  const taskLive = useTaskLive(section === 'workbench' || section === 'results' ? selectedTask : null, refreshTasksOnly);

  async function refresh(projectId?: string, preferredTaskId?: string | null, nextSection?: AppSection) {
    const requestId = ++refreshRequestRef.current;
    try {
      const identity = await api.health();
      if (identity.app_id !== 'crossborder-catalog-cowork' || identity.protocol_name !== 'agentteams' || identity.protocol_version !== 1) {
        throw new Error('Web 与后端版本不兼容。');
      }
      const projectResult = await api.projects();
      const activeId = projectId || selectedProject?.id || projectResult.items[0]?.id;
      const active = projectResult.items.find((item) => item.id === activeId) || null;
      const nextTasks = active ? (await api.tasks(active.id)).items : [];
      if (requestId !== refreshRequestRef.current) return;
      setHealth(identity.agentteams?.ready === false ? 'degraded' : 'online');
      setMessage(identity.agentteams?.ready === false ? `AgentTeams 未就绪：${identity.agentteams.last_error || '请先启动 AgentTeams 服务'}` : '');
      setProjects(projectResult.items);
      const projectChanged = active?.id !== selectedProject?.id;
      setSelectedProject(active);
      setTasks(nextTasks);
      const requestedTask = preferredTaskId === undefined ? (projectChanged ? null : selectedTask) : preferredTaskId;
      const nextTask = requestedTask && nextTasks.some((task) => task.id === requestedTask) ? requestedTask : null;
      setSelectedTask(nextTask);
      if (nextSection) setSection(nextSection);
      else if (projectChanged) setSection('overview');
      if (active) void refreshBundle(active.id);
    } catch (reason) {
      if (requestId !== refreshRequestRef.current) return;
      setHealth('offline');
      setMessage(localizedMessage(reason));
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function createProject(name: string) {
    setDialogBusy(true);
    setDialogError('');
    try {
      const result = await api.createProject(name);
      setDialogOpen(false);
      await refresh(result.project.id, null, 'catalog');
    } catch (reason) {
      setDialogError(localizedMessage(reason));
    } finally {
      setDialogBusy(false);
    }
  }

  async function createTask(objective: string, materialIds: string[]) {
    if (!selectedProject) return;
    const result = await api.createTask(selectedProject.id, objective, materialIds);
    await api.runTask(result.task.id);
    await refresh(selectedProject.id, result.task.id, 'workbench');
  }

  function openTask(taskId: string) {
    setSelectedTask(taskId);
    setSection('workbench');
  }

  function openResults(artifactId?: string) {
    setPreferredArtifactId(artifactId || '');
    setSection('results');
  }

  async function decideApproval(approvalId: string, payload: Record<string, unknown>, rejected: boolean) {
    if (rejected) await api.reject(approvalId, payload);
    else await api.approve(approvalId, payload);
    await taskLive.refresh();
    await refreshTasksOnly();
    if (selectedProject) void refreshBundle(selectedProject.id);
  }

  const sections: Array<[AppSection, string]> = [
    ['overview', '总览'],
    ['catalog', '目录'],
    ['workbench', '工作台'],
    ['results', '交付'],
  ];

  return (
    <div className="app-shell">
      <header className="topbar">
        <button type="button" className="brand-lockup" onClick={() => selectedProject && setSection('overview')}>
          <strong>跨境目录</strong>
        </button>
        {projects.length ? (
          <ProjectSwitcher
            projects={projects}
            selected={selectedProject}
            onSelect={(id) => void refresh(id, null, 'overview')}
            onCreate={() => { setDialogError(''); setDialogOpen(true); }}
          />
        ) : null}
        <div className="topbar-actions">
          <span className={`health ${health}`}><i />{statusLabel(health)}</span>
          <button className="topbar-button" onClick={() => setSettingsOpen(true)} aria-label="打开设置" title="设置"><Settings size={16} /></button>
          <button className="topbar-button" onClick={() => void refresh(selectedProject?.id, selectedTask)} aria-label="刷新"><RefreshCw size={15} /></button>
        </div>
      </header>

      <main className={`workspace-layout${selectedProject ? '' : ' welcome'}`}>
        {selectedProject ? (
          <nav className="section-nav" aria-label="主功能区">
            {sections.map(([id, label]) => (
              <button
                key={id}
                className={section === id ? 'active' : ''}
                onClick={() => {
                  if (id === 'workbench' && !selectedTask && tasks[0]) openTask(tasks[0].id);
                  else setSection(id);
                }}
              >
                {label}
              </button>
            ))}
          </nav>
        ) : null}
        <section className="main-stage" id="main-stage">
          {selectedProject ? (
            <>
              {message && <p className="banner-message">{message}</p>}
              {section === 'overview' && (
                <OverviewView
                  project={selectedProject}
                  tasks={tasks}
                  bundle={bundle}
                  loading={bundleLoading}
                  error={bundleError}
                  onOpenTask={openTask}
                  onGoCatalog={() => setSection('catalog')}
                  onGoWorkbench={() => {
                    if (!selectedTask && tasks[0]) openTask(tasks[0].id);
                    else setSection('workbench');
                  }}
                />
              )}
              {section === 'catalog' && (
                <CatalogView
                  project={selectedProject}
                  tasks={tasks}
                  bundle={bundle}
                  loading={bundleLoading}
                  error={bundleError}
                  onRefreshBundle={() => refreshBundle(selectedProject.id)}
                  onCreateTask={createTask}
                  onOpenTask={openTask}
                />
              )}
              {section === 'workbench' && (
                <WorkbenchView
                  tasks={tasks}
                  selectedTaskId={selectedTask}
                  onSelectTask={openTask}
                  detail={taskLive.detail}
                  projection={taskLive.projection}
                  streamState={taskLive.streamState}
                  loading={taskLive.loading}
                  error={taskLive.error}
                  onOpenResults={openResults}
                  onDecideApproval={decideApproval}
                />
              )}
              {section === 'results' && (
                <ResultsView
                  tasks={tasks}
                  selectedTaskId={selectedTask}
                  detail={taskLive.detail}
                  taskArtifacts={taskLive.projection?.artifacts || taskLive.detail?.artifacts || []}
                  bundle={bundle}
                  preferredArtifactId={preferredArtifactId}
                  loading={bundleLoading || taskLive.loading}
                  error={bundleError || taskLive.error}
                />
              )}
            </>
          ) : (
            <section className="welcome-state">
              <h1>美国女装目录工作台</h1>
              <p>导出 Shopify 与 eBay US Listing 包，不自动发布。</p>
              <button className="primary large" onClick={() => setDialogOpen(true)}>创建项目</button>
              {message && <p className="error">{message}</p>}
            </section>
          )}
        </section>
      </main>

      <CreateProjectDialog
        open={dialogOpen}
        busy={dialogBusy}
        error={dialogError}
        onClose={() => setDialogOpen(false)}
        onCreate={createProject}
      />
      <SettingsCenter open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
