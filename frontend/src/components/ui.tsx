import { ReactNode, useEffect, useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight, Search, X, Inbox, ArrowUpDown } from 'lucide-react'

export const Card = ({ children, className = '', hover, style }: { children: ReactNode; className?: string; hover?: boolean; style?: React.CSSProperties }) =>
  <section className={`card ${hover ? 'hover' : ''} ${className}`} style={style}>{children}</section>

export const CardHead = ({ title, sub, right, icon }: { title: ReactNode; sub?: ReactNode; right?: ReactNode; icon?: ReactNode }) =>
  <div className="card-head"><div className="row">{icon && <span className="icon-chip">{icon}</span>}<div><h2>{title}</h2>{sub && <div className="sub">{sub}</div>}</div></div>{right}</div>

export const PageHead = ({ title, sub, eyebrow, right }: { title: ReactNode; sub?: ReactNode; eyebrow?: string; right?: ReactNode }) =>
  <div className="page-head fade-in"><div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h1>{title}</h1>{sub && <p>{sub}</p>}</div>{right && <div className="row wrap">{right}</div>}</div>

export const Stat = ({ label, value, unit, foot, icon, tone }: { label: string; value: ReactNode; unit?: string; foot?: ReactNode; icon?: ReactNode; tone?: 'ok' | 'warn' | 'bad' }) =>
  <Card hover><div className="stat"><div className="label">{icon && <span className={`icon-chip ${tone || ''}`}>{icon}</span>}{label}</div>
    <div className="value mono">{value}{unit && <small>{unit}</small>}</div>{foot && <div className="foot">{foot}</div>}</div></Card>

export const Badge = ({ children, tone }: { children: ReactNode; tone?: 'ok' | 'warn' | 'bad' | 'info' }) => <span className={`badge ${tone || ''}`}>{children}</span>
export const toneOf = (lvl?: string): 'ok' | 'warn' | 'bad' | undefined => lvl === 'ok' ? 'ok' : lvl === 'watch' || lvl === 'warn' ? 'warn' : lvl === 'alert' || lvl === 'bad' || lvl === 'discuss' ? 'bad' : undefined

export const Btn = ({ children, variant, size, icon, ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' | 'danger'; size?: 'sm'; icon?: boolean }) =>
  <button {...p} className={`btn ${variant || ''} ${size || ''} ${icon ? 'icon' : ''} ${p.className || ''}`}>{children}</button>

export const Field = ({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) =>
  <div className="field"><label>{label}</label>{children}{hint && <span className="tiny faint">{hint}</span>}</div>

export const Seg = <T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode }[] }) =>
  <div className="seg" role="tablist">{options.map(o => <button key={o.value} className={value === o.value ? 'on' : ''} onClick={() => onChange(o.value)} role="tab">{o.label}</button>)}</div>

export const Switch = ({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label?: string }) =>
  <button className={`switch ${on ? 'on' : ''}`} onClick={() => onChange(!on)} role="switch" aria-checked={on} aria-label={label} />

export const Progress = ({ value, tone }: { value: number; tone?: 'ok' | 'warn' | 'bad' }) =>
  <div className={`progress ${tone || ''}`}><div style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></div>

export const Spinner = () => <span className="spin" />
export const Loading = ({ rows = 3 }: { rows?: number }) => <div className="stack">{Array.from({ length: rows }).map((_, i) => <div key={i} className="skeleton" style={{ height: 46 }} />)}</div>
export const Empty = ({ title, sub, icon, action }: { title: string; sub?: string; icon?: ReactNode; action?: ReactNode }) =>
  <div className="empty"><span className="icon-chip lg">{icon || <Inbox size={20} />}</span><h3>{title}</h3>{sub && <p className="small" style={{ marginTop: 4 }}>{sub}</p>}{action && <div style={{ marginTop: 14 }}>{action}</div>}</div>

export const Alert = ({ tone, title, children, icon }: { tone?: 'ok' | 'warn' | 'bad' | 'info'; title?: ReactNode; children?: ReactNode; icon?: ReactNode }) =>
  <div className={`alert ${tone || ''}`}>{icon}<div className="grow">{title && <b>{title}</b>}{children && <div className={title ? 'small muted' : ''} style={{ marginTop: title ? 2 : 0 }}>{children}</div>}</div></div>

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => { if (!open) return; const k = (e: KeyboardEvent) => e.key === 'Escape' && onClose(); window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k) }, [open])
  if (!open) return null
  return <div className="overlay" onMouseDown={onClose}><div className={`modal ${wide ? 'wide' : ''}`} onMouseDown={e => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={title}>
    <div className="card-head"><h2>{title}</h2><Btn variant="ghost" icon onClick={onClose} aria-label="Close"><X size={18} /></Btn></div>{children}</div></div>
}

export function Confirm({ open, title, text, onYes, onNo, danger = true, yes = 'Delete' }: { open: boolean; title: string; text: string; onYes: () => void; onNo: () => void; danger?: boolean; yes?: string }) {
  return <Modal open={open} onClose={onNo} title={title}><p className="muted">{text}</p><div className="row end" style={{ marginTop: 20 }}><Btn onClick={onNo}>Cancel</Btn><Btn variant={danger ? 'danger' : 'primary'} onClick={onYes}>{yes}</Btn></div></Modal>
}

