import { useState } from 'react'
import { BarChart3, Lightbulb } from 'lucide-react'
import { shortDate, useFetch } from '../lib/hooks'
import { Alert, Card, CardHead, Empty, Loading, PageHead, Seg, Stat } from '../components/ui'
import { BarsChart, ComboChart, Donut, Heat, Legend2, TrendChart } from '../components/charts'

export default function Analytics() {
  const [days, setDays] = useState('90'); const { data, loading } = useFetch<any>(`/api/analytics?days=${days}`)
  if (loading && !data) return <Loading rows={6} />
  if (!data) return <Empty title="Analytics unavailable" />
  const weekly = data.weekly.map((w: any) => ({ ...w, wk: shortDate(w.week) })); const hm = data.theme_heatmap
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Main" title="Health analytics" sub="Patterns across your own logs: how sleep, stress, energy and pain move together, and which symptom themes recur by week." right={<Seg value={days} onChange={setDays} options={[{ value: '30', label: '30 days' }, { value: '90', label: '90 days' }, { value: '180', label: '6 months' }]} />} />
    <div className="grid g4"><Stat label="Days logged" value={data.days_logged} icon={<BarChart3 size={15} />} /><Stat label="Weeks analysed" value={data.weekly.length} /><Stat label="Themes tracked" value={hm.rows.length} /><Stat label="Evidence sources" value={data.sources.length} /></div>
    {data.observations.length > 0 && <Alert tone="info" icon={<Lightbulb size={18} />} title="Observations">{data.observations.map((o: string) => <div key={o}>{o}</div>)}<div className="tiny faint" style={{ marginTop: 4 }}>{data.note}</div></Alert>}
    <div className="grid g-main"><Card><CardHead title="Weekly averages" sub="Sleep, energy and stress by week" /><TrendChart data={weekly} x="wk" area height={290} series={[{ key: 'sleep_hours', name: 'Sleep (h)' }, { key: 'energy_level', name: 'Energy' }, { key: 'stress_level', name: 'Stress' }]} /></Card>
      <Card><CardHead title="Mood mix" />{data.moods.length ? <><Donut data={data.moods.map((m: any) => ({ name: m.mood, value: m.count }))} height={190} /><Legend2 data={data.moods.map((m: any) => ({ name: m.mood, value: m.count }))} /></> : <Empty title="No moods logged" />}</Card></div>
    <div className="grid g2"><Card><CardHead title="Correlation matrix" sub="Pearson r between daily metrics (needs 5+ days)" /><Heat rows={data.labels} cols={data.labels} signed values={data.correlation.map((r: (number | null)[]) => r.map(v => v == null ? null : +v.toFixed(2)))} fmt={n => n.toFixed(1)} /></Card>
      <Card><CardHead title="Pain & water vs steps" sub="Weekly" /><ComboChart data={weekly} x="wk" height={250} bars={[{ key: 'water_glasses', name: 'Water', color: 'var(--c2)' }, { key: 'pain_level', name: 'Pain', color: 'var(--c4)' }]} lines={[{ key: 'steps', name: 'Steps', color: 'var(--c3)' }]} /></Card></div>
    <Card><CardHead title="Symptom themes by week" sub="Evidence mentions per specialty theme" />{hm.rows.length ? <Heat rows={hm.rows.map((r: any) => r.theme)} cols={hm.weeks.map((w: string) => shortDate(w))} values={hm.rows.map((r: any) => r.counts.map((c: number) => c || null))} /> : <Empty title="No symptom themes yet" />}</Card>
    <div className="grid g2"><Card><CardHead title="Where your evidence comes from" /><BarsChart data={data.sources.map((s: any) => ({ s: s.source, n: s.count }))} x="s" height={230} series={[{ key: 'n', name: 'Chunks' }]} colorByRow /></Card>
      <Card><CardHead title="Sleep vs stress" sub="Weekly averages" /><TrendChart data={weekly} x="wk" height={230} series={[{ key: 'sleep_hours', name: 'Sleep (h)' }, { key: 'stress_level', name: 'Stress' }]} /></Card></div>
  </div>
}
