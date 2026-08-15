import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, ChevronDown, FileText, Folder, PackageOpen } from 'lucide-react';
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
import { agentLabel, localizedMessage, statusLabel } from '../../lib/crossborderLabels';
import type { CoworkInputAttachment, CoworkTask } from '../../types';

interface Props { taskId: string; onRefreshTasks: () => Promise<void>; onBackToProject: () => void }
type WorkspaceId = 'workflow' | 'catalog_steward_agent' | 'compliance_specialist_agent' | 'listing_operations_agent' | 'governance_reviewer_agent' | 'documentWorkSpace';

type VirtualDirectoryId = 'sources' | 'catalog' | 'compliance' | 'listings' | 'governance' | 'exports' | 'reports';
interface VirtualDirectory { id: VirtualDirectoryId; label: string; description: string }
const VIRTUAL_DIRECTORIES: VirtualDirectory[] = [
  { id: 'sources', label: '源文件', description: '本次商品目录任务所附的供应商文件。' },
  { id: 'catalog', label: '商品目录', description: '规范 Product/SKU 事实与分类结果。' },
  { id: 'compliance', label: '合规检查', description: '美国服装法规与平台政策检查结果。' },
  { id: 'listings', label: '平台草稿', description: 'Shopify 和 eBay 美国站商品草稿。' },
  { id: 'governance', label: '治理审核', description: '交付决策、审核结果与审批记录。' },
  { id: 'exports', label: '导出包', description: '可交付的平台商品目录包。' },
  { id: 'reports', label: '报告', description: '其他生成的报告和辅助文件。' },
];

function artifactDirectory(artifact: TaskDetail['artifacts'][number]): VirtualDirectoryId {
  const value = `${artifact.artifact_type} ${artifact.worker_name} ${artifact.file_name}`.toLowerCase();
  if (value.includes('export') || value.includes('package') || value.includes('zip')) return 'exports';
  if (value.includes('listing') || value.includes('shopify') || value.includes('ebay')) return 'listings';
  if (value.includes('compliance') || value.includes('policy')) return 'compliance';
  if (value.includes('governance') || value.includes('review') || value.includes('approval')) return 'governance';
  if (value.includes('catalog') || value.includes('product') || value.includes('sku') || value.includes('taxonomy')) return 'catalog';
  return 'reports';
}

function sourcePaths(detail: TaskDetail): string[] {
  const paths = detail.task.input?.source_paths;
  return Array.isArray(paths) ? paths.map(String) : [];
}

function baseName(path: string): string {
  return path.replace(/\\/g, '/').split('/').filter(Boolean).pop() || path;
}

function isProductEvent(value: unknown): value is ProductEvent {
  if (!value || typeof value !== 'object') return false;
  const event = value as Partial<ProductEvent>;
  return typeof event.id === 'string'
    && typeof event.sequence === 'number'
    && event.protocol_name === 'eigent'
    && event.protocol_version === 1
    && typeof event.action === 'string'
    && Boolean(event.payload_json && typeof event.payload_json === 'object');
}

