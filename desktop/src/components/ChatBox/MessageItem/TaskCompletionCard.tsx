// Adapted from ../_reference/eigent/src/components/ChatBox/MessageItem/TaskCompletionCard.tsx.
// Trigger creation is intentionally omitted; rerun remains a cowork API action.

import { CircleCheckBig, RotateCcw } from 'lucide-react';

interface TaskCompletionCardProps {
  taskPrompt?: string;
  onRerun?: () => void;
}

export function TaskCompletionCard({ taskPrompt = '', onRerun }: TaskCompletionCardProps) {
  return (
    <article className="task-completion-card" data-chat-message-card="completion">
      <div className="task-completion-icon">
        <CircleCheckBig size={18} />
      </div>
      <div>
        <strong>任务已完成</strong>
        <p>{taskPrompt || 'CAMEL Workforce 已完成该任务。'}</p>
      </div>
      {onRerun ? (
        <button className="task-completion-action" onClick={onRerun} type="button">
          <RotateCcw size={14} />
          重新运行
        </button>
      ) : null}
    </article>
  );
}
