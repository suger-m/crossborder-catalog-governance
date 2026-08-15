// Adapted from ../_reference/eigent/src/components/ChatBox/BottomBox/QueuedBox.tsx.

import { ChevronDown, ChevronUp, Circle, FileText, X } from 'lucide-react';
import { useState } from 'react';
import type { FileAttachment } from './InputBox';

export interface QueuedMessage {
  id: string;
  content: string;
  timestamp: number;
  files?: FileAttachment[];
}

interface QueuedBoxProps {
  queuedMessages: QueuedMessage[];
  onRemoveQueuedMessage: (id: string) => void;
  onSelectQueuedMessage: (message: QueuedMessage) => void;
}

export function QueuedBox({
  queuedMessages,
  onRemoveQueuedMessage,
  onSelectQueuedMessage,
}: QueuedBoxProps) {
  const [expanded, setExpanded] = useState(true);
  if (queuedMessages.length === 0) return null;

  return (
    <div className="queued-box">
      <header className="queued-box-header">
        <button onClick={() => setExpanded((value) => !value)} title="展开/收起排队任务" type="button">
          {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>
        <strong>{queuedMessages.length}</strong>
        <span>queued tasks</span>
      </header>

      {expanded ? (
        <div className="queued-box-list">
          {queuedMessages.map((message) => (
            <div className="queued-item" key={message.id}>
              <button
                className="queued-item-main"
                onClick={() => onSelectQueuedMessage(message)}
                title={message.content}
                type="button"
              >
                <Circle size={13} />
                <span>{message.content}</span>
                {message.files?.length ? (
                  <small>
                    <FileText size={12} />
                    {message.files.length}
                  </small>
                ) : null}
              </button>
              <button
                className="queued-item-remove"
                onClick={() => onRemoveQueuedMessage(message.id)}
                title="移除排队任务"
                type="button"
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
