import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, ChevronDown, Download, FileText, Folder, LoaderCircle, PackageOpen, TriangleAlert } from 'lucide-react';
import { api, type AgentWorkspace, type Artifact, type ArtifactPreview, type ProductEvent, type ProjectMaterial, type TaskDetail } from '../../api';
import { ApprovalCard } from '../../components/ApprovalCard/ApprovalCard';
import { BottomBar } from '../../components/BottomBar';
import { ChatBox } from '../../components/ChatBox';
import { ListingWorkspace } from '../../components/ListingWorkspace/ListingWorkspace';
import { ProductGraph } from '../../components/ProductGraph/ProductGraph';
import { ProductIssues } from '../../components/ProductIssues/ProductIssues';
import { WorkFlow } from '../../components/WorkFlow';
import { MarkDown } from '../../components/WorkFlow/MarkDown';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '../../components/ui/resizable';
import { projectDetail, projectNativeTask, projectTask, reduceWorkspaceState } from '../../state/crossborderWorkspaceState';
import { agentLabel, localizedMessage, statusLabel } from '../../lib/crossborderLabels';
import type { CoworkInputAttachment, CoworkTask } from '../../types';

interface Props { taskId: string; onRefreshTasks: () => Promise<void>; onBackToProject: () => void }
type WorkspaceId = 'workflow' | 'catalog_steward_agent' | 'compliance_specialist_agent' | 'listing_operations_agent' | 'governance_reviewer_agent' | 'documentWorkSpace';
type VirtualDirectoryId = 'sources' | 'catalog' | 'compliance' | 'listings' | 'governance' | 'exports' | 'reports';

const VIRTUAL_DIRECTORIES: Array<{ id: VirtualDirectoryId; label: string; description: string }> = [
  { id: 'sources', label: '项目素材', description: '当前项目已导入的供应商文件。' },
  { id: 'catalog', label: '商品目录', description: '规范 Product/SKU 事实与分类结果。' },
  { id: 'compliance', label: '合规检查', description: '美国服装法规与平台政策检查结果。' },
  { id: 'listings', label: '平台草稿', description: 'Shopify 和 eBay 美国站商品草稿。' },
  { id: 'governance', label: '治理审核', description: '交付决策、审核结果与审批记录。' },
  { id: 'exports', label: '导出包', description: '可交付的平台商品目录包。' },
  { id: 'reports', label: '报告', description: '生成的 Markdown 报告与辅助文件。' },
];

function artifactDirectory(artifact: Artifact): VirtualDirectoryId {
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

function isProductEvent(value: unknown): value is ProductEvent {
  if (!value || typeof value !== 'object') return false;
  const event = value as Partial<ProductEvent>;
  return typeof event.id === 'string' && typeof event.sequence === 'number' && event.protocol_name === 'eigent' && event.protocol_version === 1 && typeof event.action === 'string' && Boolean(event.payload_json && typeof event.payload_json === 'object');
}

function contiguous(events: ProductEvent[], cursor: number): ProductEvent[] | null {
  const additions = events.filter((event) => event.sequence > cursor).sort((left, right) => left.sequence - right.sequence);
  let expected = cursor + 1;
  for (const event of additions) {
    if (event.sequence !== expected) return null;
    expected += 1;
  }
  return additions;
}

function ArtifactPreviewPane({ artifact }: { artifact: Artifact }) {
  const [preview, setPreview] = useState<ArtifactPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    let disposed = false;
    setPreview(null); setLoading(true); setError('');
    void api.artifactPreview(artifact.id).then((value) => { if (!disposed) setPreview(value); }).catch((reason) => { if (!disposed) setError(localizedMessage(reason)); }).finally(() => { if (!disposed) setLoading(false); });
    return () => { disposed = true; };
  }, [artifact.id]);
  async function loadMore() {
    if (!preview?.next_offset) return;
    try {
      setLoading(true);
      const next = await api.artifactPreview(artifact.id, preview.next_offset);
      setPreview({ ...next, content: `${preview.content || ''}${next.content || ''}` });
    } catch (reason) { setError(localizedMessage(reason)); } finally { setLoading(false); }
  }
  const isMarkdown = artifact.mime_type.includes('markdown') || artifact.file_name.toLowerCase().endsWith('.md');
  return <article className="artifact-preview"><div className="card-heading"><div><span className="kicker">生成文件</span><h3>{artifact.title}</h3></div><a className="primary artifact-download" href={api.artifactDownloadUrl(artifact.id)}><Download size={14} />下载</a></div><dl><dt>文件名</dt><dd>{artifact.file_name}</dd><dt>负责人</dt><dd>{agentLabel(artifact.worker_name)}</dd><dt>生成时间</dt><dd>{artifact.created_at ? new Date(artifact.created_at).toLocaleString('zh-CN') : '—'}</dd></dl>{loading && !preview ? <div className="workspace-inline-state"><LoaderCircle className="spin" size={16} />正在读取该文件…</div> : null}{error ? <div className="workspace-inline-state failed"><TriangleAlert size={16} />{error}</div> : null}{preview?.content != null ? <div className={`artifact-content ${isMarkdown ? 'markdown' : 'plain'}`}>{isMarkdown ? <MarkDown content={preview.content} enableTypewriter={false} /> : <pre>{preview.content}</pre>}</div> : !loading && !error ? <p className="notice">该文件不支持文本预览，可下载后查看。</p> : null}{preview?.truncated ? <button className="secondary artifact-load-more" disabled={loading} onClick={() => void loadMore()}>继续加载</button> : null}</article>;
}

