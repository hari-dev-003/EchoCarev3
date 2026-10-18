import { useEffect, useState } from 'react'
import { Droplets, Flame, Moon, Save, Smile, Zap, Footprints } from 'lucide-react'
import { api } from '../lib/api'
import { useApp } from '../lib/store'
import { shortDate, todayStr, useFetch } from '../lib/hooks'
import { Btn, Card, CardHead, DataTable, Field, Loading, PageHead, Stat, Seg } from '../components/ui'
import { BarsChart, ComboChart, TrendChart } from '../components/charts'
import { EmergencyAlert, EmergencyInfo } from '../components/Emergency'

const MOODS = ['happy', 'calm', 'focused', 'tired', 'anxious', 'sad']
export default function Tracker() {
  const { toast } = useApp(); const [range, setRange] = useState('30'); const { data, loading, reload } = useFetch<any[]>(`/api/tracker?days=${range}`)
  const [f, setF] = useState<any>({ entry_date: todayStr(), sleep_hours: 7, water_glasses: 6, stress_level: 4, energy_level: 6, pain_level: 1, steps: 5000, mood: 'calm', notes: '' }); const [em, setEm] = useState<EmergencyInfo | null>(null)
  useEffect(() => { const e = data?.find(r => r.entry_date === f.entry_date); if (e) setF({ ...f, ...e, notes: e.notes || '' }) }, [data, f.entry_date])
  const save = async () => { setEm(null); try { const r = await api.post('/api/tracker', { ...f, notes: f.notes || null }); if (r.is_emergency) setEm(r); else { toast('Check-in saved', 'ok'); reload() } } catch (e: any) { toast(e.message, 'bad') } }
  const rows = (data || []).map(r => ({ ...r, day: shortDate(r.entry_date) })); const avg = (k: string) => { const v = rows.map(r => r[k]).filter((x: any) => x != null); return v.length ? (v.reduce((a: number, b: number) => a + b, 0) / v.length).toFixed(1) : '—' }
  const slider = (k: string, label: string, min: number, max: number, step = 1, unit = '') => <Field label={`${label}: ${f[k]}${unit}`}><input className="range" type="range" min={min} max={max} step={step} value={f[k] ?? min} onChange={e => setF({ ...f, [k]: Number(e.target.value) })} /></Field>
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Record" title="Daily Tracker" sub="A 30-second check-in. Consistent logging unlocks pattern detection and your wellness score." right={<Seg value={range} onChange={setRange} options={[{ value: '14', label: '14d' }, { value: '30', label: '30d' }, { value: '90', label: '90d' }]} />} />
    <div className="grid g4"><Stat label="Avg sleep" value={avg('sleep_hours')} unit="h" icon={<Moon size={15} />} /><Stat label="Avg energy" value={avg('energy_level')} unit="/10" icon={<Zap size={15} />} /><Stat label="Avg stress" value={avg('stress_level')} unit="/10" icon={<Flame size={15} />} tone="warn" /><Stat label="Avg water" value={avg('water_glasses')} unit="glasses" icon={<Droplets size={15} />} /></div>
    <div className="grid g-main-r">
      <Card><CardHead title="Check-in" sub="Pick a date to view or edit that day" />
        <div className="stack">{em && <EmergencyAlert info={em} />}
          <Field label="Date"><input className="input" type="date" max={todayStr()} value={f.entry_date} onChange={e => setF({ ...f, entry_date: e.target.value })} /></Field>
          {slider('sleep_hours', 'Sleep', 0, 14, 0.5, ' h')}{slider('water_glasses', 'Water', 0, 15, 1, ' glasses')}{slider('stress_level', 'Stress', 0, 10)}{slider('energy_level', 'Energy', 0, 10)}{slider('pain_level', 'Pain', 0, 10)}
          <Field label="Steps"><input className="input" type="number" min={0} value={f.steps ?? ''} onChange={e => setF({ ...f, steps: e.target.value === '' ? null : Number(e.target.value) })} /></Field>
          <Field label="Mood"><div className="seg">{MOODS.map(m => <button key={m} className={f.mood === m ? 'on' : ''} onClick={() => setF({ ...f, mood: m })}>{m}</button>)}</div></Field>
          <Field label="Notes (optional, indexed as evidence)"><textarea className="textarea" style={{ minHeight: 80 }} value={f.notes} onChange={e => setF({ ...f, notes: e.target.value })} placeholder="Anything notable today?" /></Field>
          <Btn variant="primary" onClick={save}><Save size={16} />Save check-in</Btn></div></Card>
      <div className="stack">
        <Card><CardHead title="Sleep & energy" icon={<Moon size={17} />} />{loading ? <Loading /> : <TrendChart data={rows} x="day" area height={230} series={[{ key: 'sleep_hours', name: 'Sleep (h)' }, { key: 'energy_level', name: 'Energy /10' }]} />}</Card>
        <div className="grid g2">
          <Card><CardHead title="Stress vs pain" />{<TrendChart data={rows} x="day" height={200} series={[{ key: 'stress_level', name: 'Stress' }, { key: 'pain_level', name: 'Pain' }]} />}</Card>
          <Card><CardHead title="Water & steps" icon={<Footprints size={17} />} /><ComboChart data={rows} x="day" height={200} bars={[{ key: 'water_glasses', name: 'Water (glasses)', color: 'var(--c2)' }]} lines={[{ key: 'steps', name: 'Steps', color: 'var(--c3)' }]} /></Card></div>
      </div></div>
    <Card><CardHead title="History" sub="Sortable, filterable log" /><DataTable rows={[...rows].reverse()} pageSize={8} cols={[
      { key: 'entry_date', label: 'Date', sort: r => r.entry_date }, { key: 'sleep_hours', label: 'Sleep', sort: r => r.sleep_hours ?? 0, render: r => r.sleep_hours != null ? `${r.sleep_hours} h` : '—' }, { key: 'energy_level', label: 'Energy', sort: r => r.energy_level ?? 0 },
      { key: 'stress_level', label: 'Stress', sort: r => r.stress_level ?? 0 }, { key: 'pain_level', label: 'Pain', sort: r => r.pain_level ?? 0 }, { key: 'water_glasses', label: 'Water' }, { key: 'steps', label: 'Steps' }, { key: 'mood', label: 'Mood', render: r => r.mood ? <span className="tag">{r.mood}</span> : '—' }, { key: 'notes', label: 'Notes', render: r => <span className="small muted">{(r.notes || '').slice(0, 50)}</span> }]} /></Card>
  </div>
}
