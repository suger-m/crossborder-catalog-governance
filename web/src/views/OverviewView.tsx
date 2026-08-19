import { Database, FileText, Package, Play, ShoppingBag } from 'lucide-react';
import type { Project, Task } from '../api';
import type { ProjectBundle } from '../hooks/useProjectBundle';
import { formatDateTime } from '../lib/format';
import { statusLabel } from '../lib/crossborderLabels';
import { primaryExport, projectArtifacts } from '../projection/artifactProjection';
import { EmptyState, ErrorState, LoadingState, StatusBadge } from '../components/common/StatusViews';

interface Props {
  project: Project;
  tasks: Task[];
  bundle: ProjectBundle;
  loading: boolean;
  error: string;
  onOpenTask: (taskId: string) => void;
  onGoCatalog: () => void;
  onGoWorkbench: () => void;
}

export function OverviewView({
  project,
  tasks,
  bundle,
  loading,
  error,
  onOpenTask,
  onGoCatalog,
  onGoWorkbench,
}: Props) {
  if (loading && !bundle.materials.length && !tasks.length) {
    return <LoadingState title="正在加载项目总览" />;
  }
  if (error && !bundle.materials.length) {
    return <ErrorState description={error} />;
  }

  const recentCompleted = tasks
    .filter((task) => task.status === 'completed')
    .slice(0, 5);
  const projectedArtifacts = projectArtifacts(bundle.artifacts);
  const primaryDelivery = primaryExport(bundle.artifacts);
  const recentDeliveries = projectedArtifacts
    .filter((item) => item.deliveryClass !== 'internal')
    .slice(0, 6)
    .map((item) => item.artifact);
  const running = tasks.filter((task) => task.status === 'running').length;
  const pendingApproval = tasks.filter((task) => task.status === 'waiting_approval').length;

  return (
    <section className="view-panel overview-view">
      <header className="view-header">
        <div>
          <span className="eyebrow">项目总览</span>
          <h1>{project.name}</h1>
          <p>面向美国市场的女装商品目录治理：Shopify 与 eBay US 草稿导出，不自动上架。</p>
        </div>
        <div className="overview-actions">
          <button onClick={onGoCatalog}>管理素材与目录</button>
          <button className="primary" onClick={onGoWorkbench}>进入任务工作台</button>
        </div>
      </header>

      <div className="stat-grid">
        <article><Database size={18} /><strong>{bundle.materials.length}</strong><span>项目素材</span></article>
        <article><ShoppingBag size={18} /><strong>{bundle.products.length}</strong><span>规范商品</span></article>
        <article><Play size={18} /><strong>{tasks.length}</strong><span>任务总数</span></article>
        <article><Package size={18} /><strong>{bundle.artifacts.length}</strong><span>已生成产物</span></article>
      </div>

      <div className="overview-grid">
        <section className="panel-card">
          <div className="panel-card-heading">
            <div><span className="kicker">目标市场与渠道</span><h2>交付边界</h2></div>
          </div>
          <ul className="market-list">
            <li><strong>目标市场</strong><span>美国（女装）</span></li>
            <li><strong>渠道</strong><span>Shopify · eBay US</span></li>
            <li><strong>交付方式</strong><span>导出 Listing 包，不自动发布</span></li>
            <li><strong>协作运行时</strong><span>AgentTeams Manager / Worker</span></li>
          </ul>
          <div className="overview-status-row">
            <span>执行中 {running}</span>
            <span>待审批 {pendingApproval}</span>
            <span>资源版本 {bundle.resources.length}</span>
            <span>合规发现 {bundle.findings.filter((item) => item.status !== 'pass').length}</span>
          </div>
        </section>

        <section className="panel-card">
          <div className="panel-card-heading">
            <div><span className="kicker">最近任务</span><h2>执行动态</h2></div>
            <span className="muted">{tasks.length}</span>
          </div>
          {tasks.length ? (
            <div className="task-summary-list">
              {tasks.slice(0, 8).map((task) => (
                <button key={task.id} onClick={() => onOpenTask(task.id)}>
                  <span className={`task-dot ${task.status}`} />
                  <span>
                    <strong>{task.objective}</strong>
                    <small>{statusLabel(task.status)} · {formatDateTime(task.updated_at)}</small>
                  </span>
                  <StatusBadge status={task.status} />
                </button>
              ))}
            </div>
          ) : (
            <EmptyState
              title="还没有任务"
              description="先在「素材与商品目录」添加资料，再创建治理任务。"
              action={<button className="primary" onClick={onGoCatalog}>去添加素材</button>}
            />
          )}
        </section>

        <section className="panel-card">
          <div className="panel-card-heading">
            <div><span className="kicker">最近交付</span><h2>产物与完成结果</h2></div>
          </div>
          {recentDeliveries.length || recentCompleted.length ? (
            <div className="delivery-list">
              {primaryDelivery ? <article className="delivery-primary" key={primaryDelivery.artifact.id}>
                <Package size={18} />
                <div>
                  <strong>{primaryDelivery.artifact.title || '最终导出包'}</strong>
                  <small>{primaryDelivery.artifact.file_name} · 可下载</small>
                </div>
              </article> : null}
              {recentDeliveries.filter((artifact) => artifact.id !== primaryDelivery?.artifact.id).map((artifact) => (
                <article key={artifact.id}>
                  <FileText size={16} />
                  <div>
                    <strong>{artifact.title || artifact.file_name}</strong>
                    <small>{artifact.file_name} · {formatDateTime(artifact.created_at)}</small>
                  </div>
                </article>
              ))}
              {!recentDeliveries.length && recentCompleted.map((task) => (
                <article key={task.id}>
                  <Package size={16} />
                  <div>
                    <strong>{task.objective}</strong>
                    <small>已完成 · {formatDateTime(task.updated_at)}</small>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="暂无交付物" description="任务完成后，导出包、合规报告和 Listing 草稿会出现在这里。" />
          )}
        </section>
      </div>
    </section>
  );
}
