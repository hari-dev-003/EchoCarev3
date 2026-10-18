import { useState } from 'react'
import { BellRing, SlidersHorizontal, RotateCcw, Save } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useApp } from '../lib/store'
import { useFetch, fmtDate } from '../lib/hooks'
import { Alert, Badge, Btn, Card, CardHead, Empty, Field, Loading, PageHead, Stat } from '../components/ui'

const TONE: any = { urgent: 'bad', soon: 'warn', routine: 'info' }
const NAMES: Record<string, string> = { systolic_high: 'Systolic BP: raise a flag at or above (mmHg)', diastolic_high: 'Diastolic BP: flag at or above (mmHg)', systolic_urgent: 'Systolic BP: urgent at or above', diastolic_urgent: 'Diastolic BP: urgent at or above', fasting_sugar_high: 'Fasting sugar: flag at or above (mg/dL)', fasting_sugar_urgent: 'Fasting sugar: urgent at or above', postmeal_sugar_high: 'Post-meal sugar: flag at or above', spo2_low: 'Oxygen saturation: flag below (%)', spo2_urgent: 'Oxygen saturation: urgent below (%)', heart_rate_high: 'Heart rate: flag above (bpm)', heart_rate_low: 'Heart rate: flag below (bpm)', temperature_high: 'Temperature: flag at or above (°C)', sleep_low: 'Sleep: flag below (hours)', stress_high: 'Stress: flag at or above (0-10)', pain_high: 'Pain: flag at or above (0-10)', adherence_low: 'Medicine adherence: flag below (%)' }

export default function Alerts() {
  const { toast } = useApp(); const a = useFetch<any>('/api/alerts'); const [edit, setEdit] = useState<Record<string, string>>({})
  if (a.loading || !a.data) return <Loading rows={5} />
  const d = a.data; const val = (k: string) => edit[k] ?? String(d.thresholds[k])
  const save = async () => { try { await api.put('/api/alerts/thresholds', { thresholds: edit }); setEdit({}); toast('Thresholds saved', 'ok'); a.reload() } catch (e: any) { toast(e.message, 'bad') } }
  const reset = async () => { await api.del('/api/alerts/thresholds'); setEdit({}); toast('Back to defaults', 'ok'); a.reload() }
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Safety" title="Alerts" sub="Your readings from the last 14 days compared with thresholds you control. Each alert says how soon to act." />
    <div className="grid g3"><Stat label="Urgent" value={d.counts.urgent} tone={d.counts.urgent ? 'bad' : 'ok'} /><Stat label="Act within days" value={d.counts.soon} tone={d.counts.soon ? 'warn' : 'ok'} /><Stat label="Routine" value={d.counts.routine} /></div>
    <div className="grid g3-2">
      <Card><CardHead title="Current alerts" icon={<BellRing size={17} />} />{!d.items.length ? <Empty title="Nothing to flag" sub="No readings crossed your thresholds in the last 14 days." /> : <div className="stack" style={{ gap: 10 }}>{d.items.map((i: any) => <div key={i.key} className="card flat tight"><div className="row between wrap"><div><Badge tone={TONE[i.urgency]}>{i.urgency}</Badge> <b>{i.title}</b></div><span className="tiny faint">{fmtDate(i.date)}</span></div><div className="small" style={{ margin: '6px 0' }}>{i.detail}</div><div className="small muted">{i.guidance}</div><Link to={i.href} className="tiny">Open records</Link></div>)}</div>}
        <p className="tiny faint" style={{ marginTop: 12 }}>{d.disclaimer}</p></Card>
      <Card><CardHead title="Your thresholds" icon={<SlidersHorizontal size={17} />} right={<div className="row"><Btn size="sm" variant="ghost" onClick={reset}><RotateCcw size={13} />Defaults</Btn><Btn size="sm" variant="primary" disabled={!Object.keys(edit).length} onClick={save}><Save size={13} />Save</Btn></div>} />
        <Alert tone="info" title="Talk to your clinician">Defaults are general guide values. If a doctor gave you personal targets, enter them here.</Alert>
        <div className="stack" style={{ gap: 8, marginTop: 12, maxHeight: 460, overflow: 'auto' }}>{Object.keys(d.defaults).map(k => <Field key={k} label={NAMES[k] || k} hint={`allowed ${d.limits[k][0]} to ${d.limits[k][1]}`}><input className="input mono" type="number" step="any" value={val(k)} onChange={e => setEdit({ ...edit, [k]: e.target.value })} /></Field>)}</div></Card></div></div>
}
