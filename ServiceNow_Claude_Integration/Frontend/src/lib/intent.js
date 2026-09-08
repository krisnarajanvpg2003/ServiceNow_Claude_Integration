// Rule-based intent parser: maps a natural-language question to one of the
// read-only backend endpoints. It runs entirely in the browser, needs no API
// key, and is deterministic, so every question is traceable to one GET request
// (shown under each answer).
//
// Returns either
//   { kind: 'api', path, params, tool, meta }   -> call the backend
//   { kind: 'local', text }                     -> answer locally (help / fallback)

const INC_RE = /\bINC\s?(\d{4,})\b/i
const SYS_ID_RE = /\b[0-9a-f]{32}\b/i
const EMAIL_RE = /\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b/i

const NOUN = {
  incident: /\b(incidents?|tickets?|issues?|problems?|outages?|cases?)\b/i,
  catalog: /\b(catalog(?:ue)?|items?|services?|offerings?|products?|requests?)\b/i,
  category: /\bcategor(?:y|ies)\b/i,
  group: /\b(groups?|teams?)\b/i,
  user: /\b(users?|username|people|person|employees?|accounts?|profiles?|who\s*is|who's|whois)\b/i,
  recs:
    /\b(recommend\w*|optimi[sz]\w*|inactive|low[\s-]?usage|unused|abandon\w*|slow|fulfil\w*|description quality|poor descriptions?|clean\s?up)\b/i,
  packages:
    /\b(packages?|tool\s?packages?|which tools|what tools|tools? (?:are |is )?(?:loaded|available|exposed|enabled)|capabilities)\b/i,
  health:
    /\b(health|healthy|status|ping|alive|online|reachable|connected|connection|is (?:the )?(?:api|backend|server) (?:up|running|working))\b/i,
  help: /^\s*(\/?help|\?|what can you do|what can i ask|commands?|how (?:do|can) i use (?:this|you))\b/i,
}

// Field aliases for "INC0015548 show me the short description and description".
// Longest phrases are matched first so "short description" wins over "description".
// Each entry is [phrase pattern, incident field key].
const INCIDENT_FIELDS = [
  ['short description', 'short_description'],
  ['short desc', 'short_description'],
  ['description', 'description'],
  ['long description', 'description'],
  ['additional comments', 'comments'],
  ['comments', 'comments'],
  ['work notes', 'work_notes'],
  ['notes', 'work_notes'],
  ['close notes', 'close_notes'],
  ['close code', 'close_code'],
  ['resolution notes', 'close_notes'],
  ['caller', 'caller_id'],
  ['reported by', 'caller_id'],
  ['requested by', 'caller_id'],
  ['opened by', 'opened_by'],
  ['opened at', 'opened_at'],
  ['opened', 'opened_at'],
  ['created by', 'sys_created_by'],
  ['created on', 'created_on'],
  ['created', 'created_on'],
  ['updated by', 'sys_updated_by'],
  ['updated on', 'updated_on'],
  ['updated', 'updated_on'],
  ['last updated', 'updated_on'],
  ['resolved at', 'resolved_at'],
  ['resolved by', 'resolved_by'],
  ['resolved', 'resolved_at'],
  ['closed at', 'closed_at'],
  ['closed by', 'closed_by'],
  ['closed', 'closed_at'],
  ['due date', 'due_date'],
  ['sla due', 'sla_due'],
  ['assignment group', 'assignment_group'],
  ['assigned to', 'assigned_to'],
  ['assignee', 'assigned_to'],
  ['owner', 'assigned_to'],
  ['subcategory', 'subcategory'],
  ['category', 'category'],
  ['incident state', 'incident_state'],
  ['state', 'state'],
  ['status', 'state'],
  ['priority', 'priority'],
  ['impact', 'impact'],
  ['urgency', 'urgency'],
  ['severity', 'severity'],
  ['approval', 'approval'],
  ['escalation', 'escalation'],
  ['active', 'active'],
  ['channel', 'contact_type'],
  ['contact type', 'contact_type'],
  ['configuration item', 'cmdb_ci'],
  ['service offering', 'service_offering'],
  ['business service', 'business_service'],
  ['service', 'business_service'],
  ['number', 'number'],
  ['sys id', 'sys_id'],
  ['sys_id', 'sys_id'],
]

// Sorted longest-first so the greedy pass masks the biggest phrase it can.
const FIELD_PATTERNS = INCIDENT_FIELDS.map(([phrase, key]) => [
  new RegExp(`\\b${phrase.replace(/[_\s]+/g, '[\\s_]+')}\\b`, 'gi'),
  key,
]).sort((a, b) => b[0].source.length - a[0].source.length)

/**
 * Field names the question asked for, in the order they were written.
 * Returns [] when the question names none, meaning "show everything".
 */
export function extractIncidentFields(text) {
  let masked = text
  const hits = []
  for (const [re, key] of FIELD_PATTERNS) {
    re.lastIndex = 0
    let m
    while ((m = re.exec(masked)) !== null) {
      hits.push({ index: m.index, key })
      // Blank out the span so a shorter alias cannot match inside it.
      masked = masked.slice(0, m.index) + ' '.repeat(m[0].length) + masked.slice(m.index + m[0].length)
      re.lastIndex = m.index + m[0].length
    }
  }
  const ordered = hits.sort((a, b) => a.index - b.index).map((h) => h.key)
  return [...new Set(ordered)]
}

// Requests to change something or send something. This integration only reads,
// so these are answered honestly instead of being matched to the nearest GET.
const WRITE_ACTIONS = [
  [/\b(send|forward|mail)\b[^.]*\bemail\b|\bemail\b[^.]*\b(to|it|this|the details)\b/i,
   'send email'],
  [/\bcreate\b[^.]*\b(script|report|email|incident|ticket|change|request|task|user|article)\b/i,
   'create things'],
  [/\b(update|modify|edit|change|rename|reassign)\b[^.]*\b(incident|ticket|state|priority|record|assignment)\b/i,
   'update records'],
  [/\b(resolve|close|reopen|cancel|delete|remove)\b[^.]*\b(incident|ticket|change|request|record|INC\d+)\b/i,
   'resolve or close records'],
  [/\b(resolve|close|reopen|delete)\b\s+INC/i, 'resolve or close records'],
  // A record number next to a change verb: "INC0015548 change the short description to ..."
  [/\bINC\s?\d{4,}\b[^.]*\b(change|update|edit|modify|set|rename)\b|\b(change|update|edit|modify|set|rename)\b[^.]*\bINC\s?\d{4,}\b/i,
   'update records'],
  [/\bassign\b[^.]*\b(to|incident|ticket)\b/i, 'assign records'],
  [/\badd\b[^.]*\b(comment|work note|note)\b/i, 'add comments'],
]

const READ_ONLY_TEXT = [
  'Keyword mode only reads — it maps your question to a single GET request, so it cannot %s.',
  '',
  '**Turn on the Claude switch** (top right) and ask again. Claude can create and update',
  'records when the backend is started with `--allow-write`, and it shows you the command',
  'it runs before anything changes.',
  '',
  'In keyword mode I can still show you the data: `INC0015548` for the full record, or',
  '`INC0015548 short description and caller` for named fields.',
].join('\n')

/** The write/send action a question is asking for, or null when it only reads. */
export function detectWriteAction(text) {
  for (const [re, label] of WRITE_ACTIONS) {
    if (re.test(text)) return label
  }
  return null
}

const STATES = [
  { re: /\bnew\b/i, code: '1', label: 'New' },
  { re: /\b(?:in[\s-]?progress|active|wip|being worked)\b/i, code: '2', label: 'In Progress' },
  { re: /\b(?:on[\s-]?hold|pending|awaiting)\b/i, code: '3', label: 'On Hold' },
  { re: /\bresolved\b/i, code: '6', label: 'Resolved' },
  { re: /\bclosed\b/i, code: '7', label: 'Closed' },
  { re: /\bcancell?ed\b/i, code: '8', label: 'Canceled' },
]

const REC_TYPES = [
  { re: /\binactive\b/i, type: 'inactive_items' },
  { re: /\b(?:low[\s-]?usage|unused|rarely|seldom|least (?:used|ordered))\b/i, type: 'low_usage' },
  { re: /\babandon/i, type: 'high_abandonment' },
  { re: /\b(?:slow|fulfil)/i, type: 'slow_fulfillment' },
  { re: /\bdescription/i, type: 'description_quality' },
]

const STOP = new Set(
  (
    'show me all the a an list get find fetch give display please my some top first last latest newest recent most ' +
    'of in from to for and with about any every current open unresolved outstanding tickets ticket incidents incident ' +
    'items item catalog catalogue groups group teams team users user categories category results records what are is ' +
    'there can you do i we have has which who whats number details detail info information on it that this these those ' +
    'see want need look up lookup search query by sorted order recommendations recommendation how many count assignment ' +
    'service servicenow snow available existing our your their oldest newest earliest updated created modified changed ' +
    'between since before after until till during within past previous ago today yesterday week month year days weeks ' +
    'months years hours priority'
  ).split(' '),
)

const HELP_TEXT = [
  'I answer read-only questions about your ServiceNow instance through the local MCP API. Try:',
  '- **Incidents**: "show the 5 most recent incidents", "closed incidents about wifi", "get INC0015571"',
  '- **Dates**: "incidents created in the last 7 days", "incidents from June 2025", "incidents updated since 2025-06-01", "incidents before 2024"',
  '- **Sorting**: "oldest incidents", "recently updated incidents", "incidents by priority"',
  '- **Catalog**: "catalog items about laptop", "show catalog item <sys_id>", "list catalog categories"',
  '- **Optimization**: "catalog recommendations for inactive items and low usage"',
  '- **Groups**: "list groups matching network"',
  '- **Users**: "who is svc.claudecode.readonly", "user by email someone@example.com"',
  '- **System**: "health", "which tool packages are loaded"',
  'You can also type a raw API path such as `/incidents?limit=3&state=7&sort=updated`.',
].join('\n')

const FALLBACK_TEXT =
  "I'm not sure which ServiceNow data you're after. I can look up **incidents**, **catalog items**, **catalog categories**, **optimization recommendations**, **groups** and **users**. Try \"show recent incidents\" or type **help** for examples."

const ALLOWED_PATHS =
  '`/`, `/health`, `/incidents`, `/incidents/{number}`, `/catalog/items`, `/catalog/items/{sys_id}`, `/catalog/categories`, `/catalog/recommendations`, `/groups`, `/users/{username}`, `/users/by-email/{email}`, `/packages`'

export function parseIntent(input, now = new Date()) {
  const text = (input || '').trim()
  if (!text) return local(FALLBACK_TEXT)

  if (NOUN.help.test(text)) return local(HELP_TEXT)

  // "email this to me", "create a change" - say what this can and cannot do.
  const writeAction = detectWriteAction(text)
  if (writeAction) return local(READ_ONLY_TEXT.replace('%s', writeAction))

  // Power-user mode: a raw API path such as /incidents?limit=3
  if (text.startsWith('/')) return parseRawPath(text)

  const inc = text.match(INC_RE)
  if (inc) {
    const number = `INC${inc[1]}`
    const fields = extractIncidentFields(text.replace(INC_RE, ' '))
    return api(`/incidents/${encodeURIComponent(number)}`, {}, 'get_incident_by_number', { number, fields })
  }

  const sysId = text.match(SYS_ID_RE)
  if (sysId) {
    return api(`/catalog/items/${sysId[0].toLowerCase()}`, {}, 'get_catalog_item', { sysId: sysId[0] })
  }

  const email = text.match(EMAIL_RE)
  if (email) {
    return api(`/users/by-email/${encodeURIComponent(email[0])}`, {}, 'get_user', { email: email[0] })
  }

  const hasDomainNoun =
    NOUN.incident.test(text) ||
    NOUN.catalog.test(text) ||
    NOUN.group.test(text) ||
    NOUN.user.test(text) ||
    NOUN.category.test(text)

  if (NOUN.packages.test(text)) return api('/packages', {}, 'list_tool_packages')
  if (NOUN.health.test(text) && !hasDomainNoun) return api('/health', {}, 'health')

  if (NOUN.recs.test(text) && !NOUN.incident.test(text) && !NOUN.group.test(text) && !NOUN.user.test(text)) {
    const types = REC_TYPES.filter((t) => t.re.test(text)).map((t) => t.type)
    const params = types.length ? { types: types.join(',') } : {}
    return api('/catalog/recommendations', params, 'get_optimization_recommendations', { types })
  }

  if (NOUN.category.test(text)) {
    const q = extractQuery(text, NOUN.category)
    return api('/catalog/categories', { limit: extractLimit(text), q }, 'list_catalog_categories', { q })
  }

  const username = NOUN.user.test(text) ? extractUsername(text) : null
  if (username) return api(`/users/${encodeURIComponent(username)}`, {}, 'get_user', { username })

  if (NOUN.group.test(text)) {
    const q = extractQuery(text, NOUN.group)
    return api('/groups', { limit: extractLimit(text), q }, 'list_groups', { q })
  }

  if (NOUN.user.test(text)) {
    return local(
      'The read-only API looks up one user at a time, by username or email. Try `user svc.claudecode.readonly`, `who is abel.tuter`, or `user by email jane@example.com`.',
    )
  }

  if (NOUN.catalog.test(text) && !NOUN.incident.test(text)) {
    const q = extractQuery(text, NOUN.catalog)
    return api('/catalog/items', { limit: extractLimit(text), q }, 'list_catalog_items', { q })
  }

  if (NOUN.incident.test(text)) {
    // Pull the date phrase out first so "last 7 days" is not read as "limit 7" or as a search term.
    const { range, rest } = extractDateRange(text, now)
    const state = STATES.find((s) => s.re.test(rest))
    const q = extractQuery(rest, NOUN.incident)
    const sort = extractSort(rest) || (range?.field === 'updated' ? SORTS.updated : null)

    const params = { limit: extractLimit(rest), q, state: state?.code }
    if (range) {
      params[`${range.field}_from`] = range.from || ''
      params[`${range.field}_to`] = range.to || ''
    }
    if (sort) {
      params.sort = sort.sort
      params.order = sort.order
    }

    const notes = []
    if (!state && /\b(?:open|unresolved|outstanding)\b/i.test(rest)) {
      notes.push(
        'The API filters by one exact state, so these span all states. Ask for "new", "in progress", "on hold", "resolved" or "closed" incidents to narrow it down.',
      )
    }
    if (!range && /\b(?:month|year|week|dates?|dated|ago|since|before|after|between|until)\b/i.test(text)) {
      notes.push(
        'I couldn\'t read a date in that question, so these are simply the most recent incidents. Try "in August 2025", "last 30 days" or "between 2025-06-01 and 2025-06-30".',
      )
    }
    const meta = { q, stateLabel: state?.label, range, sortLabel: sort?.label, note: notes.join(' ') || undefined }
    return api('/incidents', params, 'list_incidents', meta)
  }

  // A lone token such as "abel.tuter" is almost certainly a username.
  const lone = text.match(/^[\w-]+\.[\w.-]+$/)
  if (lone && !/\.(?:com|net|org|io|dev)$/i.test(lone[0])) {
    return api(`/users/${encodeURIComponent(lone[0])}`, {}, 'get_user', { username: lone[0] })
  }

  return local(FALLBACK_TEXT)
}

/** Map a backend pathname to the tool name used to pick a renderer. */
export function toolForPath(pathname) {
  const p = pathname.replace(/\/+$/, '') || '/'
  if (p === '/') return 'index'
  if (p === '/health') return 'health'
  if (p === '/packages') return 'list_tool_packages'
  if (p === '/incidents') return 'list_incidents'
  if (/^\/incidents\/[^/]+$/.test(p)) return 'get_incident_by_number'
  if (p === '/catalog/items') return 'list_catalog_items'
  if (/^\/catalog\/items\/[^/]+$/.test(p)) return 'get_catalog_item'
  if (p === '/catalog/categories') return 'list_catalog_categories'
  if (p === '/catalog/recommendations') return 'get_optimization_recommendations'
  if (p === '/groups') return 'list_groups'
  if (/^\/users\/(?:by-email\/)?[^/]+$/.test(p)) return 'get_user'
  return null
}

function parseRawPath(text) {
  const [rawPath, rawQuery = ''] = text.split('?')
  const path = rawPath.trim().replace(/\/+$/, '') || '/'
  const tool = toolForPath(path)
  if (!tool) {
    return local(`I can only call the read-only endpoints the backend exposes: ${ALLOWED_PATHS}.`)
  }
  const params = Object.fromEntries(new URLSearchParams(rawQuery.trim()))
  return api(path, params, tool, {})
}

/* ------------------------------------------------------------------ */
/* Sorting                                                             */
/* ------------------------------------------------------------------ */

const SORTS = {
  oldest: { sort: 'created', order: 'asc', label: 'oldest first' },
  updated: { sort: 'updated', order: 'desc', label: 'most recently updated first' },
  priority: { sort: 'priority', order: 'asc', label: 'highest priority first' },
  number: { sort: 'number', order: 'asc', label: 'by incident number' },
}

function extractSort(text) {
  const t = text.toLowerCase()
  if (/\b(?:oldest|earliest|first created|first opened|ascending|asc)\b/.test(t)) return SORTS.oldest
  if (/\b(?:recently|last|latest|most recently|newly)\s+(?:updated|modified|changed|touched|edited)\b/.test(t)) return SORTS.updated
  if (/\b(?:by|sorted by|order by|ordered by)\s+(?:last\s+)?(?:update|updated|modified)\b/.test(t)) return SORTS.updated
  if (/\b(?:by|sorted by|order by|ordered by|highest|top|most urgent)\s*priority\b|\bpriority\s+(?:order|first)\b|\bmost urgent\b/.test(t)) {
    return SORTS.priority
  }
  if (/\b(?:by|sorted by|order by|ordered by)\s+(?:incident\s+)?number\b/.test(t)) return SORTS.number
  return null
}

/* ------------------------------------------------------------------ */
/* Dates                                                               */
/* ------------------------------------------------------------------ */

const MONTH_RE =
  '(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
const MONTH_INDEX = { jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5, jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11 }
const MONTH_NAMES = [
  'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december',
]
// Every full month name is an unambiguous date word except "may".
const UNAMBIGUOUS_MONTHS = new Set(MONTH_NAMES.filter((n) => n !== 'may'))
const DATE_CONTEXT_BEFORE =
  /\b(?:in|during|for|on|of|since|after|before|until|till|from|between|and|created|updated|opened|closed|resolved|month)\s*$/i

/** Optimal-string-alignment edit distance (Levenshtein plus adjacent transpositions). */
function editDistance(a, b) {
  const m = a.length
  const n = b.length
  const d = Array.from({ length: m + 1 }, (_, i) => {
    const row = new Array(n + 1).fill(0)
    row[0] = i
    return row
  })
  for (let j = 0; j <= n; j++) d[0][j] = j
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1)
    }
  }
  return d[m][n]
}

