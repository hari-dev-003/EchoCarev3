import { useState } from 'react'
import { LockKeyhole, ScrollText, Download, Trash2, Database, ShieldAlert } from 'lucide-react'
import { api, download } from '../lib/api'
import { useApp } from '../lib/store'
import { useFetch, fmtDate } from '../lib/hooks'
import { Alert, Badge, Btn, Card, CardHead, DataTable, Field, Loading, Modal, PageHead, Seg, Stat, Switch } from '../components/ui'

const WHAT: Record<string, string> = { ai_processing: 'Use Google Gemini', web_search: 'Allow web search (Tavily)', caregiver_sharing: 'Allow caregiver sharing and share links' }

function Controls() {
  const { toast, logout } = useApp(); const p = useFetch<any>('/api/privacy'); const hist = useFetch<any[]>('/api/privacy/consents'); const [del, setDel] = useState(false); const [txt, setTxt] = useState(''); const [acct, setAcct] = useState(false)
  if (p.loading || !p.data) return <Loading rows={5} />
  const d = p.data; const s = d.settings
  const set = async (patch: any) => { try { const r = await api.put('/api/privacy', patch); p.setData({ ...d, settings: r.settings }); hist.reload(); toast('Saved', 'ok') } catch (e: any) { toast(e.message, 'bad') } }
  const wipe = async () => { try { await api.post('/api/privacy/delete-all', { confirm: txt, delete_account: acct }); toast('Your data was erased', 'ok'); setDel(false); acct ? logout() : p.reload() } catch (e: any) { toast(e.message, 'bad') } }
  return <div className="stack" style={{ gap: 20 }}>
    <div className="grid g3"><Stat label="Records held" value={Object.values(d.data_counts).reduce((a: any, b: any) => a + b, 0) as number} icon={<Database size={18} />} /><Stat label="Files in vault" value={d.stored_files} foot={`${(d.stored_bytes / 1048576).toFixed(1)} MB`} /><Stat label="AI processing" value={s.ai_processing ? 'On' : 'Off'} tone={s.ai_processing ? 'warn' : 'ok'} /></div>
    <div className="grid g2">
      <Card><CardHead title="Consent" sub="Nothing leaves your database for an AI provider unless you switch it on." icon={<LockKeyhole size={17} />} />
        <div className="stack">{(['ai_processing', 'web_search', 'caregiver_sharing'] as const).map(k => <div key={k} className="card flat tight"><div className="row between"><div><b>{WHAT[k]}</b><div className="small muted">{d.consent_text[k]}</div>{k === 'ai_processing' && !d.ai_key_present && <div className="tiny faint">No Gemini key is configured on this server, so this has no effect yet.</div>}{k === 'web_search' && !d.web_key_present && <div className="tiny faint">No Tavily key is configured on this server.</div>}</div><Switch on={!!s[k]} onChange={v => set({ [k]: v })} label={WHAT[k]} /></div></div>)}</div>
        <div className="stack" style={{ marginTop: 14 }}>{d.notes.map((n: string) => <p key={n} className="small muted">• {n}</p>)}</div></Card>
      <div className="stack">
        <Card><CardHead title="Keep data for" sub="Older tracker entries, vitals, story entries, chat and dose logs are removed automatically at sign-in." icon={<ShieldAlert size={17} />} />
          <Field label="Retention"><select className="select" value={s.retention_days ?? ''} onChange={e => set({ retention_days: e.target.value ? +e.target.value : null })}><option value="">Keep until I delete them</option>{[[90, '3 months'], [180, '6 months'], [365, '1 year'], [730, '2 years'], [1825, '5 years']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
          <div className="row" style={{ marginTop: 10 }}><Btn size="sm" onClick={async () => { const r = await api.post('/api/privacy/retention/run'); toast(r.enabled ? `Removed ${Object.values(r.deleted).reduce((a: any, b: any) => a + b, 0)} old records` : 'Retention is off', 'ok'); p.reload() }}>Apply now</Btn></div></Card>
        <Card><CardHead title="Your data" icon={<Download size={17} />} />
          <p className="small muted">Everything you have stored for the active profile as a JSON file.</p>
          <div className="row wrap" style={{ marginTop: 10 }}><Btn onClick={async () => download(await api.blob('/api/export'), 'echocare-export.json')}><Download size={15} />Download my data</Btn><Btn variant="danger" onClick={() => setDel(true)}><Trash2 size={15} />Erase all my data</Btn></div></Card>
        <Card><CardHead title="Consent history" />{!hist.data?.length ? <p className="small muted">No changes yet.</p> : hist.data.slice(0, 6).map(h => <div key={h.id} className="row between small" style={{ padding: '6px 0', borderTop: '1px solid var(--line)' }}><span>{WHAT[h.purpose] || h.purpose}</span><span><Badge tone={h.granted ? 'ok' : 'bad'}>{h.granted ? 'granted' : 'withdrawn'}</Badge> <span className="tiny faint">{fmtDate(h.created_at)}</span></span></div>)}</Card></div></div>
    <Modal open={del} onClose={() => setDel(false)} title="Erase all my data"><div className="stack"><Alert tone="bad" title="This cannot be undone">All stories, vitals, reports, files, insights, shares and links for every profile in this account are removed, including the ChromaDB vectors.</Alert>
      <label className="row small" style={{ gap: 8 }}><input type="checkbox" checked={acct} onChange={e => setAcct(e.target.checked)} />Also delete my account and sign me out</label>
      <Field label="Type DELETE to confirm"><input className="input mono" value={txt} onChange={e => setTxt(e.target.value)} /></Field><div className="row end"><Btn onClick={() => setDel(false)}>Cancel</Btn><Btn variant="danger" disabled={txt !== 'DELETE'} onClick={wipe}>Erase</Btn></div></div></Modal></div>
}

function Audit() {
  const [who, setWho] = useState('all'); const a = useFetch<any[]>('/api/privacy/audit?limit=300')
  if (a.loading || !a.data) return <Loading rows={5} />
  const rows = a.data.filter(r => who === 'all' || (who === 'others' ? !r.by_me : r.by_me))
  return <Card><CardHead title="Audit trail" sub="Who did what on your account and your profiles, newest first. Caregiver access appears as “others”." icon={<ScrollText size={17} />} right={<Seg value={who} onChange={setWho} options={[{ value: 'all', label: 'All' }, { value: 'me', label: 'By me' }, { value: 'others', label: 'By others' }]} />} />
    <DataTable rows={rows} pageSize={12} cols={[{ key: 'created_at', label: 'When', sort: (r: any) => r.created_at, render: (r: any) => new Date(r.created_at).toLocaleString() }, { key: 'email', label: 'Who', sort: (r: any) => r.email || '', render: (r: any) => r.by_me ? 'You' : (r.email || 'System') }, { key: 'action', label: 'Action', sort: (r: any) => r.action, render: (r: any) => <Badge tone={r.action.includes('delete') || r.action.includes('revoke') ? 'warn' : undefined}>{r.action.replace(/_/g, ' ')}</Badge> }, { key: 'profile_name', label: 'Profile', render: (r: any) => r.profile_name || '—' }, { key: 'detail', label: 'Detail', render: (r: any) => <span className="small muted">{r.detail}</span> }]} /></Card>
}

export default function Privacy() {
  const [tab, setTab] = useState('ctl')
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Trust" title="Privacy & consent" sub="You decide what is processed, what is shared and how long it is kept." right={<Seg value={tab} onChange={setTab} options={[{ value: 'ctl', label: 'Controls' }, { value: 'audit', label: 'Audit trail' }]} />} />
    {tab === 'ctl' ? <Controls /> : <Audit />}</div>
}
