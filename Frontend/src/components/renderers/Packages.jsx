import { Badge, EmptyNote } from './shared.jsx'

export default function Packages({ result }) {
  if (!result || !result.current_package) return <EmptyNote>No package information returned.</EmptyNote>
  const available = result.available_packages || []
  return (
    <article className="card">
      <div className="card-head">
        <div>
          <div className="eyebrow">Loaded tool package</div>
          <div className="card-title">{result.current_package}</div>
        </div>
        <Badge tone="ok">Active</Badge>
      </div>
      {result.message && <p className="dim small">{result.message}</p>}
      <div className="chips">
        {available.map((p) => (
          <span key={p} className={`chip ${p === result.current_package ? 'chip-active' : ''}`}>
            {p}
          </span>
        ))}
      </div>
    </article>
  )
}
