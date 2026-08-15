import { useEffect, useState } from 'react';
import { api, type ModelRoleStatus, type ModelSettings, type SkillDetail, type SkillSummary } from '../../api';
import { SKILL_DESCRIPTIONS, localizedMessage, skillLabel } from '../../lib/crossborderLabels';

type SettingsTab = 'models' | 'skills';

const SKILL_OWNERS: Record<string, string> = {
  'product-catalog': '商品目录专员',
  'womenswear-classification': '商品目录专员',
  'us-apparel-compliance': '合规专员',
  'shopify-product-policy': '合规专员',
  'ebay-us-fashion-policy': '合规专员',
  'product-localization-en-us': '商品刊登专员',
  'shopify-listing': '商品刊登专员',
  'ebay-us-listing': '商品刊登专员',
  'catalog-governance': '治理审核员',
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
      } catch (reason) { setMessage(localizedMessage(reason)); }
    })();
  }, [open]);

  if (!open) return null;

  async function saveModel(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setMessage('');
    try {
      const extra_params = JSON.parse(form.extra_params || '{}') as Record<string, unknown>;
      const saved = await api.saveModelSettings({ source: form.source, model_platform: form.model_platform, model_type: form.model_type, api_url: form.api_url, extra_params, ...(form.api_key ? { api_key: form.api_key } : {}) });
      setSettings(saved); setRoles(await api.modelReadiness()); setForm((current) => ({ ...current, api_key: '' })); setMessage('模型配置已保存。');
    } catch (reason) { setMessage(reason instanceof Error ? reason.message : '模型设置中的 JSON 参数格式无效。'); }
    finally { setBusy(false); }
  }

  async function smokeTest() {
    setBusy(true); setMessage('正在测试模型连接…');
    try { const result = await api.modelSmoke(); setRoles(result); setMessage('模型连接测试完成。'); } catch (reason) { setMessage(localizedMessage(reason)); }
    finally { setBusy(false); }
  }

  async function selectSkill(item: SkillSummary) {
    try { setSkill(await api.skill(item.name)); } catch (reason) { setMessage(localizedMessage(reason)); }
  }

  return <div className="settings-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) onClose(); }}>
    <section className="settings-center" role="dialog" aria-modal="true" aria-label="工作区设置">
      <header className="settings-center-header"><div><span className="eyebrow">平台配置</span><h2>设置</h2><p>配置本项目使用的模型运行环境和版本化智能体技能。</p></div><button className="icon-button" onClick={onClose} disabled={busy} aria-label="关闭设置">×</button></header>
      <nav className="settings-tabs" aria-label="设置栏目"><button className={tab === 'models' ? 'active' : ''} onClick={() => setTab('models')}>模型与运行环境</button><button className={tab === 'skills' ? 'active' : ''} onClick={() => setTab('skills')}>智能体技能 <span>{skills.length}</span></button></nav>
      {message && <p className={message.includes('已保存') || message.includes('完成') ? 'success' : 'error'}>{message}</p>}
      {tab === 'models' ? <section className="settings-content"><div className="settings-card"><div className="card-heading"><div><span className="kicker">当前模型</span><h3>大模型服务商</h3></div>{settings && <span className="status completed">{{ custom: '自定义', cloud: '云端', local: '本地' }[settings.source] || settings.source}</span>}</div><form className="settings-form" onSubmit={(event) => void saveModel(event)}><label>配置来源<select value={form.source} onChange={(event) => setForm({ ...form, source: event.target.value })}><option value="custom">自定义</option><option value="cloud">云端</option><option value="local">本地</option></select></label><label>模型平台<input required value={form.model_platform} placeholder="openai-compatible" onChange={(event) => setForm({ ...form, model_platform: event.target.value })} /></label><label>模型名称<input required value={form.model_type} placeholder="deepseek-chat" onChange={(event) => setForm({ ...form, model_type: event.target.value })} /></label><label>API 基础地址<input value={form.api_url} placeholder="https://…/v1" onChange={(event) => setForm({ ...form, api_url: event.target.value })} /></label><label>API 密钥<input type="password" value={form.api_key} autoComplete="new-password" placeholder={settings?.has_api_key ? '已保存密钥；输入新值可替换' : '请输入服务商密钥'} onChange={(event) => setForm({ ...form, api_key: event.target.value })} /></label><label>附加参数（JSON）<textarea value={form.extra_params} onChange={(event) => setForm({ ...form, extra_params: event.target.value })} /></label><div className="settings-actions"><button className="primary" type="submit" disabled={busy}>{busy ? '保存中…' : '保存模型设置'}</button><button type="button" onClick={() => void smokeTest()} disabled={busy}>测试连接</button></div></form></div><div className="settings-card"><div className="card-heading"><div><span className="kicker">智能体团队角色</span><h3>运行就绪状态</h3></div></div><div className="role-readiness">{['planner', 'worker', 'reviewer'].map((role) => <article key={role}><strong>{{ planner: '规划器', worker: '执行智能体', reviewer: '审核器' }[role]}</strong><span className={roles[role]?.ok || roles[role]?.configured ? 'ready' : 'not-ready'}>{roles[role]?.ok ? '已就绪' : roles[role]?.configured ? '已配置' : '需要配置'}</span><small>{roles[role]?.model_type || roles[role]?.error || '使用当前模型配置'}</small></article>)}</div></div></section>
        : <section className="settings-content skills-settings"><div className="settings-card"><div className="card-heading"><div><span className="kicker">版本化技能</span><h3>已安装的智能体技能</h3></div><span className="muted">共 {skills.length} 项</span></div><p className="notice">技能从项目仓库加载，由对应业务智能体根据任务选择。技能不是自由提示词，也不会被模型输出静默替换。</p><div className="skill-list">{skills.map((item) => <button key={item.name} className={skill?.name === item.name ? 'selected' : ''} onClick={() => void selectSkill(item)}><strong>{skillLabel(item.name)}</strong><span>{SKILL_OWNERS[item.name] || '平台技能'} · {item.name}</span><small>{SKILL_DESCRIPTIONS[item.name] || item.description || '暂无描述。'}</small></button>)}{!skills.length && <p className="muted">配置的技能目录中尚未发现技能。</p>}</div></div><article className="settings-card skill-preview">{skill ? <><div className="card-heading"><div><span className="kicker">技能说明文件</span><h3>{skillLabel(skill.name)}</h3></div><span className="status completed">已加载</span></div><pre>{skill.content}</pre></> : <div className="empty-state"><h3>选择一项技能</h3><p>选择技能后可查看其说明和归属智能体。</p></div>}</article></section>}
    </section>
  </div>;
}
