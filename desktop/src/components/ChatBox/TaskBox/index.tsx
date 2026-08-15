// Adapted from ../_reference/eigent/src/components/ChatBox/TaskBox/.

import type { CoworkTask } from '@/types';
import type { Task as NativeChatTask } from '@/store/chatStore';
import { TaskCard } from './TaskCard';

interface TaskBoxProps {
  tasks: CoworkTask[];
  activeTaskId?: string;
  activeNativeTask?: NativeChatTask;
  onSelectTask: (taskId: string) => void;
}

export function TaskBox({ tasks, activeTaskId, activeNativeTask, onSelectTask }: TaskBoxProps) {
  return (
    <div className="task-list">
      {tasks.map((task) => (
        <TaskCard
          key={task.id}
          task={task}
          active={task.id === activeTaskId}
          nativeTask={task.id === activeTaskId ? activeNativeTask : undefined}
          onSelectTask={onSelectTask}
        />
      ))}
      {tasks.length === 0 ? <div className="empty-state">暂无任务</div> : null}
    </div>
  );
}
