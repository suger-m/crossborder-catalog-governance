// Adapted from ../_reference/eigent/src/components/ChatBox/TaskBox/TypeCardSkeleton.tsx.
// The skeleton is local CSS only; it does not depend on Eigent's ui/progress stack.

import { ChevronDown, LoaderCircle } from 'lucide-react';
import { TaskType } from './TaskType';

interface TypeCardSkeletonProps {
  isTakeControl?: boolean;
}

export function TypeCardSkeleton({ isTakeControl = false }: TypeCardSkeletonProps) {
  const pulseClass = isTakeControl ? '' : ' pulse';

  return (
    <div className="chat-type-card-skeleton" data-type-card-skeleton>
      <div className="chat-type-card-progress" />
      <div className="chat-type-card-lines">
        <span className={`skeleton-line wide${pulseClass}`} />
        <span className={`skeleton-line half${pulseClass}`} />
        <span className={`skeleton-line half${pulseClass}`} />
      </div>
      <div className="chat-type-card-toolbar">
        <TaskType type={1} />
        <span>Tasks</span>
        <ChevronDown className="rotated" size={16} />
      </div>
      <div className="chat-type-card-items">
        {[1, 2, 3].map((item) => (
          <div className="chat-type-card-skeleton-item" key={item}>
            <LoaderCircle className={isTakeControl ? '' : 'spin'} size={15} />
            <span className={`skeleton-line wide${pulseClass}`} />
          </div>
        ))}
      </div>
    </div>
  );
}
