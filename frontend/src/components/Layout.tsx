import { ReactNode, useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Activity, BarChart3, Bell, BookOpen, CalendarClock, ClipboardList, FileText, FlaskConical, GraduationCap, HeartPulse, LayoutDashboard, LogOut, Menu, MessageCircleHeart, Moon, Pill, Search, Settings, ShieldCheck, Siren, Sparkles, Stethoscope, Sun, Target, Users, Map, History, ScrollText, Languages, FileDown, X, Check, BadgeCheck, FileLock2, BellRing, Share2, LockKeyhole } from 'lucide-react'
import { useApp } from '../lib/store'
import { useFetch } from '../lib/hooks'
import { api } from '../lib/api'
import { LANGS } from '../lib/i18n'
import { Avatar, Btn } from './ui'

const NAV: { label: string; items: { to: string; key: string; icon: ReactNode; admin?: boolean }[] }[] = [
  { label: 'main', items: [{ to: '/', key: 'dashboard', icon: <LayoutDashboard size={17} /> }, { to: '/analytics', key: 'analytics', icon: <BarChart3 size={17} /> }, { to: '/timeline', key: 'timeline', icon: <History size={17} /> }] },
  { label: 'record', items: [{ to: '/story', key: 'story', icon: <ScrollText size={17} /> }, { to: '/survey', key: 'survey', icon: <ClipboardList size={17} /> }, { to: '/tracker', key: 'tracker', icon: <Activity size={17} /> }, { to: '/vitals', key: 'vitals', icon: <HeartPulse size={17} /> }, { to: '/reports', key: 'reports', icon: <FileText size={17} /> }, { to: '/labs', key: 'labs', icon: <FlaskConical size={17} /> }, { to: '/medicines', key: 'medicines', icon: <Pill size={17} /> }] },
  { label: 'ai', items: [{ to: '/insights', key: 'insights', icon: <Sparkles size={17} /> }, { to: '/echo', key: 'echo', icon: <MessageCircleHeart size={17} /> }, { to: '/guard', key: 'guard', icon: <ShieldCheck size={17} /> }] },
  { label: 'care', items: [{ to: '/doctors', key: 'doctors', icon: <Map size={17} /> }, { to: '/appointments', key: 'appointments', icon: <CalendarClock size={17} /> }, { to: '/consult', key: 'consult', icon: <FileDown size={17} /> }, { to: '/emergency', key: 'emergency', icon: <Siren size={17} /> }, { to: '/family', key: 'family', icon: <Users size={17} /> }] },
  { label: 'trust', items: [{ to: '/alerts', key: 'alerts', icon: <BellRing size={17} /> }, { to: '/vault', key: 'vault', icon: <FileLock2 size={17} /> }, { to: '/verified-report', key: 'verified_report', icon: <BadgeCheck size={17} /> }, { to: '/verification', key: 'verification', icon: <ShieldCheck size={17} /> }, { to: '/sharing', key: 'sharing', icon: <Share2 size={17} /> }, { to: '/privacy', key: 'privacy', icon: <LockKeyhole size={17} /> }] },
  { label: 'more', items: [{ to: '/wellness', key: 'wellness', icon: <Target size={17} /> }, { to: '/learn', key: 'learn', icon: <GraduationCap size={17} /> }, { to: '/settings', key: 'settings', icon: <Settings size={17} /> }, { to: '/admin', key: 'admin', icon: <Stethoscope size={17} />, admin: true }] },
]

function useOutside(ref: React.RefObject<HTMLElement>, cb: () => void) {
  useEffect(() => { const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) cb() }; document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h) }, [])
}

