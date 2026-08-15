/** Eigent-aligned: Completion Report only shows real task.report, never toolkit preview. */
export function completionReportContent(
  task?: { report?: string | null } | null
): string {
  return String(task?.report || '').trim();
}
