// Adapted from ../_reference/eigent/src/components/TaskState/index.tsx.
// Keeps Eigent's task-state summary API without depending on its chatStore/i18n.

import { CircleCheckBig, CircleSlash2, LoaderCircle } from 'lucide-react';

export type TaskStateType =
  | 'all'
  | 'done'
  | 'reassigned'
  | 'ongoing'
  | 'pending'
  | 'failed';

export interface TaskStateProps {
  all?: number;
  done: number;
  progress: number;
  skipped: number;
  reAssignTo?: number;
  failed?: number;
  forceVisible?: boolean;
  selectedState?: TaskStateType;
  onStateChange?: (selectedState: TaskStateType) => void;
  clickable?: boolean;
  running?: boolean;
}

const labels: Record<TaskStateType, string> = {
  all: '全部',
  done: '完成',
  reassigned: '已重派',
  ongoing: '进行中',
  pending: '待处理',
  failed: '失败',
};

function stateClass(state: TaskStateType, selectedState: TaskStateType, clickable: boolean): string {
  return [
    'task-state-item',
    selectedState === state ? 'active' : '',
    clickable ? 'clickable' : '',
    `state-${state}`,
  ]
    .filter(Boolean)
    .join(' ');
}

function TaskStateButton({
  state,
  count,
  forceVisible,
  selectedState,
  clickable,
  onStateChange,
  running,
}: {
  state: TaskStateType;
  count?: number;
  forceVisible: boolean;
  selectedState: TaskStateType;
  clickable: boolean;
  onStateChange?: (selectedState: TaskStateType) => void;
  running?: boolean;
}) {
  if (!count && !forceVisible) return null;
  const Icon =
    state === 'done'
      ? CircleCheckBig
      : state === 'failed' || state === 'reassigned'
        ? CircleSlash2
        : state === 'ongoing' || state === 'pending'
          ? LoaderCircle
          : null;

  return (
    <button
      className={stateClass(state, selectedState, clickable)}
      disabled={!clickable}
      onClick={() => onStateChange?.(state)}
      title={`${labels[state]} ${count || 0}`}
    >
      {Icon ? <Icon size={12} className={running && state === 'ongoing' ? 'spin' : ''} /> : null}
      <span>{labels[state]}</span>
      <strong>{count || 0}</strong>
    </button>
  );
}

export function TaskState({
  all,
  done,
  reAssignTo,
  progress,
  skipped,
  failed,
  forceVisible = false,
  selectedState = 'all',
  onStateChange,
  clickable = true,
  running = false,
}: TaskStateProps) {
  return (
    <div className="task-state" aria-label="任务状态摘要">
      <TaskStateButton
        state="all"
        count={all}
        forceVisible={forceVisible}
        selectedState={selectedState}
        clickable={clickable}
        onStateChange={onStateChange}
      />
      <TaskStateButton
        state="done"
        count={done}
        forceVisible={forceVisible}
        selectedState={selectedState}
        clickable={clickable}
        onStateChange={onStateChange}
      />
      <TaskStateButton
        state="reassigned"
        count={reAssignTo}
        forceVisible={forceVisible}
        selectedState={selectedState}
        clickable={clickable}
        onStateChange={onStateChange}
      />
      <TaskStateButton
        state="ongoing"
        count={progress}
        forceVisible={forceVisible}
        selectedState={selectedState}
        clickable={clickable}
        onStateChange={onStateChange}
        running={running}
      />
      <TaskStateButton
        state="failed"
        count={failed}
        forceVisible={forceVisible}
        selectedState={selectedState}
        clickable={clickable}
        onStateChange={onStateChange}
      />
      <TaskStateButton
        state="pending"
        count={skipped}
        forceVisible={forceVisible}
        selectedState={selectedState}
        clickable={clickable}
        onStateChange={onStateChange}
      />
    </div>
  );
}