/** Map "augest", "sept", "Feburary" to a canonical month name, or null. */
function canonicalMonth(word) {
  const w = word.toLowerCase()
  if (w.length < 3) return null
  if (MONTH_NAMES.includes(w)) return w
  if (w.length <= 4) return MONTH_NAMES.find((n) => n.startsWith(w)) || null // jan, feb, sept, ...
  return MONTH_NAMES.find((n) => editDistance(w, n) <= (w.length >= 8 ? 2 : 1)) || null
}

/**
 * Fix month typos when they sit in a date context and drop a trailing "month"
 * word, so "created on augest month" becomes "created on august".
 */
function normalizeMonths(text) {
  return text.replace(/\b([A-Za-z]{3,})\b(\s+month\b)?(?=(\s+\d{4}\b)?)/g, (match, word, monthWord, yearAhead, offset, whole) => {
    const canonical = canonicalMonth(word)
    if (!canonical) return match
    const inContext =
      Boolean(monthWord) ||
      Boolean(yearAhead) ||
      DATE_CONTEXT_BEFORE.test(whole.slice(0, offset)) ||
      (UNAMBIGUOUS_MONTHS.has(canonical) && word.toLowerCase() === canonical)
    return inContext ? canonical : match
  })
}
const NUM_WORDS = {
  a: 1, an: 1, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
  twelve: 12, fourteen: 14, fifteen: 15, thirty: 30, sixty: 60, ninety: 90,
}
const NUM = '(\\d{1,4}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|fourteen|fifteen|thirty|sixty|ninety)'
const UNIT = '(hour|day|week|month|year)'

