// Adapted from ../_reference/eigent/src/components/BottomBar/index.tsx:
// keep the bottom workspace switcher boundary while sourcing state from props.

import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { WorkspaceMenu } from '@/components/WorkspaceMenu';

interface BottomBarProps {
  agents: Agent[];
  activeWorkspace: string;
  isChatBoxVisible: boolean;
  onToggleChatBox: () => void;
  onSelectWorkspace: (workspaceId: string) => void;
}

export function BottomBar({
  agents,
  activeWorkspace,
  isChatBoxVisible,
  onToggleChatBox,
  onSelectWorkspace,
}: BottomBarProps) {
  return (
    <footer className="bottom-bar">
      <button
        className="bottom-bar-toggle"
        onClick={onToggleChatBox}
        title={isChatBoxVisible ? 'Hide ChatBox' : 'Show ChatBox'}
      >
        {isChatBoxVisible ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
      </button>
      <WorkspaceMenu
        agents={agents}
        activeWorkspace={activeWorkspace}
        onSelectWorkspace={onSelectWorkspace}
      />
    </footer>
  );
}
