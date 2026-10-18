import { useEffect, useRef, useState } from 'react'
import { Check, Pause, Play, Plus, RefreshCw, Target, Timer, Trash2 } from 'lucide-react'
import { api } from '../lib/api'
import { useApp } from '../lib/store'
import { useFetch } from '../lib/hooks'
import { Badge, Btn, Card, CardHead, Confirm, Empty, Field, Loading, Modal, PageHead, Progress, Seg, Slideshow, Stat } from '../components/ui'
import { ScoreRing } from '../components/charts'

function Program({ p }: { p: any }) {
  const [left, setLeft] = useState(p.minutes * 60); const [run, setRun] = useState(false); const id = useRef<any>(null)
  useEffect(() => { if (!run) return; id.current = setInterval(() => setLeft(l => { if (l <= 1) { setRun(false); return 0 } return l - 1 }), 1000); return () => clearInterval(id.current) }, [run])
  const m = String(Math.floor(left / 60)).padStart(2, '0'), s = String(left % 60).padStart(2, '0')
  return <Card hover><div className="row between"><div><h3>{p.title}</h3><div className="small faint">{p.category} · {p.minutes} min</div></div><Badge tone="info">{m}:{s}</Badge></div>
    <ol className="small muted" style={{ paddingLeft: 18, margin: '12px 0', lineHeight: 1.8 }}>{p.steps.map((x: string) => <li key={x}>{x}</li>)}</ol>
    <div className="row"><Btn size="sm" variant={run ? undefined : 'primary'} onClick={() => setRun(!run)}>{run ? <><Pause size={14} />Pause</> : <><Play size={14} />{left === 0 ? 'Done' : 'Start'}</>}</Btn><Btn size="sm" variant="ghost" onClick={() => { setRun(false); setLeft(p.minutes * 60) }}><RefreshCw size={14} />Reset</Btn></div></Card>
}

