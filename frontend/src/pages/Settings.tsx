import { useState } from 'react'
import { Download, KeyRound, Palette, Sparkles, Database, Trash2 } from 'lucide-react'
import { api, download } from '../lib/api'
import { useApp } from '../lib/store'
import { useFetch } from '../lib/hooks'
import { LANGS } from '../lib/i18n'
import { Alert, Badge, Btn, Card, CardHead, Field, PageHead, Seg, Switch } from '../components/ui'

export default function Settings() {
  const { user, theme, toggleTheme, lang, setLang, a11y, setA11y, toast, bump, profile } = useApp(); const status = useFetch<any>('/api/ai/status')
  const [pw, setPw] = useState({ current_password: '', new_password: '' })
  const change = async () => { try { await api.post('/api/auth/password', pw); setPw({ current_password: '', new_password: '' }); toast('Password updated', 'ok') } catch (e: any) { toast(e.message, 'bad') } }
  const exp = async () => { const d = await api.get('/api/export'); download(new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' }), `echocare_${profile?.name || 'profile'}.json`); toast('Export downloaded', 'ok') }
  const seed = async () => { if (!confirm('Replace this profile’s data with demo data?')) return; await api.post('/api/demo/seed'); toast('Demo data loaded', 'ok'); bump() }
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="More" title="Settings" sub="Appearance, accessibility, security, data and AI services." />
    <div className="grid g2">
      <Card><CardHead title="Appearance & accessibility" icon={<Palette size={17} />} /><div className="stack">
        <div className="row between"><span>Theme</span><Seg value={theme} onChange={v => v !== theme && toggleTheme()} options={[{ value: 'light', label: 'Light' }, { value: 'dark', label: 'Dark' }]} /></div>
        <div className="row between"><span>Language</span><Seg value={lang} onChange={setLang as any} options={LANGS.map(l => ({ value: l.code, label: l.label }))} /></div>
        <div className="row between"><span>Text size</span><Seg value={a11y.text} onChange={v => setA11y({ text: v })} options={[{ value: 'normal', label: 'Normal' }, { value: 'large', label: 'Large' }, { value: 'xlarge', label: 'Extra large' }]} /></div>
        <div className="row between"><div><div>High contrast</div><div className="tiny faint">Stronger borders and text colours</div></div><Switch on={a11y.contrast} onChange={v => setA11y({ contrast: v })} label="High contrast" /></div>
        <div className="row between"><div><div>Animations</div><div className="tiny faint">Turn off for reduced motion</div></div><Switch on={a11y.motion} onChange={v => setA11y({ motion: v })} label="Animations" /></div></div></Card>
      <Card><CardHead title="Account" icon={<KeyRound size={17} />} /><div className="stack"><div className="small"><b>{user?.name}</b><br /><span className="muted">{user?.email}</span> {user?.is_admin && <Badge tone="info">admin</Badge>}</div><Field label="Current password"><input className="input" type="password" value={pw.current_password} onChange={e => setPw({ ...pw, current_password: e.target.value })} autoComplete="current-password" /></Field><Field label="New password" hint="At least 8 characters"><input className="input" type="password" value={pw.new_password} onChange={e => setPw({ ...pw, new_password: e.target.value })} autoComplete="new-password" /></Field><Btn variant="primary" disabled={pw.new_password.length < 8 || !pw.current_password} onClick={change}>Update password</Btn></div></Card>
      <Card><CardHead title="AI & infrastructure" icon={<Sparkles size={17} />} sub="Configured in backend/.env" /><div className="stack" style={{ gap: 10 }}>
        {[['Google Gemini', status.data?.gemini], ['Tavily web search', status.data?.tavily], ['Department classifier', status.data?.classifier_trained]].map(([n, ok]: any) => <div key={n} className="row between small"><span>{n}</span><Badge tone={ok ? 'ok' : 'warn'}>{ok ? 'ready' : 'not configured'}</Badge></div>)}
        <div className="row between small"><span>ChromaDB embeddings</span><Badge tone="ok">{status.data?.vector?.active_embedding_backend || '…'}</Badge></div>
        {status.data && (!status.data.gemini || !status.data.tavily) && <Alert tone="info">Missing keys never produce fake output; the feature reports that it is not configured.</Alert>}</div></Card>
      <Card><CardHead title="Your data" icon={<Database size={17} />} sub={`For ${profile?.name}`} /><div className="stack"><Btn onClick={exp}><Download size={16} />Export profile data (JSON)</Btn><Btn onClick={seed}><Sparkles size={16} />Load demo data into this profile</Btn><p className="tiny faint">Retention, consent and account deletion are under Privacy &amp; consent.</p></div></Card>
    </div></div>
}
