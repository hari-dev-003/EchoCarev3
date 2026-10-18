import { useEffect, useRef, useState } from 'react'
import { Brain, Globe, Mic, Search, Send, ShieldCheck, Square, Trash2, Bot, MessageCircleQuestion } from 'lucide-react'
import { api } from '../lib/api'
import { useApp } from '../lib/store'
import { useFetch } from '../lib/hooks'
import { Alert, Avatar, Badge, Btn, Card, CardHead, PageHead } from '../components/ui'
import { useRecorder } from '../lib/recorder'

const TOOL: Record<string, { label: string; icon: JSX.Element }> = {
  safety_check: { label: 'Safety check', icon: <ShieldCheck size={12} /> }, followup: { label: 'Follow-up', icon: <MessageCircleQuestion size={12} /> }, rag_search: { label: 'RAG · ChromaDB', icon: <Search size={12} /> },
  web_search: { label: 'Web · Tavily', icon: <Globe size={12} /> }, gemini_generate: { label: 'Gemini', icon: <Brain size={12} /> },
}
const STARTERS = ['I have had a headache for 3 days, about 6/10, worse in the morning', 'What is a normal blood pressure range?', 'Summarise what my records say about my sleep', 'What should I ask my doctor about my recent labs?']

export default function Echo() {
  const { lang, toast, user } = useApp(); const hist = useFetch<any[]>('/api/chat'); const status = useFetch<any>('/api/ai/status')
  const [log, setLog] = useState<any[]>([]); const [text, setText] = useState(''); const [busy, setBusy] = useState(false); const end = useRef<HTMLDivElement>(null)
  useEffect(() => { if (hist.data) setLog(hist.data) }, [hist.data]); useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }) }, [log, busy])
  const rec = useRecorder(async blob => { try { const fd = new FormData(); fd.append('file', blob, 'v.wav'); const r = await api.form('/api/voice/transcribe', fd); if (r.ok) setText(r.text); else toast(r.reason || 'Transcription unavailable', 'bad') } catch (e: any) { toast(e.message, 'bad') } })
  const send = async (m = text) => {
    if (!m.trim() || busy) return; setText(''); setBusy(true); setLog(l => [...l, { id: 'tmp', role: 'user', content: m }])
    try { const r = await api.post('/api/chat', { message: m, lang }); setLog(l => [...l, { id: Date.now() + '', role: 'assistant', content: r.content, kind: r.kind, tools_used: r.tools_used, web_sources: r.web_sources, is_emergency: r.is_emergency, resources: r.resources, retrieval: r.retrieval }]) }
    catch (e: any) { toast(e.message, 'bad') } finally { setBusy(false) }
  }
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="AI & Safety" title="Echo, your AI companion" sub="A tool-using agent with an auditable policy: safety check first, follow-up questions, your own evidence via ChromaDB, optional web grounding via Tavily, then Gemini. It never diagnoses." right={<Btn onClick={async () => { await api.del('/api/chat'); setLog([]) }}><Trash2 size={15} />Clear chat</Btn>} />
    {status.data && !status.data.gemini && <Alert tone="info" title="Gemini is not configured">Echo will run safety checks, ask follow-ups and retrieve your evidence, but cannot write replies until GOOGLE_API_KEY is set in backend/.env.</Alert>}
    <div className="grid g-main">
      <Card className="chat" style={{ padding: 16 }}>
        <div className="chat-log">{!log.length && <div className="stack" style={{ margin: 'auto', textAlign: 'center', maxWidth: 480 }}><span className="icon-chip lg" style={{ margin: '0 auto' }}><Bot size={22} /></span><h2>Hi {user?.name.split(' ')[0]}, I'm Echo.</h2><p className="muted">Ask about your symptoms, trends or reports. Try one of these:</p><div className="row wrap" style={{ justifyContent: 'center' }}>{STARTERS.map(s => <Btn key={s} size="sm" onClick={() => send(s)}>{s.length > 46 ? s.slice(0, 44) + '…' : s}</Btn>)}</div></div>}
          {log.map((m, i) => <div key={m.id + i} className={`msg ${m.role === 'user' ? 'me' : ''}`}>{m.role !== 'user' && <Avatar name="Echo" />}<div><div className={`bubble ${m.is_emergency ? 'em' : ''}`}>{m.content}
            {m.is_emergency && m.resources && <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>{m.resources.map((r: any) => <li key={r.label}><b>{r.label}:</b> {r.value}</li>)}</ul>}</div>
            {m.role === 'assistant' && m.tools_used && <div className="row wrap" style={{ marginTop: 6, gap: 6 }}>{m.tools_used.map((t: string) => <Badge key={t}>{TOOL[t]?.icon}{TOOL[t]?.label || t}</Badge>)}</div>}
            {m.web_sources?.length > 0 && <div className="small" style={{ marginTop: 6 }}>{m.web_sources.map((w: any) => <div key={w.url}><a href={w.url} target="_blank" rel="noreferrer">{w.title}</a></div>)}</div>}</div></div>)}
          {busy && <div className="msg"><Avatar name="Echo" /><div className="bubble"><span className="spin" /></div></div>}<div ref={end} /></div>
        <div className="row" style={{ paddingTop: 10, borderTop: '1px solid var(--border)' }}>
          {rec.supported && <Btn icon onClick={rec.recording ? rec.stop : rec.start} variant={rec.recording ? 'danger' : undefined} aria-label="Voice input">{rec.recording ? <Square size={16} /> : <Mic size={17} />}</Btn>}
          <input className="input" placeholder="Ask Echo anything…" value={text} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && send()} aria-label="Message" /><Btn variant="primary" icon disabled={busy || !text.trim()} onClick={() => send()} aria-label="Send"><Send size={17} /></Btn></div>
      </Card>
      <div className="stack"><Card><CardHead title="Agent policy" sub="Deterministic and auditable" /><ol className="small muted" style={{ paddingLeft: 18, margin: 0, lineHeight: 1.9 }}><li><b>Safety check</b> on every message, always first</li><li><b>Follow-ups</b> for missing duration, severity or trigger (never twice in a row)</li><li><b>RAG</b> over your evidence in ChromaDB</li><li><b>Web</b> via Tavily only if the question needs it</li><li><b>Gemini</b> answers in your language, non-diagnostically</li></ol></Card>
        <Card><CardHead title="Tools" /><div className="stack" style={{ gap: 8 }}><div className="row between small"><span>Gemini</span><Badge tone={status.data?.gemini ? 'ok' : 'warn'}>{status.data?.gemini ? 'connected' : 'not configured'}</Badge></div><div className="row between small"><span>Tavily web search</span><Badge tone={status.data?.tavily ? 'ok' : 'warn'}>{status.data?.tavily ? 'connected' : 'not configured'}</Badge></div><div className="row between small"><span>ChromaDB vectors</span><Badge tone="ok">{status.data?.vector?.active_embedding_backend || '…'} embeddings</Badge></div></div></Card></div>
    </div></div>
}
