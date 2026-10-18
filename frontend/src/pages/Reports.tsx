import { useRef, useState } from 'react'
import { FileText, Plus, Trash2, Upload } from 'lucide-react'
import { api } from '../lib/api'
import { useApp } from '../lib/store'
import { fmtDate, useFetch, todayStr } from '../lib/hooks'
import { StatusBadge } from '../components/trust'
import { Alert, Badge, Btn, Card, CardHead, Confirm, Empty, Field, Loading, Modal, PageHead } from '../components/ui'

export default function Reports() {
  const { toast } = useApp(); const { data, loading, reload } = useFetch<any[]>('/api/reports'); const status = useFetch<any>('/api/ai/status'); const file = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false); const [del, setDel] = useState<string | null>(null); const [open, setOpen] = useState(false); const [sel, setSel] = useState<any>(null)
  const [m, setM] = useState({ title: '', report_date: todayStr(), rows: [{ test: '', value: '', unit: '', reference_range: '' }] })
  const upload = async (f: File) => { setBusy(true); try { const fd = new FormData(); fd.append('file', f); const r = await api.form('/api/reports', fd); toast(`${r.fields.length} values extracted via ${r.method}`, r.fields.length ? 'ok' : undefined); if (r.note) toast(r.note, 'bad'); reload() } catch (e: any) { toast(e.message, 'bad') } finally { setBusy(false); if (file.current) file.current.value = '' } }
  const saveManual = async () => { try { await api.post('/api/reports/manual', { title: m.title || 'Manual entry', report_date: m.report_date, fields: m.rows.filter(r => r.test && r.value) }); setOpen(false); toast('Report saved', 'ok'); reload() } catch (e: any) { toast(e.message, 'bad') } }
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Record" title="Medical Reports" sub="Upload a lab report (PDF or photo). Gemini Vision reads the values; without a key we fall back to PDF text / OCR, or you can enter values by hand." right={<><Btn onClick={() => setOpen(true)}><Plus size={16} />Enter manually</Btn><Btn variant="primary" disabled={busy} onClick={() => file.current?.click()}><Upload size={16} />{busy ? 'Reading…' : 'Upload report'}</Btn><input ref={file} hidden type="file" accept=".pdf,.png,.jpg,.jpeg,.webp" onChange={e => e.target.files?.[0] && upload(e.target.files[0])} /></>} />
    {status.data && !status.data.gemini && <Alert tone="info" title="Gemini Vision is not configured">Add GOOGLE_API_KEY to backend/.env for AI extraction from scans. Digital PDFs still work through text extraction.</Alert>}
    {loading ? <Loading /> : !data?.length ? <Card><Empty title="No reports yet" sub="Upload your first lab report to start tracking trends." icon={<FileText size={20} />} /></Card> :
      <div className="grid g2">{data.map(r => { const out = r.fields.filter((f: any) => f.out_of_range).length; return <Card key={r.id} hover><div className="row between"><div className="row"><span className="icon-chip"><FileText size={16} /></span><div><h3>{r.title}</h3><div className="small faint">{fmtDate(r.report_date)} · {r.method}</div></div></div><Btn variant="ghost" icon onClick={() => setDel(r.id)} aria-label="Delete"><Trash2 size={16} /></Btn></div>
        <div className="row wrap" style={{ margin: '12px 0' }}><Badge>{r.fields.length} values</Badge><Badge tone={out ? 'bad' : 'ok'}>{out} out of range</Badge><StatusBadge s={r.verification?.status || 'Unverified'} /></div>{r.summary && <p className="small muted">{r.summary}</p>}
        <Btn size="sm" style={{ marginTop: 12 }} onClick={() => setSel(r)}>View values</Btn></Card> })}</div>}
    <Modal open={!!sel} onClose={() => setSel(null)} title={sel?.title || ''} wide>{sel && <div className="table-wrap"><table className="table"><thead><tr><th>Test</th><th>Value</th><th>Unit</th><th>Reference</th><th>Status</th></tr></thead><tbody>{sel.fields.map((f: any, i: number) => <tr key={i}><td><b>{f.test}</b></td><td className="mono">{f.value}</td><td>{f.unit || '—'}</td><td className="mono muted">{f.reference_range || '—'}</td><td>{f.out_of_range ? <Badge tone="bad">out of range</Badge> : <Badge tone="ok">ok</Badge>}</td></tr>)}</tbody></table></div>}</Modal>
    <Modal open={open} onClose={() => setOpen(false)} title="Enter report values" wide><div className="stack"><div className="form-grid"><Field label="Title"><input className="input" value={m.title} onChange={e => setM({ ...m, title: e.target.value })} placeholder="e.g. CBC, Lipid profile" /></Field><Field label="Report date"><input className="input" type="date" value={m.report_date} onChange={e => setM({ ...m, report_date: e.target.value })} /></Field></div>
      {m.rows.map((r, i) => <div className="grid g4" key={i}>{(['test', 'value', 'unit', 'reference_range'] as const).map(k => <input key={k} className="input" placeholder={k === 'reference_range' ? 'Reference e.g. 12-15.5' : k[0].toUpperCase() + k.slice(1)} value={r[k]} onChange={e => { const rows = [...m.rows]; rows[i] = { ...r, [k]: e.target.value }; setM({ ...m, rows }) }} />)}</div>)}
      <div className="row between"><Btn size="sm" onClick={() => setM({ ...m, rows: [...m.rows, { test: '', value: '', unit: '', reference_range: '' }] })}><Plus size={14} />Add row</Btn><Btn variant="primary" onClick={saveManual}>Save report</Btn></div></div></Modal>
    <Confirm open={!!del} title="Delete report?" text="Its values will disappear from lab trends." onNo={() => setDel(null)} onYes={async () => { await api.del(`/api/reports/${del}`); setDel(null); reload() }} />
  </div>
}
