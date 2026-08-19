import { LoaderCircle, TriangleAlert, Inbox } from 'lucide-react';
import type { ReactNode } from 'react';
import { statusLabel } from '../../lib/crossborderLabels';

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  return <span className={`status-badge ${normalized}`}>{statusLabel(normalized)}</span>;
}

export function LoadingState({ title = '加载中', description = '正在从后端读取权威状态…' }: { title?: string; description?: string }) {
  return (
    <div className="state-panel loading">
      <LoaderCircle className="spin" size={22} />
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </div>
  );
}

export function ErrorState({ title = '加载失败', description }: { title?: string; description: string }) {
  return (
    <div className="state-panel failed">
      <TriangleAlert size={22} />
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="state-panel empty">
      <Inbox size={28} />
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
