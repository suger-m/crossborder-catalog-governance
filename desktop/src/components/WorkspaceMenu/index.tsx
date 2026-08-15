// Adapted from ../_reference/eigent/src/components/WorkspaceMenu/index.tsx.
// Preserves Eigent's taskAssigning workspace menu model while routing every
// selection through the native Eigent ChatStore taskAssigning state.

import {
  Bot,
  CodeXml,
  FileText,
  FolderOpen,
  Globe,
  Image,
  Network,
  type LucideIcon,
} from 'lucide-react';
import { useMemo } from 'react';
import {
  MenuToggleGroup,
  MenuToggleItem,
} from '@/components/MenuButton/MenuButton';
import {
  COWORK_WORKER_CODES,
  COWORK_WORKER_LABELS,
  COWORK_WORKER_MENU_ORDER,
} from '@/lib/coworkWorkers';

interface WorkspaceMenuProps {
  agents: Agent[];
  activeWorkspace: string;
  onSelectWorkspace: (workspaceId: string) => void;
}

interface WorkspaceAgentEntry {
  agent_id: string;
  name: string;
  type: string;
  tasks: TaskInfo[];
  tools?: string[];
  status?: AgentStatus;
  sourceWorkerName?: string;
}

const WORKER_MENU_ORDER = COWORK_WORKER_MENU_ORDER;

const WORKER_CODES = COWORK_WORKER_CODES;

const agentIconMap: Record<string, LucideIcon> = {
  developer_agent: CodeXml,
  browser_agent: Globe,
  document_agent: FileText,
  multi_modal_agent: Image,
  social_media_agent: Bot,
};

function visibleTaskCount(agent: WorkspaceAgentEntry): string {
  const completed = agent.tasks.filter((task) => task.status === 'completed').length;
  return `${completed}/${agent.tasks.length}`;
}

function uiAgentTypeLabel(type?: string): string {
  if (type === 'browser_agent') return '浏览器';
  if (type === 'document_agent') return '文档';
  if (type === 'developer_agent') return '终端';
  if (type === 'multi_modal_agent') return '多模态';
  if (type === 'social_media_agent') return '社媒';
  return 'Worker';
}

function agentClass(agent: WorkspaceAgentEntry): string {
  return [
    'workspace-menu-agent',
    `agent-${agent.type}`,
    agent.status || '',
  ]
    .filter(Boolean)
    .join(' ');
}

function workerCode(agent: WorkspaceAgentEntry): string {
  return WORKER_CODES[agent.sourceWorkerName || agent.agent_id] || agent.name.slice(0, 2).toUpperCase();
}

function orderIndex(agent: WorkspaceAgentEntry): number {
  const index = WORKER_MENU_ORDER.indexOf(agent.sourceWorkerName || agent.agent_id);
  return index === -1 ? WORKER_MENU_ORDER.length : index;
}

function nativeWorkspaceType(agent: Agent): string {
  const value =
    `${agent.sourceWorkerName || ''} ${agent.type} ${agent.name}`.toLowerCase();
  if (value.includes('retrieval') || value.includes('browser')) {
    return 'browser_agent';
  }
  if (
    value.includes('analysis') ||
    value.includes('review') ||
    value.includes('document')
  ) {
    return 'document_agent';
  }
  return 'developer_agent';
}

function nativeAgentEntries(agents: Agent[]): WorkspaceAgentEntry[] {
  return agents
    .map((agent) => ({
      agent_id: agent.agent_id,
      name:
        COWORK_WORKER_LABELS[agent.sourceWorkerName || ''] || agent.name,
      type: nativeWorkspaceType(agent),
      tasks: agent.tasks,
      tools: agent.tools,
      status: agent.status,
      sourceWorkerName: agent.sourceWorkerName || agent.agent_id,
    }))
    .sort((left, right) => {
      const orderDelta = orderIndex(left) - orderIndex(right);
      return orderDelta || left.name.localeCompare(right.name);
    });
}

export function WorkspaceMenu({
  agents,
  activeWorkspace,
  onSelectWorkspace,
}: WorkspaceMenuProps) {
  const agentList = useMemo<WorkspaceAgentEntry[]>(() => {
    return nativeAgentEntries(agents);
  }, [agents]);

  return (
    <nav className="workspace-menu eigent-workspace-menu" aria-label="工作区">
      <MenuToggleGroup
        type="single"
        size="md"
        orientation="horizontal"
        value={activeWorkspace}
        className="workspace-menu-toggle-group"
      >
        <MenuToggleItem
          value="workflow"
          data-workspace-id="workflow"
          icon={<Network />}
          className="workspace-menu-system"
          onClick={() => onSelectWorkspace('workflow')}
          title="工作流"
        />
        <MenuToggleItem
          value="documentWorkSpace"
          data-workspace-id="documentWorkSpace"
          icon={<FolderOpen />}
          className="workspace-menu-system"
          onClick={() => onSelectWorkspace('documentWorkSpace')}
          title="智能体文件夹"
        />
        {agentList.map((agent) => {
          const SubIcon = agentIconMap[agent.type] || Bot;
          const disabled =
            !['developer_agent', 'browser_agent', 'document_agent', 'multi_modal_agent'].includes(agent.type) ||
            (agent.tasks.length === 0 && agent.status !== 'running');

          return (
            <MenuToggleItem
              key={agent.agent_id}
              value={agent.agent_id}
              data-workspace-id={agent.agent_id}
              disabled={disabled}
              icon={<Bot />}
              subIcon={<SubIcon />}
              showSubIcon
              className={agentClass(agent)}
              onClick={() => onSelectWorkspace(agent.agent_id)}
              title={`${agent.name} - ${uiAgentTypeLabel(agent.type)} ${visibleTaskCount(agent)}`}
              rightElement={
                agent.tasks.length > 0 ? (
                  <span className="workspace-menu-count">{visibleTaskCount(agent)}</span>
                ) : null
              }
            >
              <span className="workspace-menu-agent-code">{workerCode(agent)}</span>
            </MenuToggleItem>
          );
        })}
      </MenuToggleGroup>
    </nav>
  );
}
