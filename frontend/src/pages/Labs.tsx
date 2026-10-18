import { useEffect, useMemo, useState } from 'react'
import { FlaskConical } from 'lucide-react'
import { refText, shortDate, useFetch } from '../lib/hooks'
import { Badge, Card, CardHead, DataTable, Empty, Loading, PageHead, Stat } from '../components/ui'
import { TrendChart, BarsChart } from '../components/charts'

export default function Labs() {
  const { data, loading } = useFetch<any>('/api/labs/series'); const [sel, setSel] = useState('')
  const tests: string[] = data?.tests || []; useEffect(() => { if (tests.length && !tests.includes(sel)) setSel(tests[0]) }, [tests.join('|')])
  const pts: any[] = (data?.series?.[sel] || []).map((p: any) => ({ ...p, day: shortDate(p.date) })); const last = pts[pts.length - 1]
  const counts = useMemo(() => tests.map(t => { const p = data.series[t]; return { name: data.series[t][0].label, abnormal: p.filter((x: any) => x.out_of_range).length, normal: p.filter((x: any) => !x.out_of_range).length } }), [data])
  if (loading) return <Loading rows={5} />
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Record" title="Lab Trends" sub="Every numeric test across all reports, plotted over time against its reference range (green band)." />
    {!tests.length ? <Card><Empty title="No lab values yet" sub="Upload or enter a report to see trends." icon={<FlaskConical size={20} />} /></Card> : <>
      <div className="grid g4"><Stat label="Distinct tests" value={tests.length} icon={<FlaskConical size={15} />} /><Stat label="Out of range now" value={data.alerts.length} tone={data.alerts.length ? 'bad' : 'ok'} foot="latest reading per test" /><Stat label="Selected test" value={last?.value ?? '—'} unit={last?.unit || ''} foot={last ? (last.out_of_range ? <Badge tone="bad">{last.direction}</Badge> : <Badge tone="ok">in range</Badge>) : ''} /><Stat label="Readings" value={pts.length} foot="for this test" /></div>
      <div className="grid g-main">
        <Card><CardHead title="Trend" right={<select className="select" style={{ width: 'auto' }} value={sel} onChange={e => setSel(e.target.value)} aria-label="Select test">{tests.map(t => <option key={t} value={t}>{data.series[t][0].label}</option>)}</select>} />
          <TrendChart data={pts} x="day" area height={300} series={[{ key: 'value', name: last?.label || 'Value' }]} ref={{ low: last?.low, high: last?.high }} /></Card>
        <Card><CardHead title="Readings per test" sub="In range vs out of range" /><BarsChart data={counts} x="name" layout="vertical" stacked height={300} series={[{ key: 'normal', name: 'In range', color: 'var(--ok)' }, { key: 'abnormal', name: 'Out of range', color: 'var(--bad)' }]} /></Card></div>
      <Card><CardHead title="Out-of-range now" sub="Worth discussing with your clinician" /><DataTable rows={data.alerts.map((a: any, i: number) => ({ ...a, id: String(i) }))} searchable={false} cols={[{ key: 'label', label: 'Test', render: (a: any) => <b>{a.label}</b>, sort: (a: any) => a.label }, { key: 'value', label: 'Latest', render: (a: any) => `${a.value} ${a.unit || ''}` }, { key: 'ref', label: 'Reference', render: (a: any) => refText(a.low, a.high) }, { key: 'direction', label: 'Direction', render: (a: any) => <Badge tone="bad">{a.direction}</Badge> }, { key: 'trend', label: 'Trend', render: (a: any) => a.trend || '—' }, { key: 'date', label: 'Date' }]} empty="Everything is within range" /></Card></>}
  </div>
}
