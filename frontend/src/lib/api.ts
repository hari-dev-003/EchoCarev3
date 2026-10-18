const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
export const getToken = () => { try { return localStorage.getItem('ec_token') } catch { return null } }
export const setToken = (t: string | null) => { try { t ? localStorage.setItem('ec_token', t) : localStorage.removeItem('ec_token') } catch {} }
export const getProfileId = () => { try { return localStorage.getItem('ec_profile') } catch { return null } }
export const setProfileId = (p: string | null) => { try { p ? localStorage.setItem('ec_profile', p) : localStorage.removeItem('ec_profile') } catch {} }

export class ApiError extends Error { status: number; constructor(msg: string, status: number) { super(msg); this.status = status } }

function headers(extra?: HeadersInit, json = true): HeadersInit {
  const h: Record<string, string> = {}
  const t = getToken(); if (t) h.Authorization = `Bearer ${t}`
  const p = getProfileId(); if (p) h['X-Profile-Id'] = p
  if (json) h['Content-Type'] = 'application/json'
  return { ...h, ...(extra as Record<string, string>) }
}

async function handle(r: Response) {
  if (r.status === 401 && getToken()) { setToken(null); window.dispatchEvent(new Event('ec-logout')) }
  if (!r.ok) {
    let msg = r.statusText
    try { const j = await r.json(); msg = typeof j.detail === 'string' ? j.detail : Array.isArray(j.detail) ? j.detail.map((d: any) => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('; ') : msg } catch {}
    throw new ApiError(msg, r.status)
  }
  const ct = r.headers.get('content-type') || ''
  return ct.includes('application/json') ? r.json() : r
}

export const api = {
  get: <T = any>(path: string): Promise<T> => fetch(BASE + path, { headers: headers() }).then(handle) as Promise<T>,
  post: <T = any>(path: string, body?: any): Promise<T> => fetch(BASE + path, { method: 'POST', headers: headers(), body: body === undefined ? undefined : JSON.stringify(body) }).then(handle) as Promise<T>,
  put: <T = any>(path: string, body?: any): Promise<T> => fetch(BASE + path, { method: 'PUT', headers: headers(), body: JSON.stringify(body) }).then(handle) as Promise<T>,
  patch: <T = any>(path: string, body?: any): Promise<T> => fetch(BASE + path, { method: 'PATCH', headers: headers(), body: JSON.stringify(body) }).then(handle) as Promise<T>,
  del: <T = any>(path: string): Promise<T> => fetch(BASE + path, { method: 'DELETE', headers: headers() }).then(handle) as Promise<T>,
  form: <T = any>(path: string, fd: FormData): Promise<T> => fetch(BASE + path, { method: 'POST', headers: headers(undefined, false), body: fd }).then(handle) as Promise<T>,
  blob: async (path: string, method = 'GET', body?: any): Promise<Blob> => {
    const r = await fetch(BASE + path, { method, headers: headers(), body: body === undefined ? undefined : JSON.stringify(body) })
    if (!r.ok) throw new ApiError(r.statusText, r.status)
    return r.blob()
  },
  url: (path: string) => BASE + path,
}

export function download(blob: Blob, name: string) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}
