import { useEffect, useMemo, useState } from 'react';
import { api, type ProductEvent, type TaskDetail } from '../../api';
import { ApprovalCard } from '../../components/ApprovalCard/ApprovalCard';
import { BottomBar } from '../../components/BottomBar';
import { ChatBox } from '../../components/ChatBox';
import { ListingWorkspace } from '../../components/ListingWorkspace/ListingWorkspace';
import { ProductGraph } from '../../components/ProductGraph/ProductGraph';
import { ProductIssues } from '../../components/ProductIssues/ProductIssues';
import { WorkFlow } from '../../components/WorkFlow';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '../../components/ui/resizable';
import { projectDetail, projectNativeTask, projectTask } from '../../state/crossborderWorkspaceState';
import type { CoworkInputAttachment, CoworkTask } from '../../types';

interface Props { taskId: string; onRefreshTasks: () => Promise<void> }
type WorkspaceId = 'workflow' | 'catalog_steward_agent' | 'compliance_specialist_agent' | 'listing_operations_agent' | 'governance_reviewer_agent' | 'documentWorkSpace';

function FilesWorkspace({ detail }: { detail: TaskDetail }) {
  const [selected, setSelected] = useState<string | null>(detail.artifacts[0]?.id || null);
  const artifact = detail.artifacts.find((item) => item.id === selected) || null;
  return <section className="files-workspace"><div className="section-header"><div><span className="eyebrow">ARTIFACT WORKSPACE</span><h2>Files & evidence</h2></div><span className="muted">{detail.artifacts.length} artifacts</span></div><div className="files-workspace-grid"><nav className="artifact-list">{detail.artifacts.map((item) => <button key={item.id} className={item.id === selected ? 'selected' : ''} onClick={() => setSelected(item.id)}><strong>{item.title}</strong><small>{item.file_name} · {item.artifact_type}</small></button>)}{!detail.artifacts.length && <p className="muted">Artifacts will appear as workers finish.</p>}</nav>{artifact ? <article className="artifact-preview"><div className="card-heading"><div><span className="kicker">{artifact.artifact_type}</span><h3>{artifact.title}</h3></div><a className="primary" href={api.artifactDownloadUrl(artifact.id)}>Download</a></div><dl><dt>File</dt><dd>{artifact.file_name}</dd><dt>Owner</dt><dd>{artifact.worker_name}</dd><dt>Created</dt><dd>{new Date(artifact.created_at).toLocaleString()}</dd></dl><p className="notice">This artifact is sourced from the backend artifact registry. Select another file to inspect it independently.</p></article> : <div className="empty-state"><h3>Select an artifact</h3><p>Each report, evidence bundle, and export package has its own identity.</p></div>}</div></section>;
}

function BusinessWorkspace({ id, taskId, detail, agents }: { id: WorkspaceId; taskId: string; detail: TaskDetail; agents: Agent[] }) {
  if (id === 'workflow') return <WorkFlow agents={agents} activeAgentId="workflow" focusedAgentId={agents.find((agent) => agent.status === 'running')?.agent_id} />;
  if (id === 'catalog_steward_agent') return <section className="agent-workspace"><div className="section-header"><div><span className="eyebrow">CATALOG STEWARD</span><h2>Product & SKU graph</h2><p className="muted">Canonical facts, variants, source evidence, and version history.</p></div></div><ProductGraph taskId={taskId} /></section>;
  if (id === 'compliance_specialist_agent') return <section className="agent-workspace"><div className="section-header"><div><span className="eyebrow">COMPLIANCE SPECIALIST</span><h2>US compliance review</h2><p className="muted">Apparel requirements and marketplace policy findings remain linked to source evidence.</p></div></div><ProductIssues result={detail.task.result} /></section>;
  if (id === 'listing_operations_agent') return <section className="agent-workspace"><div className="section-header"><div><span className="eyebrow">LISTING OPERATIONS</span><h2>Channel drafts</h2><p className="muted">Shopify and eBay US listing packages derived from canonical Product facts.</p></div></div><ListingWorkspace result={detail.task.result} /></section>;
  if (id === 'governance_reviewer_agent') return <section className="agent-workspace"><div className="section-header"><div><span className="eyebrow">GOVERNANCE REVIEWER</span><h2>Release readiness</h2><p className="muted">Resolve blockers, review evidence, and complete required approvals before export.</p></div></div><ProductIssues result={detail.task.result} /></section>;
  return <FilesWorkspace detail={detail} />;
}

