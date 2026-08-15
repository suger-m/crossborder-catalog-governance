import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, Database, Download, FilePlus2, FileText, Loader2, PackagePlus, Play, Upload } from 'lucide-react';
import { api, type Project, type ProjectMaterial, type Task } from '../../api';
import { localizedMessage, statusLabel } from '../../lib/crossborderLabels';

interface Props {
  project: Project;
  tasks: Task[];
  onCreateTask: (objective: string, materialIds: string[]) => Promise<void>;
  onOpenTask: (taskId: string) => void;
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export function ProjectHome({ project, tasks, onCreateTask, onOpenTask }: Props) {
  const [materials, setMaterials] = useState<ProjectMaterial[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [objective, setObjective] = useState('');
  const [busy, setBusy] = useState<'loading' | 'uploading' | 'importing' | 'creating' | ''>('loading');
  const [message, setMessage] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const materialRequestRef = useRef(0);
  const activeProjectRef = useRef(project.id);
  activeProjectRef.current = project.id;

  async function loadMaterials(projectId = project.id) {
    const requestId = ++materialRequestRef.current;
    try {
      const result = await api.projectMaterials(projectId);
      if (requestId !== materialRequestRef.current) return null;
      setMaterials(result.items);
      setSelectedIds((current) => current.filter((id) => result.items.some((item) => item.id === id)));
      setMessage('');
      return result.items;
    } catch (reason) {
      if (requestId !== materialRequestRef.current) return null;
      setMessage(localizedMessage(reason));
      return null;
    } finally {
      if (requestId === materialRequestRef.current) setBusy('');
    }
  }

  useEffect(() => {
    setMaterials([]);
    setSelectedIds([]);
    setObjective('');
    setBusy('loading');
    void loadMaterials(project.id);
    return () => { materialRequestRef.current += 1; };
  }, [project.id]);

  async function upload(files: FileList | null) {
    const items = Array.from(files || []);
    if (!items.length) return;
    setBusy('uploading'); setMessage('');
    try {
      const result = await api.uploadProjectMaterials(project.id, items);
      if (activeProjectRef.current !== project.id) return;
      const loaded = await loadMaterials(project.id);
      if (!loaded || activeProjectRef.current !== project.id) return;
      setSelectedIds((current) => Array.from(new Set([...current, ...result.items.map((item) => item.id)])));
      setMessage(`已添加 ${result.items.length} 份素材。`);
    } catch (reason) { setMessage(localizedMessage(reason)); setBusy(''); }
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  async function importExample() {
    setBusy('importing'); setMessage('');
    try {
      const result = await api.importExampleMaterials(project.id);
      if (activeProjectRef.current !== project.id) return;
      const loaded = await loadMaterials(project.id);
      if (!loaded || activeProjectRef.current !== project.id) return;
      setSelectedIds((current) => Array.from(new Set([...current, ...result.items.map((item) => item.id)])));
      setMessage('女装示例数据已导入并选中。重复导入会自动去重。');
    } catch (reason) { setMessage(localizedMessage(reason)); setBusy(''); }
  }

  function toggleMaterial(id: string) {
    setSelectedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }

  async function createTask(event: React.FormEvent) {
    event.preventDefault();
    if (!objective.trim() || !selectedIds.length) return;
    setBusy('creating'); setMessage('');
    try { await onCreateTask(objective.trim(), selectedIds); }
    catch (reason) { setMessage(localizedMessage(reason)); setBusy(''); }
  }

  const selectedSize = useMemo(() => materials.filter((item) => selectedIds.includes(item.id)).reduce((sum, item) => sum + item.size_bytes, 0), [materials, selectedIds]);
  const disabled = Boolean(busy) || !objective.trim() || selectedIds.length === 0;

  return <section className="project-home">
    <header className="project-home-header">
      <div><span className="eyebrow">项目工作区</span><h1>{project.name}</h1><p>项目可以独立存在；添加素材并明确任务目标后，才会创建执行任务。</p></div>
      <div className="project-home-stats"><span><Database size={15} />{materials.length} 份素材</span><span><Play size={15} />{tasks.length} 个任务</span></div>
    </header>

    <div className="project-home-grid">
      <section className="material-library">
        <div className="section-header"><div><span className="eyebrow">项目素材库</span><h2>素材数据</h2></div><div className="material-actions"><button onClick={() => fileInputRef.current?.click()} disabled={Boolean(busy)}><Upload size={15} />上传素材</button><button onClick={() => void importExample()} disabled={Boolean(busy)}><PackagePlus size={15} />{busy === 'importing' ? '导入中…' : '导入示例数据'}</button></div></div>
        <input ref={fileInputRef} className="sr-only" type="file" multiple accept=".csv,.json,.jsonl,.md,.txt,.xlsx,.pdf,.png,.jpg,.jpeg,.webp" aria-label="选择项目素材" onChange={(event) => void upload(event.target.files)} />
        {busy === 'loading' ? <div className="material-empty"><Loader2 className="spin" /><p>正在读取项目素材…</p></div>
          : materials.length ? <div className="material-list">{materials.map((item) => {
            const selected = selectedIds.includes(item.id);
            return <article className={`material-row ${selected ? 'selected' : ''}`} key={item.id}>
              <button className="material-select" onClick={() => toggleMaterial(item.id)} aria-label={`${selected ? '取消选择' : '选择'} ${item.file_name}`}><span className="material-check">{selected ? <Check size={14} /> : null}</span><FileText size={18} /><span><strong>{item.file_name}</strong><small>{item.origin === 'example' ? '示例数据' : '用户上传'} · {formatBytes(item.size_bytes)} · SHA-256 {item.sha256.slice(0, 10)}</small></span></button>
              <a href={api.projectMaterialDownloadUrl(item.id)} title="下载原始素材"><Download size={15} /></a>
            </article>;
          })}</div>
          : <div className="material-empty"><FilePlus2 size={30} /><h3>项目还没有素材</h3><p>上传供应商商品资料，或显式导入一份可直接运行的女装示例数据。</p><div><button className="primary" onClick={() => fileInputRef.current?.click()}><Upload size={15} />上传素材</button><button onClick={() => void importExample()}><PackagePlus size={15} />导入示例数据</button></div></div>}
      </section>

      <aside className="project-task-panel">
        <form onSubmit={(event) => void createTask(event)}>
          <span className="eyebrow">新建治理任务</span><h2>选择素材后开始</h2><p>智能体团队会建立商品事实、检查美国合规并生成 Shopify/eBay 草稿。</p>
          <label>任务目标<textarea value={objective} onChange={(event) => setObjective(event.target.value)} placeholder="例如：审核这批女装的美国合规性，并生成 Shopify 和 eBay 美国站草稿" /></label>
          <div className="task-selection-summary"><strong>{selectedIds.length} 份已选素材</strong><span>{formatBytes(selectedSize)}</span></div>
          {!materials.length ? <p className="task-guidance">请先上传素材或导入示例数据。</p> : !selectedIds.length ? <p className="task-guidance">请从左侧勾选本次任务需要使用的素材。</p> : null}
          <button className="primary project-run-button" type="submit" disabled={disabled}>{busy === 'creating' ? <><Loader2 className="spin" size={16} />正在创建…</> : <><Play size={16} />创建并运行任务</>}</button>
          {message && <p className={message.includes('已') ? 'success' : 'error'}>{message}</p>}
        </form>
        <div className="recent-project-tasks"><div className="section-label"><h3>最近任务</h3><span>{tasks.length}</span></div>{tasks.slice(0, 5).map((task) => <button key={task.id} onClick={() => onOpenTask(task.id)}><span className={`task-dot ${task.status}`} /><span><strong>{task.objective}</strong><small>{statusLabel(task.status)}</small></span><span>›</span></button>)}{!tasks.length && <p>还没有任务。导入素材后创建第一项任务。</p>}</div>
      </aside>
    </div>
  </section>;
}
