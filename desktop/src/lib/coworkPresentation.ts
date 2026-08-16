const TOOL_DISPLAY_NAMES: Record<string, string> = {
  list_skills: '查看可用技能',
  load_skill: '加载技能',
  read_skill_resource: '读取技能资料',
  list_project_resources: '查看项目资源',
  inspect_task_materials: '查看任务素材',
  summarize_canonical_products: '查看规范商品摘要',
  summarize_listing_drafts: '查看平台草稿摘要',
  read_artifact_text: '读取文件内容',
  list_pending_approvals: '查看待审批事项',
  build_canonical_catalog: '建立规范商品目录',
  evaluate_us_apparel_compliance: '执行美国服装合规检查',
  create_listing_drafts: '生成平台草稿',
  review_catalog_release: '执行目录治理审核',
};

const EVENT_DISPLAY_NAMES: Record<string, string> = {
  task_started: '任务已开始',
  task_completed: '任务已完成',
  task_failed: '任务失败',
  tool_call_started: '工具已启动',
  tool_call_succeeded: '工具执行成功',
  tool_call_failed: '工具执行失败',
  workforce_process_completed: '执行已完成',
  workforce_process_failed: '执行失败',
};

const HIDDEN_WORKER_EVENT_TYPES = new Set([
  'shared_task_channel_created',
  'task_assigned',
  'task_completed',
  'task_created',
  'task_started',
  'task_update',
  'task_updated',
  'tool_call_failed',
  'tool_call_started',
  'tool_call_succeeded',
  'workforce_auto_review_started',
  'workforce_process_completed',
  'workforce_process_failed',
  'workforce_process_started',
  'workforce_session_created',
]);

export function asRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

export function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

export function firstString(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim();
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  }
  return '';
}

