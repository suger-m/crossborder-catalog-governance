// Adapted from ../_reference/eigent/src/components/ChatBox/FloatingAction.tsx.
// The action stays inside the ChatBox project section, but routes through the
// cowork task control API supplied by the parent component.

import { Square } from 'lucide-react';
import type { CoworkTaskStatus } from '@/types';

interface FloatingActionProps {
  status?: CoworkTaskStatus;
  loading?: boolean;
  onSkip?: () => void;
  className?: string;
}

export function FloatingAction({
  status,
  loading = false,
  onSkip,
  className = '',
}: FloatingActionProps) {
  if (status !== 'running') return null;

  return (
    <div className={`chat-floating-action ${className}`} data-chat-floating-action>
      <div className="chat-floating-action-pill">
        <button
          className="chat-floating-action-button"
          disabled={loading || !onSkip}
          onClick={onSkip}
          type="button"
        >
          <Square size={13} />
          停止任务
        </button>
      </div>
    </div>
  );
}
