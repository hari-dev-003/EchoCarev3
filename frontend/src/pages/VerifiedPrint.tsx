import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useApp } from '../lib/store'
import { ReportBody } from './VerifiedReport'

/** Standalone printable page (browser "Save as PDF") so Tamil and Hindi render with the system fonts. */
export default function VerifiedPrint() {
  const { id } = useParams(); const { profile } = useApp(); const [r, setR] = useState<any>(null); const [err, setErr] = useState('')
  useEffect(() => { api.get(`/api/verified-report/${id}`).then(x => { setR(x); setTimeout(() => window.print(), 600) }).catch(e => setErr(e.message)) }, [id])
  if (err) return <p style={{ padding: 30 }}>{err}</p>
  if (!r) return <p style={{ padding: 30 }}>Loading…</p>
  return <div className="print-page" style={{ maxWidth: 820, margin: '0 auto', padding: 24 }}><h1 style={{ marginBottom: 4 }}>Verified Health Report</h1><p className="muted small">{profile?.name} · {new Date(r.generated_at).toLocaleDateString()} · Report {r.id.slice(0, 8).toUpperCase()}</p><p className="tiny faint" style={{ margin: '6px 0 16px' }}>Each section is labelled with where its information came from. Only items marked Verified were confirmed by a human reviewer. This is not a diagnosis.</p><ReportBody r={r} /></div>
}
