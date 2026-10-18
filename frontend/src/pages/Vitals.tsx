import { useState } from 'react'
import { HeartPulse, Plus, Trash2 } from 'lucide-react'
import { api } from '../lib/api'
import { useApp } from '../lib/store'
import { shortDate, useFetch, todayStr } from '../lib/hooks'
import { Badge, Btn, Card, CardHead, Confirm, DataTable, Field, Loading, Modal, PageHead, Stat, toneOf } from '../components/ui'
import { TrendChart } from '../components/charts'

const empty = { entry_date: todayStr(), weight_kg: '', height_cm: '', systolic: '', diastolic: '', heart_rate: '', fasting_sugar: '', postmeal_sugar: '', spo2: '', temperature_c: '' }
export default function Vitals() {
  const { toast } = useApp(); const { data, loading, reload } = useFetch<any>('/api/vitals'); const [open, setOpen] = useState(false); const [f, setF] = useState<any>(empty); const [del, setDel] = useState<string | null>(null)
  const items: any[] = data?.items || []; const last = items[items.length - 1]; const rows = items.map(r => ({ ...r, day: shortDate(r.entry_date), bmi: r.bmi }))
  const save = async () => { const body: any = { entry_date: f.entry_date }; Object.keys(f).forEach(k => { if (k !== 'entry_date' && f[k] !== '') body[k] = Number(f[k]) }); try { await api.post('/api/vitals', body); setOpen(false); setF(empty); toast('Vitals saved', 'ok'); reload() } catch (e: any) { toast(e.message, 'bad') } }
  const num = (k: string, label: string, step = 1) => <Field label={label}><input className="input" type="number" step={step} value={f[k]} onChange={e => setF({ ...f, [k]: e.target.value })} /></Field>
  const card = (label: string, val: any, unit: string, cat?: [string, string]) => <Stat label={label} value={val ?? '—'} unit={val != null ? unit : undefined} tone={cat && toneOf(cat[1])} foot={cat ? <Badge tone={toneOf(cat[1])}>{cat[0]}</Badge> : 'No data'} icon={<HeartPulse size={15} />} />
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Record" title="Vitals" sub="BMI, blood pressure and blood sugar, described against usual target ranges. Never a diagnosis." right={<Btn variant="primary" onClick={() => setOpen(true)}><Plus size={16} />Add reading</Btn>} />
    {loading ? <Loading rows={4} /> : <>
      <div className="grid g4">{card('BMI', last?.bmi, 'kg/m²', last?.bmi_cat)}{card('Blood pressure', last?.systolic ? `${last.systolic}/${last.diastolic}` : null, 'mmHg', last?.bp_cat)}{card('Fasting sugar', last?.fasting_sugar, 'mg/dL', last?.fasting_cat)}{card('Post-meal sugar', last?.postmeal_sugar, 'mg/dL', last?.postmeal_cat)}</div>
      <div className="grid g2">
        <Card><CardHead title="Blood pressure" sub="Systolic / diastolic (target: below 120/80)" /><TrendChart data={rows} x="day" height={250} series={[{ key: 'systolic', name: 'Systolic' }, { key: 'diastolic', name: 'Diastolic' }]} ref={{ low: 60, high: 120 }} domain={[50, 'auto']} /></Card>
        <Card><CardHead title="Blood sugar" sub="Fasting vs post-meal (mg/dL)" /><TrendChart data={rows} x="day" area height={250} series={[{ key: 'fasting_sugar', name: 'Fasting' }, { key: 'postmeal_sugar', name: 'Post-meal' }]} /></Card>
        <Card><CardHead title="Weight & BMI" /><TrendChart data={rows} x="day" height={230} series={[{ key: 'weight_kg', name: 'Weight (kg)' }, { key: 'bmi', name: 'BMI' }]} /></Card>
        <Card><CardHead title="Usual target ranges" sub="WHO / standard adult categories" /><div className="stack" style={{ gap: 12 }}>{(data?.targets || []).map((t: any) => <div key={t.name} className="list-item"><div><b>{t.name}</b> <Badge tone="ok">{t.target}</Badge><div className="small muted" style={{ marginTop: 3 }}>{t.note}</div></div></div>)}</div></Card></div>
      <Card><CardHead title="All readings" /><DataTable rows={[...items].reverse()} pageSize={8} cols={[{ key: 'entry_date', label: 'Date', sort: r => r.entry_date }, { key: 'weight_kg', label: 'Weight', render: r => r.weight_kg ? `${r.weight_kg} kg` : '—' }, { key: 'bmi', label: 'BMI', sort: r => r.bmi ?? 0, render: r => r.bmi ? <>{r.bmi} <Badge tone={toneOf(r.bmi_cat?.[1])}>{r.bmi_cat?.[0]}</Badge></> : '—' },
        { key: 'bp', label: 'BP', render: r => r.systolic ? <>{r.systolic}/{r.diastolic} <Badge tone={toneOf(r.bp_cat?.[1])}>{r.bp_cat?.[0]}</Badge></> : '—' }, { key: 'fasting_sugar', label: 'Fasting', render: r => r.fasting_sugar ?? '—' }, { key: 'postmeal_sugar', label: 'Post-meal', render: r => r.postmeal_sugar ?? '—' }, { key: 'heart_rate', label: 'HR', render: r => r.heart_rate ?? '—' },
        { key: 'x', label: '', render: r => <Btn variant="ghost" size="sm" icon onClick={() => setDel(r.id)} aria-label="Delete"><Trash2 size={15} /></Btn> }]} /></Card></>}
    <Modal open={open} onClose={() => setOpen(false)} title="Add vitals reading"><div className="form-grid">
      <Field label="Date"><input className="input" type="date" max={todayStr()} value={f.entry_date} onChange={e => setF({ ...f, entry_date: e.target.value })} /></Field>{num('weight_kg', 'Weight (kg)', 0.1)}{num('height_cm', 'Height (cm)')}{num('heart_rate', 'Heart rate (bpm)')}{num('systolic', 'Systolic (mmHg)')}{num('diastolic', 'Diastolic (mmHg)')}{num('fasting_sugar', 'Fasting sugar (mg/dL)')}{num('postmeal_sugar', 'Post-meal sugar (mg/dL)')}{num('spo2', 'SpO₂ (%)')}{num('temperature_c', 'Temperature (°C)', 0.1)}</div>
      <div className="row end" style={{ marginTop: 20 }}><Btn onClick={() => setOpen(false)}>Cancel</Btn><Btn variant="primary" onClick={save}>Save reading</Btn></div></Modal>
    <Confirm open={!!del} title="Delete reading?" text="This cannot be undone." onNo={() => setDel(null)} onYes={async () => { await api.del(`/api/vitals/${del}`); setDel(null); reload() }} />
  </div>
}