function FilesWorkspace({ detail, artifacts, selectedArtifactId, onSelectArtifact }: { detail: TaskDetail; artifacts: Artifact[]; selectedArtifactId: string; onSelectArtifact: (id: string) => void }) {
  const [materials, setMaterials] = useState<ProjectMaterial[]>([]);
  const [projectArtifacts, setProjectArtifacts] = useState<Artifact[]>([]);
  const [selected, setSelected] = useState(selectedArtifactId ? `artifact:${selectedArtifactId}` : 'dir:sources');
  useEffect(() => { if (selectedArtifactId) setSelected(`artifact:${selectedArtifactId}`); }, [selectedArtifactId]);
  useEffect(() => { void api.projectMaterials(detail.task.project_id).then((result) => setMaterials(result.items)).catch(() => setMaterials([])); }, [detail.task.project_id]);
  useEffect(() => {
    let disposed = false;
    const workers = ['catalog_steward_agent', 'compliance_specialist_agent', 'listing_operations_agent', 'governance_reviewer_agent'];
    void Promise.all(workers.map((worker) => api.agentWorkspace(detail.task.project_id, worker).catch(() => null))).then((workspaces) => {
      if (disposed) return;
      const unique = new Map<string, Artifact>();
      workspaces.forEach((workspace) => workspace?.artifacts?.forEach((item) => unique.set(item.id, item)));
      setProjectArtifacts(Array.from(unique.values()));
    });
    return () => { disposed = true; };
  }, [detail.task.project_id]);
  const visibleArtifacts = useMemo(() => {
    const unique = new Map<string, Artifact>();
    [...projectArtifacts, ...artifacts].forEach((item) => unique.set(item.id, item));
    return Array.from(unique.values());
  }, [artifacts, projectArtifacts]);
  const selectedDirectory = VIRTUAL_DIRECTORIES.find((directory) => selected === `dir:${directory.id}`);
  const artifact = visibleArtifacts.find((item) => selected === `artifact:${item.id}`) || null;
  const material = materials.find((item) => selected === `material:${item.id}`) || null;
  const artifactsByDirectory = new Map<VirtualDirectoryId, Artifact[]>();
  VIRTUAL_DIRECTORIES.forEach((directory) => artifactsByDirectory.set(directory.id, []));
  visibleArtifacts.forEach((item) => artifactsByDirectory.get(artifactDirectory(item))?.push(item));
  return <section className="files-workspace"><div className="section-header"><div><span className="eyebrow">文件工作区</span><h2>文件与证据</h2></div><span className="muted">{materials.length} 个素材 · {visibleArtifacts.length} 个产物</span></div><div className="files-workspace-grid"><nav className="virtual-file-tree" aria-label="项目虚拟文件"><div className="virtual-root"><PackageOpen size={16} /><strong>{detail.task.objective}</strong></div>{VIRTUAL_DIRECTORIES.map((directory) => { const files = artifactsByDirectory.get(directory.id) || []; const count = directory.id === 'sources' ? materials.length : files.length; return <section className="virtual-directory" key={directory.id}><button className={`virtual-directory-row ${selected === `dir:${directory.id}` ? 'selected' : ''}`} onClick={() => setSelected(`dir:${directory.id}`)}><ChevronDown size={14} /><Folder size={15} /><span>{directory.label}</span><small>{count}</small></button><div className="virtual-directory-files">{directory.id === 'sources' && materials.map((item) => <button key={item.id} className={selected === `material:${item.id}` ? 'selected' : ''} onClick={() => setSelected(`material:${item.id}`)} title={item.file_name}><FileText size={14} /><span>{item.file_name}</span></button>)}{files.map((item) => <button key={item.id} className={selected === `artifact:${item.id}` ? 'selected' : ''} onClick={() => { setSelected(`artifact:${item.id}`); onSelectArtifact(item.id); }} title={item.file_name}><FileText size={14} /><span>{item.file_name}</span></button>)}</div></section>; })}</nav>{artifact ? <ArtifactPreviewPane artifact={artifact} /> : material ? <article className="artifact-preview"><div className="card-heading"><div><span className="kicker">项目素材</span><h3>{material.file_name}</h3></div><a className="primary artifact-download" href={api.projectMaterialDownloadUrl(material.id)}><Download size={14} />下载</a></div><dl><dt>类型</dt><dd>{material.mime_type}</dd><dt>大小</dt><dd>{material.size_bytes.toLocaleString('zh-CN')} 字节</dd><dt>来源</dt><dd>{material.origin === 'example' ? '示例素材' : '用户上传'}</dd></dl></article> : <div className="virtual-directory-preview"><Folder size={34} /><span className="kicker">虚拟目录</span><h3>{selectedDirectory?.label || '项目文件'}</h3><p>{selectedDirectory?.description || '请从目录树中选择目录或文件。'}</p><strong>{selectedDirectory?.id === 'sources' ? materials.length : selectedDirectory ? artifactsByDirectory.get(selectedDirectory.id)?.length || 0 : 0} 项</strong></div>}</div></section>;
}

