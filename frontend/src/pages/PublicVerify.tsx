import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { BadgeCheck, ShieldQuestion } from 'lucide-react'
import { api } from '../lib/api'
import { Alert, Card } from '../components/ui'
import { StatusBadge } from '../components/trust'

export default function PublicVerify() {
  const { id } = useParams(); const [sp] = useSearchParams(); const [d, setD] = useState<any>(null); const [err, setErr] = useState('')
  useEffect(() => { api.get(`/api/public/verify/${id}${sp.get('h') ? `?h=${sp.get('h')}` : ''}`).then(setD).catch(e => setErr(e.message)) }, [id])
  return <div style={{ maxWidth: 520, margin: '0 auto', padding: 20 }}><Card>
    <div className="row" style={{ marginBottom: 14 }}><span className="icon-chip">{d ? <BadgeCheck size={18} /> : <ShieldQuestion size={18} />}</span><div><h2>EchoCare verification</h2><div className="small muted">Public check. No personal health information is shown.</div></div></div>
    {err ? <Alert tone="bad" title="Not found">No report with this ID exists in EchoCare.</Alert> : !d ? <p>Checking…</p> : <div className="stack">
      <div className="row between"><span className="muted">Report ID</span><b className="mono">{d.report_id}</b></div>
      <div className="row between"><span className="muted">Status</span><StatusBadge s={d.status} /></div>
      <div className="row between"><span className="muted">Issue date</span><b>{d.issue_date}</b></div>
      <div className="row between"><span className="muted">Reviewed by a person</span><b>{d.human_reviewed ? 'Yes' : 'No'}</b></div>
      <div><span className="muted small">Integrity hash (SHA-256)</span><div className="mono tiny" style={{ wordBreak: 'break-all' }}>{d.integrity_hash || 'no file stored'}</div></div>
      {d.hash_matches !== undefined && <Alert tone={d.hash_matches ? 'ok' : 'bad'} title={d.hash_matches ? 'Hash matches' : 'Hash does not match'}>{d.hash_matches ? 'The document you hold is identical to the one recorded.' : 'The document you hold differs from the one recorded. Do not rely on it.'}</Alert>}
      <p className="tiny faint">{d.notice}</p></div>}</Card></div>
}
