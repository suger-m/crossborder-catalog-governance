import type { Finding } from '../../api';

function bucket(item: Finding): 'blocking' | 'confirmation' | 'information' {
  if (item.status === 'blocked' || item.severity === 'blocking') return 'blocking';
  if (item.status === 'needs_confirmation' || item.severity === 'confirmation') return 'confirmation';
  return 'information';
}

export function ProductIssues({ findings }: { findings: Finding[] }) {
  const visible = findings.filter((item) => item.status !== 'pass');
  const groups: Array<[ReturnType<typeof bucket>, string]> = [
    ['blocking', '阻塞交付'],
    ['confirmation', '需要确认'],
    ['information', '信息与证据'],
  ];
  if (!visible.length) return <div className="empty-state"><h3>未发现业务问题</h3><p>该智能体已完成检查，本项目当前没有需要展示的问题。</p></div>;
  return <div className="issue-groups">{groups.map(([key, label]) => {
    const items = visible.filter((item) => bucket(item) === key);
    return <section className={`issue-group ${key}`} key={key}><div className="section-label"><h3>{label}</h3><span>{items.length}</span></div>{items.length ? items.map((item) => <article className="issue" key={item.id}><strong>{item.title || item.field || '商品目录检查项'}</strong><p>{item.message}</p><small>{[item.scope, ...(item.platforms || [])].filter(Boolean).join(' · ') || '商品目录治理'}</small></article>) : <p className="muted">无</p>}</section>;
  })}</div>;
}
