// Adapted from ../_reference/eigent/src/components/WorkFlow/index.tsx.
// Keeps Eigent's horizontal worker-lane behavior while using cowork view data.

import {
  PanOnScrollMode,
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useReactFlow,
  type NodeTypes,
} from '@xyflow/react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { WorkerNodeView } from '@/types';
import { Node as CustomNodeComponent, type WorkflowFlowNode } from './node';
import { createWorkflowWheelHandler } from './workflowWheelHandler';
import '@xyflow/react/dist/style.css';

interface WorkflowProps {
  agents: Agent[];
  activeAgentId?: string;
  focusedAgentId?: string;
  onSelectAgent?: (agentId: string) => void;
}

const nodeTypes: NodeTypes = {
  node: (props) => <CustomNodeComponent {...props} />,
};

const NODE_WIDTH = 342;
const EXPANDED_NODE_WIDTH = 684;
const NODE_GAP = 20;

const BASE_WORKERS: WorkerNodeView[] = [
  {
    agent_id: 'catalog_steward_agent',
    name: 'Catalog Steward',
    type: 'worker',
    workspace_type: 'developer_agent',
    status: 'pending',
    tools: ['inspect_product', 'classify_product', 'build_sku_graph'],
    tasks: [],
    log: [],
  },
  {
    agent_id: 'compliance_specialist_agent',
    name: 'Compliance Specialist',
    type: 'worker',
    workspace_type: 'document_agent',
    status: 'pending',
    tools: ['load_compliance_skill', 'check_us_apparel', 'validate_marketplace_policy'],
    tasks: [],
    log: [],
  },
  {
    agent_id: 'listing_operations_agent',
    name: 'Listing Operations',
    type: 'worker',
    workspace_type: 'document_agent',
    status: 'pending',
    tools: ['load_localization_skill', 'build_shopify_draft', 'build_ebay_draft'],
    tasks: [],
    log: [],
  },
  {
    agent_id: 'governance_reviewer_agent',
    name: 'Governance Reviewer',
    type: 'worker',
    workspace_type: 'document_agent',
    status: 'pending',
    tools: ['validate_evidence', 'review_release_readiness', 'request_human_approval'],
    tasks: [],
    log: [],
  },
];

const BASE_ORDER = new Map(BASE_WORKERS.map((worker, index) => [worker.agent_id, index]));

function nativeWorkerType(agent: Agent): WorkerNodeView['type'] {
  const value =
    `${agent.sourceWorkerName || ''} ${agent.name}`.toLowerCase();
  if (value.includes('retrieval')) return 'retrieval_worker';
  if (value.includes('source') && value.includes('ingest')) return 'source_ingest_worker';
  if (value.includes('analysis')) return 'analysis_worker';
  if (value.includes('review')) return 'reviewer';
  return 'worker';
}

function nativeAgentToWorkerNode(agent: Agent): WorkerNodeView {
  return {
    agent_id: agent.agent_id,
    name: agent.name,
    type: nativeWorkerType(agent),
    workspace_type:
      agent.type === 'single_agent' ? 'developer_agent' : agent.type,
    status: agent.status || 'pending',
    tools: agent.tools || [],
    tasks: agent.tasks.map((task) => ({
      id: task.id,
      content: task.content,
      status: task.status === 'skipped' ? 'waiting' : task.status || 'waiting',
      result: task.report || task.terminal?.join('\n'),
      report: task.report,
      terminal: task.terminal,
      fileList: task.fileList,
      failure_count: task.failure_count,
      reAssignTo: task.reAssignTo,
      toolkits: (task.toolkits || []).map((toolkit) => ({
        id: toolkit.toolkitId || `${task.id}:${toolkit.toolkitName}:${toolkit.toolkitMethods}`,
        tool_name: toolkit.toolkitMethods || toolkit.toolkitName,
        status: toolkit.toolkitStatus || 'pending',
        input_json: {},
        output_json: toolkit.message ? { message: toolkit.message } : {},
      })),
    })),
    log: [],
  };
}

function normalizeWorkerId(value?: string): string {
  const normalized = String(value || '').replace(/^worker_/, '');
  return normalized === 'reviewer_worker' ? 'reviewer' : normalized;
}

function workflowAgentKey(agent: WorkerNodeView): string {
  const candidates = [agent.agent_id, agent.type, agent.name].map(normalizeWorkerId);
  return candidates.find((candidate) => BASE_ORDER.has(candidate)) || normalizeWorkerId(agent.agent_id);
}