const RELATIVE_LAST = new RegExp(
  `\\b(?:(?:in|within|over|during|for|from)\\s+)?(?:the\\s+)?(?:last|past|previous)\\s+(?:${NUM}\\s+)?${UNIT}s?\\b`,
  'i',
)
const NEWER_THAN = new RegExp(`\\b(?:newer than|within|less than|under|in the past)\\s+${NUM}\\s+${UNIT}s?(?:\\s+ago)?\\b`, 'i')
const OLDER_THAN = new RegExp(`\\b(?:older than|more than|over|earlier than)\\s+${NUM}\\s+${UNIT}s?(?:\\s+(?:ago|old))?\\b`, 'i')
const AGO = new RegExp(`\\b${NUM}\\s+${UNIT}s?\\s+ago\\b`, 'i')
const THIS_PERIOD = /\bthis\s+(week|month|year)\b/i

const pad = (n) => String(n).padStart(2, '0')

/** ServiceNow encoded-query date format. */
export function formatSnowDate(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function startOfDay(d) {
  const x = new Date(d)
  x.setHours(0, 0, 0, 0)
  return x
}
function endOfDay(d) {
  const x = new Date(d)
  x.setHours(23, 59, 59, 0)
  return x
}
function addUnits(d, unit, n) {
  const x = new Date(d)
  if (unit === 'hour') x.setHours(x.getHours() + n)
  else if (unit === 'day') x.setDate(x.getDate() + n)
  else if (unit === 'week') x.setDate(x.getDate() + 7 * n)
  else if (unit === 'month') x.setMonth(x.getMonth() + n)
  else if (unit === 'year') x.setFullYear(x.getFullYear() + n)
  return x
}
function startOfPeriod(unit, now) {
  const x = startOfDay(now)
  if (unit === 'week') {
    const day = (x.getDay() + 6) % 7 // Monday = 0
    x.setDate(x.getDate() - day)
  } else if (unit === 'month') x.setDate(1)
  else if (unit === 'year') x.setMonth(0, 1)
  return x
}
const monthIdx = (name) => MONTH_INDEX[name.slice(0, 3).toLowerCase()]
const monthBounds = (y, m) => ({ start: new Date(y, m, 1, 0, 0, 0, 0), end: new Date(y, m + 1, 0, 23, 59, 59, 0) })
const yearBounds = (y) => ({ start: new Date(y, 0, 1, 0, 0, 0, 0), end: new Date(y, 11, 31, 23, 59, 59, 0) })
const toNum = (w) => NUM_WORDS[w.toLowerCase()] ?? parseInt(w, 10)
const plural = (n, unit) => `${n} ${unit}${n === 1 ? '' : 's'}`

/**
 * Absolute date phrases: 2025-06-01, 5 June 2025, June 5 2025, June 2025, "in June", "august", 2024.
 * Each phrase carries `text` (as typed, used to strip it from the question) and
 * `display` (tidied, with the assumed year when none was given) for the reply.
 */
function findDatePhrases(text, now) {
  const found = []
  const overlaps = (index, len) => found.some((f) => index < f.index + f.text.length && index + len > f.index)
  const push = (index, str, start, end, kind, display) => {
    if (!overlaps(index, str.length)) found.push({ index, text: str, start, end, kind, display: display || str })
  }
  const capMonth = (s) => s.replace(new RegExp(MONTH_RE, 'i'), (w) => w[0].toUpperCase() + w.slice(1))
  const monthOnly = (index, name) => {
    const idx = monthIdx(name)
    // "in December" said in June means last December; the current month counts as this year.
    const year = idx > now.getMonth() ? now.getFullYear() - 1 : now.getFullYear()
    const b = monthBounds(year, idx)
    push(index, name, b.start, b.end, 'month', `${capMonth(MONTH_NAMES[idx])} ${year}`)
  }
  let re
  let m
  re = /\b(\d{4})-(\d{2})-(\d{2})\b/g
  while ((m = re.exec(text))) {
    const d = new Date(+m[1], +m[2] - 1, +m[3])
    push(m.index, m[0], startOfDay(d), endOfDay(d), 'day')
  }
  re = new RegExp(`\\b(\\d{1,2})(?:st|nd|rd|th)?\\s+${MONTH_RE}\\.?,?\\s+(\\d{4})\\b`, 'gi')
  while ((m = re.exec(text))) {
    const d = new Date(+m[3], monthIdx(m[2]), +m[1])
    push(m.index, m[0], startOfDay(d), endOfDay(d), 'day', capMonth(m[0]))
  }
  re = new RegExp(`\\b${MONTH_RE}\\.?\\s+(\\d{1,2})(?:st|nd|rd|th)?,?\\s+(\\d{4})\\b`, 'gi')
  while ((m = re.exec(text))) {
    const d = new Date(+m[3], monthIdx(m[1]), +m[2])
    push(m.index, m[0], startOfDay(d), endOfDay(d), 'day', capMonth(m[0]))
  }
  re = new RegExp(`\\b${MONTH_RE}\\.?,?\\s+(\\d{4})\\b`, 'gi')
  while ((m = re.exec(text))) {
    const b = monthBounds(+m[2], monthIdx(m[1]))
    push(m.index, m[0], b.start, b.end, 'month', capMonth(m[0]))
  }
  // Month without a year: after a preposition ("on august", "in may") ...
  re = new RegExp(
    `\\b(?:in|during|for|since|after|before|until|till|from|on|of|between|and)\\s+${MONTH_RE}\\b(?!\\s*,?\\s*\\d)`,
    'gi',
  )
  while ((m = re.exec(text))) monthOnly(m.index + m[0].length - m[1].length, m[1])
  // ... or a bare full month name, except "may" which is usually just a verb.
  re = /\b(january|february|march|april|june|july|august|september|october|november|december)\b(?!\s*,?\s*\d)/gi
  while ((m = re.exec(text))) monthOnly(m.index, m[1])
  re = /\b(19\d{2}|20\d{2})\b/g
  while ((m = re.exec(text))) {
    const b = yearBounds(+m[1])
    push(m.index, m[0], b.start, b.end, 'year')
  }
  return found.sort((a, b) => a.index - b.index)
}

function removeSpans(text, spans) {
  if (!spans.length) return text
  const sorted = [...spans].sort((a, b) => a[0] - b[0])
  let out = ''
  let cursor = 0
  for (const [s, e] of sorted) {
    if (s > cursor) out += text.slice(cursor, s)
    out += ' '
    cursor = Math.max(cursor, e)
  }
  return (out + text.slice(cursor)).replace(/\s{2,}/g, ' ').trim()
}

/**
 * Turn a date phrase in the text into a ServiceNow date window.
 * Returns { range: { from, to, label, field } | null, rest } where `rest` is the
 * text with the date phrase removed so it cannot be mistaken for a limit or a keyword.
 */
export function extractDateRange(input, now = new Date()) {
  const text = normalizeMonths(input.replace(INC_RE, ' ').replace(SYS_ID_RE, ' '))
  const lower = text.toLowerCase()
  const field = /\b(?:updated|modified|changed|touched|edited)\b/.test(lower) ? 'updated' : 'created'
  const spans = []
  const mark = (m) => spans.push([m.index, m.index + m[0].length])
  let from = null
  let to = null
  let label = ''
  let m

  if ((m = lower.match(/\btoday\b/))) {
    from = startOfDay(now)
    to = now
    label = 'today'
    mark(m)
  } else if ((m = lower.match(/\byesterday\b/))) {
    const y = addUnits(now, 'day', -1)
    from = startOfDay(y)
    to = endOfDay(y)
    label = 'yesterday'
    mark(m)
  } else if ((m = lower.match(RELATIVE_LAST))) {
    const n = m[1] ? toNum(m[1]) : 1
    from = addUnits(now, m[2], -n)
    to = now
    label = `in the last ${plural(n, m[2])}`
    mark(m)
  } else if ((m = lower.match(THIS_PERIOD))) {
    from = startOfPeriod(m[1], now)
    to = now
    label = `this ${m[1]}`
    mark(m)
  } else if ((m = lower.match(NEWER_THAN))) {
    const n = toNum(m[1])
    from = addUnits(now, m[2], -n)
    to = now
    label = `in the last ${plural(n, m[2])}`
    mark(m)
  } else if ((m = lower.match(OLDER_THAN))) {
    const n = toNum(m[1])
    to = addUnits(now, m[2], -n)
    label = `older than ${plural(n, m[2])}`
    mark(m)
  } else if ((m = lower.match(AGO))) {
    const n = toNum(m[1])
    from = addUnits(now, m[2], -n)
    to = now
    label = `since ${plural(n, m[2])} ago`
    mark(m)
  } else {
    const phrases = findDatePhrases(text, now)
    if (phrases.length >= 2) {
      const [a, b] = phrases
      from = a.start
      to = b.end
      label = `between ${a.display} and ${b.display}`
      spans.push([a.index, b.index + b.text.length])
    } else if (phrases.length === 1) {
      const p = phrases[0]
      const before = lower.slice(0, p.index).trim()
      const kw = before.match(/\b(since|after|from|starting|later than|newer than|before|until|till|up to|by|prior to|earlier than|older than|on|in|during|dated)\s*$/)
      const word = kw?.[1]
      if (word && /^(since|starting)$/.test(word)) {
        from = p.start
        label = `since ${p.display}`
      } else if (word && /^(after|later than|newer than)$/.test(word)) {
        from = new Date(p.end.getTime() + 1000)
        label = `after ${p.display}`
      } else if (word && /^(before|until|till|up to|by|prior to|earlier than|older than)$/.test(word)) {
        to = new Date(p.start.getTime() - 1000)
        label = `before ${p.display}`
      } else {
        from = p.start
        to = p.end
        label = `${p.kind === 'day' ? 'on' : 'in'} ${p.display}`
      }
      spans.push([kw ? p.index - (kw[0].length + (before.length - before.trimEnd().length)) : p.index, p.index + p.text.length])
    }
  }

  const rest = removeSpans(text, spans)
  if (!from && !to) return { range: null, rest }
  return {
    range: { from: from ? formatSnowDate(from) : null, to: to ? formatSnowDate(to) : null, label, field },
    rest,
  }
}

/* ------------------------------------------------------------------ */
/* Limits, search terms, usernames                                     */
/* ------------------------------------------------------------------ */

function extractLimit(text) {
  const t = text.replace(INC_RE, ' ').replace(SYS_ID_RE, ' ')
  const m =
    t.match(
      /\b(?:top|first|last|latest|newest|recent|oldest|limit(?: to)?|show(?: me)?|list|get|give me|find|fetch|display)\s+(\d{1,3})\b/i,
    ) ||
    t.match(
      /\b(\d{1,3})\s+(?:\w+\s+){0,2}?(?:incidents?|tickets?|issues?|problems?|items?|groups?|teams?|categories|users?|results?|records?|recommendations?|entries|rows)\b/i,
    )
  if (m) return clamp(parseInt(m[1], 10), 1, 50)
  if (/\b(?:how many|count|number of|total)\b/i.test(t)) return 50
  if (/\ball\b/i.test(t)) return 20
  return 5
}

function extractQuery(text, nounRe) {
  const t = text.replace(INC_RE, ' ').replace(SYS_ID_RE, ' ').replace(EMAIL_RE, ' ')

  const quoted = t.match(/["“]([^"”]+)["”]/) || t.match(/(?:^|\s)'([^']+)'/)
  if (quoted) return cleanQuery(quoted[1])

  const kw = t.match(
    /\b(?:about|regarding|related to|mentioning|containing|matching|named|called|titled|like|keyword|search(?:ing)? for|look(?:ing)? for|search|concerning)\s+(.+)$/i,
  )
  if (kw) {
    const q = cleanQuery(kw[1])
    if (q) return q
  }

  // Descriptive words right before the noun: "closed wifi incidents" -> "wifi"
  const match = nounRe.exec(t)
  if (match) {
    const before = t.slice(0, match.index).trim().split(/\s+/).filter(Boolean).slice(-3)
    const words = []
    for (let i = before.length - 1; i >= 0; i--) {
      const w = before[i].replace(/[^\w.-]/g, '')
      if (!w || STOP.has(w.toLowerCase()) || /^\d+$/.test(w) || isStateWord(w)) break
      words.unshift(w)
    }
    if (words.length) return words.join(' ')
  }
  return ''
}

function cleanQuery(raw) {
  let q = raw.trim().replace(/[?!.,;:]+$/g, '').trim()
  q = q.split(/\s+(?:that|which|where|whose|with|in state|state|from|since|sorted|ordered|limit|please|created|updated|opened)\b/i)[0]
  q = q.replace(/^(?:the|a|an|any|some)\s+/i, '')
  q = q.replace(/\s+(?:incidents?|tickets?|issues?|problems?|items?|groups?|teams?|categories|users?|thanks|thank you)$/i, '')
  return q.trim()
}

function extractUsername(text) {
  const at = text.match(/(?:^|\s)@([\w.-]+)/)
  if (at) return at[1]
  const m = text.match(
    /\b(?:user(?:name)?(?:\s+details?|\s+info(?:rmation)?|\s+profile|\s+account)?|account|profile|who\s*is|who's|whois|look\s*up|lookup|details? (?:for|of|about|on)|info(?:rmation)? (?:for|on|about))\s+(?:named\s+|called\s+|for\s+|of\s+|the\s+|with username\s+|with user name\s+)?([\w][\w.-]*)/i,
  )
  if (m && !STOP.has(m[1].toLowerCase()) && !isStateWord(m[1])) return m[1].replace(/[.?!,]+$/, '')
  const lone = text.trim().match(/^[\w-]+\.[\w.-]+$/)
  if (lone && !/\.(?:com|net|org|io|dev)$/i.test(lone[0])) return lone[0]
  return null
}

function isStateWord(word) {
  return STATES.some((s) => s.re.test(word)) || /^(?:open|unresolved|outstanding)$/i.test(word)
}

function clamp(n, min, max) {
  return Math.min(Math.max(n, min), max)
}

function api(path, params, tool, meta = {}) {
  return { kind: 'api', path, params, tool, meta }
}

function local(text) {
  return { kind: 'local', text }
}
