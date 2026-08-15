// Adapted from ../_reference/eigent/src/components/ChatBox/MessageItem/UserMessageCard.tsx.
// Skill/file actions from Eigent are represented as readonly chips here; local
// file access still goes through the controlled desktop preload path elsewhere.

import { Check, Copy, Sparkles } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';

interface UserMessageCardProps {
  id: string;
  content: string;
  className?: string;
}

type ContentNode =
  | { type: 'text'; value: string }
  | { type: 'skill'; name: string };

const COPIED_RESET_MS = 1600;
const SKILL_TAG_REGEX = /\{\{([^}]+)\}\}/g;

function parseContentWithSkillTags(content: string): ContentNode[] {
  const nodes: ContentNode[] = [];
  let lastIndex = 0;
  SKILL_TAG_REGEX.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = SKILL_TAG_REGEX.exec(content)) !== null) {
    if (match.index > lastIndex) {
      nodes.push({ type: 'text', value: content.slice(lastIndex, match.index) });
    }
    nodes.push({ type: 'skill', name: match[1].trim() });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < content.length) {
    nodes.push({ type: 'text', value: content.slice(lastIndex) });
  }
  return nodes.length > 0 ? nodes : [{ type: 'text', value: content }];
}

export function UserMessageCard({
  id,
  content,
  className = '',
}: UserMessageCardProps) {
  const [copied, setCopied] = useState(false);
  const contentNodes = useMemo(() => parseContentWithSkillTags(content), [content]);

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
      className={`message-card user-message-card ${className}`}
      data-chat-message-card="user"
      data-message-id={id}
    >
      <button className="message-card-copy" onClick={handleCopy} title="复制消息" type="button">
        {copied ? <Check size={14} /> : <Copy size={14} />}
      </button>
      <div className="user-message-content">
        {contentNodes.map((node, index) =>
          node.type === 'text' ? (
            <span key={index}>{node.value}</span>
          ) : (
            <span className="message-skill-chip" key={`${node.name}-${index}`} title="技能标签">
              <Sparkles size={13} />
              {node.name}
            </span>
          )
        )}
      </div>
    </article>
  );
}
