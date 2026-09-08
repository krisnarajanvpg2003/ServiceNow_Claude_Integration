import { DataTable, EmptyNote, Mono } from './shared.jsx'

export default function ApiIndex({ result }) {
  const endpoints = result?.endpoints || []
  if (!endpoints.length) return <EmptyNote>The API index returned no endpoints.</EmptyNote>
  const columns = [
    { key: 'name', label: 'Endpoint', render: (e) => <strong>{e.name}</strong> },
    { key: 'url', label: 'URL', grow: true, render: (e) => <Mono>{e.url}</Mono> },
    { key: 'tool', label: 'MCP tool', render: (e) => (e.tool ? <Mono>{e.tool}</Mono> : <span className="dim">—</span>) },
    { key: 'notes', label: 'Notes' },
  ]
  return (
    <div className="stack">
      {result?.name && <p className="dim small">{result.name}</p>}
      <DataTable columns={columns} rows={endpoints} rowKey={(e) => e.url} />
    </div>
  )
}
