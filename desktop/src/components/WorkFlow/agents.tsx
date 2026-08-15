// Adapted from ../_reference/eigent/src/components/WorkFlow/agents.tsx.
// Keeps Eigent's agent display-map boundary while mapping to this project's CAMEL worker profiles.

import {
  Bot,
  FileSearch,
  LineChart,
  ShieldCheck,
  UserRound,
} from 'lucide-react';
import type { ReactNode } from 'react';

export type CoworkWorkflowAgentType =
  | 'retrieval_worker'
  | 'source_ingest_worker'
  | 'analysis_worker'
  | 'reviewer'
  | 'reviewer_worker'
  | 'planner'
  | 'human'
  | 'worker';

export interface AgentDisplayInfo {
  name: string;
  icon: ReactNode;
  tone: 'blue' | 'green' | 'amber' | 'rose' | 'violet' | 'slate' | 'teal' | 'gray';
}

export const agentMap: Record<CoworkWorkflowAgentType, AgentDisplayInfo> = {
  retrieval_worker: {
    name: 'Retrieval Worker',
    icon: <FileSearch size={16} />,
    tone: 'blue',
  },
  source_ingest_worker: {
    name: 'Source Ingest Worker',
    icon: <FileSearch size={16} />,
    tone: 'teal',
  },
  analysis_worker: {
    name: 'Analysis Worker',
    icon: <LineChart size={16} />,
    tone: 'green',
  },
  reviewer: {
    name: 'Reviewer',
    icon: <ShieldCheck size={16} />,
    tone: 'rose',
  },
  reviewer_worker: {
    name: 'Reviewer',
    icon: <ShieldCheck size={16} />,
    tone: 'rose',
  },
  planner: {
    name: 'Planner',
    icon: <Bot size={16} />,
    tone: 'slate',
  },
  human: {
    name: 'Human',
    icon: <UserRound size={16} />,
    tone: 'gray',
  },
  worker: {
    name: 'Worker',
    icon: <Bot size={16} />,
    tone: 'slate',
  },
};

export const WORKFLOW_AGENT_LIST: {
  id: CoworkWorkflowAgentType;
  name: string;
  icon: ReactNode;
}[] = Object.entries(agentMap).map(([id, info]) => ({
  id: id as CoworkWorkflowAgentType,
  name: info.name,
  icon: info.icon,
}));

export function normalizeAgentType(value?: string): CoworkWorkflowAgentType {
  if (!value) return 'worker';
  const normalized = value.replace(/^worker_/, '') as CoworkWorkflowAgentType;
  return normalized in agentMap ? normalized : 'worker';
}

export function getWorkflowAgentDisplay(agentName: string): AgentDisplayInfo {
  return agentMap[normalizeAgentType(agentName)];
}
