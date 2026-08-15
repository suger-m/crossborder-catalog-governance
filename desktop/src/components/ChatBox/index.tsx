// Adapted from ../_reference/eigent/src/components/ChatBox/index.tsx.
// This keeps the Eigent ChatBox orchestration shape while using cowork API props.

import { useRef, useState } from 'react';
import type { CoworkInputAttachment, CoworkTask, CoworkTaskDetail } from '@/types';
import type { Task as NativeChatTask } from '@/store/chatStore';
import {
  BottomBox,
  type BottomBoxState,
  type FileAttachment,
  type QueuedMessage,
} from './BottomBox';
import { HeaderBox } from './HeaderBox';
import { ProjectChatContainer } from './ProjectChatContainer';

interface ChatBoxProps {
  objective: string;
  tasks: CoworkTask[];
  activeTaskId?: string;
  activeTask?: CoworkTask;
  nativeTask?: NativeChatTask;
  loading: boolean;
  onObjectiveChange: (value: string) => void;
  onSubmit: (inputFiles?: CoworkInputAttachment[]) => void | Promise<void>;
  onRefresh: () => void;
  onSelectTask: (taskId: string) => void;
  onStartTask?: (taskId: string) => void | Promise<void>;
  onOpenFile?: (taskId: string, file: FileInfo) => void;
  onCancelTask: () => void;
  activeDetail?: CoworkTaskDetail | null;
  onApproveHumanInterrupt?: (interruptId: string) => void | Promise<void>;
  onRejectHumanInterrupt?: (interruptId: string) => void | Promise<void>;
}

function bottomState(task: CoworkTask | undefined, loading: boolean): BottomBoxState {
  if (loading && !task) return 'splitting';
  if (!task) return 'input';
  if (task.kind === 'chat') return 'input';
  if (task.status === 'completed') return 'finished';
  if (task.status === 'waiting_approval' || task.status === 'waiting_human_input' || task.status === 'paused') {
    return 'confirm';
  }
  if (loading || task.status === 'running') return 'running';
  return 'input';
}

export function ChatBox({
  objective,
  tasks,
  activeTaskId,
  activeTask,
  nativeTask,
  loading,
  onObjectiveChange,
  onSubmit,
  onRefresh,
  onSelectTask,
  onStartTask,
  onOpenFile,
  onCancelTask,
  activeDetail,
  onApproveHumanInterrupt,
  onRejectHumanInterrupt,
}: ChatBoxProps) {
  const selectedTask = activeTask || tasks.find((task) => task.id === activeTaskId);
  const [files, setFiles] = useState<FileAttachment[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const [queuedMessages, setQueuedMessages] = useState<QueuedMessage[]>([]);
  const state = bottomState(selectedTask, loading);

  const submit = async () => {
    await onSubmit(files);
    setFiles([]);
  };

  const addFile = async () => {
    // Browser fallback is the normal desktop-web path. Electron can still
    // provide the native bridge when available, but the control must never
    // become a no-op when that bridge is absent.
    const bridge = window.coworkDesktop;
    if (!bridge) {
      inputRef.current?.click();
      return;
    }
    const result = await bridge.selectDataFile({
      title: 'Attach cowork input files',
      multiple: true,
      allowedExtensions: ['csv', 'json', 'jsonl', 'md', 'txt', 'xlsx', 'parquet'],
    });
    if (result.canceled) return;
    setFiles((previous) => {
      const next = new Map(previous.map((file) => [file.filePath, file]));
      result.files.forEach((file) => {
        next.set(file.path, {
          fileName: file.name,
          filePath: file.path,
          extension: file.extension,
        });
      });
      return Array.from(next.values());
    });
  };

  const onBrowserFiles = (selected: FileList | null) => {
    if (!selected) return;
    setFiles((previous) => {
      const next = new Map(previous.map((file) => [file.filePath, file]));
      Array.from(selected).forEach((file) => {
        next.set(file.name, {
          fileName: file.name,
          filePath: file.name,
          extension: file.name.split('.').pop()?.toLowerCase(),
          file,
        });
      });
      return Array.from(next.values());
    });
  };

  const queueMessage = () => {
    if (!objective.trim() && files.length === 0) return;
    setQueuedMessages((previous) => [
      ...previous,
      {
        id: `queued-${Date.now()}-${previous.length}`,
        content: objective.trim() || 'Attached files',
        timestamp: Date.now(),
        files,
      },
    ]);
    onObjectiveChange('');
    setFiles([]);
  };

  const removeQueuedMessage = (id: string) => {
    setQueuedMessages((previous) => previous.filter((message) => message.id !== id));
  };

  const selectQueuedMessage = (message: QueuedMessage) => {
    onObjectiveChange(message.content);
    setFiles(message.files || []);
    removeQueuedMessage(message.id);
  };

  return (
    <aside className="chat-panel eigent-left-chat">
      <HeaderBox loading={loading} taskCount={tasks.length} onRefresh={onRefresh} />
      <ProjectChatContainer
        tasks={tasks}
        activeTaskId={activeTaskId}
        activeNativeTask={nativeTask}
        loading={loading}
        onOpenFile={onOpenFile}
        onSelectTask={onSelectTask}
        onStartTask={onStartTask}
        activeDetail={activeDetail}
        onApproveHumanInterrupt={onApproveHumanInterrupt}
        onRejectHumanInterrupt={onRejectHumanInterrupt}
        onSkipTask={onCancelTask}
      />
      <BottomBox
        state={state}
        objective={objective}
        activeTaskId={activeTaskId}
        activeTask={selectedTask}
        loading={loading}
        files={files}
        queuedMessages={queuedMessages}
        agents={nativeTask?.taskAssigning || []}
        onObjectiveChange={onObjectiveChange}
        onFilesChange={setFiles}
        onAddFile={addFile}
        onSubmit={submit}
        onQueueMessage={queueMessage}
        onRemoveQueuedMessage={removeQueuedMessage}
        onSelectQueuedMessage={selectQueuedMessage}
      />
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".csv,.json,.jsonl,.md,.txt,.xlsx,.parquet"
        className="sr-only"
        onChange={(event) => onBrowserFiles(event.target.files)}
      />
    </aside>
  );
}
