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

  const recentCompleted = tasks.filter((task) => task.status === 'completed').slice(0, 5);
  const projectedArtifacts = projectArtifacts(bundle.artifacts);
  const primaryDelivery = primaryExport(bundle.artifacts);
  const recentDeliveries = projectedArtifacts
    .filter((item) => item.deliveryClass !== 'internal')
    .slice(0, 6)
    .map((item) => item.artifact);
  const running = tasks.filter((task) => task.status === 'running').length;
  const pendingApproval = tasks.filter((task) => task.status === 'waiting_approval').length;
  const primaryAction = tasks.length ? onGoWorkbench : onGoCatalog;

  return (
    <section className="view-panel overview-view">
      <header className="view-header">
        <div>
          <h1>{project.name}</h1>
        </div>
        <div className="overview-actions">
          <button className="primary" onClick={primaryAction}>{tasks.length ? '打开工作台' : '添加素材'}</button>
        </div>
      </header>

      <div className="context-pills">
        <span>美国市场</span>
        <span>Shopify · eBay US</span>
        <span>只导出不上架</span>
        {running ? <span>执行中 {running}</span> : null}
        {pendingApproval ? <span>待审批 {pendingApproval}</span> : null}
      </div>

      <div className="metric-row">
        <div><strong>{bundle.materials.length}</strong><span>素材</span></div>
        <div><strong>{bundle.products.length}</strong><span>商品</span></div>
        <div><strong>{tasks.length}</strong><span>任务</span></div>
        <div><strong>{bundle.artifacts.length}</strong><span>产物</span></div>
      </div>

      <div className="overview-grid">
        <section>
          <div className="panel-card-heading">
            <h2>任务</h2>
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
                description="先添加供应商资料。"
              action={<button className="primary" onClick={onGoCatalog}>添加素材</button>}
            />
          )}
        </section>

        <section>
          <div className="panel-card-heading">
            <h2>交付</h2>
          </div>
          {recentDeliveries.length || recentCompleted.length ? (
            <div className="delivery-list">
              {primaryDelivery ? (
                <article className="delivery-primary" key={primaryDelivery.artifact.id}>
                  <div>
                    <strong>{primaryDelivery.artifact.title || '最终导出包'}</strong>
                    <small>{primaryDelivery.artifact.file_name} · 可下载</small>
                  </div>
                </article>
              ) : null}
              {recentDeliveries.filter((artifact) => artifact.id !== primaryDelivery?.artifact.id).map((artifact) => (
                <article key={artifact.id}>
                  <div>
                    <strong>{artifact.title || artifact.file_name}</strong>
                    <small>{artifact.file_name} · {formatDateTime(artifact.created_at)}</small>
                  </div>
                </article>
              ))}
              {!recentDeliveries.length && recentCompleted.map((task) => (
                <article key={task.id}>
                  <div>
                    <strong>{task.objective}</strong>
                    <small>已完成 · {formatDateTime(task.updated_at)}</small>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="暂无交付物" description="完成后会出现在这里。" />
          )}
        </section>
      </div>
    </section>
  );
}
