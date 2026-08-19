import type { ListingDraft } from '../../api';
import { EmptyState } from '../common/StatusViews';

function DraftCard({ draft }: { draft: ListingDraft }) {
  return (
    <article className="listing-card">
      <div className="card-heading">
        <div>
          <span className="kicker">{draft.platform === 'shopify' ? 'SHOPIFY' : 'EBAY 美国站'} 草稿</span>
          <h3>{draft.title}</h3>
        </div>
        <span className="status-badge draft">基于 Product v{draft.derived_from_product_version}</span>
      </div>
      <p className="muted">规则版本 {draft.platform_rule_version}</p>
      <dl>
        <dt>分类</dt><dd>{draft.category || '—'}</dd>
        <dt>描述</dt><dd>{draft.description || '—'}</dd>
      </dl>
      {draft.gaps.length > 0 && (
        <div className="listing-gaps">
          <strong>尚未解决的字段映射缺口</strong>
          {draft.gaps.map((gap) => <p key={`${gap.field}-${gap.reason}`}>{gap.field}: {gap.reason}</p>)}
        </div>
      )}
      <details>
        <summary>查看平台字段</summary>
        <pre>{JSON.stringify(draft.data, null, 2)}</pre>
      </details>
    </article>
  );
}

export function ListingDraftsPanel({ drafts }: { drafts: ListingDraft[] }) {
  if (!drafts.length) {
    return <EmptyState title="未生成平台草稿" description="Listing 专员完成处理后，Shopify 与 eBay 美国站草稿会出现在这里。" />;
  }
  return (
    <div>
      <p className="notice">平台草稿来源于当前项目的规范 Product 事实，修改商品事实后需要重新生成。</p>
      <div className="listing-grid">{drafts.map((draft) => <DraftCard key={draft.id} draft={draft} />)}</div>
    </div>
  );
}
