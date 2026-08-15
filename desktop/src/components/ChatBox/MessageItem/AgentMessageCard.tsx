// Adapted from ../_reference/eigent/src/components/ChatBox/MessageItem/AgentMessageCard.tsx.
// Copy and attachment actions are constrained to browser APIs and cowork data.

import { Check, Copy, FileText } from 'lucide-react';
import { useCallback, useState } from 'react';
import { MarkDown } from './MarkDown';

interface AgentMessageCardProps {
  id: string;
  content: string;
  className?: string;
  files?: FileInfo[];
  onOpenFile?: (file: FileInfo) => void;
}

const COPIED_RESET_MS = 1600;

export function AgentMessageCard({
  id,
  content,
  className = '',
  files = [],
  onOpenFile,
}: AgentMessageCardProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), COPIED_RESET_MS);
    } catch {
      setCopied(false);
    }
  }, [content]);

  return (
    <article
      className={`message-card agent-message-card ${className}`}
      data-chat-message-card="agent"
      data-message-id={id}
    >
      <button className="message-card-copy" onClick={handleCopy} title="复制消息" type="button">
        {copied ? <Check size={14} /> : <Copy size={14} />}
      </button>
      <MarkDown content={content} />
      {files.length > 0 ? (
        <div className="message-file-grid">
          {files.slice(0, 6).map((file) => (
            <button
              className="message-file-chip"
              key={file.artifact_id || file.path}
              onClick={() => onOpenFile?.(file)}
              title={file.path}
              type="button"
            >
              <FileText size={14} />
              {file.name}
            </button>
          ))}
        </div>
      ) : null}
    </article>
  );
}
