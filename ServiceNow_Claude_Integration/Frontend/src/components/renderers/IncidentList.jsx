import { Badge, DataTable, EmptyNote, LinkButton } from './shared.jsx'
import { priorityTone, stateTone, truncate } from '../../lib/format.js'

/** "2025-06-25 01:39:26" as a date line with the time underneath, so the column stays narrow. */
function DateCell({ value }) {
  if (!value) return <span className="dim">—</span>
  const [date, time] = String(value).split(' ')
  return (
    <span className="cell-date">
      {date}
      {time && <small>{time}</small>}
    </span>
  )
}

export default function IncidentList({ result, onFollowUp }) {
  const incidents = result?.incidents || []
  if (!incidents.length) return <EmptyNote>{result?.message || 'No incidents matched.'}</EmptyNote>

  const columns = [
    {
      key: 'number',
      label: 'Number',
      sticky: true,
      render: (r) => (
        <LinkButton onClick={() => onFollowUp?.(`Show incident ${r.number}`)} title="Open incident details">
          {r.number}
        </LinkButton>
      ),
    },
    {
      key: 'short_description',
      label: 'Short description',
      grow: true,
      render: (r) => <span title={r.short_description || ''}>{truncate(r.short_description, 60) || '—'}</span>,
    },
    { key: 'state', label: 'State', render: (r) => <Badge tone={stateTone(r.state)}>{r.state}</Badge> },
    { key: 'priority', label: 'Priority', render: (r) => <Badge tone={priorityTone(r.priority)}>{r.priority}</Badge> },
    { key: 'category', label: 'Category' },
    { key: 'created_on', label: 'Created', render: (r) => <DateCell value={r.created_on} /> },
    { key: 'updated_on', label: 'Updated', render: (r) => <DateCell value={r.updated_on} /> },
  ]

  return <DataTable columns={columns} rows={incidents} rowKey={(r) => r.sys_id || r.number} />
}
