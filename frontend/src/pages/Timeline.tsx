import { useMemo, useState } from 'react'
import { fmtDate, useFetch } from '../lib/hooks'
import { Badge, Card, CardHead, Empty, Loading, PageHead, Seg } from '../components/ui'
import { BarsChart } from '../components/charts'

const TYPES: Record<string, string> = { story: 'Story', tracker: 'Tracker', vitals: 'Vitals', report: 'Report', appointment: 'Visit', opinion: 'Opinion' }
export default function Timeline() {
  const { data, loading } = useFetch<any[]>('/api/timeline'); const [f, setF] = useState('all')
  const list = (data || []).filter(e => f === 'all' || e.type === f)
  const byMonth = useMemo(() => { const m: Record<string, number> = {}; (data || []).forEach(e => { const k = e.date.slice(0, 7); m[k] = (m[k] || 0) + 1 }); return Object.entries(m).sort().map(([month, events]) => ({ month, events })) }, [data])
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Main" title="Health Timeline" sub="Everything on one line: stories, notes, vitals, reports, visits and specialist opinions." right={<Seg value={f} onChange={setF} options={[{ value: 'all', label: 'All' }, ...Object.entries(TYPES).map(([value, label]) => ({ value, label }))]} />} />
    <div className="grid g-main-r"><Card><CardHead title="Activity by month" /><BarsChart data={byMonth} x="month" series={[{ key: 'events', name: 'Events' }]} height={240} /></Card>
      <Card>{loading ? <Loading /> : !list.length ? <Empty title="Nothing on the timeline yet" /> : <div className="timeline">{list.slice(0, 80).map((e, i) => <div className="tl-item" key={i}><span className="tl-dot" />
        <div className="row wrap small"><b>{e.title}</b><Badge tone="info">{TYPES[e.type]}</Badge><span className="faint">{fmtDate(e.date)}</span></div>{e.detail && <p className="small muted" style={{ marginTop: 3 }}>{e.detail}</p>}<div className="row wrap" style={{ marginTop: 5 }}>{(e.tags || []).filter((t: string) => t !== 'general_wellbeing').map((t: string) => <span className="tag" key={t}>{t}</span>)}</div></div>)}</div>}</Card></div>
  </div>
}
