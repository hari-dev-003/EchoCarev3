import { useState } from 'react'
import { Users, Link2, Copy, Trash2, UserPlus, Check, X } from 'lucide-react'
import { api } from '../lib/api'
import { useApp } from '../lib/store'
import { useFetch, fmtDate } from '../lib/hooks'
import { Alert, Badge, Btn, Card, CardHead, Empty, Field, Loading, Modal, PageHead, Seg } from '../components/ui'

const SCOPES = ['records', 'reports', 'vitals', 'medicines', 'insights']
const SECTIONS = ['summary', 'vitals', 'medicines', 'reports', 'alerts']
const toggle = (a: string[], x: string) => a.includes(x) ? a.filter(y => y !== x) : [...a, x]
const Checks = ({ all, on, set }: { all: string[]; on: string[]; set: (v: string[]) => void }) => <div className="row wrap">{all.map(x => <label key={x} className="row small" style={{ gap: 6 }}><input type="checkbox" checked={on.includes(x)} onChange={() => set(toggle(on, x))} />{x}</label>)}</div>

function Caregivers() {
  const { toast, profile, refreshProfiles } = useApp(); const l = useFetch<any[]>('/api/sharing/caregivers'); const inv = useFetch<any[]>('/api/sharing/invitations'); const mine = useFetch<any[]>('/api/sharing/shared-with-me')
  const [open, setOpen] = useState(false); const [f, setF] = useState({ email: '', role: 'viewer', scopes: ['records', 'vitals'] as string[], note: '' })
  const invite = async () => { try { await api.post('/api/sharing/caregivers', f); setOpen(false); toast('Invitation sent. Access starts only when they accept.', 'ok'); l.reload() } catch (e: any) { toast(e.message, 'bad') } }
  const answer = async (id: string, a: string) => { try { await api.post(`/api/sharing/invitations/${id}/${a}`); toast(a === 'accept' ? 'Access accepted' : 'Declined', 'ok'); inv.reload(); mine.reload(); refreshProfiles() } catch (e: any) { toast(e.message, 'bad') } }
  const rev = async (id: string) => { await api.del(`/api/sharing/caregivers/${id}`); l.reload() }
  const upd = async (id: string, role: string) => { await api.patch(`/api/sharing/caregivers/${id}`, { role }); l.reload() }
  return <div className="stack">
    {!!inv.data?.length && <Card><CardHead title="Invitations for you" icon={<UserPlus size={17} />} />{inv.data.map(i => <div key={i.id} className="row between wrap" style={{ padding: '8px 0' }}><div><b>{i.owner_name}</b> invited you to see <b>{i.profile_name}</b> as <Badge>{i.role}</Badge><div className="tiny faint">Shared: {i.scopes.join(', ')}</div></div><div className="row"><Btn size="sm" variant="primary" onClick={() => answer(i.id, 'accept')}><Check size={14} />Accept</Btn><Btn size="sm" onClick={() => answer(i.id, 'decline')}><X size={14} />Decline</Btn></div></div>)}</Card>}
    {!!mine.data?.length && <Card><CardHead title="Profiles shared with you" sub="Pick them from the profile switcher at the top." icon={<Users size={17} />} />{mine.data.map(m => <div key={m.profile_id} className="small" style={{ padding: '6px 0' }}><b>{m.profile_name}</b> from {m.owner_name} · {m.role} · {m.scopes.join(', ')}</div>)}</Card>}
    <Card><CardHead title={`Caregivers for ${profile?.name}`} sub="Only the owner of a profile can add, change or remove caregivers." icon={<Users size={17} />} right={<Btn variant="primary" size="sm" onClick={() => setOpen(true)}><UserPlus size={14} />Invite caregiver</Btn>} />
      {l.error ? <Alert tone="info" title="Owner only">You are viewing someone else's profile, so you cannot manage who else can see it.</Alert> : !l.data?.length ? <Empty title="No caregivers" sub="Invite a family member or helper. You choose viewer or editor and exactly what they can see." /> : <div className="table-wrap"><table className="table"><thead><tr><th>Person</th><th>Role</th><th>Can see</th><th>Status</th><th /></tr></thead><tbody>{l.data.map(c => <tr key={c.id}><td><b>{c.grantee_email}</b><div className="tiny faint">{fmtDate(c.created_at)}</div></td>
        <td>{c.status === 'revoked' ? c.role : <select className="select" style={{ width: 110 }} value={c.role} onChange={e => upd(c.id, e.target.value)}><option>viewer</option><option>editor</option></select>}</td><td className="small">{c.scopes.join(', ')}</td><td><Badge tone={c.status === 'accepted' ? 'ok' : c.status === 'pending' ? 'warn' : 'bad'}>{c.status}</Badge></td><td>{c.status !== 'revoked' && <Btn size="sm" variant="ghost" icon aria-label="Revoke access" onClick={() => rev(c.id)}><Trash2 size={14} /></Btn>}</td></tr>)}</tbody></table></div>}</Card>
    <Modal open={open} onClose={() => setOpen(false)} title="Invite a caregiver"><div className="stack"><Field label="Their e-mail address"><input className="input" type="email" value={f.email} onChange={e => setF({ ...f, email: e.target.value })} /></Field>
      <Field label="Role" hint="Viewers can only look. Editors can also add and change records."><select className="select" value={f.role} onChange={e => setF({ ...f, role: e.target.value })}><option>viewer</option><option>editor</option></select></Field>
      <Field label="What they can see"><Checks all={SCOPES} on={f.scopes} set={s => setF({ ...f, scopes: s })} /></Field>
      <Alert tone="info" title="They need an EchoCare account">They must register with this e-mail, confirm it with a code, and accept. Every access is written to your audit trail.</Alert>
      <div className="row end"><Btn onClick={() => setOpen(false)}>Cancel</Btn><Btn variant="primary" disabled={!f.email.includes('@') || !f.scopes.length} onClick={invite}>Send invitation</Btn></div></div></Modal></div>
}

