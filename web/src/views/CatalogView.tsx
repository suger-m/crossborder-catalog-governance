import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, Download, FilePlus2, FileText, Loader2, PackagePlus, Play, Upload } from 'lucide-react';
import { api, type ProductDetail, type ProductSummary, type Project, type ProjectMaterial, type ProjectResource, type Task } from '../api';
import type { ProjectBundle } from '../hooks/useProjectBundle';
import { formatBytes, formatDateTime } from '../lib/format';
import { agentLabel, localizedMessage, statusLabel } from '../lib/crossborderLabels';
import { EmptyState, ErrorState, LoadingState, StatusBadge } from '../components/common/StatusViews';
import { ListingDraftsPanel } from '../components/catalog/ListingDraftsPanel';
import { ComplianceFindingsPanel } from '../components/catalog/ComplianceFindingsPanel';

interface Props {
  project: Project;
  tasks: Task[];
  bundle: ProjectBundle;
  loading: boolean;
  error: string;
  onRefreshBundle: () => Promise<void>;
  onCreateTask: (objective: string, materialIds: string[]) => Promise<void>;
  onOpenTask: (taskId: string) => void;
}

function factValue(item: unknown): string {
  if (Array.isArray(item)) return item.join(', ') || '—';
  if (typeof item === 'object' && item !== null) return JSON.stringify(item);
  return String(item || '—');
}