function FilesWorkspace({ detail }: { detail: TaskDetail }) {
  const sources = sourcePaths(detail);
  const [selected, setSelected] = useState('dir:sources');
  const selectedDirectory = VIRTUAL_DIRECTORIES.find((directory) => selected === `dir:${directory.id}`);
  const artifact = detail.artifacts.find((item) => selected === `artifact:${item.id}`) || null;
  const sourceIndex = selected.startsWith('source:') ? Number(selected.slice(7)) : -1;
  const selectedSource = sourceIndex >= 0 ? sources[sourceIndex] : '';
  const artifactsByDirectory = new Map<VirtualDirectoryId, TaskDetail['artifacts']>();
  VIRTUAL_DIRECTORIES.forEach((directory) => artifactsByDirectory.set(directory.id, []));
  detail.artifacts.forEach((item) => artifactsByDirectory.get(artifactDirectory(item))?.push(item));

  return <section className="files-workspace">
    <div className="section-header"><div><span className="eyebrow">文件工作区</span><h2>文件与证据</h2></div><span className="muted">{sources.length} 个源文件 · {detail.artifacts.length} 个产物</span></div>
    <div className="files-workspace-grid">
      <nav className="virtual-file-tree" aria-label="任务虚拟文件">
        <div className="virtual-root"><PackageOpen size={16} /><strong>{detail.task.objective}</strong></div>
        {VIRTUAL_DIRECTORIES.map((directory) => {
          const files = artifactsByDirectory.get(directory.id) || [];
          const count = directory.id === 'sources' ? sources.length : files.length;
          return <section className="virtual-directory" key={directory.id}>
            <button className={`virtual-directory-row ${selected === `dir:${directory.id}` ? 'selected' : ''}`} onClick={() => setSelected(`dir:${directory.id}`)}><ChevronDown size={14} /><Folder size={15} /><span>{directory.label}</span><small>{count}</small></button>
            <div className="virtual-directory-files">
              {directory.id === 'sources' && sources.map((path, index) => <button key={`${path}:${index}`} className={selected === `source:${index}` ? 'selected' : ''} onClick={() => setSelected(`source:${index}`)} title={path}><FileText size={14} /><span>{baseName(path)}</span></button>)}
              {files.map((item) => <button key={item.id} className={selected === `artifact:${item.id}` ? 'selected' : ''} onClick={() => setSelected(`artifact:${item.id}`)} title={item.file_name}><FileText size={14} /><span>{item.file_name}</span></button>)}
            </div>
          </section>;
        })}
      </nav>
      {artifact ? <article className="artifact-preview"><div className="card-heading"><div><span className="kicker">生成文件</span><h3>{artifact.title}</h3></div><a className="primary" href={api.artifactDownloadUrl(artifact.id)}>下载</a></div><dl><dt>文件名</dt><dd>{artifact.file_name}</dd><dt>负责人</dt><dd>{agentLabel(artifact.worker_name)}</dd><dt>生成时间</dt><dd>{new Date(artifact.created_at).toLocaleString('zh-CN')}</dd></dl><p className="notice">该文件由平台产物注册表管理，具有独立标识和下载地址。</p></article>
        : selectedSource ? <article className="artifact-preview"><div className="card-heading"><div><span className="kicker">源文件</span><h3>{baseName(selectedSource)}</h3></div></div><dl><dt>位置</dt><dd>{selectedSource}</dd><dt>状态</dt><dd>已添加到任务输入</dd></dl><p className="notice">源文件作为工作流输入；生成结果会作为不可变产物单独保存。</p></article>
          : <div className="virtual-directory-preview"><Folder size={34} /><span className="kicker">虚拟目录</span><h3>{selectedDirectory?.label || '任务文件'}</h3><p>{selectedDirectory?.description || '请从目录树中选择目录或文件。'}</p><strong>{selectedDirectory?.id === 'sources' ? sources.length : selectedDirectory ? artifactsByDirectory.get(selectedDirectory.id)?.length || 0 : 0} 项</strong></div>}
    </div>
  </section>;
}

function BusinessWorkspace({ id, taskId, detail, agents }: { id: WorkspaceId; taskId: string; detail: TaskDetail; agents: Agent[] }) {
  if (id === 'workflow') return <WorkFlow agents={agents} activeAgentId="workflow" focusedAgentId={agents.find((agent) => agent.status === 'running')?.agent_id} />;
  if (id === 'catalog_steward_agent') return <section className="agent-workspace"><div className="section-header"><div><span className="eyebrow">商品目录专员</span><h2>Product/SKU 商品图谱</h2><p className="muted">管理规范商品事实、变体、来源证据与版本记录。</p></div></div><ProductGraph taskId={taskId} /></section>;
  if (id === 'compliance_specialist_agent') return <section className="agent-workspace"><div className="section-header"><div><span className="eyebrow">合规专员</span><h2>美国市场合规审核</h2><p className="muted">服装法规与平台政策检查结果均关联到原始证据。</p></div></div><ProductIssues result={detail.task.result} /></section>;
  if (id === 'listing_operations_agent') return <section className="agent-workspace"><div className="section-header"><div><span className="eyebrow">商品刊登专员</span><h2>平台商品草稿</h2><p className="muted">基于规范 Product 事实生成 Shopify 和 eBay 美国站草稿。</p></div></div><ListingWorkspace result={detail.task.result} /></section>;
  if (id === 'governance_reviewer_agent') return <section className="agent-workspace"><div className="section-header"><div><span className="eyebrow">治理审核员</span><h2>交付就绪审核</h2><p className="muted">导出前处理阻塞项、审核证据并完成必要审批。</p></div></div><ProductIssues result={detail.task.result} /></section>;
  return <FilesWorkspace detail={detail} />;
}

