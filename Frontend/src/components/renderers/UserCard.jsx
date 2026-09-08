import { Badge, EmptyNote, KV, Mono } from './shared.jsx'
import { dv, initials, isTrue } from '../../lib/format.js'

export default function UserCard({ result }) {
  const u = result?.user
  if (!u) return <EmptyNote>{result?.message || 'User not found.'}</EmptyNote>

  const name = dv(u.name).trim() || `${dv(u.first_name)} ${dv(u.last_name)}`.trim() || dv(u.user_name)
  const subline = [dv(u.user_name), dv(u.email)].filter(Boolean).join(' · ')

  return (
    <article className="card profile">
      <div className="profile-head">
        <div className="avatar-lg" aria-hidden="true">
          {initials(name)}
        </div>
        <div className="profile-id">
          <div className="card-title">{name}</div>
          {subline && <div className="dim mono-sm">{subline}</div>}
          <div className="badges">
            <Badge tone={isTrue(u.active) ? 'ok' : 'muted'}>{isTrue(u.active) ? 'Active' : 'Inactive'}</Badge>
            {isTrue(u.vip) && <Badge tone="warn">VIP</Badge>}
            {isTrue(u.locked_out) && <Badge tone="critical">Locked out</Badge>}
            {dv(u.identity_type) && <Badge tone="neutral">{dv(u.identity_type)}</Badge>}
            {isTrue(u.web_service_access_only) && <Badge tone="info">Web service only</Badge>}
          </div>
        </div>
      </div>
      <KV
        rows={[
          ['Title', dv(u.title)],
          ['Department', dv(u.department)],
          ['Company', dv(u.company)],
          ['Location', dv(u.location)],
          ['Manager', dv(u.manager)],
          ['Phone', dv(u.phone)],
          ['Mobile', dv(u.mobile_phone)],
          ['Time zone', dv(u.time_zone)],
          ['Last login', dv(u.last_login_time) || dv(u.last_login)],
          ['Created', dv(u.sys_created_on)],
          ['Updated', dv(u.sys_updated_on)],
          ['sys_id', dv(u.sys_id) ? <Mono>{dv(u.sys_id)}</Mono> : ''],
        ]}
      />
    </article>
  )
}
