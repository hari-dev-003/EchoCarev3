/** Runtime UI translation. English source strings are the keys; catalogs live in src/locales/{ta,hi}.json.
 *  A MutationObserver translates text nodes and a few attributes as React renders, so every page (including
 *  server-supplied text and chart labels) follows the selected language without touching component code. */
export type Lang = 'en' | 'ta' | 'hi'
const ATTRS = ['placeholder', 'title', 'aria-label', 'alt']
const SKIP = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'NOSCRIPT', 'CODE'])
let lang: Lang = 'en'
let cat: Record<string, string> = {}
let pats: { re: RegExp; tpl: string }[] = []
let obs: MutationObserver | null = null
const cache = new Map<string, string | null>()
const origText = new WeakMap<Node, string>(), lastOut = new WeakMap<Node, string>()
const origAttr = new WeakMap<Element, Record<string, string>>()
const touched = new Set<Node>()
const LOCALE: Record<Lang, string> = { en: undefined as any, ta: 'ta-IN', hi: 'hi-IN' }
export const curLang = () => lang
export const curLocale = () => LOCALE[lang]

const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
function compile(c: Record<string, string>) {
  cat = c; cache.clear(); pats = []
  for (const k of Object.keys(c)) if (/\{\d+\}/.test(k)) {
    const re = new RegExp('^' + k.split(/(\{\d+\})/).map(p => /^\{\d+\}$/.test(p) ? '(.+?)' : esc(p)).join('') + '$', 's')
    pats.push({ re, tpl: c[k] })
  }
  pats.sort((a, b) => b.re.source.length - a.re.source.length)
}

function tx(core: string, depth = 0): string | null {
  if (cache.has(core)) return cache.get(core)!
  let out: string | null = cat[core] ?? null
  if (out === null && depth < 2) for (const p of pats) {
    const m = p.re.exec(core)
    if (m) { out = p.tpl.replace(/\{(\d+)\}/g, (_, n) => { const g = m[+n + 1] ?? ''; return tx(g, depth + 1) ?? g }); break }
  }
  if (out === null && depth < 3) {
    const num = /^(\d+(?:[.,]\d+)?)\s+([A-Za-z][\s\S]*)$/.exec(core)        // "2 story" -> "2 <story>"
    if (num) { const r = tx(num[2], depth + 1); if (r != null) out = num[1] + ' ' + r }
  }
  if (out === null && depth < 3 && /[,/]\s?/.test(core)) {                   // "story, survey, tracker"
    const parts = core.split(/(,\s*|\/)/); let hit = false
    const mapped = parts.map(p => { if (/^(,\s*|\/)$/.test(p)) return p; const r = tx(p.trim(), depth + 1); if (r != null) { hit = true; return r } return p })
    if (hit) out = mapped.join('')
  }
  if (depth === 0) cache.set(core, out)
  return out
}
function translateText(s: string): string | null {
  const m = /^(\s*)([\s\S]*?)(\s*)$/.exec(s)!
  const core = m[2].replace(/\s+/g, ' ')
  if (!core || !/[A-Za-z]/.test(core)) return null
  const t = tx(core)
  return t == null ? null : m[1] + t + m[3]
}

const skipped = (n: Node) => { for (let e = n.parentElement; e; e = e.parentElement) { if (SKIP.has(e.tagName) || e.hasAttribute('data-no-translate')) return true } return false }
function doText(n: Text) {
  if (lastOut.get(n) === n.nodeValue) return           // our own write
  const s = n.nodeValue || ''
  const t = translateText(s)
  if (t == null || t === s) { origText.delete(n); return }
  if (skipped(n)) return
  origText.set(n, s); lastOut.set(n, t); n.nodeValue = t; touched.add(n)
}
function doAttrs(e: Element) {
  for (const a of ATTRS) {
    const v = e.getAttribute(a); if (!v) continue
    const rec = origAttr.get(e)
    if (rec && rec[a] !== undefined && rec['out:' + a] === v) continue
    const t = translateText(v); if (t == null || t === v) continue
    const r = rec || {}; r[a] = v; r['out:' + a] = t; origAttr.set(e, r); e.setAttribute(a, t); touched.add(e)
  }
}
function walk(root: Node) {
  if (root.nodeType === 3) { doText(root as Text); return }
  if (root.nodeType !== 1) return
  const el = root as Element
  if (SKIP.has(el.tagName) || el.hasAttribute('data-no-translate')) return
  doAttrs(el)
  const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT)
  let n: Node | null = w.nextNode()
  while (n) { n.nodeType === 3 ? doText(n as Text) : doAttrs(n as Element); n = w.nextNode() }
}
function restore() {
  for (const n of touched) {
    if (n.nodeType === 3 && origText.has(n)) { (n as Text).nodeValue = origText.get(n)!; origText.delete(n); lastOut.delete(n) }
    else if (n.nodeType === 1) { const r = origAttr.get(n as Element); if (r) { for (const a of ATTRS) if (r[a] !== undefined) (n as Element).setAttribute(a, r[a]); origAttr.delete(n as Element) } }
  }
  touched.clear()
}

let queued: MutationRecord[] = [], raf = 0
function flush() {
  raf = 0; const recs = queued; queued = []
  if (touched.size > 5000) for (const n of touched) if (!n.isConnected) touched.delete(n)
  obs?.disconnect()
  try { for (const r of recs) {
    if (r.type === 'characterData') doText(r.target as Text)
    else if (r.type === 'attributes') doAttrs(r.target as Element)
    else r.addedNodes.forEach(walk)
  } } finally { start() }
}
function start() { obs?.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS }) }

export async function setLanguage(l: Lang) {
  obs?.disconnect(); obs = null; if (raf) cancelAnimationFrame(raf); queued = []
  restore(); lang = l
  document.documentElement.setAttribute('lang', l)
  if (l === 'en') return
  const mod = l === 'ta' ? await import('../locales/ta.json') : await import('../locales/hi.json')
  compile((mod as any).default || mod)
  walk(document.body)
  obs = new MutationObserver(recs => { queued.push(...recs); if (!raf) raf = requestAnimationFrame(flush) })
  start()
}
