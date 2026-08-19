import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, Download, FileText, Folder, LoaderCircle, PackageOpen, TriangleAlert } from 'lucide-react';
import { api, type Artifact, type ArtifactPreview, type ProjectMaterial, type Task, type TaskDetail } from '../api';
import type { ProjectBundle } from '../hooks/useProjectBundle';
import { formatBytes, formatDateTime } from '../lib/format';
import { agentLabel, localizedMessage } from '../lib/crossborderLabels';
import { primaryExport, projectArtifacts, type ProjectedArtifact } from '../projection/artifactProjection';
import { EmptyState, ErrorState, LoadingState } from '../components/common/StatusViews';
import { MarkdownPreview } from '../components/common/MarkdownPreview';
import { ListingDraftsPanel } from '../components/catalog/ListingDraftsPanel';
import { ComplianceFindingsPanel } from '../components/catalog/ComplianceFindingsPanel';

type VirtualDirectoryId = 'sources' | 'catalog' | 'compliance' | 'listings' | 'governance' | 'exports' | 'reports' | 'internal';

const VIRTUAL_DIRECTORIES: Array<{ id: VirtualDirectoryId; label: string; description: string }> = [
  { id: 'sources', label: '项目素材', description: '当前项目已导入的供应商文件。' },
  { id: 'catalog', label: '商品目录', description: '规范 Product/SKU 事实与分类结果。' },
  { id: 'compliance', label: '合规检查', description: '美国服装法规与平台政策检查结果。' },
  { id: 'listings', label: '平台草稿', description: 'Shopify 和 eBay 美国站商品草稿。' },
  { id: 'governance', label: '治理审核', description: '交付决策、审核结果与审批记录。' },
  { id: 'exports', label: '导出包', description: '可交付的平台商品目录包。' },
  { id: 'reports', label: '报告', description: '生成的 Markdown 报告与辅助文件。' },
  { id: 'internal', label: '内部资料', description: '结构化元数据和过程性文件，默认不作为最终交付。' },
];

interface Props {
  tasks: Task[];
  selectedTaskId: string | null;
  detail: TaskDetail | null;
  taskArtifacts: Artifact[];
  bundle: ProjectBundle;
  preferredArtifactId?: string;
  loading: boolean;
  error: string;
}

function PrimaryDeliveryPanel({ projected }: { projected: ProjectedArtifact | null }) {
  if (!projected) {
    return (
      <section className="primary-delivery missing">
        <div>
          <h2>尚未生成最终导出包</h2>
          <p>治理审核通过后会出现在这里。</p>
        </div>
        <span className="delivery-state">等待生成</span>
      </section>
    );
  }
  const artifact = projected.artifact;
  const memberCount = Number(artifact.metadata?.member_count || artifact.dependency_ids?.length || 0);
  return (
    <section className="primary-delivery">
      <div className="delivery-heading">
        <div>
          <h2>{artifact.title || '美国站商品目录导出包'}</h2>
          <p>{artifact.file_name}</p>
        </div>
        <span className="delivery-state">已封存</span>
      </div>
      <div className="delivery-facts">
        <div><span>文件大小</span><strong>{formatBytes(artifact.size_bytes)}</strong></div>
        <div><span>包内文件</span><strong>{memberCount ? `${memberCount} 个` : '已生成'}</strong></div>
        <div><span>完整性</span><strong>SHA-256 已记录</strong></div>
      </div>
      <a className="delivery-download" href={api.artifactDownloadUrl(artifact.id)}><Download size={16} />下载导出包</a>
      <small>仅导出，不自动发布到 Shopify 或 eBay US</small>
    </section>
  );
}

function StructuredArtifactPreview({ content }: { content: string }) {
  let value: unknown;
  try { value = JSON.parse(content) as unknown; } catch { value = null; }
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return <div className="structured-preview"><strong>结构化文件</strong><p>该文件为内部结构化资料，原始内容不在主界面展开。</p></div>;
  }
  const entries = Object.entries(value as Record<string, unknown>).filter(([, item]) => ['string', 'number', 'boolean'].includes(typeof item)).slice(0, 8);
  return <div className="structured-preview"><div className="structured-preview-heading"><strong>结构化摘要</strong><span>{Object.keys(value as Record<string, unknown>).length} 个字段</span></div><div className="structured-preview-grid">{entries.map(([key, item]) => <div key={key}><span>{key}</span><strong>{String(item)}</strong></div>)}</div><p>原始 JSON 保留在下载文件中，仅在此显示可读摘要。</p></div>;
}

