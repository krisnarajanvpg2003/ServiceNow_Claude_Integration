import { ActiveBadge, Badge, DataTable, EmptyNote, KV, Mono } from './shared.jsx'
import { dv, isTrue, stripHtml } from '../../lib/format.js'

export default function CatalogItemDetail({ result }) {
  const item = result?.data ?? result?.item ?? result
  if (!item || (!item.sys_id && !item.name)) {
    return <EmptyNote>{result?.message || 'Catalog item not found.'}</EmptyNote>
  }

  const variables = item.variables || []
  const description = stripHtml(dv(item.description))
  const short = stripHtml(dv(item.short_description))

  const columns = [
    { key: 'label', label: 'Label', grow: true, render: (v) => dv(v.label) || dv(v.name) },
    { key: 'name', label: 'Name', render: (v) => <Mono>{dv(v.name)}</Mono> },
    { key: 'type', label: 'Type' },
    {
      key: 'mandatory',
      label: 'Mandatory',
      render: (v) => (isTrue(v.mandatory) ? <Badge tone="warn">Required</Badge> : <span className="dim">Optional</span>),
    },
    { key: 'default_value', label: 'Default' },
  ]

  return (
    <article className="card">
      <div className="card-head">
        <div>
          <div className="eyebrow">Catalog item</div>
          <div className="card-title">{dv(item.name)}</div>
        </div>
        <div className="badges">
          <ActiveBadge value={item.active} />
          {item.price && item.price !== '$0.00' && <Badge tone="info">{item.price}</Badge>}
        </div>
      </div>
      {short && <p className="prose">{short}</p>}
      {description && description !== short && <p className="prose dim">{description}</p>}
      <KV
        rows={[
          ['Category', dv(item.category)],
          ['Delivery time', dv(item.delivery_time)],
          ['Availability', dv(item.availability)],
          ['Order', dv(item.order)],
          ['sys_id', item.sys_id ? <Mono>{item.sys_id}</Mono> : ''],
        ]}
      />
      <div className="subhead">Variables ({variables.length})</div>
      <DataTable
        columns={columns}
        rows={variables}
        rowKey={(v) => v.sys_id || v.name}
        empty="This item has no variables."
      />
    </article>
  )
}
