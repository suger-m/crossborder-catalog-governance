// Adapted from ../_reference/eigent/src/components/ChatBox/TaskBox/TaskCard.tsx.
// The card keeps Eigent's task summary/progress/state/list shape while using
// readonly CAMEL Workforce tasks from the native Eigent ChatStore.

import { ChevronDown, CircleCheckBig, LoaderCircle, TriangleAlert } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { TaskState, type TaskStateType } from '@/components/TaskState';
import type { CoworkTask, CoworkTaskDetail } from '@/types';
import type { Task as NativeChatTask } from '@/store/chatStore';
import { statusLabel } from '@/lib/crossborderLabels';
import { StreamingTaskList } from './StreamingTaskList';
import { TaskType, type TaskTypeValue } from './TaskType';
import { TypeCardSkeleton } from './TypeCardSkeleton';

interface TaskCardProps {
  task: CoworkTask;
  active: boolean;
  nativeTask?: NativeChatTask;
  onSelectTask: (taskId: string) => void;
  onStartTask?: (taskId: string) => void | Promise<void>;
  detail?: CoworkTaskDetail | null;
  onApproveHumanInterrupt?: (interruptId: string) => void | Promise<void>;
  onRejectHumanInterrupt?: (interruptId: string) => void | Promise<void>;
}

function taskType(status?: string): TaskTypeValue {
  if (status === 'completed') return 3;
  if (status === 'running' || status === 'waiting_approval' || status === 'waiting_human_input' || status === 'paused') {
    return 2;
  }
  return 1;
}

function statusIcon(status?: string) {
  if (status === 'completed') return <CircleCheckBig size={15} />;
  if (status === 'failed' || status === 'cancelled') return <TriangleAlert size={15} />;
  return <LoaderCircle className={status === 'running' ? 'spin' : ''} size={15} />;
}

function taskStateCounts(tasks: TaskInfo[]) {
  return {
    all: tasks.length,
    done: tasks.filter((task) => task.status === 'completed').length,
    progress: tasks.filter((task) => task.status === 'running').length,
    skipped: tasks.filter((task) => !task.status || task.status === 'waiting' || task.status === 'skipped').length,
    failed: tasks.filter((task) => task.status === 'failed' || task.status === 'blocked').length,
    reAssignTo: tasks.filter((task) => task.reAssignTo).length,
  };
}

function taskMatchesState(task: TaskInfo, selectedState: TaskStateType) {
  if (selectedState === 'all') return true;
  if (selectedState === 'done') return task.status === 'completed' && !task.reAssignTo;
  if (selectedState === 'reassigned') return Boolean(task.reAssignTo);
  if (selectedState === 'ongoing') {
    return !['completed', 'failed', 'blocked', 'skipped', 'waiting', ''].includes(task.status || '') && !task.reAssignTo;
  }
  if (selectedState === 'pending') return (!task.status || ['waiting', 'skipped', ''].includes(task.status)) && !task.reAssignTo;
  if (selectedState === 'failed') return ['failed', 'blocked'].includes(task.status || '') && !task.reAssignTo;
  return true;
}

function fallbackProgress(status?: string) {
  if (status === 'completed') return 100;
  if (status === 'running') return 45;
  if (status === 'failed' || status === 'cancelled') return 100;
  return 0;
}

function emptySubtaskText(status?: string) {
  if (status === 'draft' || status === 'pending' || status === 'planned') {
    return '智能体团队正在准备执行；如果自动启动失败，可点击「运行」重试。';
  }
  if (status === 'waiting_approval' || status === 'waiting_human_input') {
    return '等待人工处理后，Workforce 才会继续。';
  }
  if (status === 'paused') return '任务已暂停，恢复后继续执行。';
  if (status === 'completed') return '任务已完成，暂无持久化的 CAMEL 子任务。';
  if (status === 'failed' || status === 'cancelled') return '没有记录到 CAMEL 子任务。';
  return '暂无智能体子任务。';
}

