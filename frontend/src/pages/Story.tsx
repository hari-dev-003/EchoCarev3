import { useState } from 'react'
import { Mic, Plus, Square, Trash2, ScrollText } from 'lucide-react'
import { api } from '../lib/api'
import { fmtDate, useFetch } from '../lib/hooks'
import { useApp } from '../lib/store'
import { Badge, Btn, Card, CardHead, Confirm, Empty, Loading, PageHead, Stat } from '../components/ui'
import { EmergencyAlert, EmergencyInfo } from '../components/Emergency'
import { useRecorder } from '../lib/recorder'
import { Donut, Legend2 } from '../components/charts'

export default function Story() {
  const { toast } = useApp(); const { data, loading, reload } = useFetch<any[]>('/api/story'); const stats = useFetch<any>('/api/evidence/stats')
  const [text, setText] = useState(''); const [busy, setBusy] = useState(false); const [em, setEm] = useState<EmergencyInfo | null>(null); const [del, setDel] = useState<string | null>(null)
  const rec = useRecorder(async blob => { setBusy(true); try { const fd = new FormData(); fd.append('file', blob, 'voice.wav'); const r = await api.form('/api/voice/transcribe', fd); if (r.ok) setText(t => (t ? t + ' ' : '') + r.text); else toast(r.reason || 'Transcription unavailable', 'bad') } catch (e: any) { toast(e.message, 'bad') } finally { setBusy(false) } })
  const save = async () => {
    setBusy(true); setEm(null)
    try { const r = await api.post('/api/story', { text }); if (r.is_emergency) setEm(r); else { setText(''); toast('Story saved and indexed', 'ok'); reload(); stats.reload() } } catch (e: any) { toast(e.message, 'bad') } finally { setBusy(false) }
  }
  const themes = Object.entries(stats.data?.by_theme || {}).filter(([k]) => k !== 'general_wellbeing').map(([name, value]) => ({ name, value: value as number }))
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Record" title="My Story" sub="Describe what you're experiencing in your own words. Each entry is tagged by specialty, split into evidence chunks, and indexed for semantic search." />
    <div className="grid g-main">
      <Card><CardHead title="New entry" icon={<ScrollText size={17} />} />
        <div className="stack">{em && <EmergencyAlert info={em} />}
          <textarea className="textarea" style={{ minHeight: 150 }} placeholder="e.g. I've had a throbbing headache most afternoons for two weeks, usually after screen time…" value={text} onChange={e => setText(e.target.value)} />
          <div className="row between wrap"><div className="row">{rec.supported && <Btn onClick={rec.recording ? rec.stop : rec.start} variant={rec.recording ? 'danger' : undefined}>{rec.recording ? <><Square size={14} />Stop recording</> : <><Mic size={15} />Record voice</>}</Btn>}<span className="small faint">{text.length} / 4000</span></div>
            <Btn variant="primary" disabled={busy || text.trim().length < 3} onClick={save}><Plus size={16} />Save entry</Btn></div></div></Card>
      <div className="stack"><Stat label="Evidence chunks" value={stats.data?.total ?? '—'} foot={`${stats.data?.indexed ?? 0} indexed in ChromaDB`} />
        <Card><CardHead title="Themes so far" />{themes.length ? <><Donut data={themes} height={150} /><Legend2 data={themes} /></> : <p className="muted small">Tags appear after your first entry.</p>}</Card></div>
    </div>
    <Card><CardHead title="Your entries" sub={`${data?.length || 0} total`} />
      {loading ? <Loading /> : !data?.length ? <Empty title="No entries yet" sub="Your first entry starts the evidence trail." /> :
        data.map(e => <div className="list-item" key={e.id}><div className="grow"><div className="row wrap small" style={{ marginBottom: 6 }}><span className="faint">{fmtDate(e.created_at)}</span>{e.timeline && <Badge tone="info">{e.timeline}</Badge>}{e.extracted_symptoms.map((s: string) => <span className="tag" key={s}>{s.replace('_', ' ')}</span>)}</div><p>{e.text}</p></div>
          <Btn variant="ghost" icon onClick={() => setDel(e.id)} aria-label="Delete entry"><Trash2 size={16} /></Btn></div>)}</Card>
    <Confirm open={!!del} title="Delete entry?" text="This also removes its evidence from search." onNo={() => setDel(null)} onYes={async () => { await api.del(`/api/story/${del}`); setDel(null); reload(); stats.reload() }} />
  </div>
}
