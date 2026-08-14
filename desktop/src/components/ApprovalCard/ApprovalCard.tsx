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
      setError('Enter or select the verified value before continuing.');
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
        <div><span className="kicker">HUMAN APPROVAL</span><h3>{approval.title}</h3></div>
        <span className={`status ${approval.status}`}>{approval.status}</span>
      </div>
      <p>{approval.description}</p>
      {options.length > 0 ? (
        <label className="choice-label">Resolve with
          <select value={selected} onChange={(event) => setSelected(event.target.value)} disabled={!pending || busy}>
            {options.map((choice) => <option key={choice} value={choice}>{choice}</option>)}
          </select>
        </label>
      ) : requiresValue ? (
        <label className="choice-label">Verified value
          <input value={selected} onChange={(event) => setSelected(event.target.value)} disabled={!pending || busy} placeholder="Enter the confirmed product fact" />
        </label>
      ) : null}
      {error && <p className="error">{error}</p>}
      {pending && <div className="card-actions">
        <button className="primary" disabled={busy} onClick={() => void decide(false)}>Approve & continue</button>
        <button disabled={busy} onClick={() => void decide(true)}>Reject</button>
      </div>}
    </article>
  );
}
