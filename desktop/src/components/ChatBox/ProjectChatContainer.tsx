// Adapted from ../_reference/eigent/src/components/ChatBox/ProjectChatContainer.tsx.
// Provides the scroll container for cowork task query groups without depending
// on Eigent's project/chat stores.

import { useEffect, useMemo, useRef } from 'react';
import type { CoworkTask, CoworkTaskDetail } from '@/types';
import type { Task as NativeChatTask } from '@/store/chatStore';
import { PRODUCT_LOGO_URL, PRODUCT_NAME, WELCOME_SUBTITLE, WELCOME_TITLE } from '@/lib/brand';
import { ProjectSection } from './ProjectSection';

interface ProjectChatContainerProps {
  tasks: CoworkTask[];
  activeTaskId?: string;
  activeNativeTask?: NativeChatTask;
  loading?: boolean;
  onSelectTask: (taskId: string) => void;
  onStartTask?: (taskId: string) => void | Promise<void>;
  onOpenFile?: (taskId: string, file: FileInfo) => void;
  onSkipTask: () => void;
  activeDetail?: CoworkTaskDetail | null;
  onApproveHumanInterrupt?: (interruptId: string) => void | Promise<void>;
  onRejectHumanInterrupt?: (interruptId: string) => void | Promise<void>;
}

function taskTime(task: CoworkTask) {
  return task.updated_at || task.created_at || task.id;
}

export function ProjectChatContainer({
  tasks,
  activeTaskId,
  activeNativeTask,
  loading = false,
  onSelectTask,
  onStartTask,
  onOpenFile,
  onSkipTask,
  activeDetail,
  onApproveHumanInterrupt,
  onRejectHumanInterrupt,
}: ProjectChatContainerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const orderedTasks = useMemo(
    () => [...tasks].sort((a, b) => taskTime(a).localeCompare(taskTime(b))),
    [tasks]
  );

  useEffect(() => {
    if (!containerRef.current) return;
    containerRef.current.scrollTo({
      top: containerRef.current.scrollHeight,
      behavior: 'smooth',
    });
  }, [orderedTasks.length]);

  if (orderedTasks.length === 0) {
    return (
      <div className="project-chat-container init-state">
        <div className="chat-empty-intro eigent-chat-empty">
          <img className="chat-empty-logo" src={PRODUCT_LOGO_URL} alt={PRODUCT_NAME} />
          <strong>{WELCOME_TITLE}</strong>
          <span>{WELCOME_SUBTITLE}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="project-chat-container" ref={containerRef}>
      {orderedTasks.map((task) => {
        const active = task.id === activeTaskId;
        return (
          <ProjectSection
            active={active}
            key={task.id}
            loading={loading}
            onOpenFile={onOpenFile}
            onSelectTask={onSelectTask}
            onStartTask={onStartTask}
            onSkip={onSkipTask}
            task={task}
            nativeTask={task.id === activeTaskId ? activeNativeTask : undefined}
            detail={task.id === activeTaskId ? activeDetail : null}
            onApproveHumanInterrupt={onApproveHumanInterrupt}
            onRejectHumanInterrupt={onRejectHumanInterrupt}
          />
        );
      })}
    </div>
  );
}