export function Workspace({ taskId, onRefreshTasks }: Props) {
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [events, setEvents] = useState<ProductEvent[]>([]);
  const [streamState, setStreamState] = useState<'connecting' | 'live' | 'reconnecting' | 'closed'>('connecting');
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>('workflow');
  const [chatVisible, setChatVisible] = useState(true);
  const [objective, setObjective] = useState('');
  const [error, setError] = useState('');
  const refresh = async () => { try { const next = await api.task(taskId); setDetail(next); setObjective(next.task.objective); await onRefreshTasks(); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } };
  useEffect(() => { let disposed = false; let source: EventSource | null = null; let timer: number | undefined; let cursor = 0; const connect = async () => { if (disposed) return; setStreamState(cursor ? 'reconnecting' : 'connecting'); try { const snapshot = await api.productEvents(taskId, cursor); if (snapshot.items?.length) { setEvents((current) => [...current, ...snapshot.items.filter((item) => item.sequence > cursor)]); cursor = Math.max(cursor, ...snapshot.items.map((item) => item.sequence)); } source = new EventSource(api.productEventStreamUrl(taskId, cursor)); source.onopen = () => setStreamState('live'); source.onerror = () => { source?.close(); if (!disposed) { setStreamState('reconnecting'); timer = window.setTimeout(() => void connect(), 1500); } }; source.addEventListener('cowork_product_event', (raw) => { try { const event = JSON.parse((raw as MessageEvent<string>).data) as ProductEvent; if (event.sequence !== cursor + 1) { source?.close(); void connect(); return; } cursor = event.sequence; setEvents((current) => [...current, event]); void refresh(); } catch { setError('Invalid product event received.'); } }); } catch (reason) { if (!disposed) { setError(reason instanceof Error ? reason.message : String(reason)); timer = window.setTimeout(() => void connect(), 1500); } } }; void refresh(); void connect(); const recovery = window.setInterval(() => void refresh(), 10000); return () => { disposed = true; source?.close(); if (timer) window.clearTimeout(timer); window.clearInterval(recovery); setStreamState('closed'); }; }, [taskId]);
  const nativeTask = useMemo(() => detail ? projectNativeTask(detail, events) : undefined, [detail, events]);
  const coworkTask = useMemo<CoworkTask | undefined>(() => detail ? projectTask(detail, events) : undefined, [detail, events]);
  const coworkDetail = useMemo(() => detail ? projectDetail(detail, events) : null, [detail, events]);
  const agents = nativeTask?.taskAssigning || [];
  async function submit(attachments?: CoworkInputAttachment[]) { if (!detail) return; const files = (attachments || []).map((item) => item.file).filter((item): item is File => Boolean(item)); if (files.length) await api.uploadSources(taskId, files); await api.runTask(taskId); await refresh(); }
  async function decide(approvalId: string, payload: Record<string, unknown>, rejected: boolean) { if (rejected) await api.reject(approvalId, payload); else await api.approve(approvalId, payload); await refresh(); }
  if (!detail) return <div className="workspace-state">{error || 'Loading task workspace…'}</div>;
  return <main className="native-workspace-shell"><section className="native-workspace-frame"><ResizablePanelGroup direction="horizontal" key={chatVisible ? 'chat-open' : 'chat-closed'}>{chatVisible && <><ResizablePanel defaultSize={31} minSize={22} className="min-h-0"><ChatBox objective={objective} tasks={coworkTask ? [coworkTask] : []} activeTaskId={taskId} activeTask={coworkTask} nativeTask={nativeTask} loading={detail.task.status === 'running'} onObjectiveChange={setObjective} onSubmit={submit} onRefresh={() => void refresh()} onSelectTask={() => undefined} onStartTask={() => submit()} onCancelTask={() => undefined} activeDetail={coworkDetail} onOpenFile={() => setActiveWorkspace('documentWorkSpace')} /></ResizablePanel><ResizableHandle withHandle className="custom-resizable-handle" /></> }<ResizablePanel className="min-h-0"><section className="native-workspace-main"><header className="native-workspace-header"><div><span className="eyebrow">CROSS-BORDER CATALOG WORKSPACE</span><h1>{detail.task.objective}</h1></div><span className={`stream-state ${streamState}`}>{streamState === 'live' ? 'Live' : streamState}</span></header>{error && <div className="error-banner">{error}</div>}<div className="native-workspace-content"><BusinessWorkspace id={activeWorkspace} taskId={taskId} detail={detail} agents={agents} /></div><BottomBar agents={agents} activeWorkspace={activeWorkspace} isChatBoxVisible={chatVisible} onToggleChatBox={() => setChatVisible((value) => !value)} onSelectWorkspace={(id) => setActiveWorkspace(id as WorkspaceId)} /></section></ResizablePanel></ResizablePanelGroup></section>{detail.approvals.filter((approval) => approval.status === 'pending').map((approval) => <ApprovalCard key={approval.id} approval={approval} onDecide={decide} />)}</main>;
}
