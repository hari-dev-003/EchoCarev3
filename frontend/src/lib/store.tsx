import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, getProfileId, getToken, setProfileId, setToken } from './api'
import { Lang, tr } from './i18n'
import { setLanguage } from './translate'

export type User = { id: string; name: string; email: string; is_admin: boolean; language: Lang }
export type Profile = { id: string; name: string; relation: string; shared?: boolean; role?: string }
type Toast = { id: number; msg: string; kind?: 'ok' | 'bad' }

type Ctx = {
  user: User | null; ready: boolean; profiles: Profile[]; profile: Profile | null
  login: (token: string, user: User) => Promise<void>; logout: () => void
  switchProfile: (id: string) => void; refreshProfiles: () => Promise<void>
  theme: 'light' | 'dark'; toggleTheme: () => void
  lang: Lang; setLang: (l: Lang) => void; t: (k: string) => string
  toast: (msg: string, kind?: 'ok' | 'bad') => void; toasts: Toast[]
  version: number; bump: () => void
  a11y: { text: 'normal' | 'large' | 'xlarge'; contrast: boolean; motion: boolean }; setA11y: (p: Partial<Ctx['a11y']>) => void
}
const C = createContext<Ctx>(null as any)
export const useApp = () => useContext(C)

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [pid, setPid] = useState<string | null>(getProfileId())
  const [theme, setTheme] = useState<'light' | 'dark'>(() => (document.documentElement.getAttribute('data-theme') as any) || 'light')
  const [lang, setLangState] = useState<Lang>(() => { try { return (localStorage.getItem('ec_lang') as Lang) || 'en' } catch { return 'en' } })
  const [toasts, setToasts] = useState<Toast[]>([])
  const [version, setVersion] = useState(0)
  const [a11y, setA11yState] = useState<Ctx['a11y']>(() => { try { return { text: 'normal', contrast: false, motion: true, ...JSON.parse(localStorage.getItem('ec_a11y') || '{}') } } catch { return { text: 'normal', contrast: false, motion: true } } })
  useEffect(() => { const r = document.documentElement; r.setAttribute('data-text', a11y.text); r.setAttribute('data-contrast', a11y.contrast ? 'high' : 'normal'); r.setAttribute('data-motion', a11y.motion ? 'full' : 'reduced'); try { localStorage.setItem('ec_a11y', JSON.stringify(a11y)) } catch {} }, [a11y])
  const setA11y = (p: Partial<Ctx['a11y']>) => setA11yState(a => ({ ...a, ...p }))

  const refreshProfiles = useCallback(async () => {
    const own: Profile[] = await api.get('/api/profiles')
    let shared: Profile[] = []
    try { shared = (await api.get('/api/sharing/shared-with-me')).map((x: any) => ({ id: x.profile_id, name: x.profile_name, relation: 'shared', shared: true, role: x.role })) } catch {}
    const list = [...own, ...shared]
    setProfiles(list)
    const stored = getProfileId()
    const chosen = list.find(p => p.id === stored) || list.find(p => p.relation === 'self') || list[0]
    if (chosen) { setProfileId(chosen.id); setPid(chosen.id) }
  }, [])

  const logout = useCallback(() => { setToken(null); setProfileId(null); setUser(null); setProfiles([]); setPid(null) }, [])
  const login = useCallback(async (token: string, u: User) => { setToken(token); setUser(u); if (u.language) setLangState(u.language); await refreshProfiles() }, [refreshProfiles])

  useEffect(() => {
    const onOut = () => logout(); window.addEventListener('ec-logout', onOut)
    ;(async () => {
      if (getToken()) { try { const u: User = await api.get('/api/auth/me'); setUser(u); await refreshProfiles() } catch { setToken(null) } }
      setReady(true)
    })()
    return () => window.removeEventListener('ec-logout', onOut)
  }, [])

  useEffect(() => { document.documentElement.setAttribute('data-theme', theme); try { localStorage.setItem('ec_theme', theme) } catch {} }, [theme])
  useEffect(() => { setLanguage(lang) }, [lang])
  const toggleTheme = () => setTheme(t => (t === 'light' ? 'dark' : 'light'))
  const setLang = (l: Lang) => { setLangState(l); try { localStorage.setItem('ec_lang', l) } catch {}; if (user) api.patch('/api/auth/me', { language: l }).catch(() => {}) }
  const toast = useCallback((msg: string, kind?: 'ok' | 'bad') => { const id = Date.now() + Math.random(); setToasts(t => [...t, { id, msg, kind }]); setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4200) }, [])
  const switchProfile = (id: string) => { setProfileId(id); setPid(id); setVersion(v => v + 1) }
  const bump = useCallback(() => setVersion(v => v + 1), [])
  const profile = profiles.find(p => p.id === pid) || null

  const value = useMemo<Ctx>(() => ({ user, ready, profiles, profile, login, logout, switchProfile, refreshProfiles, theme, toggleTheme, lang, setLang, t: (k: string) => tr(lang, k), toast, toasts, version, bump, a11y, setA11y }),
    [user, ready, profiles, profile, theme, lang, toasts, version, a11y])
  return <C.Provider value={value}>{children}</C.Provider>
}
