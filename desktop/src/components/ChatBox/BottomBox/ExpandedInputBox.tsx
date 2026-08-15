// Adapted from ../_reference/eigent/src/components/ChatBox/BottomBox/ExpandedInputBox.tsx.
// Eigent dependencies replaced here: AddWorker is disabled, i18n text is literal,
// and worker data comes directly from native ChatStore taskAssigning.

import {
  BarChart3,
  Bot,
  CodeXml,
  FileText,
  Globe,
  Image,
  Plus,
  Search,
  Share2,
  X,
} from 'lucide-react';
import { useEffect, useState, type ReactNode } from 'react';
import { InputBox, type InputBoxProps } from './InputBox';

interface PromptExample {
  title: string;
  prompt: string;
  icon: ReactNode;
}

const defaultPromptExamples: PromptExample[] = [
  {
    title: '目录治理',
    prompt: '整理供应商商品资料，建立规范 Product/SKU 事实并标记缺失字段。',
    icon: <Search size={15} />,
  },
  {
    title: '合规复核',
    prompt: '复核美国服装合规、平台字段和证据缺口，并给出交付结论。',
    icon: <BarChart3 size={15} />,
  },
];

export interface ExpandedInputBoxProps {
  inputProps: InputBoxProps;
  agents: Agent[];
  onClose?: () => void;
  className?: string;
}

export function ExpandedInputBox({
  inputProps,
  agents,
  onClose,
  className = '',
}: ExpandedInputBoxProps) {
  const [agentList, setAgentList] = useState<Agent[]>([]);

  const agentIconMap: Record<string, ReactNode> = {
    developer_agent: <CodeXml size={13} />,
    browser_agent: <Globe size={13} />,
    document_agent: <FileText size={13} />,
    multi_modal_agent: <Image size={13} />,
    social_media_agent: <Share2 size={13} />,
  };

  useEffect(() => {
    setAgentList(agents);
  }, [agents]);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [onClose]);

  const handlePromptClick = (prompt: string) => {
    inputProps.onChange?.(prompt);
  };

  const displayAgents = agentList.slice(0, 6);
  const remainingCount = agentList.length > 6 ? agentList.length - 6 : 0;

  return (
    <div className="expanded-input-backdrop" data-expanded-input-backdrop onMouseDown={() => onClose?.()}>
      <section
        aria-modal="true"
        className={`expanded-input-box ${className}`}
        data-expanded-input-box
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
      >
        {/* BoxHeader */}
        <div className="expanded-input-header">
          <div className="expanded-agent-list">
            {displayAgents.map((agent, index) => (
              <div className={agentChipClass(agent)} key={agent.agent_id || index} title={agent.name}>
                {agentIconMap[agent.type] || <Bot size={13} />}
                <span>{agent.name}</span>
              </div>
            ))}
            {remainingCount > 0 ? <div className="expanded-agent-more">+{remainingCount}</div> : null}
            {agentList.length === 0 ? <span className="expanded-agent-empty">暂未分配智能体</span> : null}
            <button
              aria-label="智能体分配"
              className="expanded-add-worker-button"
              disabled
              title="智能体分配由 CAMEL 智能体团队控制"
              type="button"
            >
              <Plus size={14} />
            </button>
          </div>

          <button className="expanded-close-button" onClick={onClose} title="关闭" type="button">
            <X size={17} />
          </button>
        </div>

        {/* InputSection */}
        <div className="expanded-input-main">
          <InputBox className="expanded-chat-input" hideExpandButton {...inputProps} />
        </div>

        {/* ActionBox - Prompt Examples Always Visible */}
        <div className="expanded-prompt-strip">
          {defaultPromptExamples.map((example, index) => (
            <button
              className="expanded-prompt-card"
              key={`${example.title}-${index}`}
              onClick={() => handlePromptClick(example.prompt)}
              type="button"
            >
              {example.icon}
              <span>
                <strong>{example.title}</strong>
                <small>{example.prompt}</small>
              </span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

function agentChipClass(agent: Agent): string {
  return [
    'expanded-agent-chip',
    `agent-${agent.type}`,
    agent.status || '',
    agent.tasks.length > 0 ? 'assigned' : 'base',
  ]
    .filter(Boolean)
    .join(' ');
}