function isAgentActive(agent: WorkerNodeView, activeAgentId?: string): boolean {
  if (!activeAgentId) return false;
  const normalizedActive = normalizeWorkerId(activeAgentId);
  if (normalizedActive === agent.agent_id || normalizedActive === agent.type || activeAgentId === agent.workspace_type) {
    return true;
  }
  return activeAgentId === 'documentWorkSpace' && agent.workspace_type === 'document_agent';
}

function mergeBaseWorkers(agents: WorkerNodeView[]): WorkerNodeView[] {
  const byId = new Map<string, WorkerNodeView>();
  BASE_WORKERS.forEach((worker) => byId.set(worker.agent_id, worker));
  agents.forEach((agent) => {
    const key = workflowAgentKey(agent);
    const previous = byId.get(key);
    const agentTools = agent.tools || [];
    const previousTools = previous?.tools || [];
    byId.set(key, {
      ...previous,
      ...agent,
      agent_id: agent.agent_id || previous?.agent_id || key,
      type: previous?.type || agent.type,
      name: agent.name || previous?.name || key,
      tools: agentTools.length > 0 ? agentTools : previousTools,
      tasks: agent.tasks || [],
      log: agent.log || [],
    });
  });
  return Array.from(byId.values()).sort((left, right) => {
    const leftHasWork = left.tasks.length > 0 || left.status === 'running';
    const rightHasWork = right.tasks.length > 0 || right.status === 'running';
    if (leftHasWork !== rightHasWork) return leftHasWork ? -1 : 1;
    return (BASE_ORDER.get(workflowAgentKey(left)) ?? 99) - (BASE_ORDER.get(workflowAgentKey(right)) ?? 99);
  });
}

export function projectWorkflowAgents(agents: Agent[]): WorkerNodeView[] {
  return mergeBaseWorkers(agents.map(nativeAgentToWorkerNode));
}

