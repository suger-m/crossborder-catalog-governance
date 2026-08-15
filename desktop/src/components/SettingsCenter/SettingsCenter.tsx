import { useEffect, useState } from 'react';
import { api, type ModelRoleStatus, type ModelSettings, type SkillDetail, type SkillSummary } from '../../api';

type SettingsTab = 'models' | 'skills';

const SKILL_OWNERS: Record<string, string> = {
  'product-catalog': 'Catalog Steward',
  'womenswear-classification': 'Catalog Steward',
  'us-apparel-compliance': 'Compliance Specialist',
  'shopify-product-policy': 'Compliance Specialist',
  'ebay-us-fashion-policy': 'Compliance Specialist',
  'product-localization-en-us': 'Listing Operations',
  'shopify-listing': 'Listing Operations',
  'ebay-us-listing': 'Listing Operations',
  'catalog-governance': 'Governance Reviewer',
};

interface Props { open: boolean; onClose: () => void }

export function SettingsCenter({ open, onClose }: Props) {
  const [tab, setTab] = useState<SettingsTab>('models');
  const [settings, setSettings] = useState<ModelSettings | null>(null);
  const [form, setForm] = useState({ source: 'custom', model_platform: '', model_type: '', api_url: '', api_key: '', extra_params: '{}' });
  const [roles, setRoles] = useState<ModelRoleStatus>({});
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [skill, setSkill] = useState<SkillDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!open) return;
    setMessage('');
    void (async () => {
      try {
        const [model, readiness, skillResult] = await Promise.all([api.modelSettings(), api.modelReadiness(), api.skills()]);
        setSettings(model);
        setRoles(readiness);
        setSkills(skillResult.items);
        setForm((current) => ({ ...current, source: ['custom', 'local', 'cloud'].includes(model.source) ? model.source : 'custom', model_platform: model.model_platform, model_type: model.model_type, api_url: model.api_url, extra_params: JSON.stringify(model.extra_params || {}, null, 2) }));
      } catch (reason) { setMessage(reason instanceof Error ? reason.message : String(reason)); }
    })();
  }, [open]);

  if (!open) return null;

  async function saveModel(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setMessage('');
    try {
      const extra_params = JSON.parse(form.extra_params || '{}') as Record<string, unknown>;
      const saved = await api.saveModelSettings({ source: form.source, model_platform: form.model_platform, model_type: form.model_type, api_url: form.api_url, extra_params, ...(form.api_key ? { api_key: form.api_key } : {}) });
      setSettings(saved); setRoles(await api.modelReadiness()); setForm((current) => ({ ...current, api_key: '' })); setMessage('Model configuration saved.');
    } catch (reason) { setMessage(reason instanceof Error ? reason.message : 'Model settings must contain valid JSON options.'); }
    finally { setBusy(false); }
  }

  async function smokeTest() {
    setBusy(true); setMessage('Running model smoke test…');
    try { const result = await api.modelSmoke(); setRoles(result); setMessage('Smoke test completed.'); } catch (reason) { setMessage(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }

  async function selectSkill(item: SkillSummary) {
    try { setSkill(await api.skill(item.name)); } catch (reason) { setMessage(reason instanceof Error ? reason.message : String(reason)); }
  }

  return <div className="settings-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) onClose(); }}>
    <section className="settings-center" role="dialog" aria-modal="true" aria-label="Workspace settings">
      <header className="settings-center-header"><div><span className="eyebrow">PLATFORM CONFIGURATION</span><h2>Settings</h2><p>Model runtime and versioned Agent Skills used by this project.</p></div><button className="icon-button" onClick={onClose} disabled={busy} aria-label="Close settings">×</button></header>
      <nav className="settings-tabs" aria-label="Settings sections"><button className={tab === 'models' ? 'active' : ''} onClick={() => setTab('models')}>Models & runtime</button><button className={tab === 'skills' ? 'active' : ''} onClick={() => setTab('skills')}>Agent Skills <span>{skills.length}</span></button></nav>
      {message && <p className={message.includes('saved') || message.includes('completed') ? 'success' : 'error'}>{message}</p>}
      {tab === 'models' ? <section className="settings-content"><div className="settings-card"><div className="card-heading"><div><span className="kicker">ACTIVE MODEL</span><h3>LLM provider</h3></div>{settings && <span className="status completed">{settings.source}</span>}</div><form className="settings-form" onSubmit={(event) => void saveModel(event)}><label>Source<select value={form.source} onChange={(event) => setForm({ ...form, source: event.target.value })}><option value="custom">Custom</option><option value="cloud">Cloud</option><option value="local">Local</option></select></label><label>Model platform<input required value={form.model_platform} placeholder="openai-compatible" onChange={(event) => setForm({ ...form, model_platform: event.target.value })} /></label><label>Model type<input required value={form.model_type} placeholder="deepseek-chat" onChange={(event) => setForm({ ...form, model_type: event.target.value })} /></label><label>API base URL<input value={form.api_url} placeholder="https://…/v1" onChange={(event) => setForm({ ...form, api_url: event.target.value })} /></label><label>API key<input type="password" value={form.api_key} autoComplete="new-password" placeholder={settings?.has_api_key ? 'Saved key retained; enter to replace' : 'Enter provider key'} onChange={(event) => setForm({ ...form, api_key: event.target.value })} /></label><label>Extra parameters (JSON)<textarea value={form.extra_params} onChange={(event) => setForm({ ...form, extra_params: event.target.value })} /></label><div className="settings-actions"><button className="primary" type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save model settings'}</button><button type="button" onClick={() => void smokeTest()} disabled={busy}>Test connection</button></div></form></div><div className="settings-card"><div className="card-heading"><div><span className="kicker">WORKFORCE ROLES</span><h3>Runtime readiness</h3></div></div><div className="role-readiness">{['planner', 'worker', 'reviewer'].map((role) => <article key={role}><strong>{role}</strong><span className={roles[role]?.ok || roles[role]?.configured ? 'ready' : 'not-ready'}>{roles[role]?.ok ? 'Ready' : roles[role]?.configured ? 'Configured' : 'Needs configuration'}</span><small>{roles[role]?.model_type || roles[role]?.error || 'Uses the active model configuration'}</small></article>)}</div></div></section>
        : <section className="settings-content skills-settings"><div className="settings-card"><div className="card-heading"><div><span className="kicker">VERSIONED SKILLS</span><h3>Installed Agent Skills</h3></div><span className="muted">{skills.length} available</span></div><p className="notice">Skills are loaded from the repository and selected by the assigned business Agent. They are not free-form prompt text and are not silently replaced by LLM output.</p><div className="skill-list">{skills.map((item) => <button key={item.name} className={skill?.name === item.name ? 'selected' : ''} onClick={() => void selectSkill(item)}><strong>{item.name}</strong><span>{SKILL_OWNERS[item.name] || 'Platform skill'}</span><small>{item.description || 'No description provided.'}</small></button>)}{!skills.length && <p className="muted">No skills discovered in the configured skills directory.</p>}</div></div><article className="settings-card skill-preview">{skill ? <><div className="card-heading"><div><span className="kicker">SKILL.md</span><h3>{skill.name}</h3></div><span className="status completed">Loaded</span></div><pre>{skill.content}</pre></> : <div className="empty-state"><h3>Select a Skill</h3><p>Choose a Skill to inspect its instructions and ownership.</p></div>}</article></section>}
    </section>
  </div>;
}
