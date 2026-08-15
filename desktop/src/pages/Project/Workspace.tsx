import { useEffect, useState } from 'react';
import { api, type ModelSettings, type ProductEvent, type TaskDetail } from '../../api';
import { ApprovalCard } from '../../components/ApprovalCard/ApprovalCard';
import { ListingWorkspace } from '../../components/ListingWorkspace/ListingWorkspace';
import { ProductGraph } from '../../components/ProductGraph/ProductGraph';
import { ProductIssues } from '../../components/ProductIssues/ProductIssues';
import { workflowSteps } from '../../lib/workers';
type Tab = 'workflow' | 'graph' | 'issues' | 'listings' | 'files' | 'settings';
const tabs: Array<[Tab, string]> = [['workflow', 'Workflow'], ['graph', 'Product Graph'], ['issues', 'Compliance & Issues'], ['listings', 'Listings'], ['files', 'Files'], ['settings', 'Settings']];
interface Props { taskId: string; onRefreshTasks: () => Promise<void> }
function Settings() { const [settings, setSettings] = useState<ModelSettings | null>(null); const [form, setForm] = useState({ source: 'custom', model_platform: '', model_type: '', api_url: '', api_key: '', extra_params: '{}' }); const [message, setMessage] = useState(''); useEffect(() => { void (async () => { try { const value = await api.modelSettings(); setSettings(value); setForm((current) => ({ ...current, source: ['custom', 'local', 'cloud'].includes(value.source) ? value.source : 'custom', model_platform: value.model_platform, model_type: value.model_type, api_url: value.api_url, extra_params: JSON.stringify(value.extra_params || {}, null, 2) })); } catch (reason) { setMessage(reason instanceof Error ? reason.message : String(reason)); } })(); }, []); async function save(event: React.FormEvent) { event.preventDefault(); try { const extra_params = JSON.parse(form.extra_params || '{}') as Record<string, unknown>; const payload = { source: form.source, model_platform: form.model_platform, model_type: form.model_type, api_url: form.api_url, extra_params, ...(form.api_key ? { api_key: form.api_key } : {}) }; const saved = await api.saveModelSettings(payload); setSettings(saved); setForm((current) => ({ ...current, api_key: '' })); setMessage('Model configuration saved.'); } catch (reason) { setMessage(reason instanceof Error ? reason.message : 'Settings must contain valid JSON options.'); } } return <div className="settings-panel"><div className="notice">The backend never returns an API key. Leave the key field blank to retain an existing configured key.</div>{settings && <div className="settings-meta"><span>Active source: <strong>{settings.source}</strong></span><span>Key configured: <strong>{settings.has_api_key ? 'Yes' : 'No'}</strong></span><span>Version: <strong>{settings.version}</strong></span></div>}<form className="settings-form" onSubmit={(event) => void save(event)}><label>Source<select value={form.source} onChange={(event) => setForm({ ...form, source: event.target.value })}><option value="custom">Custom</option><option value="cloud">Cloud</option><option value="local">Local</option></select></label><label>Model platform<input required value={form.model_platform} placeholder="openai" onChange={(event) => setForm({ ...form, model_platform: event.target.value })} /></label><label>Model type<input required value={form.model_type} placeholder="gpt-5" onChange={(event) => setForm({ ...form, model_type: event.target.value })} /></label><label>API URL<input value={form.api_url} placeholder="https://…" onChange={(event) => setForm({ ...form, api_url: event.target.value })} /></label><label>New API key (optional)<input type="password" value={form.api_key} autoComplete="new-password" placeholder="Only enter to replace the saved key" onChange={(event) => setForm({ ...form, api_key: event.target.value })} /></label><label>Extra parameters (JSON)<textarea value={form.extra_params} onChange={(event) => setForm({ ...form, extra_params: event.target.value })} /></label><button className="primary" type="submit">Save settings</button></form>{message && <p className={message.startsWith('Model') ? 'success' : 'error'}>{message}</p>}</div>; }
function Workflow({ detail, refresh }: { detail: TaskDetail; refresh: () => Promise<void> }) { const [files, setFiles] = useState<File[]>([]); const [busy, setBusy] = useState(false); const [message, setMessage] = useState(''); const steps = workflowSteps(detail.task.steps); const hasSources = Array.isArray(detail.task.input?.source_paths) && detail.task.input.source_paths.length > 0; async function start() { if (!files.length && !hasSources) { setMessage('Add at least one source file before starting the workflow.'); return; } setBusy(true); try { if (files.length) await api.uploadSources(detail.task.id, files); await api.runTask(detail.task.id); setFiles([]); setMessage('Workflow queued. Progress will update automatically.'); await refresh(); } catch (reason) { setMessage(reason instanceof Error ? reason.message : String(reason)); } finally { setBusy(false); } } return <div className="workflow"><div className="workflow-intro"><div><span className="kicker">TASK</span><h3>{detail.task.objective}</h3><p className="muted">{detail.task.id}</p></div><span className={`status ${detail.task.status}`}>{detail.task.status}</span></div><div className="source-box"><label><strong>Source files</strong><input type="file" multiple onChange={(event) => setFiles(Array.from(event.target.files || []))} disabled={busy} /></label><p className="muted">{files.length ? `${files.length} file(s) ready to upload` : hasSources ? 'Source files uploaded' : 'CSV, Excel, JSON, PDF, Markdown, or image metadata'}</p><button className="primary" onClick={() => void start()} disabled={busy || ['running', 'completed'].includes(detail.task.status)}>{busy ? 'Starting…' : detail.task.status === 'completed' ? 'Workflow complete' : 'Start workflow'}</button></div><ol className="step-list">{steps.map((step) => <li key={step.id}><span className={`step-dot ${step.status}`} /><div><strong>{step.label}</strong><p>{step.title}</p></div><span className={`status ${step.status}`}>{step.status}</span></li>)}</ol>{detail.task.error && <p className="error">Workflow error: {detail.task.error}</p>}{message && <p className={message.startsWith('Workflow') ? 'success' : 'error'}>{message}</p>}<div className="event-log"><h4>Latest activity</h4>{detail.events.slice(-5).reverse().map((event) => <p key={event.sequence}><strong>{event.worker_name}</strong> · {event.event_type}</p>)}{!detail.events.length && <p className="muted">The plan is ready. Upload source files to begin.</p>}</div></div>; }
export function Workspace({ taskId, onRefreshTasks }: Props) {
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [productEvents, setProductEvents] = useState<ProductEvent[]>([]);
  const [streamState, setStreamState] = useState<'connecting' | 'live' | 'reconnecting' | 'closed'>('connecting');
  const [tab, setTab] = useState<Tab>('workflow');
  const [error, setError] = useState('');
  async function refresh() {
    try {
      setError('');
      setDetail(await api.task(taskId));
      await onRefreshTasks();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }
  useEffect(() => {
    let disposed = false;
    let source: EventSource | null = null;
    let retryTimer: number | undefined;
    let cursor = 0;
    const connect = async () => {
      if (disposed) return;
      setStreamState(cursor ? 'reconnecting' : 'connecting');
      try {
        const snapshot = await api.productEvents(taskId, cursor);
        if (disposed) return;
        const incoming = snapshot.items || [];
        if (incoming.length) {
          setProductEvents((current) => [...current, ...incoming.filter((item) => item.sequence > cursor)]);
          cursor = Math.max(cursor, ...incoming.map((item) => item.sequence));
        }
        source = new EventSource(api.productEventStreamUrl(taskId, cursor));
        source.onopen = () => setStreamState('live');
        source.onerror = () => {
          if (disposed) return;
          setStreamState('reconnecting');
          source?.close();
          retryTimer = window.setTimeout(() => void connect(), 1500);
        };
        source.addEventListener('cowork_product_event', (raw) => {
          if (disposed) return;
          try {
            const event = JSON.parse((raw as MessageEvent<string>).data) as ProductEvent;
            if (event.protocol_name !== 'eigent' || event.protocol_version !== 1) {
              setError('The backend product-event protocol is incompatible with this desktop build.');
              source?.close();
              return;
            }
            if (event.sequence !== cursor + 1) {
              source?.close();
              void connect();
              return;
            }
            cursor = event.sequence;
            setProductEvents((current) => [...current, event]);
            void refresh();
          } catch {
            setError('Received an invalid product event from the backend.');
          }
        });
      } catch (reason) {
        if (!disposed) {
          setStreamState('reconnecting');
          setError(reason instanceof Error ? reason.message : String(reason));
          retryTimer = window.setTimeout(() => void connect(), 1500);
        }
      }
    };
    void refresh();
    void connect();
    const recovery = window.setInterval(() => void refresh(), 10000);
    return () => {
      disposed = true;
      source?.close();
      if (retryTimer) window.clearTimeout(retryTimer);
      window.clearInterval(recovery);
      setStreamState('closed');
    };
  }, [taskId]);
  async function decide(approvalId: string, decision: Record<string, unknown>, rejected: boolean) {
    if (rejected) await api.reject(approvalId, decision); else await api.approve(approvalId, decision);
    await refresh();
  }
  if (error && !detail) return <div className="workspace-state error">Unable to load task: {error}</div>;
  if (!detail) return <div className="workspace-state">Loading task workspace…</div>;
  const recentEvents = productEvents.slice(-8).reverse();
  return <section className="workspace">
    <div className="workspace-title"><div><span className="kicker">CATALOG WORKSPACE</span><h2>{detail.task.objective}</h2><p className="muted">Backend state source · {productEvents.length} live events</p></div><div className="workspace-actions"><span className={`stream-state ${streamState}`}>{streamState === 'live' ? 'Live' : streamState}</span><button onClick={() => void refresh()}>Refresh</button></div></div>
    <nav className="tabs" aria-label="Workspace sections">{tabs.map(([id, label]) => <button key={id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>{label}</button>)}</nav>
    {error && <p className="error">Update failed: {error}</p>}
    <div className="tab-content">{tab === 'workflow' && <Workflow detail={detail} refresh={refresh} />}{tab === 'graph' && <ProductGraph taskId={taskId} />}{tab === 'issues' && <ProductIssues result={detail.task.result} />}{tab === 'listings' && <ListingWorkspace result={detail.task.result} />}{tab === 'files' && <div className="files-list">{detail.artifacts.map((artifact) => <article key={artifact.id}><div><strong>{artifact.title}</strong><p>{artifact.file_name} · {artifact.artifact_type} · {Math.max(1, Math.round(artifact.size_bytes / 1024))} KB</p></div><a href={api.artifactDownloadUrl(artifact.id)}>Download</a></article>)}{!detail.artifacts.length && <div className="empty-state"><h3>No artifacts yet</h3><p>Every workflow output, including the final listing package, will be available here as its own download.</p></div>}</div>}{tab === 'settings' && <Settings />}</div>
    <section className="activity-panel"><div className="card-heading"><h3>Workspace activity</h3><span>{recentEvents.length ? `Latest sequence ${recentEvents[0].sequence}` : 'Waiting for events'}</span></div>{recentEvents.map((event) => <article key={event.id}><span className="activity-action">{event.action}</span><div><strong>{String(event.payload_json.agent_name || event.payload_json.worker_name || event.payload_json.task_id || 'Platform')}</strong><p>{String(event.payload_json.message || event.payload_json.summary || event.payload_json.file_path || event.payload_json.state || '')}</p></div><time>{new Date(event.created_at).toLocaleTimeString()}</time></article>)}{!recentEvents.length && <p className="muted">The native workspace event stream will appear here as soon as the task starts.</p>}</section>
    {detail.approvals.filter((approval) => approval.status === 'pending').length > 0 && <section className="approval-section"><h3>Pending human approvals</h3>{detail.approvals.filter((approval) => approval.status === 'pending').map((approval) => <ApprovalCard key={approval.id} approval={approval} onDecide={decide} />)}</section>}
  </section>;
}
