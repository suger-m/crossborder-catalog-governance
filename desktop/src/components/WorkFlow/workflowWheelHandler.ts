// Adapted from ../_reference/eigent/src/components/WorkFlow/workflowWheelHandler.ts.

import type { Viewport } from '@xyflow/react';

export interface WorkflowWheelHandlerOptions {
  isEditMode: boolean;
  getViewport: () => Viewport;
  setViewport: (viewport: Viewport, opts?: { duration: number }) => void;
  clampViewportX: (x: number) => number;
}

export function createWorkflowWheelHandler(
  options: WorkflowWheelHandlerOptions
): (event: WheelEvent) => void {
  const { isEditMode, getViewport, setViewport, clampViewportX } = options;

  return (event: WheelEvent) => {
    if (isEditMode) return;

    if (event.ctrlKey) {
      event.preventDefault();
      return;
    }

    const hasScroll = event.deltaX !== 0 || event.deltaY !== 0;
    if (!hasScroll) return;

    event.preventDefault();

    const { x, y, zoom } = getViewport();
    const panDelta = event.deltaX !== 0 ? event.deltaX : event.deltaY;
    setViewport({ x: clampViewportX(x - panDelta), y, zoom }, { duration: 0 });
  };
}