function Links() {
  const { toast, profile } = useApp(); const l = useFetch<any[]>('/api/sharing/links'); const [open, setOpen] = useState(false); const [made, setMade] = useState<string | null>(null)
  const [f, setF] = useState({ label: '', sections: ['summary'] as string[], expires_hours: 24, max_views: 10, passcode: '' })
  const create = async () => { try { const r = await api.post('/api/sharing/links', { ...f, passcode: f.passcode || null }); setOpen(false); setMade(r.url); l.reload() } catch (e: any) { toast(e.message, 'bad') } }
  const copy = (u: string) => navigator.clipboard?.writeText(u).then(() => toast('Link copied', 'ok'))
  return <div className="stack"><Card><CardHead title={`Share links for ${profile?.name}`} sub="Read-only, time-limited pages for a doctor or relative who has no account." icon={<Link2 size={17} />} right={<Btn variant="primary" size="sm" onClick={() => setOpen(true)}><Link2 size={14} />New link</Btn>} />
    {made && <Alert tone="ok" title="Link created. Copy it now.">{<div className="row wrap"><span className="mono small" style={{ wordBreak: 'break-all' }}>{made}</span><Btn size="sm" onClick={() => copy(made)}><Copy size={13} />Copy</Btn></div>}</Alert>}
    {l.error ? <Alert tone="info" title="Owner only">Only the profile owner can create share links.</Alert> : !l.data?.length ? <Empty title="No links yet" /> : <div className="table-wrap"><table className="table"><thead><tr><th>Label</th><th>Shows</th><th>Expires</th><th>Views</th><th>State</th><th /></tr></thead><tbody>{l.data.map(x => <tr key={x.id}><td><b>{x.label || 'Untitled'}</b>{x.has_passcode && <div className="tiny faint">passcode protected</div>}</td><td className="small">{x.sections.join(', ')}</td><td className="small">{new Date(x.expires_at).toLocaleString()}</td><td>{x.views}{x.max_views ? ` / ${x.max_views}` : ''}</td><td><Badge tone={x.state === 'active' ? 'ok' : 'bad'}>{x.state}</Badge></td><td className="row">{x.state === 'active' && <Btn size="sm" variant="ghost" icon aria-label="Copy link" onClick={() => copy(x.url)}><Copy size={14} /></Btn>}{x.state === 'active' && <Btn size="sm" variant="ghost" icon aria-label="Revoke link" onClick={async () => { await api.del(`/api/sharing/links/${x.id}`); l.reload() }}><Trash2 size={14} /></Btn>}</td></tr>)}</tbody></table></div>}</Card>
    <Modal open={open} onClose={() => setOpen(false)} title="Create a secure link"><div className="stack"><Field label="Label (for you)"><input className="input" value={f.label} onChange={e => setF({ ...f, label: e.target.value })} placeholder="e.g. Dr. Kumar, 5 Nov visit" /></Field>
      <Field label="What the page shows"><Checks all={SECTIONS} on={f.sections} set={s => setF({ ...f, sections: s })} /></Field>
      <div className="form-grid"><Field label="Expires after"><select className="select" value={f.expires_hours} onChange={e => setF({ ...f, expires_hours: +e.target.value })}>{[[1, '1 hour'], [24, '24 hours'], [72, '3 days'], [168, '7 days'], [720, '30 days']].map(([h, t]) => <option key={h} value={h}>{t}</option>)}</select></Field>
        <Field label="Maximum views"><input className="input" type="number" min={1} max={1000} value={f.max_views} onChange={e => setF({ ...f, max_views: +e.target.value })} /></Field></div>
      <Field label="Passcode (optional)" hint="Share it separately, not in the same message."><input className="input" value={f.passcode} onChange={e => setF({ ...f, passcode: e.target.value })} /></Field>
      <div className="row end"><Btn onClick={() => setOpen(false)}>Cancel</Btn><Btn variant="primary" disabled={!f.sections.length || (!!f.passcode && f.passcode.length < 4)} onClick={create}>Create link</Btn></div></div></Modal></div>
}

export default function Sharing() {
  const [tab, setTab] = useState('care')
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Care" title="Sharing & access" sub="Decide who can see your records, for how long, and what they may change. You can withdraw access at any moment." right={<Seg value={tab} onChange={setTab} options={[{ value: 'care', label: 'Caregivers' }, { value: 'links', label: 'Secure links' }]} />} />
    {tab === 'care' ? <Caregivers /> : <Links />}</div>
}
