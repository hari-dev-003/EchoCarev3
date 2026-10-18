import { useRef, useState } from 'react'
import { BadgeCheck, Mail, ShieldCheck, UserCheck, FileSearch, Building2, Plus, Trash2 } from 'lucide-react'
import { api } from '../lib/api'
import { useApp } from '../lib/store'
import { useFetch, fmtDate } from '../lib/hooks'
import { Alert, Badge, Btn, Card, CardHead, Empty, Field, Loading, Modal, PageHead, Seg } from '../components/ui'
import { StatusBadge, CheckList, openBlob } from '../components/trust'

const STEPS = ['unverified', 'contact_verified', 'identity_pending', 'identity_verified']
const LABEL: Record<string, string> = { unverified: 'Not verified', contact_verified: 'E-mail confirmed', identity_pending: 'Identity under review', identity_verified: 'Identity verified', identity_rejected: 'Identity not accepted' }

function Kyc() {
  const { toast, user } = useApp(); const k = useFetch<any>('/api/kyc/status')
  const [otp, setOtp] = useState(''); const [dev, setDev] = useState<string | null>(null); const [busy, setBusy] = useState(false)
  const [f, setF] = useState({ legal_name: user?.name || '', id_type: 'aadhaar', id_last4: '' }); const file = useRef<HTMLInputElement>(null)
  if (k.loading || !k.data) return <Loading />
  const s = k.data; const idx = Math.max(0, STEPS.indexOf(s.status === 'identity_rejected' ? 'contact_verified' : s.status))
  const send = async () => { setBusy(true); try { const r = await api.post('/api/kyc/otp/send'); setDev(r.dev_otp || null); toast(r.sent ? 'Code sent to your e-mail' : (r.message || 'Code generated'), 'ok') } catch (e: any) { toast(e.message, 'bad') } finally { setBusy(false) } }
  const verify = async () => { try { await api.post('/api/kyc/otp/verify', { code: otp }); setOtp(''); setDev(null); toast('E-mail confirmed', 'ok'); k.reload() } catch (e: any) { toast(e.message, 'bad') } }
  const submit = async () => { try { const fd = new FormData(); Object.entries(f).forEach(([a, b]) => fd.append(a, b)); const x = file.current?.files?.[0]; if (x) fd.append('file', x); await api.form('/api/kyc/identity', fd); toast('Submitted for review', 'ok'); k.reload() } catch (e: any) { toast(e.message, 'bad') } }
  return <div className="grid g2">
    <Card><CardHead title="Your verification level" sub={s.email} icon={<BadgeCheck size={17} />} right={<Badge tone={s.status === 'identity_verified' ? 'ok' : s.status === 'identity_rejected' ? 'bad' : 'warn'}>{LABEL[s.status]}</Badge>} />
      <div className="stack" style={{ gap: 10 }}>{['Account created', 'E-mail confirmed', 'Identity submitted', 'Identity reviewed by an administrator'].map((l, i) => <div className="row" key={l}><span className="icon-chip" style={{ opacity: i <= idx ? 1 : .4 }}>{i <= idx ? <ShieldCheck size={15} /> : i + 1}</span><span className={i <= idx ? '' : 'muted'}>{l}</span></div>)}</div>
      {s.status === 'identity_rejected' && <Alert tone="bad" title="Not accepted">{s.identity.review_note || 'The reviewer could not confirm the details. You can submit again.'}</Alert>}
      <div className="stack" style={{ marginTop: 14 }}>{s.notes.map((n: string) => <p key={n} className="small muted">• {n}</p>)}</div></Card>
    <div className="stack">
      <Card><CardHead title="Step 1: confirm your e-mail" icon={<Mail size={17} />} right={s.email_verified ? <Badge tone="ok">done {fmtDate(s.email_verified_at)}</Badge> : undefined} />
        {s.email_verified ? <p className="small muted">A one-time code proved you can read this mailbox. This is not identity proof.</p> : <div className="stack">
          <Btn onClick={send} disabled={busy}><Mail size={15} />Send me a code</Btn>
          {dev && <Alert tone="warn" title="Development mode">E-mail (SMTP) is not configured, so the code is shown here: <b className="mono">{dev}</b>. Configure SMTP in backend/.env for real delivery.</Alert>}
          <Field label="6-digit code"><input className="input mono" maxLength={6} inputMode="numeric" value={otp} onChange={e => setOtp(e.target.value.replace(/\D/g, ''))} /></Field>
          <Btn variant="primary" disabled={otp.length !== 6} onClick={verify}>Verify code</Btn></div>}</Card>
      <Card><CardHead title="Step 2: identity review (optional)" icon={<UserCheck size={17} />} />
        {!s.email_verified ? <p className="small muted">Confirm your e-mail first.</p> : s.status === 'identity_pending' ? <Alert tone="info" title="Waiting for an administrator">Submitted {fmtDate(s.identity.submitted_at)}. You will see the result here.</Alert> : s.status === 'identity_verified' ? <Alert tone="ok" title="Identity reviewed">Reviewed {fmtDate(s.identity.reviewed_at)}.</Alert> :
          <div className="stack"><div className="form-grid"><Field label="Name as on ID"><input className="input" value={f.legal_name} onChange={e => setF({ ...f, legal_name: e.target.value })} /></Field>
            <Field label="ID type"><select className="select" value={f.id_type} onChange={e => setF({ ...f, id_type: e.target.value })}>{['aadhaar', 'passport', 'driving_licence', 'voter_id', 'other'].map(x => <option key={x} value={x}>{x.replace('_', ' ')}</option>)}</select></Field></div>
            <Field label="Last 4 characters of ID number" hint="We never ask for the full number."><input className="input mono" maxLength={4} value={f.id_last4} onChange={e => setF({ ...f, id_last4: e.target.value })} /></Field>
            <Field label="Photo of the ID (optional)"><input ref={file} className="input" type="file" accept="image/*,.pdf" /></Field>
            <Btn variant="primary" disabled={f.id_last4.length !== 4 || !f.legal_name.trim()} onClick={submit}>Submit for review</Btn></div>}</Card></div></div>
}

