// Adapted from ../_reference/eigent/src/components/ChatBox/TaskBox/TaskType.tsx.

export type TaskTypeValue = 1 | 2 | 3;

interface TaskTypeProps {
  type: TaskTypeValue;
}

const TYPE_LABELS: Record<TaskTypeValue, string> = {
  1: '任务规划',
  2: '任务执行',
  3: '任务完成',
};

export function TaskType({ type }: TaskTypeProps) {
  return (
    <div className={`chat-task-type type-${type}`}>
      <span aria-hidden="true" />
      <strong>{TYPE_LABELS[type]}</strong>
    </div>
  );
}
