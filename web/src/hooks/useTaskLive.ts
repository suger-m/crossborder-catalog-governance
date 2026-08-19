import { useEffect, useRef, useState } from 'react';
import {
  api,
  type ProductEvent,
  type TaskDetail,
} from '../api';
import { localizedMessage } from '../lib/crossborderLabels';
import {
  contiguousEvents,
  isProductEvent,
  projectTaskWorkspace,
  type StreamState,
  type TaskWorkspaceProjection,
} from '../projection/taskProjection';

export function useTaskLive(taskId: string | null, onTaskChanged?: () => Promise<void>) {
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [events, setEvents] = useState<ProductEvent[]>([]);
  const [messages, setMessages] = useState<Array<Record<string, unknown>>>([]);
  const [streamState, setStreamState] = useState<StreamState>('connecting');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const onTaskChangedRef = useRef(onTaskChanged);
  onTaskChangedRef.current = onTaskChanged;

  const refresh = async () => {
    if (!taskId) return;
    try {
      const next = await api.task(taskId);
      setDetail(next);
      setError('');
      await onTaskChangedRef.current?.();
    } catch (reason) {
      setError(localizedMessage(reason));
    }
  };

  useEffect(() => {
    if (!taskId) {
      setDetail(null);
      setEvents([]);
      setMessages([]);
      setStreamState('closed');
      setError('');
      setLoading(false);
      return;
    }

    let disposed = false;
    let protocolBlocked = false;
    let source: EventSource | null = null;
    let timer: number | undefined;
    let cursor = 0;
    setLoading(true);
    setDetail(null);
    setEvents([]);
    setError('');
    setStreamState('connecting');

    const scheduleReconnect = (delay = 1000) => {
      if (disposed || protocolBlocked) return;
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(() => void connect(), delay);
    };

    const connect = async () => {
      if (disposed || protocolBlocked) return;
      source?.close();
      setStreamState(cursor ? 'reconnecting' : 'connecting');
      try {
        const snapshot = await api.productEvents(taskId, cursor);
        if (snapshot.protocol_name !== 'agentteams' || snapshot.protocol_version !== 1) {
          protocolBlocked = true;
          setStreamState('closed');
          setError('Web 与后端事件协议版本不兼容，请使用同一版本后重试。');
          return;
        }
        const additions = contiguousEvents((snapshot.items || []).filter(isProductEvent), cursor);
        if (additions === null) {
          scheduleReconnect(0);
          return;
        }
        if (additions.length) {
          setEvents((current) => [...current, ...additions]);
          cursor = additions.at(-1)?.sequence || cursor;
        }
        if (disposed) return;
        source = new EventSource(api.productEventStreamUrl(taskId, cursor));
        source.onopen = () => { setStreamState('live'); setError(''); };
        source.onerror = () => { source?.close(); setStreamState('reconnecting'); scheduleReconnect(); };
        source.addEventListener('cowork_product_event', (raw) => {
          try {
            const parsed = JSON.parse((raw as MessageEvent<string>).data) as unknown;
            if (!isProductEvent(parsed)) {
              protocolBlocked = true;
              source?.close();
              setStreamState('closed');
              setError('收到不兼容的任务事件，请确认 Web 与后端版本一致。');
              return;
            }
            if (parsed.sequence <= cursor) return;
            if (parsed.sequence !== cursor + 1) {
              source?.close();
              scheduleReconnect(0);
              return;
            }
            cursor = parsed.sequence;
            setEvents((current) => [...current, parsed]);
            void refresh();
          } catch {
            protocolBlocked = true;
            source?.close();
            setStreamState('closed');
            setError('任务事件无法解析，请确认 Web 与后端版本一致。');
          }
        });
      } catch (reason) {
        if (!disposed) {
          setError(localizedMessage(reason));
          setStreamState('reconnecting');
          scheduleReconnect(1500);
        }
      }
    };

    void (async () => {
      await refresh();
      if (!disposed) setLoading(false);
      await connect();
    })();

    const recovery = window.setInterval(() => void refresh(), 10000);
    return () => {
      disposed = true;
      source?.close();
      if (timer) window.clearTimeout(timer);
      window.clearInterval(recovery);
    };
  }, [taskId]);

  useEffect(() => {
    if (!taskId) return;
    let disposed = false;
    const load = async () => {
      try {
        const result = await api.agentTeamsMessages(taskId);
        if (!disposed) setMessages(result.items || []);
      } catch (reason) {
        if (!disposed) setError(localizedMessage(reason));
      }
    };
    void load();
    const interval = window.setInterval(() => void load(), detail?.task.status === 'running' ? 3500 : 10000);
    return () => {
      disposed = true;
      window.clearInterval(interval);
    };
  }, [detail?.task.status, taskId]);

  const projection: TaskWorkspaceProjection | null = detail
    ? projectTaskWorkspace(detail, events, messages)
    : null;

  return {
    detail,
    events,
    messages,
    streamState,
    error,
    loading,
    projection,
    refresh,
  };
}