function WorkspaceStateView({ state, error }: { state: AgentWorkspace['state']; error?: string }) {
  const copy = state === 'not_started' ? ['尚未执行', '本次任务没有向该智能体分配步骤。'] : state === 'running' ? ['正在执行', '工作摘要和业务资源会随执行进度更新。'] : state === 'empty' ? ['已完成，无业务结果', '智能体已完成处理，但没有生成该工作区对应的数据。'] : state === 'failed' ? ['加载或执行失败', error || '请查看左侧任务状态后重试。'] : null;
  return copy ? <div className={`agent-workspace-state ${state}`}>{state === 'running' ? <LoaderCircle className="spin" size={20} /> : state === 'failed' ? <TriangleAlert size={20} /> : <Folder size={20} />}<div><h3>{copy[0]}</h3><p>{copy[1]}</p></div></div> : null;
}

function AgentWorkspacePanel({ workerName, projectId, fallbackState }: { workerName: string; projectId: string; fallbackState: AgentWorkspace['state'] }) {
  const [workspace, setWorkspace] = useState<AgentWorkspace | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { let disposed = false; setWorkspace(null); setError(''); void api.agentWorkspace(projectId, workerName).then((value) => { if (!disposed) setWorkspace(value); }).catch((reason) => { if (!disposed) setError(localizedMessage(reason)); }); return () => { disposed = true; }; }, [projectId, workerName]);
  if (error) return <WorkspaceStateView state="failed" error={error} />;
  if (!workspace) return fallbackState === 'not_started' ? <WorkspaceStateView state="not_started" /> : <div className="workspace-inline-state"><LoaderCircle className="spin" size={16} />正在加载智能体工作区…</div>;
  if (workspace.state !== 'completed') return <WorkspaceStateView state={workspace.state} error={workspace.error} />;
  if (workerName === 'catalog_steward_agent') return <ProductGraph projectId={projectId} />;
  if (workerName === 'listing_operations_agent') return <ListingWorkspace drafts={workspace.listings || []} />;
  return <ProductIssues findings={workspace.findings || []} />;
}

