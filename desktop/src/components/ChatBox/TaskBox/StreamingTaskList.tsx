// Adapted from ../_reference/eigent/src/components/ChatBox/TaskBox/StreamingTaskList.tsx.
// Eigent parses streaming <task> text; this adapter can still parse that form,
// and renders native Eigent TaskInfo entries from ChatStore.

import { CircleDashed, LoaderCircle } from 'lucide-react';
import { useMemo } from 'react';
import { TaskItem } from './TaskItem';
import { TaskType } from './TaskType';

interface StreamingTaskListProps {
  tasks?: TaskInfo[];
  streamingText?: string;
  emptyText?: string;
  waiting?: boolean;
}

function parseStreamingTasks(text: string): {
  tasks: string[];
  isStreaming: boolean;
} {
  const tasks: string[] = [];
  const completeTaskRegex = /<task>([\s\S]*?)<\/task>/g;
  let match: RegExpExecArray | null;
  while ((match = completeTaskRegex.exec(text)) !== null) {
    const content = match[1].trim();
    if (content) tasks.push(content);
  }

  const lastOpenTag = text.lastIndexOf('<task>');
  const lastCloseTag = text.lastIndexOf('</task>');
  let isStreaming = false;
  if (lastOpenTag > lastCloseTag) {
    const incompleteContent = text.substring(lastOpenTag + 6).trim();
    if (incompleteContent) {
      tasks.push(incompleteContent);
      isStreaming = true;
    }
  }

  return { tasks, isStreaming };
}

function taskStatusSummary(tasks: TaskInfo[]): string {
  const completed = tasks.filter((task) => task.status === 'completed').length;
  const running = tasks.filter((task) => task.status === 'running').length;
  if (running > 0) return `${running} 个运行中`;
  return `${completed}/${tasks.length} 已完成`;
}

export function StreamingTaskList({
  tasks = [],
  streamingText = '',
  emptyText = '暂无 CAMEL Workforce 子任务。',
  waiting = false,
}: StreamingTaskListProps) {
  const parsed = useMemo(() => parseStreamingTasks(streamingText), [streamingText]);
  const hasTaskInfo = tasks.length > 0;

  if (!hasTaskInfo && parsed.tasks.length === 0) {
    return (
      <div className="chat-streaming-task-list empty" data-streaming-task-list>
        <div className="chat-streaming-task-progress" />
        <div className="chat-streaming-empty">
          {waiting ? <LoaderCircle className="spin" size={15} /> : <CircleDashed size={15} />}
          <span>{emptyText}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-streaming-task-list" data-streaming-task-list>
      <div className="chat-streaming-task-progress" />
      <div className="chat-streaming-task-header">
        <TaskType type={1} />
        <span>子任务 {hasTaskInfo ? tasks.length : parsed.tasks.length}</span>
        <small>{hasTaskInfo ? taskStatusSummary(tasks) : parsed.isStreaming ? '流式解析中' : '已解析'}</small>
      </div>

      <div className="chat-streaming-task-items">
        {hasTaskInfo
          ? tasks.map((taskInfo, index) => (
              <TaskItem key={taskInfo.id || `${index}`} taskInfo={taskInfo} taskIndex={index} />
            ))
          : parsed.tasks.map((task, index) => {
              const isStreaming = parsed.isStreaming && index === parsed.tasks.length - 1;
              return (
                <div className="chat-streaming-task-text" key={`${task}-${index}`}>
                  <span className="chat-task-item-index">
                    {isStreaming ? <LoaderCircle className="spin" size={13} /> : <CircleDashed size={13} />}
                    <strong>{index + 1}</strong>
                  </span>
                  <span>
                    {task}
                    {isStreaming ? <i className="streaming-caret" /> : null}
                  </span>
                </div>
              );
            })}
      </div>
    </div>
  );
}

export { parseStreamingTasks };