function ArtifactPreviewPane({ artifact }: { artifact: Artifact }) {
  const [preview, setPreview] = useState<ArtifactPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let disposed = false;
    setPreview(null);
    setLoading(true);
    setError('');
    void api.artifactPreview(artifact.id)
      .then((value) => { if (!disposed) setPreview(value); })
      .catch((reason) => { if (!disposed) setError(localizedMessage(reason)); })
      .finally(() => { if (!disposed) setLoading(false); });
    return () => { disposed = true; };
  }, [artifact.id]);

  async function loadMore() {
    if (!preview?.next_offset) return;
    try {
      setLoading(true);
      const next = await api.artifactPreview(artifact.id, preview.next_offset);
      setPreview({ ...next, content: `${preview.content || ''}${next.content || ''}` });
    } catch (reason) {
      setError(localizedMessage(reason));
    } finally {
      setLoading(false);
    }
  }

  const isMarkdown = artifact.mime_type.includes('markdown') || artifact.file_name.toLowerCase().endsWith('.md');
  const isStructured = !isMarkdown && (artifact.mime_type.includes('json') || artifact.file_name.toLowerCase().endsWith('.json'));

  return (
    <article className="artifact-preview">
      <div className="card-heading">
        <div>
          <h3>{artifact.title}</h3>
        </div>
        <a className="primary artifact-download" href={api.artifactDownloadUrl(artifact.id)}><Download size={14} />下载</a>
      </div>
      <dl>
        <dt>文件名</dt><dd>{artifact.file_name}</dd>
        <dt>负责人</dt><dd>{agentLabel(artifact.worker_name)}</dd>
        <dt>生成时间</dt><dd>{formatDateTime(artifact.created_at)}</dd>
        <dt>大小</dt><dd>{formatBytes(artifact.size_bytes)}</dd>
      </dl>
      {loading && !preview ? <div className="workspace-inline-state"><LoaderCircle className="spin" size={16} />正在读取该文件…</div> : null}
      {error ? <div className="workspace-inline-state failed"><TriangleAlert size={16} />{error}</div> : null}
      {preview?.content != null ? (
        <div className={`artifact-content ${isMarkdown ? 'markdown' : 'plain'}`}>
          {isMarkdown ? <MarkdownPreview content={preview.content} /> : isStructured ? <StructuredArtifactPreview content={preview.content} /> : <pre>{preview.content}</pre>}
        </div>
      ) : !loading && !error ? <p className="notice">该文件不支持文本预览，可下载后查看。</p> : null}
      {preview?.truncated ? <button className="secondary artifact-load-more" disabled={loading} onClick={() => void loadMore()}>继续加载</button> : null}
    </article>
  );
}

