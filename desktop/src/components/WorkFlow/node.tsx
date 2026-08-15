// Adapted from ../_reference/eigent/src/components/WorkFlow/node.tsx.
// Eigent node interactions are preserved while data stays inside cowork props.

import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  CheckCircle2,
  Circle,
  CircleSlash2,
  Copy,
  FileText,
  Hourglass,
  Loader2,
  Search,
  SquareChevronLeft,
  SquareCode,
  TerminalSquare,
  XCircle,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { TaskState, type TaskStateType } from '@/components/TaskState';
import { Button } from '@/components/ui/button';
import type { ToolCall, WorkerNodeView, WorkerTaskView } from '@/types';
import { getToolkitIcon } from '@/lib/toolkitIcons';
import { statusLabel, stepLabel, toolLabel } from '@/lib/crossborderLabels';
import { getWorkflowAgentDisplay, normalizeAgentType } from './agents';
import { completionReportContent } from './completionReportContent';
import { MarkDown } from './MarkDown';

export interface WorkflowNodeData extends Record<string, unknown> {
  agent: WorkerNodeView;
  isExpanded: boolean;
  isActive?: boolean;
  onExpandChange: (nodeId: string, isExpanded: boolean) => void;
  onSelectAgent?: (agentId: string) => void;
}

export type WorkflowFlowNode = Node<WorkflowNodeData>;

function statusIcon(status?: WorkerTaskView['status'] | WorkerNodeView['status'] | ToolCall['status']) {
  if (status === 'running' || status === 'started') return <Loader2 className="spin" size={15} />;
  if (status === 'completed' || status === 'succeeded') return <CheckCircle2 size={15} />;
  if (status === 'failed') return <XCircle size={15} />;
  if (status === 'blocked' || status === 'cancelled') return <CircleSlash2 size={15} />;
  return <Circle size={15} />;
}

function taskTitle(task: WorkerTaskView) {
  return task.content || task.result || task.id;
}

function shortTaskId(taskId: string) {
  const pieces = taskId.split('.');
  if (pieces.length > 1) return pieces.slice(1).join('.');
  if (taskId.length > 18) return taskId.slice(0, 8);
  return taskId;
}

function taskStateCounts(tasks: WorkerTaskView[]) {
  return {
    all: tasks.length,
    done: tasks.filter((task) => task.status === 'completed').length,
    progress: tasks.filter((task) => task.status === 'running').length,
    skipped: tasks.filter((task) => !task.status || task.status === 'waiting').length,
    failed: tasks.filter((task) => task.status === 'failed' || task.status === 'blocked').length,
    reAssignTo: tasks.filter((task) => Boolean(task.reAssignTo)).length,
  };
}

function taskMatchesState(task: WorkerTaskView, selectedState: TaskStateType) {
  if (selectedState === 'all') return true;
  if (selectedState === 'done') return task.status === 'completed' && !task.reAssignTo;
  if (selectedState === 'ongoing') return task.status === 'running' && !task.reAssignTo;
  if (selectedState === 'pending') return (!task.status || task.status === 'waiting') && !task.reAssignTo;
  if (selectedState === 'failed') return task.status === 'failed' || task.status === 'blocked';
  if (selectedState === 'reassigned') return Boolean(task.reAssignTo);
  return true;
}

function fileContent(file?: FileInfo) {
  return String(file?.content || '').trim();
}

function taskPreviewText(task?: WorkerTaskView) {
  if (!task) return '';
  const documentFile = task.fileList?.find((file) => fileContent(file));
  return (
    fileContent(documentFile) ||
    String(task.result || '').trim()
  );
}

function idleWorkspaceCopy(agent: WorkerNodeView, task?: WorkerTaskView) {
  const id = `${agent.agent_id} ${agent.name}`.toLowerCase();
  const title = id.includes('catalog') || id.includes('steward')
    ? 'Product/SKU 商品工作区'
    : id.includes('compliance')
      ? '合规工作区'
      : id.includes('listing')
        ? '平台草稿工作区'
        : id.includes('governance') || id.includes('review')
          ? '治理审核工作区'
          : '智能体工作区';
  const description = task?.status === 'running'
    ? '正在执行，等待首个有效输出。'
    : task?.status === 'failed' || task?.status === 'blocked'
      ? '执行未完成，请查看任务状态。'
      : '等待工作流执行到此步骤。';
  return { title, description };
}

