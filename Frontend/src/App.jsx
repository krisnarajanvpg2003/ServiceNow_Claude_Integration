import { useCallback, useEffect, useRef, useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import ChatWindow from './components/ChatWindow.jsx'
import Composer from './components/Composer.jsx'
import { MenuIcon } from './components/icons.jsx'
import { ApiError, BACKEND_HINT, buildUrl, callApi, getChatStatus, streamChat } from './lib/api.js'
import { parseIntent } from './lib/intent.js'
import { summarize } from './lib/summarize.js'
import {
  loadConversations,
  saveConversations,
  loadTheme,
  saveTheme,
  loadAiMode,
  saveAiMode,
  uid,
} from './lib/storage.js'

function makeTitle(text) {
  const t = text.replace(/\s+/g, ' ').trim()
  return t.length > 42 ? `${t.slice(0, 41).trimEnd()}…` : t
}

function friendlyError(err) {
  if (!(err instanceof ApiError)) return `Something went wrong: ${err?.message || String(err)}`
  if (err.unreachable || err.status === 0) {
    return `I couldn't reach the ServiceNow REST API. Start the backend from the \`servicenow-mcp\` folder with \`.venv\\Scripts\\python.exe scripts\\rest_api.py\` so it listens on ${BACKEND_HINT}, then try again.`
  }
  if (err.status === 400) return `The API rejected that request as invalid: ${err.message}`
  if (err.status === 404) return 'The API has no endpoint for that path. Type **help** to see what I can call.'
  return `ServiceNow couldn't complete that request: ${err.message}`
}

export default function App() {
  const [conversations, setConversations] = useState(loadConversations)
  const [activeId, setActiveId] = useState(null)
  const [theme, setTheme] = useState(loadTheme)
  const [aiMode, setAiMode] = useState(loadAiMode) // Claude answers in prose
  const [chatStatus, setChatStatus] = useState(null)
  const [backendUp, setBackendUp] = useState(null) // null = still checking
  const [busy, setBusy] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const abortRef = useRef(null)
  const conversationsRef = useRef(conversations)
  conversationsRef.current = conversations

  useEffect(() => {
    saveConversations(conversations)
  }, [conversations])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    saveTheme(theme)
  }, [theme])

  useEffect(() => {
    saveAiMode(aiMode)
  }, [aiMode])

  /** Poll the backend so a stopped server shows in the header instead of surfacing as HTTP 500. */
  useEffect(() => {
    let cancelled = false
    const check = async () => {
      try {
        const { data } = await callApi('/health')
        if (!cancelled) setBackendUp(Boolean(data?.ok))
      } catch {
        if (!cancelled) setBackendUp(false)
      }
    }
    check()
    const timer = setInterval(check, 15000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [])

  /** Ask the backend whether Claude mode can be offered; the switch disables itself otherwise. */
  useEffect(() => {
    let cancelled = false
    getChatStatus()
      .then((s) => !cancelled && setChatStatus(s))
      .catch(() =>
        !cancelled &&
        setChatStatus({ available: false, reason: 'Backend not reachable.' }),
      )
    return () => {
      cancelled = true
    }
  }, [])

  const active = conversations.find((c) => c.id === activeId) || null

  const patchConversation = useCallback((id, fn) => {
    setConversations((prev) => prev.map((c) => (c.id === id ? fn(c) : c)))
  }, [])

  const appendMessage = useCallback(
    (id, message) =>
      patchConversation(id, (c) => ({ ...c, messages: [...c.messages, message], updatedAt: Date.now() })),
    [patchConversation],
  )

  const replaceMessage = useCallback(
    (id, messageId, fn) =>
      patchConversation(id, (c) => ({ ...c, messages: c.messages.map((m) => (m.id === messageId ? fn(m) : m)) })),
    [patchConversation],
  )

  /**
   * The browser maps the question to one GET against the REST API and renders
   * the payload. The backend calls the ServiceNow REST API directly.
   */
  const sendWithRules = useCallback(
    async (convId, replyId, text) => {
      const plan = parseIntent(text)
      if (plan.kind === 'local') {
        appendMessage(convId, { id: replyId, role: 'assistant', text: plan.text, ts: Date.now() })
        return
      }
      const params = { ...plan.params }
      const url = buildUrl(plan.path, params)
      appendMessage(convId, {
        id: replyId,
        role: 'assistant',
        pending: true,
        request: { method: 'GET', url },
        ts: Date.now(),
      })
      setBusy(true)
      const controller = new AbortController()
      abortRef.current = controller
      try {
        const res = await callApi(plan.path, params, { signal: controller.signal })
        const payload = res.data
        replaceMessage(convId, replyId, (m) => ({
          ...m,
          pending: false,
          text: summarize(plan, payload),
          tool: payload?.tool || plan.tool,
          payload,
          fields: plan.meta?.fields || [],
          request: { ...m.request, status: res.status, elapsedMs: payload?.elapsed_ms ?? res.elapsedMs },
        }))
      } catch (err) {
        if (err?.name === 'AbortError') {
          replaceMessage(convId, replyId, (m) => ({ ...m, pending: false, cancelled: true, text: 'Request cancelled.' }))
        } else {
          replaceMessage(convId, replyId, (m) => ({
            ...m,
            pending: false,
            text: friendlyError(err),
            error: { message: err?.message, status: err?.status ?? 0, payload: err?.payload ?? null },
            request: { ...m.request, status: err?.status ?? 0 },
          }))
        }
      } finally {
        setBusy(false)
        abortRef.current = null
      }
    },
    [appendMessage, replaceMessage],
  )

  /**
   * Claude mode: POST /chat and stream the answer. Claude runs the read-only
   * snow.py CLI against the same REST API; each command it runs is shown.
   */
  const sendWithClaude = useCallback(
    async (convId, replyId, text) => {
      const sessionId = conversationsRef.current.find((c) => c.id === convId)?.aiSessionId || null
      appendMessage(convId, {
        id: replyId,
        role: 'assistant',
        mode: 'ai',
        pending: true,
        steps: [],
        text: '',
        request: { method: 'POST', url: '/chat' },
        ts: Date.now(),
      })
      setBusy(true)
      const controller = new AbortController()
      abortRef.current = controller
      const patch = (fn) => replaceMessage(convId, replyId, fn)

      try {
        await streamChat({
          message: text,
          sessionId,
          signal: controller.signal,
          onEvent: (ev) => {
            if (ev.type === 'status') {
              patch((m) => ({ ...m, steps: [...m.steps, { kind: 'status', text: ev.text }] }))
            } else if (ev.type === 'tool_use') {
              patch((m) => ({
                ...m,
                steps: [
                  ...m.steps,
                  { kind: 'tool', id: ev.id, command: ev.input?.command || '', status: 'running' },
                ],
              }))
            } else if (ev.type === 'tool_result') {
              patch((m) => ({
                ...m,
                steps: m.steps.map((s) =>
                  s.kind === 'tool' && s.id === ev.id
                    ? { ...s, status: ev.ok ? 'ok' : 'error', result: ev.result }
                    : s,
                ),
              }))
            } else if (ev.type === 'text') {
              patch((m) => ({ ...m, text: ev.text }))
            } else if (ev.type === 'done') {
              patch((m) => ({
                ...m,
                pending: false,
                text: ev.reply || m.text || 'The agent finished without a written answer.',
                steps: m.steps.filter((s) => s.kind !== 'status'),
                ai: { model: ev.model, costUsd: ev.cost_usd, numTurns: ev.num_turns },
                request: { ...m.request, status: ev.is_error ? 502 : 200, elapsedMs: ev.elapsed_ms },
              }))
              if (ev.session_id) patchConversation(convId, (c) => ({ ...c, aiSessionId: ev.session_id }))
            } else if (ev.type === 'error') {
              patch((m) => ({
                ...m,
                pending: false,
                text: `Claude couldn't complete that request: ${ev.message}`,
                error: { message: ev.message },
                request: { ...m.request, status: 502 },
              }))
            }
          },
        })
        patch((m) => (m.pending ? { ...m, pending: false, text: m.text || 'The stream ended without an answer.' } : m))
      } catch (err) {
        if (err?.name === 'AbortError') {
          patch((m) => ({ ...m, pending: false, cancelled: true, text: 'Request cancelled.' }))
        } else {
          patch((m) => ({
            ...m,
            pending: false,
            text: friendlyError(err),
            error: { message: err?.message, status: err?.status ?? 0 },
            request: { ...m.request, status: err?.status ?? 0 },
          }))
        }
      } finally {
        setBusy(false)
        abortRef.current = null
      }
    },
    [appendMessage, replaceMessage, patchConversation],
  )

  const send = useCallback(
    async (raw) => {
      const text = (raw || '').trim()
      if (!text || busy) return

      let convId = activeId
      const userMessage = { id: uid(), role: 'user', text, ts: Date.now() }
      if (!convId) {
        convId = uid()
        setConversations((prev) => [
          { id: convId, title: makeTitle(text), createdAt: Date.now(), updatedAt: Date.now(), messages: [userMessage] },
          ...prev,
        ])
        setActiveId(convId)
      } else {
        appendMessage(convId, userMessage)
      }

      const replyId = uid()
      // Raw API paths and "help" stay local even in Claude mode.
      const useClaude =
        aiMode && chatStatus?.available && !text.startsWith('/') && !/^\s*help\b/i.test(text)
      if (useClaude) await sendWithClaude(convId, replyId, text)
      else await sendWithRules(convId, replyId, text)
    },
    [activeId, busy, aiMode, chatStatus, appendMessage, sendWithClaude, sendWithRules],
  )

  const stop = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const newChat = useCallback(() => {
    setActiveId(null)
    setSidebarOpen(false)
  }, [])

  const selectChat = useCallback((id) => {
    setActiveId(id)
    setSidebarOpen(false)
  }, [])

  const deleteChat = useCallback(
    (id) => {
      setConversations((prev) => prev.filter((c) => c.id !== id))
      if (id === activeId) setActiveId(null)
    },
    [activeId],
  )

  const aiAvailable = Boolean(chatStatus?.available)
  const aiTitle = aiAvailable
    ? `Claude (${chatStatus.model}) reads ServiceNow with snow.py and answers in plain English`
    : chatStatus?.reason || 'Checking the backend...'

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={selectChat}
        onNew={newChat}
        onDelete={deleteChat}
        theme={theme}
        onToggleTheme={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <main className="main">
        <header className="topbar">
          <button type="button" className="icon-btn hamburger" onClick={() => setSidebarOpen(true)} aria-label="Open menu">
            <MenuIcon />
          </button>
          <div className="topbar-title">ServiceNow Assistant</div>
          <label className={`ai-toggle ${aiAvailable ? '' : 'disabled'}`} title={aiTitle}>
            <input
              type="checkbox"
              checked={aiMode && aiAvailable}
              disabled={!aiAvailable}
              onChange={(e) => setAiMode(e.target.checked)}
            />
            <span className="ai-toggle-track" aria-hidden="true" />
            <span className="ai-toggle-label">Claude</span>
          </label>
          <div
            className="direct-api-badge"
            title={
              backendUp === false
                ? `The backend is not answering on ${BACKEND_HINT}. Start it with: .venv\Scripts\python.exe scripts\rest_api.py`
                : 'Calls the ServiceNow REST API directly from the backend. No MCP anywhere.'
            }
          >
            <span
              className={`dot ${backendUp === false ? 'dot-bad' : backendUp ? 'dot-ok' : ''}`}
              aria-hidden="true"
            />
            <span>{backendUp === false ? 'Backend offline' : 'ServiceNow REST API'}</span>
          </div>
        </header>
        <div className="accent-rule" aria-hidden="true" />
        <ChatWindow messages={active?.messages || []} onSuggestion={send} onFollowUp={send} />
        <Composer onSend={send} onStop={stop} busy={busy} />
      </main>
    </div>
  )
}
