// Thin client for the local ServiceNow REST API.
//
// Every request goes to API_BASE ('/api' by default). The Vite dev/preview
// server proxies /api/* to the backend (see vite.config.js), so the browser
// only ever talks to its own origin. No ServiceNow or Anthropic credentials
// exist in this app: the backend holds them.

const API_BASE = (import.meta.env.VITE_API_BASE || '/api').replace(/\/+$/, '')
export const BACKEND_HINT = 'http://127.0.0.1:8095'

export class ApiError extends Error {
  constructor(message, { status = 0, payload = null, unreachable = false } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
    // true when the backend could not be reached at all
    this.unreachable = unreachable
  }
}

/** Build a relative URL like `/incidents?limit=5&q=wifi`, skipping empty params. */
export function buildUrl(path, params = {}) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const qs = search.toString()
  return qs ? `${path}?${qs}` : path
}

function unreachable() {
  return new ApiError(`Could not reach the ServiceNow REST API at ${API_BASE} (backend expected on ${BACKEND_HINT}).`, { status: 0, unreachable: true })
}

async function parseBody(response) {
  const text = await response.text()
  try {
    return { data: text ? JSON.parse(text) : null, isJson: true }
  } catch {
    return { data: { raw: text }, isJson: false }
  }
}

function errorFrom(response, data, isJson) {
  const message = data && (data.error || data.detail || data.result?.message || data.message)

  // A 5xx that carries no explanation did not come from our backend: the dev
  // proxy answers this way when it cannot reach it at all (an empty body, or
  // plain text). Say so, rather than blaming ServiceNow for a request it never
  // received.
  if (response.status >= 500 && (!isJson || !message)) {
    return new ApiError(
      `Could not reach the ServiceNow REST API (HTTP ${response.status}). Is the backend running on ${BACKEND_HINT}?`,
      { status: response.status, payload: data, unreachable: true },
    )
  }

  return new ApiError(String(message || `HTTP ${response.status}`), {
    status: response.status,
    payload: data,
  })
}

/**
 * GET one backend endpoint. Resolves with `{ data, status, elapsedMs, url }`
 * or rejects with an ApiError carrying the backend's JSON payload when there is one.
 */
export async function callApi(path, params = {}, { signal } = {}) {
  const url = buildUrl(path, params)
  const started = performance.now()

  let response
  try {
    response = await fetch(`${API_BASE}${url}`, { signal, headers: { Accept: 'application/json' } })
  } catch (err) {
    if (err?.name === 'AbortError') throw err
    throw unreachable()
  }

  const { data, isJson } = await parseBody(response)
  const elapsedMs = Math.round(performance.now() - started)
  if (!response.ok || (data && data.ok === false)) throw errorFrom(response, data, isJson)
  return { data, status: response.status, elapsedMs, url }
}

/** GET /chat/status: whether the Claude-backed chat can run, and with what model. */
export async function getChatStatus({ signal } = {}) {
  const { data } = await callApi('/chat/status', {}, { signal })
  return data
}

/**
 * POST /chat and consume the server-sent event stream. `onEvent` receives each
 * decoded event: status, tool_use, tool_result, text, done, error.
 */
export async function streamChat({ message, sessionId = null, signal, onEvent }) {
  let response
  try {
    response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ message, session_id: sessionId }),
      signal,
    })
  } catch (err) {
    if (err?.name === 'AbortError') throw err
    throw unreachable()
  }

  if (!response.ok) {
    const { data, isJson } = await parseBody(response)
    throw errorFrom(response, data, isJson)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    // SSE frames are separated by a blank line.
    const frames = buffer.split('\n\n')
    buffer = frames.pop() || ''
    for (const frame of frames) {
      const line = frame.split('\n').find((l) => l.startsWith('data: '))
      if (!line) continue
      try {
        onEvent(JSON.parse(line.slice(6)))
      } catch {
        // ignore a malformed frame rather than killing the stream
      }
    }
  }
}
