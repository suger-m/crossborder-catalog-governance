// Adapted from ../_reference/eigent/src/components/ChatBox/MessageItem/MarkDown.tsx.
// Keeps a markdown-like message surface without bringing Eigent's app-wide
// markdown/i18n/toast dependencies into the desktop adapter.

interface MarkDownProps {
  content: string;
}

function renderLine(line: string, index: number) {
  const trimmed = line.trim();
  if (!trimmed) return <br key={index} />;
  if (trimmed.startsWith('### ')) {
    return <h3 key={index}>{trimmed.slice(4)}</h3>;
  }
  if (trimmed.startsWith('## ')) {
    return <h2 key={index}>{trimmed.slice(3)}</h2>;
  }
  if (trimmed.startsWith('# ')) {
    return <h1 key={index}>{trimmed.slice(2)}</h1>;
  }
  if (trimmed.startsWith('- ')) {
    return (
      <p className="markdown-list-item" key={index}>
        <span aria-hidden="true">•</span>
        {trimmed.slice(2)}
      </p>
    );
  }
  if (trimmed.startsWith('```')) {
    return (
      <p className="markdown-code-fence" key={index}>
        {trimmed}
      </p>
    );
  }
  return <p key={index}>{line}</p>;
}

export function MarkDown({ content }: MarkDownProps) {
  return (
    <div className="chat-markdown">
      {content.split(/\r?\n/).map(renderLine)}
    </div>
  );
}