function BusinessWorkspace({ id, detail, agents, artifacts, selectedArtifactId, onSelectArtifact, onSelectWorkspace }: { id: WorkspaceId; detail: TaskDetail; agents: Agent[]; artifacts: Artifact[]; selectedArtifactId: string; onSelectArtifact: (id: string) => void; onSelectWorkspace: (id: WorkspaceId) => void }) {
  if (id === 'workflow') return <WorkFlow agents={agents} activeAgentId="workflow" focusedAgentId={agents.find((agent) => agent.status === 'running')?.agent_id} onSelectAgent={(agentId) => onSelectWorkspace(agentId as WorkspaceId)} />;
  if (id === 'documentWorkSpace') return <FilesWorkspace detail={detail} artifacts={artifacts} selectedArtifactId={selectedArtifactId} onSelectArtifact={onSelectArtifact} />;
  const agent = agents.find((item) => item.agent_id === id);
  const headings: Record<string, [string, string]> = { catalog_steward_agent: ['Product/SKU 商品图谱', '管理规范商品事实、变体、来源证据与版本记录。'], compliance_specialist_agent: ['美国市场合规审核', '服装法规与平台政策检查结果均关联到原始证据。'], listing_operations_agent: ['平台商品草稿', '基于规范 Product 事实生成 Shopify 和 eBay 美国站草稿。'], governance_reviewer_agent: ['交付就绪审核', '处理阻塞项、审核证据并完成必要审批。'] };
  const [title, description] = headings[id] || ['智能体工作区', '展示当前项目中由该智能体拥有的业务资源。'];
  return <section className="agent-workspace"><div className="section-header"><div><span className="eyebrow">{agentLabel(id)}</span><h2>{title}</h2><p className="muted">{description}</p></div></div><AgentWorkspacePanel key={`${id}:${detail.task.updated_at}`} workerName={id} projectId={detail.task.project_id} fallbackState={agent?.workspaceState || 'not_started'} /></section>;
}

