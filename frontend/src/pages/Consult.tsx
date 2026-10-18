import { useState } from 'react'
import { FileDown, Printer } from 'lucide-react'
import { api, download } from '../lib/api'
import { useApp } from '../lib/store'
import { useFetch } from '../lib/hooks'
import { Alert, Btn, Card, CardHead, Loading, PageHead, Switch } from '../components/ui'

export default function Consult() {
  const { toast, profile } = useApp(); const secs = useFetch<Record<string, string>>('/api/consult/sections'); const [inc, setInc] = useState<Record<string, boolean>>({}); const [busy, setBusy] = useState(false)
  const on = (k: string) => inc[k] !== false
  const make = async () => { setBusy(true); try { const include = Object.fromEntries(Object.keys(secs.data || {}).map(k => [k, on(k)])); download(await api.blob('/api/consult/pdf', 'POST', { include }), 'EchoCare_Consultation_Summary.pdf'); toast('PDF downloaded', 'ok') } catch (e: any) { toast(e.message, 'bad') } finally { setBusy(false) } }
  if (!secs.data) return <Loading />
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Care" title="Consultation report" sub={`A clinician-friendly PDF for ${profile?.name}: your own recorded data, organised. Choose what to include.`} right={<Btn variant="primary" disabled={busy} onClick={make}><FileDown size={16} />{busy ? 'Building…' : 'Download PDF'}</Btn>} />
    <div className="grid g-main"><Card><CardHead title="Sections" sub={`${Object.keys(secs.data).filter(on).length} of ${Object.keys(secs.data).length} included`} />{Object.entries(secs.data).map(([k, label]) => <div key={k} className="list-item"><div className="grow"><b className="small">{label}</b></div><Switch on={on(k)} onChange={v => setInc({ ...inc, [k]: v })} label={label} /></div>)}</Card>
      <div className="stack"><Alert tone="info" title="What's inside">Tables for the survey, recent stories, tracker averages, vitals, out-of-range labs, medicines with adherence, insights with confidence, risk flags, recurring symptoms, appointments and goals.</Alert><Alert tone="warn" title="Not a diagnosis">The PDF states clearly that it contains patient-reported information to discuss with a licensed clinician.</Alert>
        <Card className="flat"><div className="row"><Btn onClick={() => window.print()}><Printer size={15} />Print this page</Btn><span className="small muted">Share the PDF by email or print it for your visit.</span></div></Card></div></div>
  </div>
}