function Notifications() {
  const [open, setOpen] = useState(false); const ref = useRef<HTMLDivElement>(null); useOutside(ref, () => setOpen(false))
  const { data, reload } = useFetch<any>('/api/notifications'); const nav = useNavigate(); const { t } = useApp()
  const unread = data?.unread || 0
  const markAll = async () => { await api.post('/api/notifications/read', { keys: (data?.items || []).map((i: any) => i.key) }); reload() }
  return <div className="rel" ref={ref}>
    <Btn icon onClick={() => setOpen(o => !o)} aria-label={t('notifications')} style={{ position: 'relative' }}><Bell size={17} />{unread > 0 && <span style={{ position: 'absolute', top: -3, right: -3, background: 'var(--bad)', color: '#fff', borderRadius: 99, fontSize: 10, minWidth: 16, height: 16, display: 'grid', placeItems: 'center', padding: '0 4px', fontWeight: 700 }}>{unread}</span>}</Btn>
    {open && <div className="dropdown fade-in"><div className="row between" style={{ padding: '6px 10px 10px' }}><b>{t('notifications')}</b><Btn size="sm" variant="ghost" onClick={markAll}><Check size={14} />Mark all read</Btn></div>
      {!(data?.items || []).length && <p className="muted small" style={{ padding: 14 }}>You're all caught up.</p>}
      {(data?.items || []).map((n: any) => <div key={n.key} className="dd-item" onClick={() => { setOpen(false); nav(n.href) }} style={{ opacity: n.read ? .55 : 1 }}>
        <span className={`icon-chip ${n.level === 'warn' ? 'warn' : ''}`}><Bell size={15} /></span><div><b className="small">{n.title}</b><div className="small muted">{n.detail}</div></div></div>)}</div>}
  </div>
}

function SearchBox() {
  const [q, setQ] = useState(''); const [res, setRes] = useState<any[] | null>(null); const ref = useRef<HTMLDivElement>(null); const nav = useNavigate(); const { t } = useApp()
  useOutside(ref, () => setRes(null))
  useEffect(() => { if (q.trim().length < 2) { setRes(null); return } const id = setTimeout(() => api.get(`/api/search?q=${encodeURIComponent(q)}`).then(r => setRes(r.results)).catch(() => setRes([])), 300); return () => clearTimeout(id) }, [q])
  return <div className="rel grow" style={{ maxWidth: 420 }} ref={ref}><Search size={15} style={{ position: 'absolute', left: 13, top: 12, color: 'var(--text-3)' }} />
    <input className="input" style={{ paddingLeft: 38, borderRadius: 999 }} placeholder={t('search')} value={q} onChange={e => setQ(e.target.value)} aria-label="Search" />
    {res && <div className="dropdown fade-in" style={{ width: '100%', right: 'auto', left: 0 }}>{res.length === 0 ? <p className="muted small" style={{ padding: 12 }}>No matches.</p> : res.map((r, i) => <div key={i} className="dd-item" onClick={() => { setRes(null); setQ(''); nav(r.href) }}><span className="tag">{r.type}</span><div className="small grow">{r.title}<div className="tiny faint">{r.date}</div></div></div>)}</div>}</div>
}

export default function Layout() {
  const { user, profile, profiles, switchProfile, theme, toggleTheme, lang, setLang, logout, t, toasts } = useApp()
  const [open, setOpen] = useState(false); const loc = useLocation(); const { data: notif } = useFetch<any>('/api/notifications')
  useEffect(() => setOpen(false), [loc.pathname])
  const mainRef = useRef<HTMLElement>(null)
  useEffect(() => { mainRef.current?.focus({ preventScroll: true }); window.scrollTo(0, 0) }, [loc.pathname])
  return <div className="app">
    <a className="skip-link" href="#main" onClick={e => { e.preventDefault(); mainRef.current?.focus() }}>Skip to main content</a>
    <aside aria-label="Sidebar" className={`sidebar ${open ? 'open' : ''}`}>
      <div className="brand"><span className="logo"><HeartPulse size={19} /></span><div>EchoCare<small>AI healthcare companion</small></div><Btn variant="ghost" icon className="menu-btn" style={{ marginLeft: 'auto' }} onClick={() => setOpen(false)}><X size={18} /></Btn></div>
      <nav className="nav" aria-label="Main navigation">{NAV.map(g => <div className="nav-group" key={g.label}><div className="nav-label">{t(g.label)}</div>
        {g.items.filter(i => !i.admin || user?.is_admin).map(i => <NavLink key={i.to} to={i.to} end={i.to === '/'} className={({ isActive }) => (isActive ? 'active' : '')}>{i.icon}{t(i.key)}{i.key === 'dashboard' && (notif?.unread || 0) > 0 && <span className="dot">{notif.unread}</span>}</NavLink>)}</div>)}</nav>
      <div className="sidebar-foot"><div className="card flat tight row"><Avatar name={user?.name || '?'} /><div className="grow"><b className="small" style={{ display: 'block', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.name}</b><span className="tiny faint">{user?.is_admin ? 'Administrator' : 'Member'}</span></div><Btn icon variant="ghost" onClick={logout} aria-label={t('signout')} title={t('signout')}><LogOut size={16} /></Btn></div></div>
    </aside>
    <div className="main">
      <header className="topbar" role="banner">
        <Btn icon className="menu-btn" onClick={() => setOpen(true)} aria-label="Menu"><Menu size={18} /></Btn>
        <SearchBox /><div className="spacer" />
        <div className="row" title={t('profile')}><select className="select" style={{ width: 'auto', borderRadius: 999, padding: '8px 14px' }} value={profile?.id || ''} onChange={e => switchProfile(e.target.value)} aria-label={t('profile')}>{profiles.map(p => <option key={p.id} value={p.id}>{p.name}{p.shared ? ' (shared with you)' : p.relation !== 'self' ? ` (${p.relation})` : ''}</option>)}</select></div>
        <div className="row" title={t('language')}><Languages size={16} className="faint" /><select className="select" style={{ width: 'auto', borderRadius: 999, padding: '8px 12px' }} value={lang} onChange={e => setLang(e.target.value as any)} aria-label={t('language')}>{LANGS.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}</select></div>
        <Btn icon onClick={toggleTheme} aria-label="Toggle theme" title={`${t('theme')}: ${theme}`}>{theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}</Btn>
        <Notifications />
      </header>
      <main id="main" ref={mainRef} tabIndex={-1} className="content" style={{ outline: 'none' }}><Outlet /><p className="disclaimer">{t('not_a_doctor')}</p></main>
    </div>
    <div className="toasts" aria-live="polite">{toasts.map(x => <div key={x.id} className={`toast ${x.kind || ''}`}>{x.msg}</div>)}</div>
  </div>
}
