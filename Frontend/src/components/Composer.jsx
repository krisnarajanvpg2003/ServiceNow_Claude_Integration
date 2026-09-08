import { useEffect, useRef, useState } from 'react'
import { ArrowUpIcon, StopIcon } from './icons.jsx'

export default function Composer({ onSend, onStop, busy }) {
  const [value, setValue] = useState('')
  const ref = useRef(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [value])

  function submit() {
    const text = value.trim()
    if (!text || busy) return
    onSend(text)
    setValue('')
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="composer-wrap">
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <textarea
          ref={ref}
          rows={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask about incidents, catalog items, groups or users…"
          aria-label="Message"
          autoFocus
        />
        {busy ? (
          <button type="button" className="send stop" onClick={onStop} aria-label="Stop request">
            <StopIcon />
          </button>
        ) : (
          <button type="submit" className="send" disabled={!value.trim()} aria-label="Send message">
            <ArrowUpIcon />
          </button>
        )}
      </form>
    </div>
  )
}
