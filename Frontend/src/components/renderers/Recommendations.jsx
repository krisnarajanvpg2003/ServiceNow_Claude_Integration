import { Badge, EmptyNote, LinkButton } from './shared.jsx'
import { dv, plural, stripHtml, truncate } from '../../lib/format.js'

export default function Recommendations({ result, onFollowUp }) {
  const recs = result?.recommendations || []
  if (!recs.length) return <EmptyNote>{result?.message || 'No recommendations were returned.'}</EmptyNote>
  return (
    <div className="stack">
      {recs.map((rec) => (
        <RecSection key={rec.type || rec.title} rec={rec} onFollowUp={onFollowUp} />
      ))}
    </div>
  )
}

function RecSection({ rec, onFollowUp }) {
  const items = rec.items || []
  const shown = items.slice(0, 8)
  const rest = items.slice(8)

  const renderItem = (item) => (
    <li key={item.sys_id || item.name}>
      <LinkButton onClick={() => onFollowUp?.(`Show catalog item ${item.sys_id}`)} title="Open catalog item details">
        {dv(item.name) || item.sys_id}
      </LinkButton>
      {dv(item.short_description) && (
        <span className="dim"> · {truncate(stripHtml(dv(item.short_description)), 100)}</span>
      )}
    </li>
  )

  return (
    <section className="card">
      <div className="card-head">
        <div className="card-title">{rec.title}</div>
        <div className="badges">
          <Badge tone={levelTone(rec.impact)}>Impact: {rec.impact}</Badge>
          <Badge tone={levelTone(rec.effort)}>Effort: {rec.effort}</Badge>
          <Badge tone="neutral">{plural(items.length, 'item')}</Badge>
        </div>
      </div>
      {rec.description && <p className="dim">{rec.description}</p>}
      {rec.action && <p className="callout">Suggested action: {rec.action}</p>}
      {items.length ? <ul className="item-list">{shown.map(renderItem)}</ul> : <EmptyNote>No items flagged.</EmptyNote>}
      {rest.length > 0 && (
        <details className="more">
          <summary>Show {rest.length} more</summary>
          <ul className="item-list">{rest.map(renderItem)}</ul>
        </details>
      )}
    </section>
  )
}

function levelTone(level) {
  const v = String(level || '').toLowerCase()
  if (v === 'high') return 'high'
  if (v === 'medium') return 'moderate'
  return 'low'
}