export function Workspace({ taskId, onRefreshTasks, onBackToProject }: Props) {
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [events, setEvents] = useState<ProductEvent[]>([]);
  const [streamState, setStreamState] = useState<'connecting' | 'live' | 'reconnecting' | 'closed'>('connecting');
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>('workflow');
  const [selectedArtifactId, setSelectedArtifactId] = useState('');
  const [chatVisible, setChatVisible] = useState(true);
  const [objective, setObjective] = useState('');
  const [error, setError] = useState('');
  const refresh = async () => { try { const next = await api.task(taskId); setDetail(next); setObjective(next.task.objective); await onRefreshTasks(); } catch (reason) { setError(localizedMessage(reason)); } };
  useEffect(() => {
    let disposed = false; let protocolBlocked = false; let source: EventSource | null = null; let timer: number | undefined; let cursor = 0;
    setEvents([]);
    const scheduleReconnect = (delay = 1000) => { if (disposed || protocolBlocked) return; if (timer) window.clearTimeout(timer); timer = window.setTimeout(() => void connect(), delay); };
    const connect = async () => {
      if (disposed || protocolBlocked) return; source?.close(); setStreamState(cursor ? 'reconnecting' : 'connecting');
      try {
        const snapshot = await api.productEvents(taskId, cursor);
        if (snapshot.protocol_name !== 'eigent' || snapshot.protocol_version !== 1) { protocolBlocked = true; setStreamState('closed'); setError('桌面端与后端事件协议版本不兼容，请安装同一版本后重试。'); return; }
        const additions = contiguous((snapshot.items || []).filter(isProductEvent), cursor);
        if (additions === null) { scheduleReconnect(0); return; }
        if (additions.length) { setEvents((current) => [...current, ...additions]); cursor = additions.at(-1)?.sequence || cursor; }
        if (disposed) return;
        source = new EventSource(api.productEventStreamUrl(taskId, cursor));
        source.onopen = () => { setStreamState('live'); setError(''); };
        source.onerror = () => { source?.close(); setStreamState('reconnecting'); scheduleReconnect(); };
        source.addEventListener('cowork_product_event', (raw) => { try { const parsed = JSON.parse((raw as MessageEvent<string>).data) as unknown; if (!isProductEvent(parsed)) { protocolBlocked = true; source?.close(); setStreamState('closed'); setError('收到不兼容的任务事件，请确认桌面端与后端版本一致。'); return; } if (parsed.sequence <= cursor) return; if (parsed.sequence !== cursor + 1) { source?.close(); scheduleReconnect(0); return; } cursor = parsed.sequence; setEvents((current) => [...current, parsed]); void refresh(); } catch { protocolBlocked = true; source?.close(); setStreamState('closed'); setError('任务事件无法解析，请确认桌面端与后端版本一致。'); } });
      } catch (reason) { if (!disposed) { setError(localizedMessage(reason)); setStreamState('reconnecting'); scheduleReconnect(1500); } }
    };
    void refresh(); void connect(); const recovery = window.setInterval(() => void refresh(), 10000);
    return () => { disposed = true; source?.close(); if (timer) window.clearTimeout(timer); window.clearInterval(recovery); };
  }, [taskId]);
  const reduced = useMemo(() => detail ? reduceWorkspaceState(detail, events) : null, [detail, events]);
  const nativeTask = useMemo(() => detail ? projectNativeTask(detail, events) : undefined, [detail, events]);
  const coworkTask = useMemo<CoworkTask | undefined>(() => detail ? projectTask(detail, events) : undefined, [detail, events]);
  const coworkDetail = useMemo(() => detail ? projectDetail(detail, events) : null, [detail, events]);
  const agents = nativeTask?.taskAssigning || [];
  async function submit(attachments?: CoworkInputAttachment[]) { if (!detail) return; const files = (attachments || []).map((item) => item.file).filter((item): item is File => Boolean(item)); if (files.length) await api.uploadSources(taskId, files); await api.runTask(taskId); await refresh(); }
  async function decide(approvalId: string, payload: Record<string, unknown>, rejected: boolean) { if (rejected) await api.reject(approvalId, payload); else await api.approve(approvalId, payload); await refresh(); }
  if (!detail) return <div className="workspace-state">{error || '正在加载任务工作区…'}</div>;
  return <main className="native-workspace-shell"><section className="native-workspace-frame"><ResizablePanelGroup direction="horizontal" key={chatVisible ? 'chat-open' : 'chat-closed'}>{chatVisible && <><ResizablePanel defaultSize={31} minSize={22} className="min-h-0"><ChatBox monitorOnly objective={objective} tasks={coworkTask ? [coworkTask] : []} activeTaskId={taskId} activeTask={coworkTask} nativeTask={nativeTask} loading={detail.task.status === 'running'} onObjectiveChange={setObjective} onSubmit={submit} onRefresh={() => void refresh()} onSelectTask={() => undefined} onStartTask={() => submit()} onCancelTask={() => undefined} activeDetail={coworkDetail} onOpenFile={(_taskId, file) => { if (file.artifact_id) setSelectedArtifactId(file.artifact_id); setActiveWorkspace('documentWorkSpace'); }} /></ResizablePanel><ResizableHandle withHandle className="custom-resizable-handle" /></>}<ResizablePanel className="min-h-0"><section className="native-workspace-main"><header className="native-workspace-header"><button className="task-back-button" onClick={onBackToProject} title="返回项目素材库"><ArrowLeft size={16} /></button><div><span className="eyebrow">跨境商品目录工作区</span><h1>{detail.task.objective}</h1></div><span className={`stream-state ${streamState}`}>{statusLabel(streamState)}</span></header>{error && <div className="error-banner">{error}</div>}{reduced?.hasGap ? <div className="error-banner">事件序列不完整，正在重新连接并补齐状态。</div> : null}<div className="native-workspace-content"><BusinessWorkspace id={activeWorkspace} detail={detail} agents={agents} artifacts={reduced?.artifacts || detail.artifacts} selectedArtifactId={selectedArtifactId} onSelectArtifact={setSelectedArtifactId} onSelectWorkspace={setActiveWorkspace} /></div><BottomBar agents={agents} activeWorkspace={activeWorkspace} isChatBoxVisible={chatVisible} onToggleChatBox={() => setChatVisible((value) => !value)} onSelectWorkspace={(id) => setActiveWorkspace(id as WorkspaceId)} /></section></ResizablePanel></ResizablePanelGroup></section>{detail.approvals.filter((approval) => approval.status === 'pending').map((approval) => <ApprovalCard key={approval.id} approval={approval} onDecide={decide} />)}</main>;
}
