import {
  ArrowRight,
  Check,
  Circle,
  CircleAlert,
  CircleDot,
  LoaderCircle,
  LockKeyhole,
  Package,
  Radio,
  Sparkles,
} from 'lucide-react';
import type { Approval, Task, TaskDetail } from '../api';
import { agentLabel, statusLabel, stepLabel } from '../lib/crossborderLabels';
import type { ActivityKind, StreamState, TaskWorkspaceProjection } from '../projection/taskProjection';
import { activityKindLabel } from '../projection/taskProjection';
import { projectArtifacts } from '../projection/artifactProjection';
import { EmptyState, ErrorState, LoadingState, StatusBadge } from '../components/common/StatusViews';
import { ApprovalCard } from '../components/approvals/ApprovalCard';

interface Props {
  tasks: Task[];
  selectedTaskId: string | null;
  onSelectTask: (taskId: string) => void;
  detail: TaskDetail | null;
  projection: TaskWorkspaceProjection | null;
  streamState: StreamState;
  loading: boolean;
  error: string;
  onOpenResults: (artifactId?: string) => void;
  onDecideApproval: (approvalId: string, payload: Record<string, unknown>, rejected: boolean) => Promise<void>;
}

function StepIcon({ status }: { status: string }) {
  if (status === 'completed' || status === 'done') return <span className="step-icon completed"><Check size={13} /></span>;
  if (status === 'running') return <span className="step-icon running"><LoaderCircle className="spin" size={14} /></span>;
  if (status === 'failed' || status === 'blocked' || status === 'waiting_approval') {
    return <span className="step-icon failed"><CircleAlert size={13} /></span>;
  }
  return <span className="step-icon"><Circle size={11} /></span>;
}

function messageIcon(kind: ActivityKind) {
  if (kind === 'handoff') return <ArrowRight size={15} />;
  if (kind === 'tool') return <CircleDot size={15} />;
  if (kind === 'artifact') return <Package size={15} />;
  if (kind === 'waiting') return <LockKeyhole size={15} />;
  if (kind === 'error') return <CircleAlert size={15} />;
  if (kind === 'result') return <Check size={15} />;
  return <Sparkles size={15} />;
}

function TaskLifecycleBanner({ detail, pending }: { detail: TaskDetail; pending: Approval[] }) {
  const status = detail.task.status;
  if (pending.length) {
    return <div className="lifecycle-banner waiting">等待审批：{pending[0].title}</div>;
  }
  if (status === 'running') return <div className="lifecycle-banner running">任务执行中</div>;
  if (status === 'completed') return <div className="lifecycle-banner completed">任务已完成</div>;
  if (status === 'failed') return <div className="lifecycle-banner failed">任务失败：{detail.task.error || '请查看进展中的异常。'}</div>;
  if (status === 'blocked' || status === 'waiting_approval') {
    return <div className="lifecycle-banner waiting">任务已阻塞</div>;
  }
  return <div className="lifecycle-banner">等待计划</div>;
}

