import { dv } from '../../lib/format.js'

export function Badge({ tone = 'neutral', children }) {
  if (children === null || children === undefined || children === '') return null
  return <span className={`badge badge-${tone}`}>{children}</span>
}

/** Definition list that silently skips empty values. */
export function KV({ rows }) {
  const visible = rows.filter(
    ([, value]) => value !== undefined && value !== null && !(typeof value === 'string' && value.trim() === ''),
  )
  if (!visible.length) return null
  return (
    <dl className="kv">
      {visible.map(([label, value]) => (
        <div className="kv-row" key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  )
}

export function DataTable({ columns, rows, rowKey, empty = 'No records.' }) {
  if (!rows?.length) return <EmptyNote>{empty}</EmptyNote>
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={[c.grow ? 'grow' : '', c.sticky ? 'sticky' : ''].join(' ').trim() || undefined}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={rowKey ? rowKey(row, i) : i}>
              {columns.map((c) => (
                <td key={c.key} className={c.sticky ? 'sticky' : undefined}>
                  {c.render ? c.render(row) : cell(row[c.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function cell(value) {
  const text = dv(value)
  return text === '' ? <span className="dim">—</span> : text
}

export function EmptyNote({ children }) {
  return <p className="empty-note">{children}</p>
}

export function Mono({ children }) {
  return <code className="mono">{children}</code>
}

export function LinkButton({ onClick, children, title }) {
  return (
    <button type="button" className="linkish" onClick={onClick} title={title}>
      {children}
    </button>
  )
}

export function ActiveBadge({ value }) {
  const active = value === true || String(value).toLowerCase() === 'true'
  return <Badge tone={active ? 'ok' : 'muted'}>{active ? 'Active' : 'Inactive'}</Badge>
}
