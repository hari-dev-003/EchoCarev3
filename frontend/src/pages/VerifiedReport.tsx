import { useState } from 'react'
import { Link } from 'react-router-dom'
import { BadgeCheck, FileDown, Printer, Sparkles } from 'lucide-react'
import { api, download } from '../lib/api'
import { useApp } from '../lib/store'
import { useFetch, fmtDate } from '../lib/hooks'
import { Alert, Badge, Btn, Card, CardHead, Empty, Loading, PageHead } from '../components/ui'
import { StatusBadge } from '../components/trust'

export const ReportBody = ({ r }: { r: any }) => { const d = r.data; return <div className="stack" style={{ gap: 16 }}>
  <Card className="flat"><CardHead title="Identity" right={<Badge tone={d.identity.label === 'Verified identity' ? 'ok' : undefined}>{d.identity.label}</Badge>} /><p><b>{d.identity.name}</b> {d.identity.relation && <span className="muted">({d.identity.relation})</span>}</p><p className="small muted">{d.identity.account_status}</p></Card>
  <Card className="flat"><CardHead title="Summary" icon={<Sparkles size={16} />} right={<Badge tone={r.summary.label === 'AI-generated' ? 'info' : undefined}>{r.summary.label}</Badge>} /><p>{r.summary.text}</p>{r.summary.sources?.length > 0 && <p className="small muted" style={{ marginTop: 8 }}>Sources: {r.summary.sources.join('; ')}</p>}{r.summary.note && <p className="tiny faint">{r.summary.note}</p>}</Card>
  <Card className="flat"><CardHead title="Reports" />{!d.reports.length ? <p className="small muted">No reports.</p> : <div className="table-wrap"><table className="table"><thead><tr><th>Report</th><th>Date</th><th>Status</th><th>Provenance</th><th>Issuer</th></tr></thead><tbody>{d.reports.map((x: any) => <tr key={x.id}><td><b>{x.title}</b></td><td>{fmtDate(x.report_date)}</td><td><StatusBadge s={x.status} /></td><td><Badge>{x.label}</Badge></td><td>{x.issuer || '—'}</td></tr>)}</tbody></table></div>}</Card>
  {d.vitals.rows.length > 0 && <Card className="flat"><CardHead title="Recent vitals" right={<Badge>{d.vitals.label}</Badge>} /><div className="table-wrap"><table className="table"><thead><tr><th>Date</th><th>Weight</th><th>BP</th><th>HR</th><th>Fasting</th><th>Post-meal</th><th>SpO2</th></tr></thead><tbody>{d.vitals.rows.map((v: any, i: number) => <tr key={i}><td>{fmtDate(v.entry_date)}</td><td>{v.weight_kg ?? '—'}</td><td>{v.systolic ? `${v.systolic}/${v.diastolic}` : '—'}</td><td>{v.heart_rate ?? '—'}</td><td>{v.fasting_sugar ?? '—'}</td><td>{v.postmeal_sugar ?? '—'}</td><td>{v.spo2 ?? '—'}</td></tr>)}</tbody></table></div></Card>}
  {d.medicines.rows.length > 0 && <Card className="flat"><CardHead title="Medicines" right={<Badge>{d.medicines.label}</Badge>} />{d.medicines.rows.map((m: any, i: number) => <div key={i} className="small" style={{ padding: '4px 0' }}><b>{m.name}</b> {m.dose} · {m.frequency}</div>)}</Card>}
  {d.alerts.rows.length > 0 && <Card className="flat"><CardHead title="Alerts" right={<Badge>{d.alerts.label}</Badge>} />{d.alerts.rows.map((a: any, i: number) => <div key={i} className="small" style={{ padding: '4px 0' }}><Badge tone={a.urgency === 'urgent' ? 'bad' : a.urgency === 'soon' ? 'warn' : 'info'}>{a.urgency}</Badge> {a.title}: {a.detail}</div>)}</Card>}
  {d.insights.rows.length > 0 && <Card className="flat"><CardHead title="Pattern insights" right={<Badge tone="info">{d.insights.label}</Badge>} />{d.insights.rows.map((i: any, k: number) => <div key={k} className="small" style={{ padding: '4px 0' }}><b>{i.theme}</b> · {Math.round(i.confidence * 100)}% ({i.label}) <span className="muted">{i.basis}</span></div>)}</Card>}
  <p className="tiny faint">Integrity hash {r.content_sha256}. Not a diagnosis.</p></div> }

export default function VerifiedReport() {
  const { toast, profile, lang } = useApp(); const list = useFetch<any[]>('/api/verified-report'); const [cur, setCur] = useState<any>(null); const [busy, setBusy] = useState(false); const [qr, setQr] = useState<string | null>(null)
  const gen = async () => { setBusy(true); try { const r = await api.post('/api/verified-report', { lang }); setCur(r); list.reload(); api.blob(`/api/verified-report/${r.id}/qr`).then(b => setQr(URL.createObjectURL(b))); toast('Verified Report created', 'ok') } catch (e: any) { toast(e.message, 'bad') } finally { setBusy(false) } }
  const openOld = async (id: string) => { setCur(await api.get(`/api/verified-report/${id}`)); setQr(URL.createObjectURL(await api.blob(`/api/verified-report/${id}/qr`))) }
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Trust" title="Verified Report" sub={`One shareable report for ${profile?.name || ''} where every section says where it came from: verified, patient-entered, extracted or AI-generated.`} right={<Btn variant="primary" disabled={busy} onClick={gen}><BadgeCheck size={16} />{busy ? 'Building…' : 'Generate new report'}</Btn>} />
    <div className="grid g3-2">
      <div>{!cur ? <Card><Empty title="No report open" sub="Generate a new one, or open an earlier report from the list." icon={<BadgeCheck size={22} />} /></Card> : <div className="stack">
        <Card><div className="row between wrap"><div><h3>Report {cur.id.slice(0, 8).toUpperCase()}</h3><div className="small muted">{new Date(cur.generated_at).toLocaleString()}</div></div><div className="row wrap"><StatusBadge s={cur.status} />
          <Btn size="sm" onClick={async () => download(await api.blob(`/api/verified-report/${cur.id}/pdf`), `EchoCare_Verified_Report_${cur.id.slice(0, 8)}.pdf`)}><FileDown size={14} />PDF (English)</Btn><Link to={`/verified-report/${cur.id}/print`} target="_blank"><Btn size="sm"><Printer size={14} />Printable ({lang.toUpperCase()})</Btn></Link></div></div>
          {qr && <div className="row" style={{ marginTop: 12 }}><img src={qr} alt="QR code to the public verification page" width={110} height={110} /><p className="small muted">Scanning shows only this report's ID, status, date and hash. No patient information.</p></div>}</Card>
        <ReportBody r={cur} /></div>}</div>
      <Card><CardHead title="Earlier reports" />{!list.data?.length ? <p className="small muted">None yet.</p> : list.data.map(r => <div key={r.id} className="row between" style={{ padding: '8px 0', borderTop: '1px solid var(--line)' }}><div><b className="small">{r.id.slice(0, 8).toUpperCase()}</b><div className="tiny faint">{fmtDate(r.generated_at)} · {r.summary_label}</div></div><Btn size="sm" onClick={() => openOld(r.id)}>Open</Btn></div>)}
        <Alert tone="info" title="Language">The PDF is in English. For Tamil or Hindi, use the printable page and “Save as PDF” in your browser.</Alert></Card></div></div>
}
