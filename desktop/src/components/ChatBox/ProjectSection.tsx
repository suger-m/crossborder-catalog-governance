// Adapted from ../_reference/eigent/src/components/ChatBox/ProjectSection.tsx.
// Eigent's store subscription is replaced by cowork props and the
// native Eigent ChatStore task state.

import { forwardRef } from 'react';
import type { CoworkTask, CoworkTaskDetail } from '@/types';
import type { Task as NativeChatTask } from '@/store/chatStore';
import { FloatingAction } from './FloatingAction';
import { UserQueryGroup } from './UserQueryGroup';

interface ProjectSectionProps {
  task: CoworkTask;
  nativeTask?: NativeChatTask;
  active: boolean;
  loading?: boolean;
  onSelectTask: (taskId: string) => void;
  onStartTask?: (taskId: string) => void | Promise<void>;
  onOpenFile?: (taskId: string, file: FileInfo) => void;
  onSkip: () => void;
  detail?: CoworkTaskDetail | null;
  onApproveHumanInterrupt?: (interruptId: string) => void | Promise<void>;
  onRejectHumanInterrupt?: (interruptId: string) => void | Promise<void>;
}

export const ProjectSection = forwardRef<HTMLDivElement, ProjectSectionProps>(
  (
    {
      task,
      nativeTask,
      active,
      loading = false,
      onSelectTask,
      onStartTask,
      onOpenFile,
      onSkip,
      detail,
      onApproveHumanInterrupt,
      onRejectHumanInterrupt,
    },
    ref
  ) => (
    <section
      className={`project-section ${active ? 'active' : ''}`}
      data-project-section={task.id}
      onClick={() => onSelectTask(task.id)}
      ref={ref}
    >
      <UserQueryGroup
        active={active}
        onOpenFile={onOpenFile}
        onSelectTask={onSelectTask}
        onStartTask={onStartTask}
        detail={detail}
        onApproveHumanInterrupt={onApproveHumanInterrupt}
        onRejectHumanInterrupt={onRejectHumanInterrupt}
        task={task}
        nativeTask={nativeTask}
      />
      <FloatingAction
        status={task.status}
        onSkip={onSkip}
        loading={loading}
      />
    </section>
  )
);

ProjectSection.displayName = 'ProjectSection';
