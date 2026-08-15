// Adapted from ../_reference/eigent/src/components/ChatBox/TaskBox/TaskItem.tsx.
// This readonly variant renders CAMEL subtask content from the cowork adapter.

import { CircleDashed, CircleDot, FileText, Wrench } from 'lucide-react';
import { statusLabel, toolLabel } from '@/lib/crossborderLabels';

interface TaskItemProps {
  taskInfo: TaskInfo;
  taskIndex: number;
  active?: boolean;
  onSelect?: () => void;
}

export function TaskItem({ taskInfo, taskIndex, active = false, onSelect }: TaskItemProps) {
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
              摘要
            </>
          ) : null}
        </small>
        {taskInfo.progressLines?.length ? (
          <span className="chat-task-progress-lines" aria-label="智能体工作进度">
            {taskInfo.progressLines.map((line, index) => <i key={`${index}:${line}`}>{line}</i>)}
          </span>
        ) : null}
        {taskInfo.toolkits?.length ? (
          <span className="chat-task-tools" aria-label="工具调用">
            {taskInfo.toolkits.map((toolkit) => (
              <i key={toolkit.toolkitId || `${toolkit.toolkitName}:${toolkit.toolkitMethods}`}>
                <Wrench size={11} />
                <span>{toolLabel(toolkit.toolkitName || toolkit.toolkitMethods)}</span>
                <b>{statusLabel(toolkit.toolkitStatus || 'pending')}</b>
              </i>
            ))}
          </span>
        ) : null}
      </span>
    </button>
  );
}
