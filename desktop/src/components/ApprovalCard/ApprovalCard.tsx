import { useState } from 'react';
import type { Approval } from '../../api';

interface Props {
  approval: Approval;
  onDecide: (approvalId: string, decision: Record<string, unknown>, rejected: boolean) => Promise<void>;
}

function choices(approval: Approval): string[] {
  const values = approval.payload.values;
  return Array.isArray(values) ? values.map(String) : [];
}

export function ApprovalCard({ approval, onDecide }: Props) {
  const options = choices(approval);
  const [selected, setSelected] = useState(options[0] || '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const pending = approval.status === 'pending';
  const requiresValue = ['catalog_conflict', 'missing_required_fact'].includes(approval.approval_type);

  async function decide(rejected: boolean) {
    if (!rejected && requiresValue && !selected.trim()) {
      setError('继续前请填写或选择已核实的值。');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await onDecide(approval.id, selected ? { selected_value: selected.trim() } : {}, rejected);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="approval-card">
      <div className="card-heading">
        <div><span className="kicker">人工审批</span><h3>{approval.title}</h3></div>
        <span className={`status ${approval.status}`}>{approval.status}</span>
      </div>
      <p>{approval.description}</p>
      {options.length > 0 ? (
        <label className="choice-label">采用以下值解决
          <select value={selected} onChange={(event) => setSelected(event.target.value)} disabled={!pending || busy}>
            {options.map((choice) => <option key={choice} value={choice}>{choice}</option>)}
          </select>
        </label>
      ) : requiresValue ? (
        <label className="choice-label">已核实的值
          <input value={selected} onChange={(event) => setSelected(event.target.value)} disabled={!pending || busy} placeholder="请输入已确认的商品事实" />
        </label>
      ) : null}
      {error && <p className="error">{error}</p>}
      {pending && <div className="card-actions">
        <button className="primary" disabled={busy} onClick={() => void decide(false)}>批准并继续</button>
        <button disabled={busy} onClick={() => void decide(true)}>驳回</button>
      </div>}
    </article>
  );
}