function Queue() {
  const { toast } = useApp(); const q = useFetch<any[]>('/api/review/queue'); const [sel, setSel] = useState<any>(null); const [note, setNote] = useState(''); const kyc = useFetch<any[]>('/api/kyc/admin/pending')
  const decide = async (d: string) => { try { await api.post(`/api/review/${sel.id}/decide`, { decision: d, note }); toast(d === 'confirm' ? 'Marked Verified' : 'Marked Failed', 'ok'); setSel(null); setNote(''); q.reload() } catch (e: any) { toast(e.message, 'bad') } }
  const kd = async (u: any, d: string) => { try { await api.post(`/api/kyc/admin/${u.user_id}/decide`, { decision: d }); toast('Saved', 'ok'); kyc.reload() } catch (e: any) { toast(e.message, 'bad') } }
  return <div className="stack">
    <Card><CardHead title="Reports waiting for a reviewer" sub="Only a person can set a report to Verified. Open the original file, compare it with the details, then confirm or reject." icon={<FileSearch size={17} />} />
      {q.loading ? <Loading /> : !q.data?.length ? <Empty title="Queue is empty" /> : <div className="table-wrap"><table className="table"><thead><tr><th>Report</th><th>Patient</th><th>Date</th><th>Automatic result</th><th /></tr></thead><tbody>{q.data.map(r => <tr key={r.id}><td><b>{r.title}</b><div className="tiny faint">{r.requested ? 'Owner asked for review' : 'Flagged by checks'}</div></td><td>{r.profile_name}</td><td>{fmtDate(r.report_date)}</td><td><StatusBadge s={r.status} /></td><td><Btn size="sm" onClick={() => setSel(r)}>Review</Btn></td></tr>)}</tbody></table></div>}</Card>
    <Card><CardHead title="Identity submissions" sub="Administrators only." icon={<UserCheck size={17} />} />
      {kyc.error ? <p className="small muted">Administrator access is required to see identity submissions.</p> : !kyc.data?.length ? <Empty title="No pending submissions" /> : kyc.data.map(u => <div key={u.user_id} className="row between wrap" style={{ padding: '10px 0', borderTop: '1px solid var(--line)' }}><div><b>{u.name}</b> <span className="muted small">{u.email}</span><div className="small">Name on ID: {u.legal_name} · {u.id_type} · ending {u.id_last4}</div></div>
        <div className="row">{u.document_id && <Btn size="sm" onClick={async () => openBlob(await api.blob(`/api/kyc/admin/${u.user_id}/document`))}>View ID</Btn>}<Btn size="sm" variant="primary" onClick={() => kd(u, 'approve')}>Approve</Btn><Btn size="sm" variant="danger" onClick={() => kd(u, 'reject')}>Reject</Btn></div></div>)}</Card>
    <Modal open={!!sel} onClose={() => setSel(null)} title={sel?.title || ''} wide>{sel && <div className="stack">
      <div className="row wrap"><StatusBadge s={sel.status} />{sel.extracted?.issuer_name && <Badge>Issuer: {sel.extracted.issuer_name}</Badge>}{sel.extracted?.patient_name && <Badge>Name on document: {sel.extracted.patient_name}</Badge>}</div>
      <CheckList checks={sel.checks} />
      {sel.has_file && <Btn onClick={async () => openBlob(await api.blob(`/api/review/${sel.id}/file`))}>Open original file</Btn>}
      <Field label="Reviewer note"><input className="input" value={note} onChange={e => setNote(e.target.value)} placeholder="What did you compare?" /></Field>
      <div className="row end"><Btn variant="danger" onClick={() => decide('reject')}>Reject</Btn><Btn variant="primary" onClick={() => decide('confirm')}>Confirm as Verified</Btn></div></div>}</Modal></div>
}

