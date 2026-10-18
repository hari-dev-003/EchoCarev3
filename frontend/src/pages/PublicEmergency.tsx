import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Phone, Siren } from 'lucide-react'
import { api } from '../lib/api'
import { Alert, Loading } from '../components/ui'

const FIELDS: [string, string][] = [['allergies', 'Allergies'], ['conditions', 'Chronic conditions'], ['medicines', 'Current medicines'], ['doctor', 'Family doctor'], ['notes', 'Notes']]
export default function PublicEmergency() {
  const { token } = useParams(); const [d, setD] = useState<any>(null); const [err, setErr] = useState('')
  useEffect(() => { api.get(`/api/public/emergency/${token}`).then(setD).catch(e => setErr(e.message)) }, [token])
  return <div style={{ maxWidth: 560, margin: '0 auto', padding: 20 }}>
    {err ? <Alert tone="bad" title="Not available">{err}</Alert> : !d ? <Loading /> : <div className="emergency-card"><header><Siren size={22} />EMERGENCY MEDICAL CARD</header><div style={{ padding: 22 }}>
      <h1>{d.name}</h1><div style={{ margin: '8px 0 16px' }}>Blood group <b style={{ color: 'var(--bad)', fontSize: 28, marginLeft: 6 }}>{d.blood_group || '—'}</b></div>
      <dl className="kv">{FIELDS.map(([k, l]) => <><dt key={k + 'd'}>{l}</dt><dd key={k}>{d[k] || '—'}</dd></>)}</dl>
      {d.contact_phone && <a className="btn primary" style={{ marginTop: 20, width: '100%', padding: 14 }} href={`tel:${d.contact_phone}`}><Phone size={17} />Call {d.contact_name || 'emergency contact'} · {d.contact_phone}</a>}
      <a className="btn danger" style={{ marginTop: 10, width: '100%', padding: 14 }} href="tel:112"><Siren size={17} />Call emergency services (112)</a></div></div>}
    <p className="disclaimer">Patient-supplied information. Verify with the patient or medical records when possible.</p></div>
}
