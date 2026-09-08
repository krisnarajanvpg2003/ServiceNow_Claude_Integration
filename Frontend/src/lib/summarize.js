// Turns a backend payload into the one-sentence reply shown above the data.
import { dv, plural } from './format.js'

export function summarize(plan, payload) {
  const tool = payload?.tool || plan.tool
  const r = payload?.result ?? payload
  const meta = plan.meta || {}
  const filters = describeFilters(meta)
  const note = meta.note ? ` ${meta.note}` : ''

  switch (tool) {
    case 'list_incidents': {
      const list = r?.incidents || []
      const order = meta.sortLabel || 'newest first'
      if (!list.length) {
        const hint = meta.range
          ? ' Nothing was created or updated in that window. Try a wider range, or drop the date to see the most recent incidents.'
          : ''
        return `I couldn't find any incidents${filters}.${hint}${note}`
      }
      return `Here ${list.length === 1 ? 'is' : 'are'} ${plural(list.length, 'incident')}${filters}, ${order}. Click a number to open it.${note}`
    }
    case 'get_incident_by_number': {
      const inc = r?.incident
      if (!inc) return r?.message || 'I could not find that incident.'
      const asked = meta.fields || []
      if (!asked.length) return `Here are the details for ${inc.number}.`
      const names = asked.map((key) => FIELD_LABELS[key] || key.replace(/_/g, ' '))
      // "the work notes are", but "the caller is"
      const singular = names.length === 1 && !names[0].endsWith('s')
      return `Here ${singular ? 'is the' : 'are the'} ${listOf(names)} for ${inc.number}.`
    }
    case 'list_catalog_items': {
      const list = r?.items || []
      if (!list.length) return `I couldn't find any catalog items${filters}.`
      return `I found ${plural(list.length, 'catalog item')}${filters}. Click one to see its details and variables.`
    }
    case 'get_catalog_item': {
      const item = r?.data ?? r?.item ?? r
      const name = dv(item?.name)
      const vars = (item?.variables || []).length
      return name
        ? `Here is the catalog item “${name}”${vars ? ` with ${plural(vars, 'variable')}` : ''}.`
        : r?.message || 'Here is the catalog item.'
    }
    case 'list_catalog_categories': {
      const list = r?.categories || []
      if (!list.length) return `I couldn't find any catalog categories${filters}.`
      return `Here ${list.length === 1 ? 'is' : 'are'} ${plural(list.length, 'catalog category', 'catalog categories')}${filters}.`
    }
    case 'get_optimization_recommendations': {
      const recs = r?.recommendations || []
      const total = recs.reduce((sum, rec) => sum + (rec.items?.length || 0), 0)
      if (!recs.length) return r?.message || 'The optimization analysis returned no recommendations.'
      return `I ran ${plural(recs.length, 'optimization check')} and flagged ${plural(total, 'catalog item')} worth reviewing.`
    }
    case 'list_groups': {
      const list = r?.groups || []
      if (!list.length) return `I couldn't find any groups${filters}.`
      return `Here ${list.length === 1 ? 'is' : 'are'} ${plural(list.length, 'group')}${filters}.`
    }
    case 'get_user': {
      const u = r?.user
      if (!u) return r?.message || 'I could not find that user.'
      const name = dv(u.name).trim() || dv(u.user_name)
      return `Here is the profile for ${name}.`
    }
    case 'list_tool_packages': {
      const count = r?.available_packages?.length || 0
      return `The MCP server currently has the “${r?.current_package}” tool package loaded, out of ${plural(count, 'available package')}.`
    }
    case 'health':
      return r?.ok
        ? `The API is up and ServiceNow at ${r.instance} answered with ${r.servicenow}.`
        : `The API responded, but it could not reach ServiceNow (${r?.servicenow || 'no detail'}).`
    case 'index':
      return 'Here is everything the local MCP API exposes.'
    default:
      return 'Here is what the API returned.'
  }
}

/** " in state “Closed” created in the last 7 days matching “wifi”" */
function describeFilters(meta) {
  const parts = []
  if (meta.stateLabel) parts.push(`in state “${meta.stateLabel}”`)
  if (meta.range?.label) parts.push(`${meta.range.field || 'created'} ${meta.range.label}`)
  if (meta.q) parts.push(`matching “${meta.q}”`)
  return parts.length ? ` ${parts.join(' ')}` : ''
}

// Field labels used when the question asked for specific fields.
const FIELD_LABELS = {
  short_description: 'short description',
  description: 'description',
  caller_id: 'caller',
  assigned_to: 'assignee',
  assignment_group: 'assignment group',
  contact_type: 'channel',
  cmdb_ci: 'configuration item',
  business_service: 'service',
  service_offering: 'service offering',
  created_on: 'created date',
  updated_on: 'updated date',
  sys_created_by: 'created by',
  sys_updated_by: 'updated by',
  opened_at: 'opened date',
  opened_by: 'opened by',
  resolved_at: 'resolved date',
  closed_at: 'closed date',
  work_notes: 'work notes',
  comments: 'additional comments',
  close_notes: 'close notes',
  incident_state: 'incident state',
  sys_id: 'sys_id',
}

/** "a", "a and b", "a, b and c" */
function listOf(names) {
  if (names.length === 1) return names[0]
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
}
