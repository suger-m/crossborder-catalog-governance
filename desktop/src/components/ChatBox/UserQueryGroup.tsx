// Adapted from ../_reference/eigent/src/components/ChatBox/UserQueryGroup.tsx.
// Groups a user objective with its CAMEL task card and assistant-side outputs.

import type { CoworkTask, CoworkTaskDetail } from '@/types';
import type { Task as NativeChatTask } from '@/store/chatStore';
import { AgentMessageCard, TaskCompletionCard, UserMessageCard } from './MessageItem';
import { TaskCard } from './TaskBox/TaskCard';

interface UserQueryGroupProps {
  task: CoworkTask;
  active: boolean;
  nativeTask?: NativeChatTask;
  onSelectTask: (taskId: string) => void;
  onStartTask?: (taskId: string) => void | Promise<void>;
  onOpenFile?: (taskId: string, file: FileInfo) => void;
  detail?: CoworkTaskDetail | null;
  onApproveHumanInterrupt?: (interruptId: string) => void | Promise<void>;
  onRejectHumanInterrupt?: (interruptId: string) => void | Promise<void>;
}

function agentMessages(task: CoworkTask, nativeTask?: NativeChatTask): Message[] {
  const messages = (nativeTask?.messages || []).filter(
    (message) => message.role === 'agent' && message.step === 'end'
  );
  const extraMessages: Message[] = [];

  if (task.error_message) {
    extraMessages.push({
      id: `${task.id}:error`,
      role: 'agent',
      content: task.error_message,
      task_id: task.id,
    });
  }

  const chatContent =
    task.kind === 'chat' &&
    typeof task.result_json?.assistant_content === 'string'
      ? task.result_json.assistant_content
      : '';
  if (chatContent) {
    extraMessages.push({
      id: `${task.id}:assistant`,
      role: 'agent',
      content: chatContent,
      step: 'end',
      task_id: task.id,
    });
  }

  if (messages.length === 0 && task.status === 'running') {
    extraMessages.push({
      id: `${task.id}:running`,
      role: 'agent',
      content: '任务正在自动执行，工具调用和结果会在右侧持续更新。',
      task_id: task.id,
    });
  }

  return [...messages, ...extraMessages];
}

function messageContent(message: Message): string {
  return message.summary || message.content || '智能体消息';
}

export function UserQueryGroup({ task, active, nativeTask, onSelectTask, onStartTask, onOpenFile, detail, onApproveHumanInterrupt, onRejectHumanInterrupt }: UserQueryGroupProps) {
  const messages = agentMessages(task, nativeTask);
  const isChat = task.kind === 'chat';

  return (
    <section className={`user-query-group ${active ? 'active' : ''}`} data-query-id={task.id}>
      <UserMessageCard id={`${task.id}:user-objective`} content={task.objective || task.id} />

      {!isChat ? (
        <TaskCard
          task={task}
          active={active}
          nativeTask={nativeTask}
          onSelectTask={onSelectTask}
          onStartTask={onStartTask}
          detail={detail}
          onApproveHumanInterrupt={onApproveHumanInterrupt}
          onRejectHumanInterrupt={onRejectHumanInterrupt}
        />
      ) : null}

      {messages.map((message) => {
        const content = messageContent(message);
        return (
          <AgentMessageCard
            content={content}
            files={message.fileList}
            id={message.id}
            key={message.id}
            onOpenFile={onOpenFile ? (file) => onOpenFile(message.task_id || task.id, file) : undefined}
          />
        );
      })}

      {!isChat && task.status === 'completed' ? <TaskCompletionCard taskPrompt={task.objective} /> : null}
    </section>
  );
}
