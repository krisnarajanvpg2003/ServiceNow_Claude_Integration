import { KV } from './shared.jsx'

export default function HealthCard({ result }) {
  const ok = Boolean(result?.ok)
  return (
    <article className="card health">
      <span className={`dot dot-lg ${ok ? 'dot-ok' : 'dot-bad'}`} aria-hidden="true" />
      <div>
        <div className="card-title">{ok ? 'Connected to ServiceNow' : 'ServiceNow unreachable'}</div>
        <KV
          rows={[
            ['Instance', result?.instance],
            ['ServiceNow reply', result?.servicenow],
            ['Tools exposed', result?.tools_exposed != null ? String(result.tools_exposed) : ''],
          ]}
        />
      </div>
    </article>
  )
}
