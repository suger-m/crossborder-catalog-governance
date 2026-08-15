// Adapted from ../_reference/eigent/src/components/ChatBox/BottomBox/index.tsx.
// Keeps the multi-state input, queued messages, and attachment composition while
// routing actions through cowork props.

import { useState } from 'react';
import type { CoworkTask } from '@/types';
import { ASK_PLACEHOLDER } from '@/lib/brand';
import type { FileAttachment } from './InputBox';
import { BoxHeader } from './BoxHeader';
import { ExpandedInputBox } from './ExpandedInputBox';
import { InputBox } from './InputBox';
import { QueuedBox, type QueuedMessage } from './QueuedBox';
import { UsageLimitBanner } from './UsageLimitBanner';

export type BottomBoxState = 'input' | 'splitting' | 'confirm' | 'running' | 'finished';

interface BottomBoxProps {
  state: BottomBoxState;
  objective: string;
  activeTaskId?: string;
  activeTask?: CoworkTask;
  loading: boolean;
  files: FileAttachment[];
  queuedMessages: QueuedMessage[];
  agents: Agent[];
  onObjectiveChange: (value: string) => void;
  onFilesChange: (files: FileAttachment[]) => void;
  onAddFile: () => void;
  onSubmit: () => void | Promise<void>;
  onQueueMessage: () => void;
  onRemoveQueuedMessage: (id: string) => void;
  onSelectQueuedMessage: (message: QueuedMessage) => void;
}

export function BottomBox({
  state,
  objective,
  activeTaskId,
  activeTask,
  loading,
  files,
  queuedMessages,
  agents,
  onObjectiveChange,
  onFilesChange,
  onAddFile,
  onSubmit,
  onQueueMessage,
  onRemoveQueuedMessage,
  onSelectQueuedMessage,
}: BottomBoxProps) {
  const [expanded, setExpanded] = useState(false);
  const [noticeDismissed, setNoticeDismissed] = useState(false);
  const queueMode = state === 'running' || state === 'splitting';
  const hasInput = Boolean(objective.trim() || files.length > 0);
  const canSendInput = queueMode ? hasInput : !loading && hasInput;
  const showNotice = !noticeDismissed && (queueMode || queuedMessages.length > 0);
  const submitInput = queueMode ? onQueueMessage : onSubmit;
  const dismissNotice = () => setNoticeDismissed(true);

  return (
    <div className="chatbox-bottom-shell">
      <QueuedBox
        queuedMessages={queuedMessages}
        onRemoveQueuedMessage={onRemoveQueuedMessage}
        onSelectQueuedMessage={onSelectQueuedMessage}
      />
      <div className={`chatbox-bottom bottom-state-${state}`}>
        <BoxHeader
          state={state}
          subtitle={queueMode ? '当前任务运行中，新输入将进入队列。' : undefined}
        />
        {showNotice ? (
          <UsageLimitBanner
            actionLabel={queuedMessages[0] ? '打开' : '关闭'}
            message={
              queueMode
                ? 'Workforce 正在运行，新输入将进入队列。'
                : `有 ${queuedMessages.length} 条排队输入等待处理。`
            }
            onAction={queuedMessages[0] ? () => onSelectQueuedMessage(queuedMessages[0]) : dismissNotice}
            onDismiss={dismissNotice}
            severity="warning"
          />
        ) : null}
        <div className="chatbox-inputbox">
          <InputBox
            disabled={loading && !queueMode}
            files={files}
            onAddFile={onAddFile}
            onChange={onObjectiveChange}
            onFilesChange={onFilesChange}
            onExpand={() => setExpanded(true)}
            onSend={submitInput}
            canSend={canSendInput}
            placeholder={ASK_PLACEHOLDER}
            sendTitle="发送"
            value={objective}
          />
        </div>
      </div>
      {expanded ? (
        <ExpandedInputBox
          agents={agents}
          onClose={() => setExpanded(false)}
          inputProps={{
            disabled: loading && !queueMode,
            files,
            onAddFile,
            onChange: onObjectiveChange,
            onFilesChange,
            onSend: submitInput,
            canSend: canSendInput,
            placeholder: ASK_PLACEHOLDER,
            sendTitle: '发送',
            value: objective,
          }}
        />
      ) : null}
    </div>
  );
}

export type { FileAttachment, QueuedMessage };
