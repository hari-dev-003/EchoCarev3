import { useState } from 'react'
import { AlertTriangle, ChevronDown, Info, Sparkles } from 'lucide-react'
import { api } from '../lib/api'
import { useApp } from '../lib/store'
import { fmtDate, useFetch } from '../lib/hooks'
import { Alert, Badge, Btn, Card, CardHead, Empty, Loading, PageHead, Progress, Stat, toneOf, Modal } from '../components/ui'
import { BarsChart, Donut, Legend2, Radar2 } from '../components/charts'

const LABEL: Record<string, string> = { similarity: 'Semantic similarity', source_diversity: 'Source diversity', occurrence_rate: 'Occurrence rate', temporal_consistency: 'Temporal consistency' }
const WEIGHT: Record<string, number> = { similarity: 40, source_diversity: 25, occurrence_rate: 20, temporal_consistency: 15 }

export default function Insights() {
  const { toast, lang } = useApp(); const ins = useFetch<any[]>('/api/insights'); const flags = useFetch<any[]>('/api/risk-flags'); const stats = useFetch<any>('/api/evidence/stats'); const ev = useFetch<any[]>('/api/evidence')
  const [busy, setBusy] = useState(false); const [why, setWhy] = useState<any>(null); const [gate, setGate] = useState<any>(null); const [q, setQ] = useState(''); const [hits, setHits] = useState<any>(null)
  const generate = async () => { setBusy(true); try { const r = await api.post(`/api/insights/generate?lang=${lang}`); setGate(r); toast(r.insights.length ? `${r.insights.length} insight(s) generated` : 'Evidence not yet sufficient', r.insights.length ? 'ok' : undefined); ins.reload() } catch (e: any) { toast(e.message, 'bad') } finally { setBusy(false) } }
  const search = async () => { if (q.trim()) setHits(await api.post('/api/evidence/search', { query: q, top_k: 6 })) }
  const src = Object.entries(stats.data?.by_source || {}).map(([name, value]) => ({ name, value: value as number }))
  const themeBars = (ins.data || []).map(i => ({ theme: i.theme, confidence: Math.round(i.confidence * 100) }))
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="AI & Safety" title="AI Insights" sub="LE-RAG: insights are produced only when your own evidence agrees across at least two source types. Every insight shows exactly how its confidence was computed." right={<Btn variant="primary" disabled={busy} onClick={generate}><Sparkles size={16} />{busy ? 'Analysing…' : 'Generate insights'}</Btn>} />
    <div className="grid g4"><Stat label="Evidence chunks" value={stats.data?.total ?? '—'} foot="stored in MongoDB" /><Stat label="Indexed in ChromaDB" value={stats.data?.indexed ?? '—'} foot="semantic vector index" /><Stat label="Insights" value={ins.data?.length ?? 0} icon={<Sparkles size={15} />} /><Stat label="Risk flags" value={flags.data?.length ?? 0} tone={flags.data?.length ? 'warn' : 'ok'} icon={<AlertTriangle size={15} />} /></div>
    {gate && !gate.insights.length && <Alert tone="info" icon={<Info size={18} />} title="Not enough corroborating evidence yet">The sufficiency gate needs at least {gate.gate.min_occurrences} mentions of a theme across {gate.gate.min_distinct_sources} different source types (e.g. story + survey + tracker note). Keep recording and try again.</Alert>}
    <div className="grid g-main">
      <div className="stack">{ins.loading ? <Loading rows={3} /> : !ins.data?.length ? <Card><Empty title="No insights yet" sub="Add a few stories, a survey and tracker notes, then generate." icon={<Sparkles size={20} />} action={<Btn variant="primary" onClick={generate} disabled={busy}>Generate now</Btn>} /></Card> :
        ins.data.map(i => <Card key={i.id} hover><div className="row between wrap"><div className="row"><span className="icon-chip"><Sparkles size={16} /></span><h3>{i.theme.replace('_', ' ')}</h3></div><Badge tone={i.confidence_label === 'high' ? 'ok' : i.confidence_label === 'moderate' ? 'warn' : undefined}>{i.confidence_label} · {Math.round(i.confidence * 100)}%</Badge></div>
          <p style={{ margin: '12px 0' }}>{i.text}</p><Progress value={i.confidence * 100} tone={i.confidence_label === 'high' ? 'ok' : 'warn'} />
          <div className="row between wrap small" style={{ marginTop: 10 }}><span className="faint">{i.evidence_summary} · {i.generated_by}</span><Btn size="sm" onClick={() => setWhy(i)}><ChevronDown size={14} />Why am I seeing this?</Btn></div></Card>)}</div>
      <div className="stack"><Card><CardHead title="Confidence by theme" />{themeBars.length ? <BarsChart data={themeBars} x="theme" layout="vertical" height={Math.max(160, themeBars.length * 48)} series={[{ key: 'confidence', name: 'Confidence %' }]} /> : <p className="muted small">Generate insights to see confidence by theme.</p>}</Card>
        <Card><CardHead title="Evidence by source" />{src.length ? <><Donut data={src} height={170} /><Legend2 data={src} /></> : <p className="muted small">No evidence yet.</p>}</Card></div></div>
    <div className="grid g2" style={{ alignItems: 'start' }}>
      <Card><CardHead title="Risk flags" sub="Cross-source discussion points" icon={<AlertTriangle size={17} />} />{!flags.data?.length ? <Empty title="Nothing flagged" /> : flags.data.map((f, i) => <div className="list-item" key={i}><Badge tone={toneOf(f.level)}>{f.level}</Badge><div><b className="small">{f.title}</b><div className="small muted">{f.detail}</div><div className="tiny faint">sources: {f.sources.join(', ')}</div></div></div>)}</Card>
      <Card><CardHead title="Semantic evidence search" sub="Query your own records through ChromaDB" />
        <div className="row"><input className="input" placeholder="e.g. my head throbs" value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && search()} /><Btn onClick={search}>Search</Btn></div>
        {hits && <div style={{ marginTop: 12 }}><div className="tiny faint" style={{ marginBottom: 6 }}>Retrieval: {hits.method}</div>{hits.results.map((r: any) => <div className="list-item" key={r.id}><Badge>{(r.similarity * 100).toFixed(0)}%</Badge><div className="small"><span className="tag">{r.source_type}</span> {r.text}</div></div>)}{!hits.results.length && <p className="muted small">No evidence found.</p>}</div>}</Card></div>
    <Card><CardHead title="Evidence log" sub="The raw, tagged chunks behind every insight" /><div className="table-wrap" style={{ maxHeight: 340, overflowY: 'auto' }}><table className="table"><thead><tr><th>Date</th><th>Source</th><th>Text</th><th>Tags</th><th>Index</th></tr></thead><tbody>{(ev.data || []).slice(0, 60).map(c => <tr key={c.id}><td className="small faint">{fmtDate(c.timestamp)}</td><td><span className="tag">{c.source_type}</span></td><td className="small">{c.text}</td><td>{c.theme_tags.map((t: string) => <span className="tag" key={t} style={{ marginRight: 4 }}>{t}</span>)}</td><td>{c.indexed ? <Badge tone="ok">chroma</Badge> : <Badge tone="warn">pending</Badge>}</td></tr>)}</tbody></table></div></Card>
    <Modal open={!!why} onClose={() => setWhy(null)} title="Why am I seeing this?" wide>{why && <div className="stack"><p className="muted small">Confidence is a weighted composite of four signals, so you can see which one drives it.</p>
      <div className="grid g2"><div className="stack">{Object.keys(WEIGHT).map(k => <div key={k}><div className="row between small"><span>{LABEL[k]} <span className="faint">(weight {WEIGHT[k]}%)</span></span><b className="mono">{Math.round((why.confidence_breakdown[k] || 0) * 100)}%</b></div><Progress value={(why.confidence_breakdown[k] || 0) * 100} /></div>)}
        <div className="divider" /><div className="small muted">Retrieval: <b>{why.confidence_breakdown.retrieval}</b><br />Evidence mentions: <b>{why.confidence_breakdown.evidence_count}</b> over <b>{why.confidence_breakdown.span_days}</b> days<br />Generated: {fmtDate(why.created_at)}</div></div>
        <Radar2 height={230} data={Object.keys(WEIGHT).map(k => ({ axis: LABEL[k].split(' ')[0], value: Math.round((why.confidence_breakdown[k] || 0) * 100) }))} /></div></div>}</Modal>
  </div>
}
