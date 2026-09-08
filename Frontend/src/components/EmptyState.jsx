const SUGGESTIONS = [
  { title: 'Recent incidents', text: 'Show me the 5 most recent incidents' },
  { title: 'By month', text: 'Incidents created in June 2025' },
  { title: 'Last 7 days', text: 'Incidents updated in the last 7 days' },
  { title: 'Oldest first', text: 'Show the 5 oldest incidents' },
  { title: 'One incident', text: 'Get incident INC0015571' },
  { title: 'Search incidents', text: 'Find closed incidents about wifi' },
  { title: 'Catalog search', text: 'List catalog items about laptop' },
  { title: 'Catalog health', text: 'Give me catalog optimization recommendations for inactive items and low usage' },
  { title: 'Groups', text: 'List groups matching network' },
  { title: 'User lookup', text: 'Who is svc.claudecode.readonly?' },
]

export default function EmptyState({ onPick }) {
  return (
    <div className="empty">
      <div className="empty-inner">
        <h1>How can I help with ServiceNow today?</h1>
        <p className="dim">Ask in plain English. Every answer shows the exact API call behind it.</p>
        <div className="suggestions">
          {SUGGESTIONS.map((s) => (
            <button key={s.text} type="button" className="suggestion" onClick={() => onPick(s.text)}>
              <span className="suggestion-title">{s.title}</span>
              <span className="suggestion-text">{s.text}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
