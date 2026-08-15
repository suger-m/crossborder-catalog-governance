// Adapted from ../_reference/eigent/src/components/ChatBox/HeaderBox/index.tsx.

import { RefreshCw, Sparkles } from 'lucide-react';

interface HeaderBoxProps {
  loading?: boolean;
  taskCount: number;
  onRefresh: () => void;
}

export function HeaderBox({ loading = false, taskCount, onRefresh }: HeaderBoxProps) {
  return (
    <div className="eigent-chat-header">
      <div className="eigent-chat-title">
        <Sparkles size={15} />
        <span>对话</span>
      </div>
      <div className="eigent-chat-header-actions">
        <span className="eigent-token-count">{taskCount} 个任务</span>
        <button className="eigent-chat-icon-button" onClick={onRefresh} disabled={loading} title="刷新">
          <RefreshCw size={18} />
        </button>
      </div>
    </div>
  );
}
