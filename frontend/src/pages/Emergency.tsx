import { useEffect, useState } from 'react'
import { Copy, Printer, RefreshCw, Save, Siren } from 'lucide-react'
import { api } from '../lib/api'
import { useApp } from '../lib/store'
import { useFetch } from '../lib/hooks'
import { Alert, Btn, Card, CardHead, Field, Loading, PageHead, Switch } from '../components/ui'
import { getToken } from '../lib/api'

const FIELDS: [string, string][] = [['blood_group', 'Blood group'], ['allergies', 'Allergies'], ['conditions', 'Chronic conditions'], ['medicines', 'Current medicines'], ['contact_name', 'Emergency contact'], ['contact_phone', 'Contact phone'], ['doctor', 'Family doctor'], ['notes', 'Other notes']]
export default function Emergency() {
  const { toast, profile } = useApp(); const { data, loading, reload } = useFetch<any>('/api/emergency/card'); const [f, setF] = useState<any>({}); const [qr, setQr] = useState('')
  useEffect(() => { if (data) { setF(data); api.blob('/api/emergency/qr').then(b => setQr(URL.createObjectURL(b))).catch(() => {}) } }, [data])
  const save = async () => { await api.put('/api/emergency/card', f); toast('Emergency card saved', 'ok'); reload() }
  if (loading || !data) return <Loading rows={5} />
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Care" title="Emergency card" sub="A one-page summary responders can open from the QR code. No login required, no account details exposed." right={<><Btn onClick={() => window.print()}><Printer size={16} />Print</Btn><Btn variant="primary" onClick={save}><Save size={16} />Save</Btn></>} />
    <div className="grid g-main">
      <Card className="no-print"><CardHead title="Details" sub={`For ${profile?.name}`} /><div className="form-grid">{FIELDS.map(([k, l]) => <Field key={k} label={l}>{k === 'notes' || k === 'medicines' || k === 'allergies' || k === 'conditions' ? <textarea className="textarea" style={{ minHeight: 70 }} value={f[k] || ''} onChange={e => setF({ ...f, [k]: e.target.value })} /> : <input className="input" value={f[k] || ''} onChange={e => setF({ ...f, [k]: e.target.value })} />}</Field>)}</div>
        <div className="row between" style={{ marginTop: 18 }}><div className="row"><Switch on={!!f.public_enabled} onChange={v => setF({ ...f, public_enabled: v })} label="Public link enabled" /><span className="small">Public link enabled</span></div><Btn size="sm" onClick={async () => { await api.post('/api/emergency/rotate'); toast('Link rotated. Old QR codes no longer work.', 'ok'); reload() }}><RefreshCw size={14} />Rotate link</Btn></div></Card>
      <div className="stack"><div className="emergency-card"><header><Siren size={22} />EMERGENCY MEDICAL CARD</header><div style={{ padding: 22 }}><div className="row between" style={{ alignItems: 'flex-start' }}><div><h2 style={{ fontSize: 22 }}>{profile?.name}</h2><div className="muted small">Blood group: <b style={{ color: 'var(--bad)', fontSize: 17 }}>{f.blood_group || '—'}</b></div></div>{qr && <img src={qr} alt="QR code to this emergency card" width={110} height={110} style={{ borderRadius: 10, background: '#fff', padding: 4 }} />}</div>
        <dl className="kv" style={{ marginTop: 16 }}>{FIELDS.slice(1).map(([k, l]) => <><dt key={k + 'd'}>{l}</dt><dd key={k}>{f[k] || '—'}</dd></>)}</dl></div></div>
        <Card className="no-print"><div className="row small"><span className="grow" style={{ wordBreak: 'break-all' }}>{data.public_url}</span><Btn size="sm" onClick={() => { navigator.clipboard?.writeText(data.public_url); toast('Link copied', 'ok') }}><Copy size={14} />Copy</Btn></div>{!f.public_enabled && <Alert tone="warn">The public link is switched off; the QR code will show “not available”.</Alert>}</Card></div></div>
  </div>
}