export function stableStringify(value: unknown): string {
  if (value == null || value === '') return '';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function truncateText(value: string, maxLength = 220): string {
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength - 3)}...`;
}

export function maybeParseJsonString(value: unknown): unknown {
  if (typeof value !== 'string') return value;
  const text = value.trim();
  if (!text || (!text.startsWith('{') && !text.startsWith('['))) return value;
  try {
    return JSON.parse(text);
  } catch {
    return value;
  }
}

export function isJsonLikeText(value: string): boolean {
  const text = value.trim();
  return (
    text.startsWith('{') ||
    text.startsWith('[') ||
    text.includes('\\"') ||
    /"[^"]+"\s*:/.test(text)
  );
}

export function stripInternalIds(value: string): string {
  return value
    .replace(/\bcowork_[a-z0-9]+(?:[._:-]\d+)*\b/gi, '')
    .replace(/\bcwfrun_[a-z0-9]+(?:[._:-]\d+)*\b/gi, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function isOpaqueTaskText(value: string, taskId?: string): boolean {
  const normalized = value.trim();
  if (!normalized) return true;
  if (taskId && normalized === taskId) return true;
  return /^cowork_[a-z0-9]+(?:[._:-]\d+)+$/i.test(normalized) || /^cwfrun_[a-z0-9]+/i.test(normalized);
}

export function readableTaskText(value: string, taskId: string, fallback: string): string {
  const stripped = stripInternalIds(value);
  if (!stripped || isOpaqueTaskText(stripped, taskId) || isJsonLikeText(stripped)) return fallback;
  return truncateText(stripped);
}

function humanizeToken(value: string): string {
  const normalized = value.replace(/[_-]+/g, ' ').trim();
  return normalized ? normalized[0].toUpperCase() + normalized.slice(1) : value;
}

export function toolDisplayName(toolName = ''): string {
  return TOOL_DISPLAY_NAMES[toolName] || humanizeToken(toolName) || '工具调用';
}

export function toolInputFocus(input?: Record<string, unknown> | null): string {
  if (!input) return '';
  const focus = firstString(
    input.query,
    input.question,
    input.objective,
    input.title,
    input.note_name,
    input.file_name,
    input.url,
    input.command,
    input.path,
    input.topic
  );
  if (focus) return truncateText(stripInternalIds(focus), 120);

  const items = asArray(input.items);
  if (items.length > 0) {
    const preview = arrayItemPreview(items, 120);
    if (preview) return preview;
    return `${items.length} 项`;
  }
  return '';
}

function arrayItemPreview(items: unknown[], maxLength = 180): string {
  const previews = items
    .map((item) => itemPreview(item, Math.max(48, Math.floor(maxLength / 2))))
    .filter(Boolean)
    .slice(0, 3);
  if (previews.length === 0) return '';
  const suffix = items.length > previews.length ? ` +${items.length - previews.length}` : '';
  return truncateText(`${previews.join(' / ')}${suffix}`, maxLength);
}

function itemPreview(item: unknown, maxLength = 180): string {
  const parsed = maybeParseJsonString(item);
  if (typeof parsed === 'string' || typeof parsed === 'number' || typeof parsed === 'boolean') {
    const summary = String(parsed).trim();
    if (!summary || isJsonLikeText(summary)) return '';
    return truncateText(stripInternalIds(summary), maxLength);
  }

  const record = asRecord(parsed);
  if (!record) return '';

  const summary = firstString(
    record.title,
    record.note_title,
    record.document_title,
    record.name,
    record.summary,
    record.result,
    record.text,
    record.content,
    record.chunk_text,
    record.text_content,
    record.note_content,
    record.description,
    record.desc,
    record.excerpt,
    record.url
  );
  if (summary && !isJsonLikeText(summary)) {
    return truncateText(stripInternalIds(summary), maxLength);
  }

  const fallback = firstString(record.id, record.chunk_id, record.document_id, record.source_ref);
  if (fallback && !isJsonLikeText(fallback)) {
    return truncateText(stripInternalIds(fallback), maxLength);
  }
  const keyValues = Object.entries(record)
    .filter(([, value]) => ['string', 'number', 'boolean'].includes(typeof value))
    .slice(0, 3)
    .map(([key, value]) => `${humanizeToken(key)}: ${stripInternalIds(String(value))}`)
    .filter((item) => !isJsonLikeText(item));
  if (keyValues.length > 0) return truncateText(keyValues.join(', '), maxLength);
  return '';
}

export function toolPayloadPreview(value: unknown, maxLength = 180): string {
  const parsed = maybeParseJsonString(value);
  if (typeof parsed === 'string') {
    return truncateText(stripInternalIds(parsed), maxLength);
  }
  const record = asRecord(parsed);
  if (record) {
    const summary = firstString(
      record.title,
      record.note_title,
      record.document_title,
      record.summary,
      record.result,
      record.text,
      record.content,
      record.url
    );
    if (summary && !isJsonLikeText(summary)) {
      return truncateText(stripInternalIds(summary), maxLength);
    }

    const items = asArray(record.items);
    if (items.length > 0) {
      return arrayItemPreview(items, maxLength) || `${items.length} 项`;
    }
    const evidence = asArray(record.evidence || record.evidence_items || record.results);
    if (evidence.length > 0) {
      return arrayItemPreview(evidence, maxLength) || `${evidence.length} 条证据`;
    }
  }
  return truncateText(stableStringify(parsed), maxLength);
}

export function toolOutputSummary(output?: Record<string, unknown> | null): string {
  if (!output) return '';
  const messagePayload = maybeParseJsonString(output.message);
  const messageRecord = asRecord(messagePayload);
  const report = asRecord(output.report) || asRecord(messageRecord?.report);
  const validationErrors = asArray(output.validation_errors)
    .map((item) => firstString(item) || stableStringify(item))
    .filter(Boolean);
  if (validationErrors.length > 0) {
    return truncateText(`校验失败：${validationErrors.join('; ')}`, 260);
  }

  const summary = firstString(
    report?.summary,
    output.summary,
    output.result_summary,
    output.result,
    messageRecord?.summary,
    messageRecord?.result,
    messageRecord?.status,
    output.status
  );
  if (summary && !isJsonLikeText(summary)) {
    return truncateText(stripInternalIds(summary), 260);
  }

  const arrays = [
    asArray(output.items),
    asArray(output.results),
    asArray(output.evidence),
    asArray(output.evidence_items),
    asArray(report?.evidence_items),
    asArray(report?.evidence),
  ];
  const firstNonEmpty = arrays.find((items) => items.length > 0);
  if (firstNonEmpty) {
    return arrayItemPreview(firstNonEmpty, 260) || `${firstNonEmpty.length} 项`;
  }

  return toolPayloadPreview(output, 260);
}

export function toolCallHeadline(
  toolName = '',
  input?: Record<string, unknown> | null,
  output?: Record<string, unknown> | null
): string {
  const label = toolDisplayName(toolName);
  const focus = toolInputFocus(input);
  if (focus) return `${label}: ${focus}`;
  const summary = toolOutputSummary(output);
  if (summary) return `${label}: ${summary}`;
  return label;
}

export function toolCallMessage(
  toolName = '',
  input?: Record<string, unknown> | null,
  output?: Record<string, unknown> | null,
  errorMessage = '',
  status = ''
): string {
  if (errorMessage) return truncateText(errorMessage, 260);
  const summary = toolOutputSummary(output);
  if (summary) return summary;
  const focus = toolInputFocus(input);
  if (focus) return focus;
  return status ? `${toolDisplayName(toolName)} ${status}` : toolDisplayName(toolName);
}

export function eventDisplayName(eventType = ''): string {
  return EVENT_DISPLAY_NAMES[eventType] || humanizeToken(eventType);
}

export function eventSummary(
  eventType = '',
  payload?: Record<string, unknown> | null,
  fallback = ''
): string {
  const toolName = firstString(payload?.tool_name, payload?.toolkit_name, payload?.method_name);
  const content = firstString(
    payload?.content,
    payload?.task_content,
    payload?.question,
    payload?.objective,
    payload?.result_summary,
    payload?.message,
    payload?.error
  );
  const output = asRecord(payload?.output_json);
  const toolSummary = toolCallMessage(toolName, asRecord(payload?.input_json), output, firstString(payload?.error), '');
  if (eventType.startsWith('tool_call_')) {
    return toolSummary || fallback || eventDisplayName(eventType);
  }
  if (content && !isJsonLikeText(content)) {
    return truncateText(stripInternalIds(content), 220);
  }
  const outputSummary = toolOutputSummary(output);
  if (outputSummary) return outputSummary;
  return fallback || eventDisplayName(eventType);
}

export function shouldDisplayWorkerEvent(eventType = ''): boolean {
  if (!eventType) return false;
  if (eventType.startsWith('human_interrupt_')) return false;
  if (eventType.startsWith('workspace_')) return false;
  return !HIDDEN_WORKER_EVENT_TYPES.has(eventType);
}
