import { FormEvent, useEffect, useState } from 'react'
import { Activity, Brain, FileText, HeartPulse, Map, Moon, ShieldCheck, Sparkles, Sun, Siren } from 'lucide-react'
import { api } from '../lib/api'
import { useApp } from '../lib/store'
import { Btn, Field, Alert } from '../components/ui'

const SLIDES = [
  { icon: <Brain size={20} />, t: 'Longitudinal Evidence RAG', d: 'Insights only appear when your own records agree across sources, each with an explainable confidence score.' },
  { icon: <ShieldCheck size={20} />, t: 'Safety-first AI', d: 'An emergency guard runs before every message. No diagnoses, ever: only discussion points for your clinician.' },
  { icon: <Map size={20} />, t: 'District-wise doctor finder', d: 'Filter by specialty and district, rank by rating, experience and distance, and navigate in one tap.' },
  { icon: <FileText size={20} />, t: 'One-click consultation PDF', d: 'Walk into any appointment with your timeline, labs, vitals and medicines neatly organised.' },
]

export default function Login() {
  const { login, theme, toggleTheme } = useApp()
  const [mode, setMode] = useState<'login' | 'register'>('login'); const [f, setF] = useState({ name: '', email: '', password: '', consent_ai: false, consent_web: false })
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false); const [i, setI] = useState(0)
  useEffect(() => { const t = setInterval(() => setI(x => (x + 1) % SLIDES.length), 5000); return () => clearInterval(t) }, [])
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(''); setBusy(true)
    try { const r = await api.post(`/api/auth/${mode}`, mode === 'login' ? { email: f.email, password: f.password } : f); await login(r.token, r.user) }
    catch (x: any) { setErr(x.message) } finally { setBusy(false) }
  }
  return <div className="login-wrap">
    <div className="login-art">
      <div className="brand" style={{ color: '#fff' }}><span className="logo" style={{ background: 'rgba(255,255,255,.2)' }}><HeartPulse size={19} /></span>EchoCare</div>
      <div className="stack" style={{ gap: 22 }}>
        <div><div className="eyebrow" style={{ color: 'rgba(255,255,255,.75)' }}>AI healthcare companion</div><h1 style={{ color: '#fff', fontSize: 40, lineHeight: 1.1, maxWidth: 14 + 'ch' }}>Your health story, finally in one place.</h1>
          <p style={{ color: 'rgba(255,255,255,.85)', marginTop: 14, maxWidth: '48ch', fontSize: 15.5 }}>Track, understand and prepare: symptoms, vitals, labs and medicines, connected by evidence-grounded AI.</p></div>
        <div className="stack" style={{ gap: 10, minHeight: 190 }}>{SLIDES.map((s, k) => <div key={k} className="feature-pill" style={{ opacity: k === i ? 1 : .5, transform: k === i ? 'scale(1.02)' : 'none', transition: '.4s', alignItems: 'flex-start' }}>
          <span style={{ marginTop: 2 }}>{s.icon}</span><div><b>{s.t}</b>{k === i && <div style={{ fontWeight: 400, opacity: .9, marginTop: 2 }}>{s.d}</div>}</div></div>)}</div>
      </div>
      <div className="row small" style={{ opacity: .8 }}><Siren size={15} />In an emergency, call 112. EchoCare does not diagnose.</div>
    </div>
    <div className="login-form"><div className="box fade-in">
      <div className="row between" style={{ marginBottom: 22 }}><div><h1 style={{ fontSize: 24 }}>{mode === 'login' ? 'Welcome back' : 'Create your account'}</h1><p className="muted small" style={{ marginTop: 4 }}>{mode === 'login' ? 'Sign in to continue to EchoCare.' : 'Your records stay private to your account.'}</p></div>
        <Btn icon onClick={toggleTheme} aria-label="Toggle theme">{theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}</Btn></div>
      <form className="stack" onSubmit={submit}>
        {mode === 'register' && <Field label="Full name"><input className="input" required value={f.name} onChange={e => setF({ ...f, name: e.target.value })} autoComplete="name" /></Field>}
        <Field label="Email"><input className="input" type="email" required value={f.email} onChange={e => setF({ ...f, email: e.target.value })} autoComplete="email" /></Field>
        <Field label="Password" hint={mode === 'register' ? 'At least 8 characters' : undefined}><input className="input" type="password" required minLength={mode === 'register' ? 8 : 1} value={f.password} onChange={e => setF({ ...f, password: e.target.value })} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /></Field>
        {mode === 'register' && <div className="stack" style={{ gap: 8 }}><p className="small muted">Optional. You can change these any time in Privacy &amp; consent. Nothing is sent to an AI provider unless you agree.</p>
          <label className="row small" style={{ gap: 8, alignItems: 'flex-start' }}><input type="checkbox" checked={f.consent_ai} onChange={e => setF({ ...f, consent_ai: e.target.checked })} />Let EchoCare send my notes and reports to Google Gemini to generate insights and summaries.</label>
          <label className="row small" style={{ gap: 8, alignItems: 'flex-start' }}><input type="checkbox" checked={f.consent_web} onChange={e => setF({ ...f, consent_web: e.target.checked })} />Let Echo search the web (Tavily) when my records are not enough.</label></div>}
        {err && <Alert tone="bad">{err}</Alert>}
        <Btn variant="primary" type="submit" disabled={busy} style={{ padding: '12px' }}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}</Btn>
      </form>
      <p className="small muted" style={{ textAlign: 'center', marginTop: 18 }}>{mode === 'login' ? 'New to EchoCare?' : 'Already registered?'}{' '}<a href="#" onClick={e => { e.preventDefault(); setMode(mode === 'login' ? 'register' : 'login'); setErr('') }}>{mode === 'login' ? 'Create an account' : 'Sign in'}</a></p>
      <p className="tiny faint" style={{ textAlign: 'center', marginTop: 22 }}>The first account registered becomes the administrator.</p>
    </div></div>
  </div>
}