export function Workspace({ taskId, onRefreshTasks, onBackToProject }: Props) {
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [events, setEvents] = useState<ProductEvent[]>([]);
  const [streamState, setStreamState] = useState<'connecting' | 'live' | 'reconnecting' | 'closed'>('connecting');
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>('workflow');
  const [chatVisible, setChatVisible] = useState(true);
  const [objective, setObjective] = useState('');
  const [error, setError] = useState('');
  const refresh = async () => { try { const next = await api.task(taskId); setDetail(next); setObjective(next.task.objective); await onRefreshTasks(); } catch (reason) { setError(localizedMessage(reason)); } };
  useEffect(() => {
    let disposed = false;
    let protocolBlocked = false;
    let source: EventSource | null = null;
    let timer: number | undefined;
    let cursor = 0;

    const scheduleReconnect = (delay = 1000) => {
      if (disposed || protocolBlocked) return;
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(() => void connect(), delay);
    };

    const connect = async () => {
      if (disposed || protocolBlocked) return;
      source?.close();
      setStreamState(cursor ? 'reconnecting' : 'connecting');
      try {
        const snapshot = await api.productEvents(taskId, cursor);
        if (snapshot.protocol_name !== 'eigent' || snapshot.protocol_version !== 1) {
          protocolBlocked = true;
          setStreamState('closed');
          setError('桌面端与后端事件协议版本不兼容，请安装同一版本后重试。');
          return;
        }
        const additions = (snapshot.items || []).filter(isProductEvent).filter((item) => item.sequence > cursor);
        if (additions.length) {
          additions.sort((left, right) => left.sequence - right.sequence);
          setEvents((current) => [...current, ...additions]);
          cursor = additions[additions.length - 1].sequence;
        }
        if (disposed) return;
        source = new EventSource(api.productEventStreamUrl(taskId, cursor));
        source.onopen = () => { setStreamState('live'); setError(''); };
        source.onerror = () => { source?.close(); setStreamState('reconnecting'); scheduleReconnect(); };
        source.addEventListener('cowork_product_event', (raw) => {
          try {
            const parsed = JSON.parse((raw as MessageEvent<string>).data) as unknown;
            if (!isProductEvent(parsed)) {
              protocolBlocked = true;
              source?.close();
              setStreamState('closed');
              setError('收到不兼容的任务事件，请确认桌面端与后端版本一致。');
              return;
            }
            if (parsed.sequence <= cursor) return;
            if (parsed.sequence !== cursor + 1) {
              source?.close();
              scheduleReconnect(0);
              return;
            }
            cursor = parsed.sequence;
            setEvents((current) => [...current, parsed]);
            void refresh();
          } catch {
            protocolBlocked = true;
            source?.close();
            setStreamState('closed');
            setError('任务事件无法解析，请确认桌面端与后端版本一致。');
          }
        });
      } catch (reason) {
        if (!disposed) {
          setError(localizedMessage(reason));
          setStreamState('reconnecting');
          scheduleReconnect(1500);
        }
      }
    };

    void refresh();
    void connect();
    const recovery = window.setInterval(() => void refresh(), 10000);
    return () => {
      disposed = true;
      source?.close();
      if (timer) window.clearTimeout(timer);
      window.clearInterval(recovery);
    };
  }, [taskId]);
  const nativeTask = useMemo(() => detail ? projectNativeTask(detail, events) : undefined, [detail, events]);
  const coworkTask = useMemo<CoworkTask | undefined>(() => detail ? projectTask(detail, events) : undefined, [detail, events]);
  const coworkDetail = useMemo(() => detail ? projectDetail(detail, events) : null, [detail, events]);
  const agents = nativeTask?.taskAssigning || [];
  async function submit(attachments?: CoworkInputAttachment[]) { if (!detail) return; const files = (attachments || []).map((item) => item.file).filter((item): item is File => Boolean(item)); if (files.length) await api.uploadSources(taskId, files); await api.runTask(taskId); await refresh(); }
  async function decide(approvalId: string, payload: Record<string, unknown>, rejected: boolean) { if (rejected) await api.reject(approvalId, payload); else await api.approve(approvalId, payload); await refresh(); }
  if (!detail) return <div className="workspace-state">{error || '正在加载任务工作区…'}</div>;
  return <main className="native-workspace-shell"><section className="native-workspace-frame"><ResizablePanelGroup direction="horizontal" key={chatVisible ? 'chat-open' : 'chat-closed'}>{chatVisible && <><ResizablePanel defaultSize={31} minSize={22} className="min-h-0"><ChatBox monitorOnly objective={objective} tasks={coworkTask ? [coworkTask] : []} activeTaskId={taskId} activeTask={coworkTask} nativeTask={nativeTask} loading={detail.task.status === 'running'} onObjectiveChange={setObjective} onSubmit={submit} onRefresh={() => void refresh()} onSelectTask={() => undefined} onStartTask={() => submit()} onCancelTask={() => undefined} activeDetail={coworkDetail} onOpenFile={() => setActiveWorkspace('documentWorkSpace')} /></ResizablePanel><ResizableHandle withHandle className="custom-resizable-handle" /></> }<ResizablePanel className="min-h-0"><section className="native-workspace-main"><header className="native-workspace-header"><button className="task-back-button" onClick={onBackToProject} title="返回项目素材库"><ArrowLeft size={16} /></button><div><span className="eyebrow">跨境商品目录工作区</span><h1>{detail.task.objective}</h1></div><span className={`stream-state ${streamState}`}>{statusLabel(streamState)}</span></header>{error && <div className="error-banner">{error}</div>}<div className="native-workspace-content"><BusinessWorkspace id={activeWorkspace} taskId={taskId} detail={detail} agents={agents} /></div><BottomBar agents={agents} activeWorkspace={activeWorkspace} isChatBoxVisible={chatVisible} onToggleChatBox={() => setChatVisible((value) => !value)} onSelectWorkspace={(id) => setActiveWorkspace(id as WorkspaceId)} /></section></ResizablePanel></ResizablePanelGroup></section>{detail.approvals.filter((approval) => approval.status === 'pending').map((approval) => <ApprovalCard key={approval.id} approval={approval} onDecide={decide} />)}</main>;
}