function ProductDetailPane({ productId }: { productId: string }) {
  const [detail, setDetail] = useState<ProductDetail | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let disposed = false;
    setLoading(true);
    setError('');
    void api.product(productId)
      .then((value) => { if (!disposed) setDetail(value); })
      .catch((reason) => { if (!disposed) setError(localizedMessage(reason)); })
      .finally(() => { if (!disposed) setLoading(false); });
    return () => { disposed = true; };
  }, [productId]);

  if (loading) return <LoadingState title="正在加载商品事实" />;
  if (error) return <ErrorState description={error} />;
  if (!detail) return <EmptyState title="未找到商品" description="该商品可能已被覆盖或尚未写入目录。" />;

  const product = detail.data;
  return (
    <section className="product-detail">
      <div className="card-heading">
        <div>
          <span className="kicker">规范 Product</span>
          <h3>{product.title}</h3>
        </div>
        <StatusBadge status={product.status} />
      </div>
      <div className="fact-grid">
        {[
          ['商品 ID', product.external_id],
          ['版本', `v${product.version}`],
          ['商品分类', product.category],
          ['服装类型', product.garment_type],
          ['材质', product.materials],
          ['纤维成分', product.fiber_content],
          ['原产地', product.country_of_origin],
          ['护理说明', product.care_instructions],
          ['制造商', product.manufacturer],
        ].map(([label, item]) => (
          <div key={String(label)}><span>{label}</span><strong>{factValue(item)}</strong></div>
        ))}
      </div>
      <h4>SKU（{product.skus.length}）</h4>
      <div className="table-wrap">
        <table>
          <thead><tr><th>SKU</th><th>颜色</th><th>尺码</th><th>价格</th><th>库存</th></tr></thead>
          <tbody>
            {product.skus.map((sku) => (
              <tr key={sku.id}>
                <td>{sku.external_id}</td>
                <td>{sku.color || '—'}</td>
                <td>{sku.size || '—'}</td>
                <td>{sku.price || '—'}</td>
                <td>{sku.inventory ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h4>来源证据与版本</h4>
      <div className="evidence-list">
        {product.facts.map((fact) => (
          <article key={fact.id}>
            <strong>{fact.field_name}: {factValue(fact.value)}</strong>
            <span>{fact.evidence.file_name} · {fact.evidence.location} · 置信度 {(fact.confidence * 100).toFixed(0)}%</span>
            <p>{fact.evidence.text || '未记录原文片段。'}</p>
          </article>
        ))}
        {!product.facts.length && <p className="muted">该商品尚未记录来源证据。</p>}
      </div>
      <p className="muted">图谱：{detail.graph.nodes.length} 个节点 · {detail.graph.edges.length} 条关系</p>
    </section>
  );
}

function ResourceList({ resources }: { resources: ProjectResource[] }) {
  if (!resources.length) {
    return <EmptyState title="尚无项目资源版本" description="任务执行后，Product/SKU、合规结论与 Listing 草稿会以资源版本写入。" />;
  }
  return (
    <div className="resource-list">
      {resources.map((resource) => (
        <article key={resource.id}>
          <div>
            <strong>{resource.logical_key}</strong>
            <small>{resource.resource_type} · v{resource.version} · {agentLabel(resource.owner_worker_name)}</small>
          </div>
          <StatusBadge status={resource.status} />
        </article>
      ))}
    </div>
  );
}

export function CatalogView({
  project,
  tasks,
  bundle,
  loading,
  error,
  onRefreshBundle,
  onCreateTask,
  onOpenTask,
}: Props) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [objective, setObjective] = useState('');
  const [busy, setBusy] = useState<'uploading' | 'importing' | 'creating' | ''>('');
  const [message, setMessage] = useState('');
  const [catalogTab, setCatalogTab] = useState<'materials' | 'products' | 'resources' | 'listings' | 'compliance'>('materials');
  const [selectedProductId, setSelectedProductId] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setSelectedIds((current) => current.filter((id) => bundle.materials.some((item) => item.id === id)));
    if (!selectedProductId && bundle.products[0]) setSelectedProductId(bundle.products[0].id);
  }, [bundle.materials, bundle.products, selectedProductId]);

  async function upload(files: FileList | null) {
    const items = Array.from(files || []);
    if (!items.length) return;
    setBusy('uploading');
    setMessage('');
    try {
      const result = await api.uploadProjectMaterials(project.id, items);
      await onRefreshBundle();
      setSelectedIds((current) => Array.from(new Set([...current, ...result.items.map((item) => item.id)])));
      setMessage(`已添加 ${result.items.length} 份素材。`);
    } catch (reason) {
      setMessage(localizedMessage(reason));
    } finally {
      setBusy('');
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function importExample() {
    setBusy('importing');
    setMessage('');
    try {
      const result = await api.importExampleMaterials(project.id);
      await onRefreshBundle();
      setSelectedIds((current) => Array.from(new Set([...current, ...result.items.map((item) => item.id)])));
      setMessage('女装示例数据已导入并选中。重复导入会自动去重。');
    } catch (reason) {
      setMessage(localizedMessage(reason));
    } finally {
      setBusy('');
    }
  }

  function toggleMaterial(id: string) {
    setSelectedIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  async function createTask(event: React.FormEvent) {
    event.preventDefault();
    if (!objective.trim() || !selectedIds.length) return;
    setBusy('creating');
    setMessage('');
    try {
      await onCreateTask(objective.trim(), selectedIds);
    } catch (reason) {
      setMessage(localizedMessage(reason));
      setBusy('');
    }
  }

  const selectedSize = useMemo(
    () => bundle.materials.filter((item) => selectedIds.includes(item.id)).reduce((sum, item) => sum + item.size_bytes, 0),
    [bundle.materials, selectedIds],
  );

  if (loading && !bundle.materials.length && !bundle.products.length) {
    return <LoadingState title="正在加载素材与商品目录" />;
  }
  if (error && !bundle.materials.length && !bundle.products.length) {
    return <ErrorState description={error} />;
  }

  return (
    <section className="view-panel catalog-view">
      <header className="view-header">
        <div>
          <span className="eyebrow">素材与商品目录</span>
          <h1>项目资料、Product/SKU 与版本来源</h1>
          <p>素材是输入；规范商品事实、资源版本和渠道草稿来自后端权威状态。</p>
        </div>
      </header>

      <nav className="subnav" aria-label="目录分区">
        {[
          ['materials', `项目素材 ${bundle.materials.length}`],
          ['products', `规范商品 ${bundle.products.length}`],
          ['resources', `资源版本 ${bundle.resources.length}`],
          ['compliance', `合规发现 ${bundle.findings.filter((item) => item.status !== 'pass').length}`],
          ['listings', `平台草稿 ${bundle.listings.length}`],
        ].map(([id, label]) => (
          <button key={id} className={catalogTab === id ? 'active' : ''} onClick={() => setCatalogTab(id as typeof catalogTab)}>{label}</button>
        ))}
      </nav>

      {catalogTab === 'materials' && (
        <div className="catalog-grid">
          <section className="panel-card">
            <div className="panel-card-heading">
              <div><span className="kicker">项目素材库</span><h2>供应商与示例资料</h2></div>
              <div className="material-actions">
                <button onClick={() => fileInputRef.current?.click()} disabled={Boolean(busy)}><Upload size={15} />上传素材</button>
                <button onClick={() => void importExample()} disabled={Boolean(busy)}><PackagePlus size={15} />{busy === 'importing' ? '导入中…' : '导入示例数据'}</button>
              </div>
            </div>
            <input
              ref={fileInputRef}
              className="sr-only"
              type="file"
              multiple
              accept=".csv,.json,.jsonl,.md,.txt,.xlsx,.pdf,.png,.jpg,.jpeg,.webp"
              aria-label="选择项目素材"
              onChange={(event) => void upload(event.target.files)}
            />
            {bundle.materials.length ? (
              <div className="material-list">
                {bundle.materials.map((item: ProjectMaterial) => {
                  const selected = selectedIds.includes(item.id);
                  return (
                    <article className={`material-row ${selected ? 'selected' : ''}`} key={item.id}>
                      <button className="material-select" onClick={() => toggleMaterial(item.id)} aria-label={`${selected ? '取消选择' : '选择'} ${item.file_name}`}>
                        <span className="material-check">{selected ? <Check size={14} /> : null}</span>
                        <FileText size={18} />
                        <span>
                          <strong>{item.file_name}</strong>
                          <small>{item.origin === 'example' ? '示例数据' : '用户上传'} · {formatBytes(item.size_bytes)} · {formatDateTime(item.created_at)}</small>
                        </span>
                      </button>
                      <a href={api.projectMaterialDownloadUrl(item.id)} title="下载原始素材"><Download size={15} /></a>
                    </article>
                  );
                })}
              </div>
            ) : (
              <EmptyState
                title="项目还没有素材"
                description="上传供应商商品资料，或显式导入一份可直接运行的女装示例数据。"
                action={(
                  <div className="inline-actions">
                    <button className="primary" onClick={() => fileInputRef.current?.click()}><Upload size={15} />上传素材</button>
                    <button onClick={() => void importExample()}><PackagePlus size={15} />导入示例数据</button>
                  </div>
                )}
              />
            )}
          </section>

          <aside className="panel-card task-create-panel">
            <form onSubmit={(event) => void createTask(event)}>
              <span className="kicker">新建治理任务</span>
              <h2>选择素材后开始</h2>
              <p>智能体团队会按目标自主协作，建立商品事实、检查美国合规、生成 Shopify / eBay US 草稿，并在完整交付目标下生成最终导出包。</p>
              <label>任务目标
                <textarea
                  value={objective}
                  onChange={(event) => setObjective(event.target.value)}
                  placeholder="例如：审核这批女装的美国合规性，并生成 Shopify 和 eBay 美国站草稿"
                />
              </label>
              <div className="task-selection-summary">
                <strong>{selectedIds.length} 份已选素材</strong>
                <span>{formatBytes(selectedSize)}</span>
              </div>
              {!bundle.materials.length
                ? <p className="task-guidance">请先上传素材或导入示例数据。</p>
                : !selectedIds.length
                  ? <p className="task-guidance">请从左侧勾选本次任务需要使用的素材。</p>
                  : null}
              <button className="primary" type="submit" disabled={Boolean(busy) || !objective.trim() || !selectedIds.length}>
                {busy === 'creating' ? <><Loader2 className="spin" size={16} />正在创建…</> : <><Play size={16} />创建并运行任务</>}
              </button>
              {message && <p className={message.includes('已') ? 'success' : 'error'}>{message}</p>}
            </form>
            <div className="recent-project-tasks">
              <div className="section-label"><h3>最近任务</h3><span>{tasks.length}</span></div>
              {tasks.slice(0, 5).map((task) => (
                <button key={task.id} onClick={() => onOpenTask(task.id)}>
                  <span className={`task-dot ${task.status}`} />
                  <span><strong>{task.objective}</strong><small>{statusLabel(task.status)}</small></span>
                  <span>›</span>
                </button>
              ))}
              {!tasks.length && <p className="muted">还没有任务。导入素材后创建第一项任务。</p>}
            </div>
          </aside>
        </div>
      )}

      {catalogTab === 'products' && (
        <div className="catalog-grid">
          <nav className="panel-card product-list" aria-label="规范商品">
            {bundle.products.length ? bundle.products.map((item: ProductSummary) => (
              <button key={item.id} className={selectedProductId === item.id ? 'selected' : ''} onClick={() => setSelectedProductId(item.id)}>
                <strong>{item.title}</strong>
                <span>{item.external_id} · v{item.version}</span>
              </button>
            )) : (
              <EmptyState title="暂无规范商品" description="运行商品目录任务后，系统将在此构建 Product/SKU 事实。" />
            )}
          </nav>
          <div className="panel-card">
            {selectedProductId
              ? <ProductDetailPane key={selectedProductId} productId={selectedProductId} />
              : <EmptyState title="选择一件商品" description="查看规范事实、SKU、来源证据与图谱关系。" />}
          </div>
        </div>
      )}

      {catalogTab === 'resources' && (
        <div className="panel-card">
          <div className="panel-card-heading"><div><span className="kicker">ProjectResource</span><h2>资源版本与归属</h2></div></div>
          <ResourceList resources={bundle.resources} />
        </div>
      )}

      {catalogTab === 'compliance' && (
        <div className="panel-card">
          <div className="panel-card-heading"><div><span className="kicker">美国合规</span><h2>服装法规与平台政策发现</h2></div></div>
          <ComplianceFindingsPanel findings={bundle.findings} />
        </div>
      )}

      {catalogTab === 'listings' && (
        <div className="panel-card">
          <div className="panel-card-heading"><div><span className="kicker">渠道草稿</span><h2>Shopify / eBay US</h2></div></div>
          <ListingDraftsPanel drafts={bundle.listings} />
        </div>
      )}
    </section>
  );
}
