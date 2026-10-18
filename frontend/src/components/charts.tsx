import { ReactNode } from 'react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart, Pie, PieChart, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export const COLORS = ['var(--c1)', 'var(--c2)', 'var(--c3)', 'var(--c4)', 'var(--c5)', 'var(--c6)', 'var(--c7)', 'var(--c8)']

export function Tip({ active, payload, label, fmt }: any) {
  if (!active || !payload?.length) return null
  return <div className="chart-tip"><b>{label ?? payload[0].payload?.name}</b>{payload.map((p: any, i: number) => <div key={i}><i style={{ background: p.color || p.fill }} />{p.name}: <b style={{ display: 'inline', margin: 0 }}>{fmt ? fmt(p.value) : p.value}</b></div>)}</div>
}
const axis = { tick: { fontSize: 11.5 }, axisLine: false, tickLine: false } as const

export type Series = { key: string; name: string; color?: string }
export const TrendChart = ({ data, x, series, height = 240, area, ref, domain }: { data: any[]; x: string; series: Series[]; height?: number; area?: boolean; ref?: { low?: number | null; high?: number | null }; domain?: [any, any] }) => {
  const Chart: any = area ? AreaChart : LineChart; const Item: any = area ? Area : Line
  return <ResponsiveContainer width="100%" height={height}><Chart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
    <defs>{series.map((s, i) => <linearGradient key={s.key} id={`g-${s.key}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={s.color || COLORS[i]} stopOpacity={0.35} /><stop offset="100%" stopColor={s.color || COLORS[i]} stopOpacity={0.02} /></linearGradient>)}</defs>
    <CartesianGrid vertical={false} strokeDasharray="3 3" /><XAxis dataKey={x} {...axis} minTickGap={24} /><YAxis {...axis} domain={domain} />
    {ref && ref.low != null && ref.high != null && <ReferenceArea y1={ref.low} y2={ref.high} fill="var(--ok)" fillOpacity={0.08} />}
    {ref && ref.high != null && ref.low == null && <ReferenceLine y={ref.high} stroke="var(--ok)" strokeDasharray="4 4" />}
    <Tooltip content={<Tip />} />{series.length > 1 && <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />}
    {series.map((s, i) => <Item key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={s.color || COLORS[i]} strokeWidth={2.4} fill={area ? `url(#g-${s.key})` : undefined} dot={data.length < 20 ? { r: 3 } : false} activeDot={{ r: 5 }} connectNulls />)}
  </Chart></ResponsiveContainer>
}

export const BarsChart = ({ data, x, series, height = 240, stacked, layout, colorByRow }: { data: any[]; x: string; series: Series[]; height?: number; stacked?: boolean; layout?: 'vertical'; colorByRow?: boolean }) =>
  <ResponsiveContainer width="100%" height={height}><BarChart data={data} layout={layout} margin={{ top: 8, right: 8, left: layout ? 28 : -18, bottom: 0 }}>
    <CartesianGrid vertical={!!layout} horizontal={!layout} strokeDasharray="3 3" />
    {layout ? <><XAxis type="number" {...axis} /><YAxis type="category" dataKey={x} {...axis} width={110} /></> : <><XAxis dataKey={x} {...axis} interval={0} /><YAxis {...axis} /></>}
    <Tooltip content={<Tip />} cursor={{ fill: 'var(--surface-2)' }} />{series.length > 1 && <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />}
    {series.map((s, i) => <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color || COLORS[i]} radius={layout ? [0, 6, 6, 0] : [6, 6, 0, 0]} stackId={stacked ? 'a' : undefined} maxBarSize={36}>
      {colorByRow && data.map((_, k) => <Cell key={k} fill={COLORS[k % COLORS.length]} />)}</Bar>)}
  </BarChart></ResponsiveContainer>

export const Donut = ({ data, height = 220, center }: { data: { name: string; value: number }[]; height?: number; center?: ReactNode }) =>
  <div style={{ position: 'relative' }}><ResponsiveContainer width="100%" height={height}><PieChart>
    <Pie data={data} dataKey="value" nameKey="name" innerRadius="62%" outerRadius="88%" paddingAngle={2} stroke="var(--surface)" strokeWidth={2}>{data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Pie>
    <Tooltip content={<Tip />} /></PieChart></ResponsiveContainer>
    {center && <div className="gauge-text" style={{ inset: 0, display: 'grid', placeItems: 'center', position: 'absolute', pointerEvents: 'none' }}>{center}</div>}</div>

export const Legend2 = ({ data }: { data: { name: string; value: number }[] }) =>
  <div className="stack" style={{ gap: 6 }}>{data.map((d, i) => <div key={d.name} className="row between small"><span className="row" style={{ gap: 8 }}><i style={{ width: 9, height: 9, borderRadius: 3, background: COLORS[i % COLORS.length], display: 'inline-block' }} />{d.name}</span><b className="mono">{d.value}</b></div>)}</div>

export const Radar2 = ({ data, height = 260 }: { data: { axis: string; value: number; max?: number }[]; height?: number }) =>
  <ResponsiveContainer width="100%" height={height}><RadarChart data={data} outerRadius="72%"><PolarGrid stroke="var(--grid)" /><PolarAngleAxis dataKey="axis" tick={{ fontSize: 11.5, fill: 'var(--text-2)' }} /><PolarRadiusAxis angle={30} tick={false} axisLine={false} />
    <Radar dataKey="value" stroke="var(--c1)" fill="var(--c1)" fillOpacity={0.28} strokeWidth={2} /><Tooltip content={<Tip />} /></RadarChart></ResponsiveContainer>

export const ComboChart = ({ data, x, bars, lines, height = 240 }: { data: any[]; x: string; bars: Series[]; lines: Series[]; height?: number }) =>
  <ResponsiveContainer width="100%" height={height}><ComposedChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}><CartesianGrid vertical={false} strokeDasharray="3 3" /><XAxis dataKey={x} {...axis} /><YAxis yAxisId="l" {...axis} /><YAxis yAxisId="r" orientation="right" {...axis} /><Tooltip content={<Tip />} /><Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
    {bars.map((s, i) => <Bar key={s.key} yAxisId="l" dataKey={s.key} name={s.name} fill={s.color || COLORS[i]} radius={[6, 6, 0, 0]} maxBarSize={30} fillOpacity={0.85} />)}
    {lines.map((s, i) => <Line key={s.key} yAxisId="r" type="monotone" dataKey={s.key} name={s.name} stroke={s.color || COLORS[(i + bars.length) % 8]} strokeWidth={2.4} dot={false} />)}</ComposedChart></ResponsiveContainer>

export const Spark = ({ data, k, color = 'var(--c1)', height = 44 }: { data: any[]; k: string; color?: string; height?: number }) =>
  <ResponsiveContainer width="100%" height={height}><AreaChart data={data} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}><defs><linearGradient id={`sp-${k}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity={0.4} /><stop offset="100%" stopColor={color} stopOpacity={0} /></linearGradient></defs>
    <Area type="monotone" dataKey={k} stroke={color} strokeWidth={2} fill={`url(#sp-${k})`} dot={false} connectNulls /></AreaChart></ResponsiveContainer>

/** Circular score ring (SVG). */
export function ScoreRing({ value, size = 150, label }: { value: number; size?: number; label?: string }) {
  const r = size / 2 - 11, c = 2 * Math.PI * r, tone = value >= 75 ? 'var(--ok)' : value >= 50 ? 'var(--warn)' : 'var(--bad)'
  return <div className="gauge-wrap" style={{ width: size, height: size }}><svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
    <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={11} />
    <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={tone} strokeWidth={11} strokeLinecap="round" strokeDasharray={`${(c * value) / 100} ${c}`} style={{ transition: 'stroke-dasharray .8s' }} /></svg>
    <div className="gauge-text"><div style={{ fontSize: size * 0.27, fontWeight: 800, letterSpacing: '-.03em', lineHeight: 1 }}>{Math.round(value)}</div>{label && <div className="tiny faint" style={{ marginTop: 2 }}>{label}</div>}</div></div>
}

/** Colour-scaled heat grid. rows × cols. */
export function Heat({ rows, cols, values, fmt, signed }: { rows: string[]; cols: string[]; values: (number | null)[][]; fmt?: (n: number) => string; signed?: boolean }) {
  const max = Math.max(1, ...values.flat().filter((v): v is number => v != null).map(Math.abs))
  const cell = (v: number | null) => {
    if (v == null) return { background: 'var(--surface-2)', color: 'var(--text-3)' }
    const a = Math.min(1, Math.abs(v) / max)
    const col = signed && v < 0 ? 'var(--c4)' : 'var(--c1)'
    return { background: `color-mix(in srgb, ${col} ${Math.round(8 + a * 80)}%, var(--surface))`, color: a > 0.55 ? '#fff' : 'var(--text)' }
  }
  return <div style={{ overflowX: 'auto' }}><div className="heat" style={{ gridTemplateColumns: `130px repeat(${cols.length}, minmax(34px, 1fr))`, minWidth: 130 + cols.length * 40 }}>
    <div />{cols.map(c => <div key={c} className="tiny faint" style={{ textAlign: 'center' }}>{c}</div>)}
    {rows.map((r, i) => <><div key={r} className="small muted" style={{ alignSelf: 'center', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r}</div>
      {values[i].map((v, j) => <div key={`${i}-${j}`} className="heat-cell" style={cell(v)} title={v == null ? '' : String(v)}>{v == null ? '' : fmt ? fmt(v) : v}</div>)}</>)}
  </div></div>
}
