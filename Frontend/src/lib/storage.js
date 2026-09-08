// Conversation history and theme live in localStorage only. Nothing here is
// sent anywhere; the backend never sees chat history.

const CONVERSATIONS_KEY = 'snow-chat.conversations.v1'
const THEME_KEY = 'snow-chat.theme'
const MAX_CONVERSATIONS = 30

export function loadConversations() {
  try {
    const raw = localStorage.getItem(CONVERSATIONS_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveConversations(list) {
  try {
    localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(list.slice(0, MAX_CONVERSATIONS)))
  } catch {
    /* storage may be full or disabled; the UI still works for this session */
  }
}

export function loadTheme() {
  try {
    const saved = localStorage.getItem(THEME_KEY)
    if (saved === 'light' || saved === 'dark') return saved
  } catch {
    /* ignore */
  }
  // Default to the light brand theme; the sidebar toggle switches to dark mode.
  return 'light'
}

export function saveTheme(theme) {
  try {
    localStorage.setItem(THEME_KEY, theme)
  } catch {
    /* ignore */
  }
}

const AI_MODE_KEY = 'snow-chat.ai-mode'

export function uid() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

const AI_KEY = 'snow.aiMode'

export function loadAiMode() {
  try {
    return localStorage.getItem(AI_KEY) === 'on'
  } catch {
    return false
  }
}

export function saveAiMode(on) {
  try {
    localStorage.setItem(AI_KEY, on ? 'on' : 'off')
  } catch {
    // storage unavailable (private window); the toggle still works for this session
  }
}
