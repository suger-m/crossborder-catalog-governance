// Adapted from ../_reference/eigent/src/components/ChatBox/BottomBox/UsageLimitBanner.tsx.
// This local variant reports cowork queue/runtime state instead of cloud quota.

import { X } from 'lucide-react';

interface UsageLimitBannerProps {
  message: string;
  actionLabel: string;
  severity: 'warning' | 'danger';
  onAction: () => void;
  onDismiss: () => void;
}

export function UsageLimitBanner({
  message,
  actionLabel,
  severity,
  onAction,
  onDismiss,
}: UsageLimitBannerProps) {
  return (
    <div className={`usage-limit-banner ${severity}`} data-usage-limit-banner>
      <strong>{message}</strong>
      <button className="usage-limit-action" onClick={onAction} type="button">
        {actionLabel}
      </button>
      <button
        aria-label="关闭提示"
        className="usage-limit-dismiss"
        onClick={onDismiss}
        title="关闭"
        type="button"
      >
        <X size={15} />
      </button>
    </div>
  );
}
