import { ActiveBadge, EmptyNote } from './shared.jsx'
import { dv, stripHtml, truncate } from '../../lib/format.js'

export default function CatalogCategories({ result }) {
  const categories = result?.categories || []
  if (!categories.length) return <EmptyNote>{result?.message || 'No catalog categories found.'}</EmptyNote>

  return (
    <ul className="row-list">
      {categories.map((c) => (
        <li key={c.sys_id}>
          <div className="row-main">
            <span className="row-title">{dv(c.title) || 'Untitled category'}</span>
            <ActiveBadge value={c.active} />
          </div>
          {dv(c.description) && <div className="dim small">{truncate(stripHtml(dv(c.description)), 140)}</div>}
          {dv(c.parent) && <div className="dim small">Parent: {dv(c.parent)}</div>}
        </li>
      ))}
    </ul>
  )
}
