import { curLocale } from '../lib/translate'
import { useState } from 'react'
import { Check, Pill, Plus, Trash2 } from 'lucide-react'
import { api } from '../lib/api'
import { useApp } from '../lib/store'
import { shortDate, todayStr, useFetch } from '../lib/hooks'
import { Badge, Btn, Card, CardHead, Confirm, Empty, Field, Loading, Modal, PageHead, Progress, Stat } from '../components/ui'
import { BarsChart, ScoreRing } from '../components/charts'

const SLOTS = ['morning', 'afternoon', 'evening', 'night']
export default function Medicines() {
  const { toast } = useApp(); const meds = useFetch<any[]>('/api/medicines'); const doses = useFetch<any[]>('/api/medicines/doses?days=14'); const adh = useFetch<any>('/api/medicines/adherence')
  const [open, setOpen] = useState(false); const [del, setDel] = useState<string | null>(null); const [f, setF] = useState<any>({ name: '', dose: '', frequency: 'Daily', slots: ['morning'], notes: '' })
  const reloadAll = () => { meds.reload(); doses.reload(); adh.reload() }
  const taken = (mid: string, slot: string) => !!doses.data?.find(d => d.medicine_id === mid && d.slot === slot && d.log_date === todayStr() && d.taken)
  const toggle = async (mid: string, slot: string) => { await api.post('/api/medicines/dose', { medicine_id: mid, slot, taken: !taken(mid, slot) }); reloadAll() }
  const add = async () => { try { await api.post('/api/medicines', f); setOpen(false); setF({ name: '', dose: '', frequency: 'Daily', slots: ['morning'], notes: '' }); toast('Medicine added', 'ok'); reloadAll() } catch (e: any) { toast(e.message, 'bad') } }
  const active = (meds.data || []).filter(m => m.active); const todayTotal = active.reduce((a, m) => a + m.slots.length, 0); const todayDone = active.reduce((a, m) => a + m.slots.filter((s: string) => taken(m.id, s)).length, 0)
  const daily = (adh.data?.daily || []).map((d: any) => ({ day: shortDate(d.date), Taken: d.taken, Missed: Math.max(0, d.expected - d.taken) }))
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Record" title="Medicine Tracker" sub="Tick off each dose as you take it. Weekly adherence feeds your risk flags and the consultation report." right={<Btn variant="primary" onClick={() => setOpen(true)}><Plus size={16} />Add medicine</Btn>} />
    {meds.loading ? <Loading /> : <>
      <div className="grid g3"><Card><div className="row" style={{ gap: 18 }}><ScoreRing size={110} value={adh.data?.percent ?? 0} label="7-day" /><div><h3>Adherence</h3><p className="small muted">{adh.data?.taken ?? 0} of {adh.data?.expected ?? 0} doses logged</p></div></div></Card>
        <Stat label="Today" value={`${todayDone}/${todayTotal}`} icon={<Check size={15} />} tone={todayTotal && todayDone === todayTotal ? 'ok' : undefined} foot={<Progress value={todayTotal ? 100 * todayDone / todayTotal : 0} tone="ok" />} />
        <Stat label="Active medicines" value={active.length} icon={<Pill size={15} />} /></div>
      <div className="grid g-main">
        <Card><CardHead title="Today's doses" sub={new Date().toLocaleDateString(curLocale(), { weekday: 'long', day: 'numeric', month: 'long' })} />
          {!active.length ? <Empty title="No medicines yet" icon={<Pill size={20} />} /> : active.map(m => <div className="list-item" key={m.id}><span className="icon-chip"><Pill size={16} /></span><div className="grow"><b>{m.name}</b> <span className="muted small">{m.dose} · {m.frequency}</span>
            <div className="row wrap" style={{ marginTop: 8 }}>{m.slots.map((s: string) => { const on = taken(m.id, s); return <Btn key={s} size="sm" variant={on ? 'primary' : undefined} onClick={() => toggle(m.id, s)}>{on && <Check size={14} />}{s}</Btn> })}</div></div>
            <Btn variant="ghost" icon onClick={() => setDel(m.id)} aria-label="Delete"><Trash2 size={16} /></Btn></div>)}</Card>
        <Card><CardHead title="Last 7 days" sub="Doses taken vs missed" /><BarsChart data={daily} x="day" stacked height={260} series={[{ key: 'Taken', name: 'Taken', color: 'var(--ok)' }, { key: 'Missed', name: 'Missed', color: 'var(--bad)' }]} /></Card></div></>}
    <Modal open={open} onClose={() => setOpen(false)} title="Add medicine"><div className="stack"><div className="form-grid"><Field label="Name"><input className="input" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} /></Field><Field label="Dose"><input className="input" value={f.dose} onChange={e => setF({ ...f, dose: e.target.value })} placeholder="e.g. 500 mg" /></Field></div>
      <Field label="When do you take it?"><div className="seg">{SLOTS.map(s => <button key={s} className={f.slots.includes(s) ? 'on' : ''} onClick={() => setF({ ...f, slots: f.slots.includes(s) ? f.slots.filter((x: string) => x !== s) : [...f.slots, s] })}>{s}</button>)}</div></Field>
      <Field label="Notes"><input className="input" value={f.notes} onChange={e => setF({ ...f, notes: e.target.value })} /></Field><div className="row end"><Btn onClick={() => setOpen(false)}>Cancel</Btn><Btn variant="primary" disabled={!f.name || !f.slots.length} onClick={add}>Add</Btn></div></div></Modal>
    <Confirm open={!!del} title="Remove medicine?" text="Its dose history will be deleted too." onNo={() => setDel(null)} onYes={async () => { await api.del(`/api/medicines/${del}`); setDel(null); reloadAll() }} />
  </div>
}
