import { DependencyList, useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { useApp } from './store'
import { curLocale } from './translate'

/** Fetches `path` and refetches whenever the active profile changes or `reload()` is called. */
export function useFetch<T = any>(path: string | null, deps: DependencyList = []) {
  const { version } = useApp()
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (!path) { setLoading(false); return }
    let live = true; setLoading(true)
    api.get<T>(path).then(d => { if (live) { setData(d); setError(null) } }).catch(e => { if (live) setError(e.message) }).finally(() => live && setLoading(false))
    return () => { live = false }
  }, [path, version, tick, ...deps])
  const reload = useCallback(() => setTick(t => t + 1), [])
  return { data, loading, error, reload, setData }
}

export const fmtDate = (s?: string | null) => { if (!s) return '—'; const d = new Date(s.length <= 10 ? s + 'T00:00:00' : s); return isNaN(+d) ? s : d.toLocaleDateString(curLocale(), { day: 'numeric', month: 'short', year: 'numeric' }) }
export const shortDate = (s: string) => { const d = new Date(s + 'T00:00:00'); return isNaN(+d) ? s : d.toLocaleDateString(curLocale(), { day: 'numeric', month: 'short' }) }
export const pct = (n: number) => `${Math.round(n * 100)}%`
export const todayStr = () => new Date().toISOString().slice(0, 10)

export const refText = (low?: number | null, high?: number | null) => low != null && high != null ? `${low} – ${high}` : high != null ? `< ${high}` : low != null ? `> ${low}` : '—'