function Issuers() {
  const { toast, user } = useApp(); const l = useFetch<any[]>('/api/trust/issuers'); const [open, setOpen] = useState(false); const [f, setF] = useState({ name: '', aliases: '', kind: 'laboratory', website: '' })
  const add = async () => { try { await api.post('/api/trust/issuers', { name: f.name, aliases: f.aliases.split(',').map(s => s.trim()).filter(Boolean), kind: f.kind, website: f.website || null }); setOpen(false); setF({ name: '', aliases: '', kind: 'laboratory', website: '' }); l.reload() } catch (e: any) { toast(e.message, 'bad') } }
  const del = async (id: string) => { try { await api.del(`/api/trust/issuers/${id}`); l.reload() } catch (e: any) { toast(e.message, 'bad') } }
  return <Card><CardHead title="Trusted issuer registry" sub="Labs and hospitals whose name, when found on a report, counts as supporting evidence. A matching name never proves a document is genuine." icon={<Building2 size={17} />} right={user?.is_admin ? <Btn variant="primary" size="sm" onClick={() => setOpen(true)}><Plus size={14} />Add issuer</Btn> : undefined} />
    {!l.data?.length ? <Empty title="No trusted issuers yet" sub="An administrator can add laboratories and hospitals here." /> : <div className="table-wrap"><table className="table"><thead><tr><th>Name</th><th>Also known as</th><th>Type</th><th /></tr></thead><tbody>{l.data.map(i => <tr key={i.id}><td><b>{i.name}</b></td><td className="muted small">{(i.aliases || []).join(', ') || '—'}</td><td>{i.kind}</td><td>{user?.is_admin && <Btn size="sm" variant="ghost" icon aria-label="Remove" onClick={() => del(i.id)}><Trash2 size={14} /></Btn>}</td></tr>)}</tbody></table></div>}
    <Modal open={open} onClose={() => setOpen(false)} title="Add trusted issuer"><div className="stack"><Field label="Name"><input className="input" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} /></Field><Field label="Other names (comma separated)"><input className="input" value={f.aliases} onChange={e => setF({ ...f, aliases: e.target.value })} /></Field><div className="form-grid"><Field label="Type"><select className="select" value={f.kind} onChange={e => setF({ ...f, kind: e.target.value })}>{['laboratory', 'hospital', 'clinic', 'pharmacy', 'other'].map(x => <option key={x}>{x}</option>)}</select></Field><Field label="Website"><input className="input" value={f.website} onChange={e => setF({ ...f, website: e.target.value })} /></Field></div><div className="row end"><Btn onClick={() => setOpen(false)}>Cancel</Btn><Btn variant="primary" disabled={f.name.trim().length < 2} onClick={add}>Add</Btn></div></div></Modal></Card>
}

export default function Verification() {
  const { user } = useApp(); const [tab, setTab] = useState('kyc')
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Trust" title="Verification" sub="Confirm who you are and who reviewed your documents. EchoCare is explicit about what each level of checking does and does not prove." right={<Seg value={tab} onChange={setTab} options={[{ value: 'kyc', label: 'My verification' }, { value: 'review', label: 'Reviewer desk' }, { value: 'issuers', label: 'Trusted issuers' }]} />} />
    {tab === 'kyc' && <Kyc />}{tab === 'review' && <Queue />}{tab === 'issuers' && <Issuers />}
  </div>
}