export function ResultsView({
  tasks,
  selectedTaskId,
  detail,
  taskArtifacts,
  bundle,
  preferredArtifactId = '',
  loading,
  error,
}: Props) {
  const [selected, setSelected] = useState(preferredArtifactId ? `artifact:${preferredArtifactId}` : 'dir:sources');

  useEffect(() => {
    if (preferredArtifactId) setSelected(`artifact:${preferredArtifactId}`);
  }, [preferredArtifactId]);

  const visibleArtifacts = useMemo(() => {
    const unique = new Map<string, Artifact>();
    [...bundle.artifacts, ...taskArtifacts].forEach((item) => unique.set(item.id, item));
    return projectArtifacts(Array.from(unique.values()));
  }, [bundle.artifacts, taskArtifacts]);

  const primaryDelivery = useMemo(() => primaryExport(visibleArtifacts.map((item) => item.artifact)), [visibleArtifacts]);

  const artifactsByDirectory = useMemo(() => {
    const map = new Map<VirtualDirectoryId, Artifact[]>();
    VIRTUAL_DIRECTORIES.forEach((directory) => map.set(directory.id, []));
    visibleArtifacts.forEach((item) => map.get(item.directory)?.push(item.artifact));
    return map;
  }, [visibleArtifacts]);

  if (loading && !bundle.materials.length && !visibleArtifacts.length) {
    return <LoadingState title="正在加载结果与文件" />;
  }
  if (error && !bundle.materials.length && !visibleArtifacts.length) {
    return <ErrorState description={error} />;
  }

  const selectedDirectory = VIRTUAL_DIRECTORIES.find((directory) => selected === `dir:${directory.id}`);
  const artifact = visibleArtifacts.find((item) => selected === `artifact:${item.artifact.id}`)?.artifact || null;
  const material = bundle.materials.find((item) => selected === `material:${item.id}`) || null;
  const taskLabel = detail?.task.objective
    || tasks.find((task) => task.id === selectedTaskId)?.objective
    || '项目结果工作区';

  return (
    <section className="view-panel results-view">
      <header className="view-header">
        <div>
          <h1>交付</h1>
        </div>
      </header>

      <PrimaryDeliveryPanel projected={primaryDelivery} />

      <div className="files-workspace-grid">
        <nav className="virtual-file-tree" aria-label="项目虚拟文件">
          <div className="virtual-root"><PackageOpen size={16} /><strong>{taskLabel}</strong></div>
          {VIRTUAL_DIRECTORIES.map((directory) => {
            const files = artifactsByDirectory.get(directory.id) || [];
            const count = directory.id === 'sources' ? bundle.materials.length : files.length;
            return (
              <section className="virtual-directory" key={directory.id}>
                <button className={`virtual-directory-row ${selected === `dir:${directory.id}` ? 'selected' : ''}`} onClick={() => setSelected(`dir:${directory.id}`)}>
                  <ChevronDown size={14} /><Folder size={15} /><span>{directory.label}</span><small>{count}</small>
                </button>
                <div className="virtual-directory-files">
                  {directory.id === 'sources' && bundle.materials.map((item: ProjectMaterial) => (
                    <button key={item.id} className={selected === `material:${item.id}` ? 'selected' : ''} onClick={() => setSelected(`material:${item.id}`)} title={item.file_name}>
                      <FileText size={14} /><span>{item.file_name}</span>
                    </button>
                  ))}
                  {files.map((item) => (
                    <button key={item.id} className={selected === `artifact:${item.id}` ? 'selected' : ''} onClick={() => setSelected(`artifact:${item.id}`)} title={item.file_name}>
                      <FileText size={14} /><span>{item.file_name}</span>
                    </button>
                  ))}
                </div>
              </section>
            );
          })}
        </nav>

        {artifact ? (
          <ArtifactPreviewPane artifact={artifact} />
        ) : material ? (
          <article className="artifact-preview">
            <div className="card-heading">
              <div><h3>{material.file_name}</h3></div>
              <a className="primary artifact-download" href={api.projectMaterialDownloadUrl(material.id)}><Download size={14} />下载</a>
            </div>
            <dl>
              <dt>类型</dt><dd>{material.mime_type}</dd>
              <dt>大小</dt><dd>{formatBytes(material.size_bytes)}</dd>
              <dt>来源</dt><dd>{material.origin === 'example' ? '示例素材' : '用户上传'}</dd>
              <dt>校验</dt><dd>SHA-256 {material.sha256.slice(0, 16)}…</dd>
            </dl>
          </article>
        ) : selectedDirectory?.id === 'listings' ? (
          <div className="panel-card fill">
            <div className="panel-card-heading"><div><span className="kicker">平台草稿目录</span><h2>{selectedDirectory.label}</h2></div></div>
            <ListingDraftsPanel drafts={bundle.listings} />
          </div>
        ) : selectedDirectory?.id === 'compliance' ? (
          <div className="panel-card fill">
            <div className="panel-card-heading"><div><span className="kicker">合规目录</span><h2>{selectedDirectory.label}</h2></div></div>
            <ComplianceFindingsPanel findings={bundle.findings} />
          </div>
        ) : (
          <div className="virtual-directory-preview">
            <Folder size={34} />
            <h3>{selectedDirectory?.label || '项目文件'}</h3>
            <p>{selectedDirectory?.description || '请从目录树中选择目录或文件。'}</p>
            <strong>
              {selectedDirectory?.id === 'sources'
                ? bundle.materials.length
                : selectedDirectory
                  ? artifactsByDirectory.get(selectedDirectory.id)?.length || 0
                  : 0}
              {' '}项
            </strong>
            {!bundle.materials.length && !visibleArtifacts.length ? (
              <EmptyState title="还没有结果文件" description="完成任务后，产物会出现在对应虚拟目录中。" />
            ) : null}
          </div>
        )}
      </div>
    </section>
  );
}