function planningTaskInfo(task: CoworkTask): TaskInfo[] {
  if (!['draft', 'pending', 'planned'].includes(task.status || '')) return [];
  return [
    {
      id: `${task.id}:ready`,
      content: task.objective || '待运行',
      status: '',
      toolkits: [],
    },
  ];
}

export function TaskCard({ task, active, nativeTask, onSelectTask, onStartTask, detail, onApproveHumanInterrupt, onRejectHumanInterrupt }: TaskCardProps) {
  const [expanded, setExpanded] = useState(active);
  const [selectedState, setSelectedState] = useState<TaskStateType>('all');
  const taskInfo = useMemo(() => {
    const projected = nativeTask?.taskInfo || [];
    return projected.length > 0 ? projected : planningTaskInfo(task);
  }, [nativeTask?.taskInfo, task]);
  const counts = useMemo(() => taskStateCounts(taskInfo), [taskInfo]);
  const filteredTasks = useMemo(
    () => taskInfo.filter((item) => taskMatchesState(item, selectedState)),
    [selectedState, taskInfo]
  );
  const progressValue = nativeTask?.progressValue ?? fallbackProgress(task.status);
  const type = taskType(task.status);

  useEffect(() => {
    if (active) setExpanded(true);
  }, [active]);

  return (
    <article className={`chat-task-card ${active ? 'active' : ''} ${task.status || 'pending'}`}>
      <button
        className="chat-task-card-main"
        onClick={() => onSelectTask(task.id)}
        title={task.objective || task.id}
        type="button"
      >
        <span className="chat-task-progress" style={{ width: `${Math.max(0, Math.min(100, progressValue))}%` }} />
        <span className="chat-task-card-heading">
          <TaskType type={type} />
          <span className="chat-task-card-status">
            {statusIcon(task.status)}
            {statusLabel(task.status || 'pending')}
          </span>
        </span>
        <strong>{nativeTask?.summaryTask || task.objective || task.id}</strong>
      </button>

      {active ? (
        <div className="chat-task-card-detail">
          <div className="chat-task-card-toolbar">
            <TaskState
              all={counts.all}
              done={counts.done}
              progress={counts.progress}
              skipped={counts.skipped}
              failed={counts.failed}
              reAssignTo={counts.reAssignTo}
              forceVisible
              selectedState={selectedState}
              onStateChange={setSelectedState}
              running={task.status === 'running'}
            />
            {onStartTask && ['draft', 'pending', 'planned'].includes(task.status || '') ? (
              <button
                className="chat-task-run"
                onClick={(event) => {
                  event.stopPropagation();
                  void onStartTask(task.id);
                }}
                type="button"
              >
                运行
              </button>
            ) : null}
            <button
              className="chat-task-collapse"
              onClick={() => setExpanded((value) => !value)}
              title={expanded ? '收起子任务' : '展开子任务'}
              type="button"
            >
              <span>{filteredTasks.length}/{taskInfo.length || 0}</span>
              <ChevronDown className={expanded ? 'rotated' : ''} size={16} />
            </button>
          </div>

          {detail?.camel_workforce?.human_interrupts?.filter((item) => item.status === 'pending' && item.interrupt_type === 'approval').map((interrupt) => (
            <div className="chat-task-approval" key={interrupt.id}>
              <span>{interrupt.prompt || '智能体请求执行需要批准的操作。'}</span>
              <div className="chat-task-approval-actions">
                <button type="button" onClick={() => void onApproveHumanInterrupt?.(interrupt.id)} disabled={!onApproveHumanInterrupt}>批准</button>
                <button type="button" onClick={() => void onRejectHumanInterrupt?.(interrupt.id)} disabled={!onRejectHumanInterrupt}>拒绝</button>
              </div>
            </div>
          ))}

          {expanded ? (
            taskInfo.length === 0 && task.status === 'running' ? (
              <TypeCardSkeleton isTakeControl={nativeTask?.isTakeControl} />
            ) : (
              <StreamingTaskList
                tasks={filteredTasks}
                emptyText={emptySubtaskText(task.status)}
                waiting={task.status === 'running'}
              />
            )
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
