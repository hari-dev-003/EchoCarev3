import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { LockKeyhole } from 'lucide-react'
import { api } from '../lib/api'
import { Alert, Badge, Btn, Card, CardHead, Field } from '../components/ui'
import { StatusBadge } from '../components/trust'

export default function PublicShare() {
  const { token } = useParams(); const [d, setD] = useState<any>(null); const [err, setErr] = useState(''); const [need, setNeed] = useState(false); const [pc, setPc] = useState('')
  const load = async (code?: string) => {
    try { const r = await fetch(api.url(`/api/public/share/${token}`), { headers: code ? { 'X-Passcode': code } : {} }); const j = await r.json().catch(() => ({}))
      if (r.status === 401) { setNeed(true); return } if (!r.ok) { setNeed(false); setErr(j.detail || 'This link is not valid'); return } setNeed(false); setErr(''); setD(j) } catch { setErr('Could not reach EchoCare') } }
  useEffect(() => { load() }, [token])
  return <div style={{ maxWidth: 760, margin: '0 auto', padding: 20 }} className="stack">
    {need && <Card><CardHead title="Passcode required" icon={<LockKeyhole size={17} />} /><div className="stack"><Field label="Passcode"><input className="input" type="password" value={pc} onChange={e => setPc(e.target.value)} onKeyDown={e => e.key === 'Enter' && load(pc)} /></Field><Btn variant="primary" onClick={() => load(pc)}>Open</Btn>{err && <Alert tone="bad">{err}</Alert>}</div></Card>}
    {!need && err && <Alert tone="bad" title="Link unavailable">{err}</Alert>}
    {d && <><Card><h2>{d.profile_name}</h2><p className="small muted">Shared read-only · expires {new Date(d.expires_at).toLocaleString()}</p><p className="tiny faint">{d.notice}</p></Card>
      {d.summary && <Card><CardHead title="Summary (last 30 days)" /><div className="row wrap"><Badge>{d.summary.days_logged} days logged</Badge>{d.summary.avg_sleep_hours != null && <Badge>sleep {d.summary.avg_sleep_hours} h</Badge>}{d.summary.avg_stress != null && <Badge>stress {d.summary.avg_stress}/10</Badge>}{d.summary.avg_pain != null && <Badge>pain {d.summary.avg_pain}/10</Badge>}</div>{d.summary.risk_flags.map((f: any, i: number) => <p key={i} className="small" style={{ marginTop: 8 }}><b>{f.title}</b> <span className="muted">{f.detail}</span></p>)}</Card>}
      {d.vitals && <Card><CardHead title="Vitals" /><div className="table-wrap"><table className="table"><thead><tr><th>Date</th><th>BP</th><th>HR</th><th>Fasting</th><th>Post-meal</th><th>SpO2</th><th>Weight</th></tr></thead><tbody>{d.vitals.map((v: any, i: number) => <tr key={i}><td>{v.entry_date}</td><td>{v.systolic ? `${v.systolic}/${v.diastolic}` : '—'}</td><td>{v.heart_rate ?? '—'}</td><td>{v.fasting_sugar ?? '—'}</td><td>{v.postmeal_sugar ?? '—'}</td><td>{v.spo2 ?? '—'}</td><td>{v.weight_kg ?? '—'}</td></tr>)}</tbody></table></div></Card>}
      {d.medicines && <Card><CardHead title="Medicines" />{d.medicines.map((m: any, i: number) => <p key={i} className="small"><b>{m.name}</b> {m.dosage || m.dose} {m.frequency}</p>)}</Card>}
      {d.reports && <Card><CardHead title="Reports" />{d.reports.map((r: any, i: number) => <div key={i} style={{ padding: '8px 0', borderTop: '1px solid var(--line)' }}><div className="row between"><b>{r.title}</b><StatusBadge s={r.verification} /></div><div className="tiny faint">{r.report_date}</div>{r.fields.map((f: any, k: number) => <div key={k} className="small row between"><span>{f.test}</span><span className="mono">{f.value} {f.unit} {f.out_of_range && <Badge tone="bad">out of range</Badge>}</span></div>)}</div>)}</Card>}
      {d.alerts && <Card><CardHead title="Alerts" />{d.alerts.map((a: any, i: number) => <p key={i} className="small"><Badge tone={a.urgency === 'urgent' ? 'bad' : a.urgency === 'soon' ? 'warn' : 'info'}>{a.urgency}</Badge> {a.title}: {a.detail}</p>)}</Card>}</>}
  </div>
}