export type Col<T> = { key: string; label: string; render?: (r: T) => ReactNode; sort?: (r: T) => string | number; width?: number }
export function DataTable<T extends { id?: string }>({ rows, cols, searchable = true, pageSize = 10, empty = 'No records' }: { rows: T[]; cols: Col<T>[]; searchable?: boolean; pageSize?: number; empty?: string }) {
  const [q, setQ] = useState(''); const [sort, setSort] = useState<{ k: string; dir: 1 | -1 } | null>(null); const [page, setPage] = useState(0)
  const filtered = useMemo(() => {
    let r = rows
    if (q) { const ql = q.toLowerCase(); r = r.filter(x => cols.some(c => String(c.sort ? c.sort(x) : (x as any)[c.key] ?? '').toLowerCase().includes(ql))) }
    if (sort) { const c = cols.find(c => c.key === sort.k); if (c) { const get = c.sort || ((x: T) => (x as any)[c.key]); r = [...r].sort((a, b) => (get(a) > get(b) ? 1 : get(a) < get(b) ? -1 : 0) * sort.dir) } }
    return r
  }, [rows, q, sort])
  useEffect(() => setPage(0), [q, rows.length])
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize)); const slice = filtered.slice(page * pageSize, page * pageSize + pageSize)
  return <div className="stack">
    {searchable && rows.length > pageSize && <div className="row"><div className="rel grow" style={{ maxWidth: 320 }}><Search size={15} style={{ position: 'absolute', left: 12, top: 12, color: 'var(--text-3)' }} /><input className="input" style={{ paddingLeft: 36 }} placeholder="Filter…" value={q} onChange={e => setQ(e.target.value)} /></div><span className="small faint">{filtered.length} rows</span></div>}
    <div className="table-wrap"><table className="table"><thead><tr>{cols.map(c => <th key={c.key} className={c.sort ? 'sortable' : ''} style={{ width: c.width }} onClick={() => c.sort && setSort(s => ({ k: c.key, dir: s?.k === c.key ? (-s.dir as 1 | -1) : 1 }))}>{c.label}{c.sort && <ArrowUpDown size={11} style={{ marginLeft: 5, verticalAlign: -1, opacity: .6 }} />}</th>)}</tr></thead>
      <tbody>{slice.length ? slice.map((r, i) => <tr key={(r as any).id || i}>{cols.map(c => <td key={c.key}>{c.render ? c.render(r) : String((r as any)[c.key] ?? '—')}</td>)}</tr>) : <tr><td colSpan={cols.length}><Empty title={empty} /></td></tr>}</tbody></table></div>
    {pages > 1 && <div className="row between"><span className="small faint">Page {page + 1} of {pages}</span><div className="row"><Btn size="sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}><ChevronLeft size={14} />Prev</Btn><Btn size="sm" disabled={page >= pages - 1} onClick={() => setPage(p => p + 1)}>Next<ChevronRight size={14} /></Btn></div></div>}
  </div>
}

export function Slideshow({ slides, interval = 6000, height }: { slides: { title: string; body: string; icon?: ReactNode; bg?: string }[]; interval?: number; height?: number }) {
  const [i, setI] = useState(0); const [hover, setHover] = useState(false)
  useEffect(() => { if (hover || slides.length < 2) return; const t = setInterval(() => setI(x => (x + 1) % slides.length), interval); return () => clearInterval(t) }, [hover, slides.length, interval])
  return <div className="slides" onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)} style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
    <div className="slides-track" style={{ transform: `translateX(-${i * 100}%)` }}>{slides.map((s, k) => <div key={k} className="slide" style={{ minHeight: height }}>
      {s.icon && <span className="icon-chip lg">{s.icon}</span>}<h2 style={{ fontSize: 21 }}>{s.title}</h2><p className="muted" style={{ maxWidth: '62ch' }}>{s.body}</p></div>)}</div>
    <div className="row between" style={{ padding: '0 20px 16px' }}><div className="dots">{slides.map((_, k) => <button key={k} className={k === i ? 'on' : ''} onClick={() => setI(k)} aria-label={`Slide ${k + 1}`} />)}</div>
      <div className="row"><Btn size="sm" icon onClick={() => setI((i - 1 + slides.length) % slides.length)} aria-label="Previous"><ChevronLeft size={16} /></Btn><Btn size="sm" icon onClick={() => setI((i + 1) % slides.length)} aria-label="Next"><ChevronRight size={16} /></Btn></div></div></div>
}

export const Marquee = ({ items }: { items: { icon?: ReactNode; text: string }[] }) =>
  <div className="marquee"><div className="marquee-track">{[...items, ...items].map((it, i) => <span key={i} className="marquee-item">{it.icon}{it.text}</span>)}</div></div>

export const Avatar = ({ name, lg }: { name: string; lg?: boolean }) => <span className={`avatar ${lg ? 'lg' : ''}`}>{name.split(' ').map(s => s[0]).slice(0, 2).join('').toUpperCase()}</span>
