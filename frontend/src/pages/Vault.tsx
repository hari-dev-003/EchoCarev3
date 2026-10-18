import { useRef, useState } from 'react'
import { FileLock2, Upload, Hash, History, QrCode, Eye, RefreshCw, UserCheck, ShieldCheck } from 'lucide-react'
import { api } from '../lib/api'
import { useApp } from '../lib/store'
import { useFetch, fmtDate } from '../lib/hooks'
import { Alert, Badge, Btn, Card, CardHead, DataTable, Empty, Loading, Modal, PageHead, Stat } from '../components/ui'
import { Donut, Legend2 } from '../components/charts'
import { CheckList, StatusBadge, openBlob } from '../components/trust'

const kb = (n?: number) => !n ? '—' : n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.round(n / 1024)} KB`

export default function Vault() {
  const { toast, profile } = useApp(); const v = useFetch<any>('/api/vault'); const [sel, setSel] = useState<any>(null); const [hist, setHist] = useState<any[] | null>(null); const [vers, setVers] = useState<any[] | null>(null); const [integ, setInteg] = useState<any>(null); const [qr, setQr] = useState<string | null>(null); const file = useRef<HTMLInputElement>(null)
  if (v.loading || !v.data) return <Loading rows={5} />
  const items = v.data.items; const counts = v.data.counts
  const open = async (r: any) => { setSel(r); setHist(null); setVers(null); setInteg(null); setQr(null); api.get(`/api/vault/${r.id}/history`).then(setHist).catch(() => {}); api.get(`/api/vault/${r.id}/versions`).then(setVers).catch(() => setVers([])); api.get(`/api/vault/${r.id}/integrity`).then(setInteg).catch(() => {}) }
  const act = async (fn: () => Promise<any>, ok: string) => { try { await fn(); toast(ok, 'ok'); await v.reload(); } catch (e: any) { toast(e.message, 'bad') } }
  const refreshSel = async () => { const d = await api.get('/api/vault'); v.setData(d); const r = d.items.find((x: any) => x.id === sel.id); if (r) open(r) }
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Trust" title="Document vault" sub={`Every report for ${profile?.name || 'this profile'} with its integrity hash, version history and verification result.`} />
    <div className="grid g4"><Stat label="Documents" value={items.length} icon={<FileLock2 size={18} />} /><Stat label="Verified by a person" value={counts['Verified'] || 0} tone="ok" icon={<ShieldCheck size={18} />} /><Stat label="Need review" value={(counts['Manual Review'] || 0) + (counts['Failed'] || 0)} tone={(counts['Manual Review'] || counts['Failed']) ? 'warn' : undefined} /><Stat label="Stored" value={kb(v.data.storage_bytes)} icon={<Hash size={18} />} /></div>
    <div className="grid g3-2">
      <Card><CardHead title="All documents" />{!items.length ? <Empty title="No documents yet" sub="Upload a report on the Reports page and it appears here automatically." /> :
        <DataTable rows={items} pageSize={8} cols={[
          { key: 'title', label: 'Document', sort: (r: any) => r.title, render: (r: any) => <><b>{r.title}</b><div className="tiny faint">{r.filename || 'entered by hand'} · v{r.current_version}</div></> },
          { key: 'report_date', label: 'Date', sort: (r: any) => r.report_date, render: (r: any) => fmtDate(r.report_date) },
          { key: 'status', label: 'Status', sort: (r: any) => r.status, render: (r: any) => <div className="row"><StatusBadge s={r.status} />{r.reviewed && <Badge tone="ok">person-reviewed</Badge>}</div> },
          { key: 'sha256', label: 'Hash', render: (r: any) => <span className="mono tiny">{r.sha256 ? r.sha256.slice(0, 10) + '…' : '—'}</span> },
          { key: 'act', label: '', render: (r: any) => <Btn size="sm" onClick={() => open(r)}>Details</Btn> }]} />}</Card>
      <Card><CardHead title="Status mix" /><Donut data={Object.entries(counts).map(([name, value]) => ({ name, value: value as number }))} center={<b style={{ fontSize: 22 }}>{items.length}</b>} /><Legend2 data={Object.entries(counts).map(([name, value]) => ({ name, value: value as number }))} />
        <Alert tone="info" title="How to read this">“Partially Verified” means automatic checks agree. Only “Verified” has been confirmed by a human reviewer.</Alert></Card></div>
    <Modal open={!!sel} onClose={() => setSel(null)} title={sel?.title || ''} wide>{sel && <div className="stack">
      <div className="row wrap"><StatusBadge s={sel.status} />{sel.score != null && <Badge>score {Math.round(sel.score * 100)}%</Badge>}<Badge>{sel.provenance}</Badge>{sel.review_requested && <Badge tone="warn">review requested</Badge>}</div>
      <p className="small muted">{sel.reason}</p><CheckList checks={sel.checks} />
      {integ?.has_file && <Alert tone={integ.intact ? 'ok' : 'bad'} title={integ.intact ? 'File is intact' : 'File does not match its stored hash'}><span className="mono tiny" style={{ wordBreak: 'break-all' }}>sha256 {integ.stored_sha256}</span></Alert>}
      <div className="row wrap">
        {sel.sha256 && <Btn onClick={async () => openBlob(await api.blob(`/api/vault/${sel.id}/file`))}><Eye size={15} />Open file</Btn>}
        <Btn onClick={() => act(async () => { await api.post(`/api/vault/${sel.id}/verify`); await refreshSel() }, 'Checks re-run')}><RefreshCw size={15} />Re-run checks</Btn>
        <Btn onClick={() => act(async () => { await api.post(`/api/vault/${sel.id}/request-review`); await refreshSel() }, 'A reviewer can now see this report')} disabled={sel.reviewed}><UserCheck size={15} />Ask for human review</Btn>
        <Btn onClick={async () => { const b = await api.blob(`/api/vault/${sel.id}/qr`); setQr(URL.createObjectURL(b)) }}><QrCode size={15} />Verification QR</Btn>
        <Btn onClick={() => file.current?.click()}><Upload size={15} />Upload new version</Btn><input ref={file} hidden type="file" accept="image/*,.pdf" onChange={e => { const f = e.target.files?.[0]; if (!f) return; const fd = new FormData(); fd.append('file', f); act(async () => { await api.form(`/api/vault/${sel.id}/versions`, fd); await refreshSel() }, 'New version stored; checks re-run') }} /></div>
      {qr && <div className="row"><img src={qr} alt="QR code linking to the public verification page" width={140} height={140} /><p className="small muted">Anyone who scans this sees only the report ID, status, date and file hash. No patient information is shown.</p></div>}
      <div className="grid g2"><div><h4 style={{ marginBottom: 6 }}>Versions</h4>{!vers ? <Loading rows={1} /> : !vers.length ? <p className="small muted">No file stored (entered by hand).</p> : vers.map(x => <div key={x.version} className="small" style={{ padding: '6px 0', borderTop: '1px solid var(--line)' }}><b>v{x.version}</b> · {x.filename} · {kb(x.size)} · {fmtDate(x.uploaded_at)}<div className="mono tiny faint">{x.sha256.slice(0, 32)}…</div></div>)}</div>
        <div><h4 style={{ marginBottom: 6 }}><History size={14} /> History</h4>{!hist ? <Loading rows={1} /> : hist.slice(0, 8).map(h => <div key={h.id} className="small" style={{ padding: '6px 0', borderTop: '1px solid var(--line)' }}><b>{h.event.replace(/_/g, ' ')}</b> → {h.status}<div className="tiny faint">{h.actor} · {fmtDate(h.created_at)}</div></div>)}</div></div></div>}</Modal></div>
}
