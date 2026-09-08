import { ActiveBadge, EmptyNote } from './shared.jsx'
import { dv, stripHtml, truncate } from '../../lib/format.js'

export default function CatalogItems({ result, onFollowUp }) {
  const items = result?.items || []
  if (!items.length) return <EmptyNote>{result?.message || 'No catalog items matched.'}</EmptyNote>

  return (
    <div className="grid-cards">
      {items.map((item) => (
        <button
          key={item.sys_id}
          type="button"
          className="card card-btn"
          onClick={() => onFollowUp?.(`Show catalog item ${item.sys_id}`)}
          title="Open catalog item details"
        >
          <div className="card-title">{dv(item.name) || 'Untitled item'}</div>
          <div className="dim small">{truncate(stripHtml(dv(item.short_description)), 110) || 'No description'}</div>
          <div className="card-foot">
            <span className="dim small">{dv(item.category)}</span>
            {item.price && item.price !== '$0.00' && <span className="price">{item.price}</span>}
            <ActiveBadge value={item.active} />
          </div>
        </button>
      ))}
    </div>
  )
}