function terminalLines(task?: WorkerTaskView): string[] {
  if (!task) return [];
  return task.terminal || [];
}

function workspaceKind(agent: WorkerNodeView) {
  if (agent.workspace_type) return agent.workspace_type;
  if (agent.type === 'retrieval_worker') return 'browser_agent';
  if (agent.type === 'source_ingest_worker') return 'developer_agent';
  if (agent.type === 'analysis_worker' || agent.type === 'reviewer' || agent.type === 'reviewer_worker') {
    return 'document_agent';
  }
  return 'developer_agent';
}

function toolkitStatusValue(status?: ToolCall['status']): 'running' | 'completed' | 'failed' | 'pending' {
  if (status === 'running') return 'running';
  if (status === 'succeeded' || status === 'completed') return 'completed';
  if (status === 'failed' || status === 'cancelled') return 'failed';
  return 'pending';
}

function toolkitDisplayName(tool: ToolCall): string {
  return toolLabel(tool.tool_name);
}

export function Node({ id, data }: NodeProps<WorkflowFlowNode>) {
  const [isExpanded, setIsExpanded] = useState(data.isExpanded);
  const [selectedState, setSelectedState] = useState<TaskStateType>('all');
  const [selectedTaskId, setSelectedTaskId] = useState<string>('');
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);
  const agent = data.agent;
  const display = getWorkflowAgentDisplay(agent.type || agent.agent_id);
  const agentType = normalizeAgentType(agent.type || agent.agent_id);
  const kind = workspaceKind(agent);
  const hasWork = agent.tasks.length > 0 || agent.status === 'running';

  const counts = useMemo(() => taskStateCounts(agent.tasks), [agent.tasks]);
  const filteredTasks = useMemo(
    () => agent.tasks.filter((task) => taskMatchesState(task, selectedState)),
    [agent.tasks, selectedState]
  );

  const selectedTask = useMemo(() => {
    return (
      agent.tasks.find((task) => task.id === selectedTaskId) ||
      filteredTasks.find((task) => task.status === 'running') ||
      filteredTasks.find((task) => task.toolkits.length > 0) ||
      filteredTasks[0] ||
      agent.tasks.find((task) => task.status === 'running') ||
      agent.tasks.find((task) => task.toolkits.length > 0) ||
      agent.tasks[0]
    );
  }, [agent.tasks, filteredTasks, selectedTaskId]);

  const toolNames = useMemo(() => {
    const fromTasks = agent.tasks.flatMap((task) => [
      ...(task.sourceToolNames || []),
      ...task.toolkits.map((tool) => tool.tool_name),
    ]);
    return Array.from(new Set(fromTasks)).filter(Boolean);
  }, [agent.tasks]);

  const selectedPreview = taskPreviewText(selectedTask);
  const selectedCompletionReport = completionReportContent(selectedTask);
  const selectedTerminal = terminalLines(selectedTask);
  useEffect(() => {
    setIsExpanded(data.isExpanded);
  }, [data.isExpanded]);

  useEffect(() => {
    const runningWithTools = agent.tasks.find(
      (task) => task.status === 'running' && task.toolkits.length > 0
    );
    if (runningWithTools && !isExpanded) {
      setSelectedTaskId(runningWithTools.id);
      setIsExpanded(true);
      data.onExpandChange(id, true);
    }
  }, [agent.tasks, data, id, isExpanded]);

  const toggleExpanded = () => {
    const next = !isExpanded;
    setIsExpanded(next);
    data.onExpandChange(id, next);
  };

  const selectAgent = () => {
    if (hasWork) data.onSelectAgent?.(agent.agent_id);
  };

  const renderPreview = () => {
    const hasPreviewOutput = Boolean(selectedPreview || selectedTerminal.length > 0);
    if (!hasPreviewOutput) {
      const idle = idleWorkspaceCopy(agent, selectedTask);
      return (
        <button className="workflow-node-preview workflow-idle-preview nodrag" onClick={selectAgent} type="button">
          <Hourglass size={16} />
          <div><strong>{idle.title}</strong><p>{idle.description}</p></div>
        </button>
      );
    }

    if (kind === 'document_agent') {
      return (
        <button className="workflow-node-preview workflow-document-preview nodrag" onClick={selectAgent} type="button">
          <FileText size={16} />
          <div>
            <strong>{selectedTask?.fileList?.[0]?.name || '文档工作区'}</strong>
            <p>{selectedPreview}</p>
          </div>
        </button>
      );
    }

    if (kind === 'developer_agent') {
      return (
        <button className="workflow-node-preview workflow-terminal-preview nodrag" onClick={selectAgent} type="button">
          <TerminalSquare size={16} />
          <pre>{selectedTerminal.slice(0, 5).join('\n')}</pre>
        </button>
      );
    }

    return (
      <button className="workflow-node-preview workflow-browser-preview nodrag" onClick={selectAgent} type="button">
        <Search size={16} />
        <div>
          <strong>检索证据</strong>
          <p>
            {selectedTask?.fileList?.some((file) => file.artifact_type === 'evidence_bundle')
              ? '证据包已生成，点击查看结构化证据。'
              : selectedTask?.status === 'running'
                ? '正在检索并整理证据包…'
                : '等待检索证据。'}
          </p>
        </div>
      </button>
    );
  };

  return (
    <>
      <Handle className="workflow-handle" type="target" position={Position.Left} />
      <motion.div
        layout
        transition={{ layout: { duration: 0.24, ease: 'easeInOut' } }}
        className={[
          'eigent-worker-node',
          agent.status,
          isExpanded ? 'expanded' : '',
          data.isActive ? 'active' : '',
          hasWork ? '' : 'empty',
        ].filter(Boolean).join(' ')}
        data-workflow-node-id={agent.agent_id}
        data-workflow-node-active={data.isActive ? 'true' : 'false'}
      >
        <div className={`worker-accent ${display.tone}`} />

        <div className="worker-node-main">
          <header className="worker-node-header">
            <button className={`worker-icon ${display.tone} nodrag`} onClick={selectAgent} type="button">
              {display.icon}
            </button>
            <button className="worker-heading nodrag" onClick={selectAgent} type="button">
              <strong>{agent.name || display.name}</strong>
              <small>{agentType === 'worker' ? '业务智能体' : agentType}</small>
            </button>
            <span className="node-status" title={agent.status}>{statusIcon(agent.status)}</span>
            <button
              className="icon-button compact nodrag"
              onClick={toggleExpanded}
              title={isExpanded ? '收起智能体详情' : '展开智能体详情'}
              type="button"
            >
              {isExpanded ? <SquareChevronLeft size={16} /> : <SquareCode size={16} />}
            </button>
          </header>

          <div className="workflow-toolkit-row">
            {toolNames.length === 0 ? (
              <span>尚未分配工具包</span>
            ) : (
              toolNames.slice(0, 6).map((tool) => <span key={tool}># {toolLabel(tool)}</span>)
            )}
          </div>

          {renderPreview()}

          <div className="workflow-node-state nodrag">
            <TaskState
              all={counts.all}
              done={counts.done}
              progress={counts.progress}
              skipped={counts.skipped}
              failed={counts.failed}
              reAssignTo={counts.reAssignTo}
              forceVisible
              selectedState={selectedState}
              onStateChange={setSelectedState}
              running={agent.status === 'running'}
            />
          </div>

          <div className="workflow-task-list">
            {filteredTasks.length === 0 ? (
              <div className="workflow-empty-task">等待分配子任务</div>
            ) : (
              filteredTasks.map((task) => (
                <button
                  key={task.id}
                  className={`workflow-task-card nodrag ${task.status || 'pending'} ${selectedTask?.id === task.id ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedTaskId(task.id);
                    if (!isExpanded) {
                      setIsExpanded(true);
                      data.onExpandChange(id, true);
                    }
                  }}
                  type="button"
                >
                  <div className="task-card-title">
                    {statusIcon(task.status)}
                    <span>{stepLabel(taskTitle(task))}</span>
                  </div>
                  <small className="workflow-task-meta">
                    <span>编号 {shortTaskId(task.id)}</span>
                    {task.toolkits.length > 0 ? <span>{task.toolkits.length} 个工具</span> : null}
                  </small>
                  {task.status === 'running' && task.toolkits.length > 0 ? (
                    <div className="workflow-running-toolkit">
                      {getToolkitIcon(toolkitDisplayName(task.toolkits[0]))}
                      <span className="workflow-running-toolkit-text">{toolkitDisplayName(task.toolkits[0])} · 执行中</span>
                    </div>
                  ) : null}
                </button>
              ))
            )}
          </div>
        </div>

        <AnimatePresence initial={false}>
          {isExpanded ? (
            <motion.aside
              animate={{ opacity: 1, x: 0 }}
              className="worker-node-detail"
              exit={{ opacity: 0, x: 18 }}
              initial={{ opacity: 0, x: 18 }}
              transition={{ duration: 0.2, ease: 'easeInOut' }}
            >
              <div
                ref={logRef}
                className="scrollbar scrollbar-always-visible flex max-h-[calc(100vh-220px)] flex-col gap-sm overflow-y-auto pr-sm"
              >
                {selectedTask ? (
                  <div ref={wrapperRef} className="flex w-full flex-col gap-sm">
                    {selectedTerminal.length > 0 ? (
                      <div className="workflow-progress-lines">
                        <strong>工作进度</strong>
                        {selectedTerminal.map((line, index) => <p key={`${index}:${line}`}>{line}</p>)}
                      </div>
                    ) : null}
                    {(selectedTask.toolkits || []).length > 0 ? (
                      selectedTask.toolkits.map((tool, index) => {
                        const toolkitName = toolkitDisplayName(tool);
                        const toolkitState = toolkitStatusValue(tool.status);
                        return (
                          <div className={`eigent-toolkit-log ${toolkitState}`} key={tool.id || `${selectedTask.id}:${index}`}>
                            <div className="eigent-toolkit-log-top">
                              {toolkitState === 'running' ? <Loader2 className="spin" size={16} /> : getToolkitIcon(toolkitName)}
                              <span className="eigent-toolkit-log-name">{toolkitName}</span>
                              <b className="eigent-toolkit-log-status">{statusLabel(toolkitState)}</b>
                            </div>
                          </div>
                        );
                      })
                    ) : (
                      <div className="workflow-empty-task">该子任务暂无工具调用</div>
                    )}

                    {selectedCompletionReport ? (
                      <div className="group relative my-2 flex w-full flex-col rounded-lg bg-surface-primary">
                        <div className="sticky top-0 z-10 flex items-center justify-between rounded-lg bg-surface-primary py-2 pl-2 pr-2">
                          <div className="text-label-sm font-bold text-text-primary">
                            完成摘要
                          </div>
                          <Button
                            variant="ghost"
                            size="xs"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (navigator.clipboard?.writeText) {
                                navigator.clipboard.writeText(selectedCompletionReport).catch(() => {
                                  return;
                                });
                              }
                            }}
                            className="text-label-xs"
                          >
                            <Copy className="text-icon-secondary" />
                            <span className="text-icon-secondary">复制</span>
                          </Button>
                        </div>
                        <div className="px-2 py-2">
                          <MarkDown
                            content={selectedCompletionReport}
                            enableTypewriter={false}
                            pTextSize="text-label-xs"
                          />
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </motion.aside>
          ) : null}
        </AnimatePresence>
      </motion.div>
      <Handle className="workflow-handle" type="source" position={Position.Right} />
    </>
  );
}
