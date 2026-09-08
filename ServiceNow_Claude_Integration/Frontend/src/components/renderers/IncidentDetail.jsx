import { useState } from 'react'
import { Badge, EmptyNote, KV, Mono } from './shared.jsx'
import { priorityTone, stateTone } from '../../lib/format.js'

// ServiceNow renders an empty choice/reference field as one of these.
const BLANK = new Set(['', 'none', '-- none --', 'unknown', 'null', 'undefined'])

function has(value) {
  if (value === null || value === undefined) return false
  return !BLANK.has(String(value).trim().toLowerCase())
}

/** Value for display, or '' so <KV> drops the row. */
function val(value) {
  return has(value) ? String(value) : ''
}

// Fields shown in the grouped sections below; everything else falls into "All fields".
const SECTIONS = [
  {
    title: 'Details',
    rows: [
      ['Caller', 'caller_id'],
      ['Channel', 'contact_type'],
      ['Category', 'category'],
      ['Subcategory', 'subcategory'],
      ['Service', 'business_service'],
      ['Service offering', 'service_offering'],
      ['Configuration item', 'cmdb_ci'],
      ['State', 'state'],
      ['Impact', 'impact'],
      ['Urgency', 'urgency'],
      ['Priority', 'priority'],
      ['Severity', 'severity'],
      ['Assignment group', 'assignment_group'],
      ['Assigned to', 'assigned_to'],
    ],
  },
  {
    title: 'Timeline',
    rows: [
      ['Opened', 'opened_at'],
      ['Opened by', 'opened_by'],
      ['Created', 'created_on'],
      ['Created by', 'sys_created_by'],
      ['Updated', 'updated_on'],
      ['Updated by', 'sys_updated_by'],
      ['Resolved', 'resolved_at'],
      ['Resolved by', 'resolved_by'],
      ['Closed', 'closed_at'],
      ['Closed by', 'closed_by'],
      ['Due date', 'due_date'],
      ['SLA due', 'sla_due'],
    ],
  },
  {
    title: 'Resolution',
    rows: [
      ['Close code', 'close_code'],
      ['Close notes', 'close_notes'],
      ['Resolution code', 'resolution_code'],
      ['Cause', 'cause'],
      ['Lessons learned', 'lessons_learned'],
    ],
  },
  {
    title: 'Process',
    rows: [
      ['Approval', 'approval'],
      ['Escalation', 'escalation'],
      ['Active', 'active'],
      ['Incident state', 'incident_state'],
      ['Made SLA', 'made_sla'],
      ['Knowledge', 'knowledge'],
      ['Reassignment count', 'reassignment_count'],
      ['Reopen count', 'reopen_count'],
      ['Child incidents', 'child_incidents'],
      ['Parent incident', 'parent_incident'],
      ['Problem', 'problem_id'],
      ['Change request', 'rfc'],
      ['Caused by change', 'caused_by'],
    ],
  },
]

// Long free-text fields get their own block rather than a grid row.
const NOTES = [
  ['Work notes', 'work_notes'],
  ['Additional comments', 'comments'],
  ['Activity', 'comments_and_work_notes'],
]

// Label for a field key, taken from the section tables above.
const LABELS = Object.fromEntries([
  ...SECTIONS.flatMap((s) => s.rows.map(([label, key]) => [key, label])),
  ...NOTES.map(([label, key]) => [key, label]),
  ['number', 'Number'],
  ['short_description', 'Short description'],
  ['description', 'Description'],
  ['sys_id', 'sys_id'],
])

const LONG_TEXT = new Set(['description', 'work_notes', 'comments', 'close_notes', 'comments_and_work_notes'])

/** Only the fields the question asked for. */
function FocusedView({ inc, fields }) {
  const asked = fields.map((key) => ({ key, label: LABELS[key] || key, value: inc[key] }))
  const present = asked.filter((f) => has(f.value))
  const missing = asked.filter((f) => !has(f.value))

  const isLong = (f) => LONG_TEXT.has(f.key) || String(f.value).length > 120
  const blocks = present.filter(isLong)
  const inline = present.filter((f) => !isLong(f))

  return (
    <article className="card">
      <div className="card-head">
        <div>
          <div className="eyebrow">{inc.number}</div>
          <div className="card-title">{inc.short_description || 'No short description'}</div>
        </div>
      </div>

      {inline.length > 0 && <KV rows={inline.map((f) => [f.label, String(f.value)])} />}

      {blocks.map((f) => (
        <div key={f.key} className="note-block">
          <div className="note-label">{f.label}</div>
          <pre className="note-text">{String(f.value).trim()}</pre>
        </div>
      ))}

      {missing.length > 0 && (
        <p className="empty-note">
          {missing.map((f) => f.label).join(', ')} {missing.length === 1 ? 'is' : 'are'} empty on this
          incident.
        </p>
      )}
    </article>
  )
}

const HEADER_FIELDS = new Set(['number', 'short_description', 'description', 'state', 'priority'])

export default function IncidentDetail({ result, fields = [] }) {
  const inc = result?.incident
  const [showAll, setShowAll] = useState(false)
  if (!inc) return <EmptyNote>{result?.message || 'Incident not found.'}</EmptyNote>

  // The question named specific fields: answer with just those.
  if (fields.length) return <FocusedView inc={inc} fields={fields} />

  const shown = new Set([
    ...HEADER_FIELDS,
    ...SECTIONS.flatMap((s) => s.rows.map(([, key]) => key)),
    ...NOTES.map(([, key]) => key),
    'sys_id',
  ])

  // Everything the sections above did not cover, still worth showing.
  const extras = Object.entries(inc)
    .filter(([key, value]) => !shown.has(key) && has(value))
    .sort(([a], [b]) => a.localeCompare(b))

  const notes = NOTES.filter(([, key]) => has(inc[key]))

  return (
    <article className="card">
      <div className="card-head">
        <div>
          <div className="eyebrow">{inc.number}</div>
          <div className="card-title">{inc.short_description || 'No short description'}</div>
        </div>
        <div className="badges">
          <Badge tone={stateTone(inc.state)}>{val(inc.state)}</Badge>
          <Badge tone={priorityTone(inc.priority)}>{val(inc.priority)}</Badge>
        </div>
      </div>

      {has(inc.description) && inc.description !== inc.short_description && (
        <p className="prose">{inc.description}</p>
      )}

      {SECTIONS.map((section) => {
        const rows = section.rows
          .map(([label, key]) => [label, val(inc[key])])
          .filter(([, value]) => value !== '')
        if (!rows.length) return null
        return (
          <section key={section.title}>
            <div className="eyebrow">{section.title}</div>
            <KV rows={rows} />
          </section>
        )
      })}

      {notes.length > 0 && (
        <section>
          <div className="eyebrow">Notes</div>
          {notes.map(([label, key]) => (
            <div key={key} className="note-block">
              <div className="note-label">{label}</div>
              <pre className="note-text">{String(inc[key]).trim()}</pre>
            </div>
          ))}
        </section>
      )}

      <section>
        <div className="eyebrow">Record</div>
        <KV rows={[['sys_id', inc.sys_id ? <Mono>{inc.sys_id}</Mono> : '']]} />
      </section>

      {extras.length > 0 && (
        <section>
          <button type="button" className="linkish" onClick={() => setShowAll((v) => !v)}>
            {showAll ? 'Hide' : `Show all ${extras.length} remaining fields`}
          </button>
          {showAll && (
            <KV rows={extras.map(([key, value]) => [key, String(value)])} />
          )}
        </section>
      )}
    </article>
  )
}
