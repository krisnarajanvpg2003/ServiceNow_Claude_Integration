import { MoonIcon, PlusIcon, SunIcon, TrashIcon } from './icons.jsx'

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  theme,
  onToggleTheme,
  open,
  onClose,
}) {
  return (
    <>
      <div className={`overlay ${open ? 'show' : ''}`} onClick={onClose} aria-hidden="true" />
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <button type="button" className="new-chat" onClick={onNew}>
          <PlusIcon /> New chat
        </button>

        <nav className="history" aria-label="Conversation history">
          {conversations.length === 0 ? (
            <p className="history-empty">Your conversations will appear here. They are stored only in this browser.</p>
          ) : (
            conversations.map((c) => (
              <div key={c.id} className={`history-item ${c.id === activeId ? 'active' : ''}`}>
                <button type="button" className="history-title" onClick={() => onSelect(c.id)} title={c.title}>
                  {c.title}
                </button>
                <button
                  type="button"
                  className="history-del"
                  onClick={(e) => {
                    e.stopPropagation()
                    onDelete(c.id)
                  }}
                  aria-label={`Delete conversation "${c.title}"`}
                  title="Delete"
                >
                  <TrashIcon />
                </button>
              </div>
            ))
          )}
        </nav>

        <div className="sidebar-foot">
          <button type="button" className="ghost-row" onClick={onToggleTheme}>
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </button>
        </div>
      </aside>
    </>
  )
}
