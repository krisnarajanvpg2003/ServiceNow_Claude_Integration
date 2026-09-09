import { useEffect, useRef, useState } from 'react'
import { ArrowUpIcon, ImageIcon, PaperclipIcon, PlusIcon, StopIcon, XIcon } from './icons.jsx'
import { uploadFile } from '../lib/api.js'

const IMAGE_ACCEPT = 'image/png,image/jpeg,image/gif,image/webp'
const FILE_ACCEPT = `${IMAGE_ACCEPT},.csv,.txt,.md,.json,.log,.xml,.yaml,.yml,.html,.js,.py,.sql`
const MAX_ATTACHMENTS = 5

function readableSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export default function Composer({ onSend, onStop, busy }) {
  const [value, setValue] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const [items, setItems] = useState([]) // { key, name, size, kind, id?, error?, uploading }
  const [dragging, setDragging] = useState(false)
  const ref = useRef(null)
  const fileInput = useRef(null)
  const menuRef = useRef(null)
  const accept = useRef(FILE_ACCEPT)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [value])

  // Close the menu on an outside click or Escape, as a menu should.
  useEffect(() => {
    if (!menuOpen) return undefined
    function onDocDown(e) {
      if (!menuRef.current?.contains(e.target)) setMenuOpen(false)
    }
    function onEsc(e) {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('mousedown', onDocDown)
    document.addEventListener('keydown', onEsc)
    return () => {
      document.removeEventListener('mousedown', onDocDown)
      document.removeEventListener('keydown', onEsc)
    }
  }, [menuOpen])

  async function attach(files) {
    const room = MAX_ATTACHMENTS - items.length
    const chosen = Array.from(files || []).slice(0, Math.max(room, 0))
    for (const file of chosen) {
      const key = `${file.name}-${file.size}-${Date.now()}-${Math.random()}`
      setItems((prev) => [
        ...prev,
        { key, name: file.name, size: file.size, kind: file.type.startsWith('image/') ? 'image' : 'text', uploading: true },
      ])
      try {
        const upload = await uploadFile(file)
        setItems((prev) =>
          prev.map((it) =>
            it.key === key ? { ...it, uploading: false, id: upload.id, kind: upload.kind, size: upload.bytes } : it,
          ),
        )
      } catch (err) {
        setItems((prev) =>
          prev.map((it) => (it.key === key ? { ...it, uploading: false, error: err?.message || 'Upload failed' } : it)),
        )
      }
    }
  }

  function pick(kind) {
    accept.current = kind === 'image' ? IMAGE_ACCEPT : FILE_ACCEPT
    setMenuOpen(false)
    // The accept attribute is applied before the dialog opens.
    requestAnimationFrame(() => fileInput.current?.click())
  }

  function remove(key) {
    setItems((prev) => prev.filter((it) => it.key !== key))
  }

  const ready = items.filter((it) => it.id && !it.error)
  const settling = items.some((it) => it.uploading)
  const canSend = !busy && !settling && (value.trim() || ready.length > 0)

  function submit() {
    if (!canSend) return
    onSend(value.trim(), ready.map((it) => ({ id: it.id, name: it.name, kind: it.kind })))
    setValue('')
    setItems([])
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  // A screenshot in the clipboard is the most common thing to attach here.
  function onPaste(e) {
    const files = Array.from(e.clipboardData?.files || [])
    if (files.length) {
      e.preventDefault()
      attach(files)
    }
  }

  return (
    <div className="composer-wrap">
      <form
        className={`composer${dragging ? ' is-dragging' : ''}`}
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
        onDragOver={(e) => {
          if (e.dataTransfer?.types?.includes('Files')) {
            e.preventDefault()
            setDragging(true)
          }
        }}
        onDragLeave={(e) => {
          if (e.currentTarget === e.target) setDragging(false)
        }}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          attach(e.dataTransfer?.files)
        }}
      >
        {items.length > 0 && (
          <ul className="attachments">
            {items.map((it) => (
              <li key={it.key} className={`attachment${it.error ? ' attachment-error' : ''}`}>
                <span className="attachment-thumb">
                  {it.kind === 'image' ? <ImageIcon /> : <PaperclipIcon />}
                </span>
                <span className="attachment-meta">
                  <span className="attachment-name">{it.name}</span>
                  <span className="attachment-sub">
                    {it.error ? it.error : it.uploading ? 'Uploading...' : readableSize(it.size)}
                  </span>
                </span>
                <button
                  type="button"
                  className="attachment-remove"
                  onClick={() => remove(it.key)}
                  aria-label={`Remove ${it.name}`}
                >
                  <XIcon />
                </button>
              </li>
            ))}
          </ul>
        )}

        <textarea
          ref={ref}
          rows={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          placeholder={
            items.length
              ? 'What should I do with these?'
              : 'Ask about incidents, catalog items, groups or users…'
          }
          aria-label="Message"
          autoFocus
        />

        <div className="composer-row">
          <div className="composer-add" ref={menuRef}>
            <button
              type="button"
              className={`icon-btn${menuOpen ? ' is-open' : ''}`}
              onClick={() => setMenuOpen((v) => !v)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label="Add an attachment"
              disabled={items.length >= MAX_ATTACHMENTS}
            >
              <PlusIcon />
            </button>
            {menuOpen && (
              <div className="add-menu" role="menu">
                <button type="button" role="menuitem" onClick={() => pick('file')}>
                  <PaperclipIcon />
                  <span>
                    Upload from computer
                    <small>Images, CSV, TXT, JSON, Markdown</small>
                  </span>
                </button>
                <button type="button" role="menuitem" onClick={() => pick('image')}>
                  <ImageIcon />
                  <span>
                    Add a photo or screenshot
                    <small>PNG, JPEG, GIF, WebP &mdash; or just paste one</small>
                  </span>
                </button>
              </div>
            )}
          </div>

          <span className="composer-note">
            {items.length >= MAX_ATTACHMENTS
              ? `${MAX_ATTACHMENTS} files is the limit`
              : 'Drop a file here, or paste a screenshot'}
          </span>

          {busy ? (
            <button type="button" className="send stop" onClick={onStop} aria-label="Stop request">
              <StopIcon />
            </button>
          ) : (
            <button type="submit" className="send" disabled={!canSend} aria-label="Send message">
              <ArrowUpIcon />
            </button>
          )}
        </div>

        <input
          ref={fileInput}
          type="file"
          multiple
          accept={accept.current}
          hidden
          onChange={(e) => {
            attach(e.target.files)
            e.target.value = ''
          }}
        />
      </form>
    </div>
  )
}
