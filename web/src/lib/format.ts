export function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDateTime(value?: string): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString('zh-CN');
  } catch {
    return value;
  }
}

export function formatShortId(value: string): string {
  return value.slice(-8);
}