function WorkflowCanvas({ agents, activeAgentId, focusedAgentId, onSelectAgent }: WorkflowProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<WorkflowFlowNode>([]);
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({});
  const [containerWidth, setContainerWidth] = useState(0);
  const [userHasPanned, setUserHasPanned] = useState(false);
  const lastFocusedIdRef = useRef('');
  const programmaticMoveRef = useRef(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { getViewport, setViewport } = useReactFlow();
  const isEditMode = false;
  const workflowAgents = useMemo(
    () => projectWorkflowAgents(agents),
    [agents]
  );
  const normalizedActiveAgentId = normalizeWorkerId(activeAgentId || '');

  const workflowSummary = useMemo(
    () => ({
      all: workflowAgents.length,
      running: workflowAgents.filter((agent) => agent.status === 'running').length,
      completed: workflowAgents.filter((agent) => agent.status === 'completed').length,
      failed: workflowAgents.filter((agent) => agent.status === 'failed').length,
      tasks: workflowAgents.reduce((count, agent) => count + agent.tasks.length, 0),
    }),
    [workflowAgents]
  );

  const totalNodesWidth = useMemo(() => {
    if (!nodes.length) return 0;
    const widths = nodes.map((node) =>
      node.data.isExpanded ? EXPANDED_NODE_WIDTH : NODE_WIDTH
    );
    return widths.reduce((sum, width) => sum + width, 0) + Math.max(nodes.length - 1, 0) * NODE_GAP + 16;
  }, [nodes]);

  const minViewportX = useMemo(() => {
    if (!containerWidth) return 0;
    const contentWidth = Math.max(totalNodesWidth, containerWidth);
    return Math.min(0, containerWidth - contentWidth);
  }, [containerWidth, totalNodesWidth]);

  const clampViewportX = useCallback(
    (x: number) => Math.min(0, Math.max(minViewportX, x)),
    [minViewportX]
  );

  const handleExpandChange = useCallback((nodeId: string, isExpanded: boolean) => {
    setExpandedNodes((prev) => ({ ...prev, [nodeId]: isExpanded }));
  }, []);

  useEffect(() => {
    let currentX = 8;
    const nextNodes = workflowAgents.map((agent) => {
      const isExpanded = expandedNodes[agent.agent_id] || false;
      const node: WorkflowFlowNode = {
        id: agent.agent_id,
        type: 'node',
        position: { x: currentX, y: 16 },
        data: {
          agent,
          isExpanded,
          isActive: isAgentActive(agent, focusedAgentId || activeAgentId),
          onExpandChange: handleExpandChange,
          onSelectAgent,
        },
      };
      currentX += (isExpanded ? EXPANDED_NODE_WIDTH : NODE_WIDTH) + NODE_GAP;
      return node;
    });
    setNodes(nextNodes);
  }, [activeAgentId, expandedNodes, focusedAgentId, handleExpandChange, onSelectAgent, setNodes, workflowAgents]);

  useEffect(() => {
    if (normalizedActiveAgentId && lastFocusedIdRef.current !== normalizedActiveAgentId) {
      setUserHasPanned(false);
    }
  }, [normalizedActiveAgentId]);

  useEffect(() => {
    const targetId = normalizedActiveAgentId;
    if (!targetId || targetId === 'workflow') return;
    if (userHasPanned) return;
    if (lastFocusedIdRef.current === targetId) return;
    const targetNode = nodes.find((node) => normalizeWorkerId(node.id) === targetId);
    if (!targetNode) return;
    const targetX = clampViewportX(-targetNode.position.x);
    lastFocusedIdRef.current = targetId;
    programmaticMoveRef.current = true;
    setViewport({ x: targetX, y: 0, zoom: 1 }, { duration: 300 });
    window.setTimeout(() => {
      programmaticMoveRef.current = false;
    }, 350);
  }, [clampViewportX, normalizedActiveAgentId, nodes, setViewport, userHasPanned]);

  useEffect(() => {
    if (!nodes.length) return;
    const viewport = getViewport();
    const clampedX = clampViewportX(viewport.x);
    if (clampedX === viewport.x && viewport.y === 0) return;
    programmaticMoveRef.current = true;
    setViewport({ ...viewport, x: clampedX, y: 0 }, { duration: 0 });
    window.setTimeout(() => {
      programmaticMoveRef.current = false;
    }, 50);
  }, [clampViewportX, containerWidth, getViewport, nodes.length, setViewport, totalNodesWidth]);

  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.clientWidth);
      }
    };

    updateWidth();
    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, []);

  useEffect(() => {
    const container = containerRef.current?.querySelector<HTMLElement>('.react-flow__pane');
    if (!container) return;

    const onWheel = createWorkflowWheelHandler({
      isEditMode,
      getViewport,
      setViewport,
      clampViewportX,
    });

    container.addEventListener('wheel', onWheel, { passive: false });
    return () => container.removeEventListener('wheel', onWheel);
  }, [clampViewportX, getViewport, setViewport]);

  return (
    <section
      className="workflow-panel eigent-workflow-panel"
      data-workflow-agent-count={workflowAgents.length}
    >
      <div className="section-header workflow-header">
        <div>
          <div className="eyebrow">WorkFlow</div>
          <h2>Worker Nodes</h2>
        </div>
        <div className="workflow-summary">
          <span>{workflowSummary.all} agents</span>
          <span>{workflowSummary.tasks} subtasks</span>
          <span>{workflowSummary.running} running</span>
          <span>{workflowSummary.completed} done</span>
          {workflowSummary.failed > 0 ? <span>{workflowSummary.failed} failed</span> : null}
        </div>
      </div>
      <div
        className="workflow-canvas eigent-workflow-canvas"
        data-workflow-node-count={nodes.length}
        ref={containerRef}
      >
        <ReactFlow
          nodes={nodes}
          edges={[]}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          proOptions={{ hideAttribution: true }}
          zoomOnScroll={false}
          zoomOnPinch={false}
          zoomOnDoubleClick={false}
          panOnDrag={isEditMode}
          panOnScroll={false}
          panOnScrollMode={PanOnScrollMode.Horizontal}
          nodesDraggable={isEditMode}
          defaultViewport={{ x: 0, y: 0, zoom: 1 }}
          onMove={(_event, viewport) => {
            const clampedX = clampViewportX(viewport.x);
            if (clampedX !== viewport.x) {
              setViewport({ ...viewport, x: clampedX });
              return;
            }
            if (!isEditMode && !programmaticMoveRef.current && Math.abs(viewport.x) > 1) setUserHasPanned(true);
          }}
        />
      </div>
    </section>
  );
}

export function WorkFlow({ agents, activeAgentId, focusedAgentId, onSelectAgent }: WorkflowProps) {
  return (
    <ReactFlowProvider>
      <WorkflowCanvas agents={agents} activeAgentId={activeAgentId} focusedAgentId={focusedAgentId} onSelectAgent={onSelectAgent} />
    </ReactFlowProvider>
  );
}
