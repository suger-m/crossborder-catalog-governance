// Adapted from ../_reference/eigent/src/components/ChatBox/TaskBox/TaskItem.tsx.
// This readonly variant renders CAMEL subtask content from the cowork adapter.

import { CircleDashed, CircleDot, FileText, Wrench } from 'lucide-react';

interface TaskItemProps {
  taskInfo: TaskInfo;
  taskIndex: number;
  active?: boolean;
  onSelect?: () => void;
}

function statusLabel(status?: string) {
  if (!status) return 'pending';
  if (status === 'completed') return 'done';
  if (status === 'running') return 'running';
  if (status === 'failed' || status === 'blocked') return 'failed';
  return status;
}

export function TaskItem({ taskInfo, taskIndex, active = false, onSelect }: TaskItemProps) {
  const toolNames = (taskInfo.toolkits || []).map(
    (toolkit) => toolkit.toolkitMethods || toolkit.toolkitName
  );

  return (
    <button
      className={`chat-task-item ${taskInfo.status || 'pending'} ${active ? 'active' : ''}`}
      onClick={onSelect}
      title={taskInfo.content}
      type="button"
    >
      <span className="chat-task-item-index">
        {taskInfo.id ? <CircleDot size={13} /> : <CircleDashed size={13} />}
        <strong>{taskIndex + 1}</strong>
      </span>
      <span className="chat-task-item-main">
        <span>{taskInfo.content || taskInfo.id}</span>
        <small>
          {statusLabel(taskInfo.status)}
          {taskInfo.report ? (
            <>
              <FileText size={12} />
              report
            </>
          ) : null}
          {toolNames.length > 0 ? (
            <>
              <Wrench size={12} />
              {toolNames.slice(0, 2).join(', ')}
            </>
          ) : null}
        </small>
      </span>
    </button>
  );
}