export default function Wellness() {
  const { toast } = useApp(); const goals = useFetch<any[]>('/api/goals'); const learn = useFetch<any>('/api/learn'); const dash = useFetch<any>('/api/dashboard')
  const [open, setOpen] = useState(false); const [del, setDel] = useState<string | null>(null); const [cat, setCat] = useState('All'); const [f, setF] = useState<any>({ title: '', target: 7, unit: '', current: 0, metric: '' })
  const add = async () => { try { await api.post('/api/goals', { ...f, target: Number(f.target), current: Number(f.current), metric: f.metric || null }); setOpen(false); setF({ title: '', target: 7, unit: '', current: 0, metric: '' }); goals.reload() } catch (e: any) { toast(e.message, 'bad') } }
  const bump = async (g: any, d: number) => { await api.patch(`/api/goals/${g.id}`, { current: Math.max(0, +(g.current + d).toFixed(1)) }); goals.reload() }
  const sync = async () => { const w = dash.data?.week_avg; if (!w) return; const m: any = { sleep_hours: w.sleep, water_glasses: w.water }; let n = 0; for (const g of goals.data || []) if (g.metric && m[g.metric] != null) { await api.patch(`/api/goals/${g.id}`, { current: m[g.metric] }); n++ } toast(n ? `Synced ${n} goal(s) from your tracker` : 'No tracker-linked goals to sync', n ? 'ok' : undefined); goals.reload() }
  const list = goals.data || []; const done = list.filter(g => g.current >= g.target).length; const overall = list.length ? Math.round(list.reduce((a, g) => a + Math.min(1, g.current / g.target), 0) / list.length * 100) : 0
  const programs = (learn.data?.wellness || []).filter((p: any) => cat === 'All' || p.category === cat); const cats = ['All', ...Array.from(new Set((learn.data?.wellness || []).map((p: any) => p.category))) as string[]]
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="More" title="Wellness & goals" sub="Set measurable goals, sync them from your tracker, and use short guided programs with built-in timers." right={<><Btn onClick={sync}><RefreshCw size={16} />Sync from tracker</Btn><Btn variant="primary" onClick={() => setOpen(true)}><Plus size={16} />New goal</Btn></>} />
    <div className="grid g3"><Card><div className="row" style={{ gap: 18 }}><ScoreRing size={110} value={overall} label="overall" /><div><h3>Goal progress</h3><p className="small muted">{done} of {list.length} goals reached</p></div></div></Card><Stat label="Active goals" value={list.length} icon={<Target size={15} />} /><Stat label="Reached" value={done} tone="ok" icon={<Check size={15} />} /></div>
    {goals.loading ? <Loading /> : !list.length ? <Card><Empty title="No goals yet" icon={<Target size={20} />} action={<Btn variant="primary" onClick={() => setOpen(true)}>Create your first goal</Btn>} /></Card> :
      <div className="grid g3">{list.map(g => { const p = Math.min(100, g.current / g.target * 100); return <Card key={g.id} hover><div className="row between"><h3>{g.title}</h3><Btn variant="ghost" icon size="sm" onClick={() => setDel(g.id)} aria-label="Delete goal"><Trash2 size={15} /></Btn></div>
        <div style={{ margin: '12px 0 8px' }} className="row between small"><span className="mono"><b style={{ fontSize: 22 }}>{g.current}</b> / {g.target} {g.unit}</span><Badge tone={p >= 100 ? 'ok' : p >= 50 ? 'info' : 'warn'}>{Math.round(p)}%</Badge></div><Progress value={p} tone={p >= 100 ? 'ok' : p < 40 ? 'warn' : undefined} />
        <div className="row" style={{ marginTop: 12 }}><Btn size="sm" onClick={() => bump(g, -1)}>−1</Btn><Btn size="sm" onClick={() => bump(g, 1)}>+1</Btn>{g.metric && <span className="tiny faint">linked: {g.metric.replace('_', ' ')}</span>}</div></Card> })}</div>}
    <div className="row between wrap"><h2>Guided programs</h2><Seg value={cat} onChange={setCat} options={cats.map(c => ({ value: c, label: c }))} /></div>
    <div className="grid g3">{programs.map((p: any) => <Program key={p.id} p={p} />)}</div>
    <Slideshow height={150} slides={[{ icon: <Timer size={20} />, title: 'Small habits compound', body: 'Two minutes of breathing, a ten-minute walk and one glass of water, repeated daily, outperform occasional big efforts.' }, { icon: <Target size={20} />, title: 'Pick measurable targets', body: 'Link goals to tracker metrics (sleep, water) and use Sync to update them automatically.' }]} />
    <Modal open={open} onClose={() => setOpen(false)} title="New goal"><div className="stack"><Field label="Title"><input className="input" value={f.title} onChange={e => setF({ ...f, title: e.target.value })} placeholder="e.g. Sleep 7+ hours" /></Field><div className="form-grid"><Field label="Target"><input className="input" type="number" value={f.target} onChange={e => setF({ ...f, target: e.target.value })} /></Field><Field label="Unit"><input className="input" value={f.unit} onChange={e => setF({ ...f, unit: e.target.value })} placeholder="h/night" /></Field><Field label="Current"><input className="input" type="number" value={f.current} onChange={e => setF({ ...f, current: e.target.value })} /></Field><Field label="Link to tracker metric"><select className="select" value={f.metric} onChange={e => setF({ ...f, metric: e.target.value })}><option value="">None (manual)</option><option value="sleep_hours">Sleep hours</option><option value="water_glasses">Water glasses</option></select></Field></div><div className="row end"><Btn onClick={() => setOpen(false)}>Cancel</Btn><Btn variant="primary" disabled={!f.title.trim()} onClick={add}>Create</Btn></div></div></Modal>
    <Confirm open={!!del} title="Delete goal?" text="This cannot be undone." onNo={() => setDel(null)} onYes={async () => { await api.del(`/api/goals/${del}`); setDel(null); goals.reload() }} />
  </div>
}
