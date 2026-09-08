import { ActiveBadge, DataTable, EmptyNote } from './shared.jsx'
import { dv, truncate } from '../../lib/format.js'

export default function Groups({ result }) {
  const groups = result?.groups || []
  if (!groups.length) return <EmptyNote>{result?.message || 'No groups matched.'}</EmptyNote>

  const columns = [
    { key: 'name', label: 'Name', render: (g) => <strong>{dv(g.name)}</strong> },
    {
      key: 'description',
      label: 'Description',
      grow: true,
      render: (g) => {
        const text = truncate(dv(g.description), 80)
        return text ? <span title={dv(g.description)}>{text}</span> : <span className="dim">—</span>
      },
    },
    { key: 'type', label: 'Type' },
    { key: 'manager', label: 'Manager' },
    { key: 'email', label: 'Email' },
    { key: 'active', label: 'Status', render: (g) => <ActiveBadge value={g.active} /> },
  ]

  return <DataTable columns={columns} rows={groups} rowKey={(g) => g.sys_id || dv(g.name)} />
}
