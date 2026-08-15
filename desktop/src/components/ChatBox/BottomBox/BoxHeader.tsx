// Adapted from ../_reference/eigent/src/components/ChatBox/BottomBox/BoxHeader.tsx.

import { CheckCircle2, ChevronLeft, Loader2, PauseCircle } from 'lucide-react';
import type { BottomBoxState } from './index';

interface BoxHeaderProps {
  state: BottomBoxState;
  subtitle?: string;
  onEdit?: () => void;
}

function stateIcon(state: BottomBoxState) {
  if (state === 'splitting' || state === 'running') return <Loader2 className="spin" size={15} />;
  if (state === 'confirm') return <PauseCircle size={15} />;
  return <CheckCircle2 size={15} />;
}

function stateLabel(state: BottomBoxState) {
  if (state === 'splitting') return '正在规划任务';
  if (state === 'confirm') return '需要确认';
  if (state === 'running') return 'Workforce 运行中';
  if (state === 'finished') return '任务已完成';
  return '新任务';
}

export function BoxHeader({ state, subtitle, onEdit }: BoxHeaderProps) {
  return (
    <header className="chatbox-bottom-header">
      {state === 'confirm' && onEdit ? (
        <button className="box-header-back" onClick={onEdit} title="返回输入" type="button">
          <ChevronLeft size={15} />
        </button>
      ) : null}
      <span>
        {stateIcon(state)}
        {stateLabel(state)}
      </span>
      {subtitle ? <small>{subtitle}</small> : null}
    </header>
  );
}
