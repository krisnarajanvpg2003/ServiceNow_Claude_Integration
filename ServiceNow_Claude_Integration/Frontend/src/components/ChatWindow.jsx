import { useEffect, useRef } from 'react'
import Message from './Message.jsx'
import EmptyState from './EmptyState.jsx'

export default function ChatWindow({ messages, onSuggestion, onFollowUp }) {
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages])

  if (!messages.length) return <EmptyState onPick={onSuggestion} />

  return (
    <div className="chat-scroll">
      <div className="chat-col">
        {messages.map((m) => (
          <Message key={m.id} message={m} onFollowUp={onFollowUp} />
        ))}
        <div ref={endRef} />
      </div>
    </div>
  )
}
