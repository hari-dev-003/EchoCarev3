import { CheckCircle2, CircleSlash, AlertTriangle, XCircle } from 'lucide-react'
import { Badge } from './ui'

export const STATUS_TONE: Record<string, 'ok' | 'warn' | 'bad' | 'info' | undefined> = { Verified: 'ok', 'Partially Verified': 'info', 'Manual Review': 'warn', Failed: 'bad', Unverified: undefined, 'Not independently verified': 'warn' }
export const StatusBadge = ({ s }: { s: string }) => <Badge tone={STATUS_TONE[s]}>{s}</Badge>

const ICON: Record<string, any> = { pass: <CheckCircle2 size={16} color="var(--ok)" />, warn: <AlertTriangle size={16} color="var(--warn)" />, fail: <XCircle size={16} color="var(--bad)" />, na: <CircleSlash size={16} color="var(--text-3)" /> }
export const CheckList = ({ checks }: { checks: any[] }) => <div className="stack" style={{ gap: 8 }}>{(checks || []).map(c => <div key={c.key} className="row" style={{ alignItems: 'flex-start' }}><span style={{ marginTop: 2 }}>{ICON[c.state]}</span><div><b className="small">{c.label}</b><div className="small muted">{c.detail}</div></div></div>)}</div>

/** Opens an authenticated file (blob) in a new tab. */
export const openBlob = (b: Blob) => { const u = URL.createObjectURL(b); window.open(u, '_blank'); setTimeout(() => URL.revokeObjectURL(u), 60000) }