export function WorkbenchView({
  tasks,
  selectedTaskId,
  onSelectTask,
  detail,
  projection,
  streamState,
  loading,
  error,
  onOpenResults,
  onDecideApproval,
}: Props) {
  if (!tasks.length) {
    return (
      <section className="view-panel">
        <EmptyState
          title="还没有可执行的任务"
          description="请先在「素材与商品目录」选择素材并创建治理任务。"
        />
      </section>
    );
  }

  if (!selectedTaskId) {
    return (
      <section className="view-panel workbench-view">
        <header className="view-header">
          <div>
            <h1>选择任务</h1>
          </div>
        </header>
        <div className="task-picker">
          {tasks.map((task) => (
            <button key={task.id} onClick={() => onSelectTask(task.id)}>
              <span className={`task-dot ${task.status}`} />
              <span>
                <strong>{task.objective}</strong>
                <small>{statusLabel(task.status)}</small>
              </span>
              <StatusBadge status={task.status} />
            </button>
          ))}
        </div>
      </section>
    );
  }

  if (loading && !detail) return <LoadingState title="正在加载任务工作台" description="读取 TaskDetail 与实时进展流…" />;
  if (!detail) return <ErrorState title="无法打开任务" description={error || '任务详情不可用。'} />;

  const steps = projection?.steps || [];
  const pendingApprovals = detail.approvals.filter((approval) => approval.status === 'pending');
  const current = projection?.currentStep || null;
  const currentAgent = current
    ? agentLabel(current.workerName)
    : detail.task.status === 'completed' ? '任务协调器' : '等待任务计划';
  const currentSummary = current?.progressLines.at(-1)
    || current?.summary
    || (pendingApprovals[0] ? `等待审批：${pendingApprovals[0].title}` : '')
    || (detail.task.status === 'running' ? '正在等待 AgentTeams 返回下一步有效进展。' : '')
    || (detail.task.status === 'completed' ? '所有已分配步骤均已完成，可以查看产物。' : '任务已创建，Manager 正在形成动态计划。');
  const recentArtifacts = projectArtifacts(projection?.artifacts || detail.artifacts)
    .filter((item) => item.deliveryClass !== 'internal')
    .slice(0, 5)
    .map((item) => item.artifact);

  return (
    <section className="view-panel workbench-view">
      <header className="view-header">
        <div>
          {tasks.length > 1 ? (
            <label className="task-switcher-title">
              <span className="sr-only">当前任务</span>
              <select value={detail.task.id} onChange={(event) => onSelectTask(event.target.value)}>
                {tasks.map((task) => (
                  <option key={task.id} value={task.id}>{task.objective}</option>
                ))}
              </select>
            </label>
          ) : (
            <h1>{detail.task.objective}</h1>
          )}
        </div>
        <div className="workbench-header-actions">
          <span className={`connection-chip ${streamState === 'live' ? 'live' : ''}`}>
            <Radio size={13} />{statusLabel(streamState)}
          </span>
          <StatusBadge status={detail.task.status} />
          <button onClick={() => onOpenResults()}>查看交付</button>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}
      {projection?.hasGap ? <div className="error-banner">事件序列不完整，正在重新连接并补齐状态。</div> : null}
      <TaskLifecycleBanner detail={detail} pending={pendingApprovals} />

      <div className="execution-progress">
        <div><strong>{steps.filter((step) => ['completed', 'done'].includes(step.status)).length}/{steps.length || 0}</strong></div>
        <div className="execution-progress-track"><span style={{ width: `${projection?.progressPercent || 0}%` }} /></div>
        <em>{projection?.progressPercent || 0}%</em>
      </div>

      <div className="execution-grid">
        <aside className="execution-plan">
          <div className="panel-card-heading">
            <h2>计划</h2>
            <span className="muted">{steps.length ? `${steps.length} 步` : '待生成'}</span>
          </div>
          {steps.length ? (
            <div className="execution-step-list">
              {steps.map((step) => (
                <div key={step.id} className={`execution-step ${current?.id === step.id ? 'current' : ''}`}>
                  <StepIcon status={step.status} />
                  <span>
                    <strong>{stepLabel(step.title)}</strong>
                    <small>{agentLabel(step.workerName)} · {statusLabel(step.status)}</small>
                    {step.summary ? <i>{step.summary}</i> : null}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="execution-empty">
              <LoaderCircle className="spin" size={18} />
              <strong>正在等待 Manager 形成计划</strong>
              <p>计划出现后会显示在这里。</p>
            </div>
          )}

          {projection?.handoffs.length ? (
            <div className="execution-handoff-list">
              <span className="muted">交接</span>
              {projection.handoffs.map((item) => (
                <div className="execution-handoff-item" key={item.id}>
                  <span>{agentLabel(item.from === 'coordinator' ? 'coordinator' : item.from)}</span>
                  <ArrowRight size={12} />
                  <strong>{agentLabel(item.to)}</strong>
                  <small>{item.title}</small>
                </div>
              ))}
            </div>
          ) : null}

          <div className="tool-capability-list">
            <span className="muted">工具</span>
            {projection?.toolCapabilities.length
              ? projection.toolCapabilities.map((label) => <span key={label} className="chip">{label}</span>)
              : <p className="muted">智能体调用业务工具后，会在此汇总可读能力名称。</p>}
          </div>
        </aside>

        <section className="execution-main">
          <div className={`execution-current-card ${pendingApprovals.length ? 'waiting' : ''}`}>
            <div className="execution-current-top">
              <span className="execution-live-dot" />
              <span>当前智能体</span>
              <strong>{currentAgent}</strong>
            </div>
            <h2>{current ? stepLabel(current.title) : detail.task.status === 'completed' ? '任务已完成' : '等待执行计划'}</h2>
            <p>{currentSummary}</p>
          </div>

          <div className="panel-card-heading activity-heading">
            <h2>进展</h2>
          </div>
          <div className="execution-activity">
            {projection?.activity.length ? projection.activity.map((item) => (
              <article key={item.id} className={`execution-activity-item ${item.kind}`}>
                <div className="execution-activity-icon">{messageIcon(item.kind)}</div>
                <div>
                  <div className="execution-activity-meta">
                    <strong>{item.sender}</strong>
                    <em>{activityKindLabel(item.kind)}</em>
                  </div>
                  <p>{item.text}</p>
                </div>
              </article>
            )) : (
              <div className="execution-empty activity-empty">
                <Sparkles size={18} />
                <strong>{detail.task.status === 'running' ? 'AgentTeams 正在准备第一条进展' : '暂无可展示的协作消息'}</strong>
                <p>收到进展后会显示在这里。</p>
              </div>
            )}
          </div>
        </section>

        <aside className="execution-inspector">
          <div className="panel-card-heading">
            <h2>交付</h2>
          </div>

          <div className="execution-inspector-card">
            <span className="inspector-value">{projection?.artifacts.length || detail.artifacts.length}</span>
            <span className="inspector-label">已生成文件</span>
            <button onClick={() => onOpenResults()}>查看全部产物 <ArrowRight size={13} /></button>
          </div>

          {recentArtifacts.length ? (
            <div className="execution-artifact-list">
              <span className="muted">最近产物</span>
              {recentArtifacts.map((artifact) => (
                <button key={artifact.id} className="execution-artifact-item" onClick={() => onOpenResults(artifact.id)}>
                  <Package size={13} />
                  <span>
                    <strong>{artifact.title || artifact.file_name}</strong>
                    <small>{agentLabel(artifact.worker_name)}</small>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <p className="muted">尚无产物文件。</p>
          )}

          {pendingApprovals.length ? (
            <div className="execution-approval-list">
              <span className="muted">待审批</span>
              {pendingApprovals.map((approval) => (
                <ApprovalCard key={approval.id} approval={approval} onDecide={onDecideApproval} />
              ))}
            </div>
          ) : (
            <div className="execution-approval quiet">
              <Check size={16} />
              <div>
                <strong>暂无阻塞审批</strong>
                <p>需要人工确认时会在此显示。</p>
              </div>
            </div>
          )}

          {detail.task.result?.summary ? (
            <div className="result-summary">
              <span className="muted">完成结果</span>
              <p>{detail.task.result.summary}</p>
            </div>
          ) : null}

          {detail.task.error ? (
            <div className="error-summary">
              <span className="muted">错误</span>
              <p>{detail.task.error}</p>
            </div>
          ) : null}

          <div className="execution-agent-list">
            <span className="muted">参与智能体</span>
            {projection?.participatingAgents.length
              ? projection.participatingAgents.map((worker) => (
                <div key={worker} className="agent-row">
                  <span className="agent-avatar"><CircleDot size={13} /></span>
                  <span>{agentLabel(worker)}</span>
                </div>
              ))
              : <p className="muted">计划生成后将显示实际参与的智能体。</p>}
          </div>
        </aside>
      </div>
    </section>
  );
}
