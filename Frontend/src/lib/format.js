// Small, dependency-free helpers for turning ServiceNow values into text.

/** ServiceNow returns either plain strings or `{ display_value, link }` objects. */
export function dv(value) {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') {
    if ('display_value' in value) return value.display_value ?? ''
    if ('value' in value) return String(value.value ?? '')
    return ''
  }
  return String(value)
}

export function isTrue(value) {
  return value === true || String(value).toLowerCase() === 'true'
}

export function truncate(text, max = 120) {
  const t = (text ?? '').toString().trim()
  return t.length > max ? `${t.slice(0, max - 1).trimEnd()}…` : t
}

export function plural(n, word, pluralWord) {
  return `${n} ${n === 1 ? word : pluralWord || `${word}s`}`
}

export function formatMs(ms) {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return ''
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`
}

export function initials(name) {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '?'
  const first = parts[0][0]
  const last = parts.length > 1 ? parts[parts.length - 1][0] : ''
  return (first + last).toUpperCase()
}

/** Catalog descriptions can contain HTML; render them as plain text instead of injecting markup. */
export function stripHtml(html) {
  if (!html) return ''
  if (typeof DOMParser === 'undefined') return String(html).replace(/<[^>]+>/g, '')
  const doc = new DOMParser().parseFromString(String(html), 'text/html')
  return (doc.body.textContent || '').replace(/\s+\n/g, '\n').trim()
}

export function priorityTone(priority) {
  const n = parseInt(String(priority ?? ''), 10)
  if (n === 1) return 'critical'
  if (n === 2) return 'high'
  if (n === 3) return 'moderate'
  if (n === 4 || n === 5) return 'low'
  return 'neutral'
}

export function stateTone(state) {
  const v = String(state ?? '').toLowerCase()
  if (!v) return 'neutral'
  if (/new/.test(v)) return 'info'
  if (/progress|active|assigned|work/.test(v)) return 'warn'
  if (/hold|pending|await/.test(v)) return 'muted'
  if (/resolved|closed|complete|done/.test(v)) return 'ok'
  if (/cancel/.test(v)) return 'muted'
  return 'neutral'
}

export function safeHost(url) {
  try {
    return new URL(url).hostname
  } catch {
    return ''
  }
}
