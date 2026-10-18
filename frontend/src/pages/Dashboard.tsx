import { curLocale } from '../lib/translate'
import { useNavigate } from 'react-router-dom'
import { Activity, AlertTriangle, Apple, CalendarClock, Droplets, Flame, FlaskConical, HeartPulse, MessageCircleHeart, Moon, Pill, ScrollText, Sparkles, Brain, Wand2, Coffee, Footprints, Zap } from 'lucide-react'
import { useApp } from '../lib/store'
import { api } from '../lib/api'
import { fmtDate, refText, shortDate, useFetch } from '../lib/hooks'
import { Alert, Badge, Btn, Card, CardHead, Empty, Loading, Marquee, Progress, Slideshow, Stat, toneOf } from '../components/ui'
import { BarsChart, Donut, Legend2, Radar2, ScoreRing, TrendChart } from '../components/charts'

const TIPS = [
  { icon: <Droplets size={15} />, text: 'Hydration: sip water through the day, not all at once' }, { icon: <Moon size={15} />, text: 'Aim for 7–9 hours of consistent sleep' },
  { icon: <Footprints size={15} />, text: '10 minutes of walking after meals supports steady blood sugar' }, { icon: <Apple size={15} />, text: 'Fill half your plate with vegetables and fruit' },
  { icon: <Coffee size={15} />, text: 'Caffeine can linger 6+ hours: try an earlier cut-off' }, { icon: <Brain size={15} />, text: '3 minutes of slow breathing can settle a racing mind' },
  { icon: <Zap size={15} />, text: 'Stand and stretch every 45–60 minutes at your desk' },
]

export default function Dashboard() {
  const { user, profile, t, toast, bump } = useApp(); const nav = useNavigate()
  const { data: d, loading, reload } = useFetch<any>('/api/dashboard')
  const seed = async () => { try { await api.post('/api/demo/seed'); toast('Demo data loaded', 'ok'); bump(); reload() } catch (e: any) { toast(e.message, 'bad') } }
  if (loading && !d) return <Loading rows={6} />
  if (!d) return <Empty title="Could not load dashboard" />
  const empty = d.counts.evidence === 0 && d.tracker.length === 0 && d.counts.reports === 0
  const lv = d.latest_vital
  const themeData = d.themes.slice(0, 6).map((x: any) => ({ name: x.theme, value: x.count }))
  const radar = [{ axis: 'Sleep', value: Math.min(10, (d.week_avg.sleep || 0) * 10 / 9) }, { axis: 'Energy', value: d.week_avg.energy || 0 }, { axis: 'Calm', value: d.week_avg.stress != null ? 10 - d.week_avg.stress : 0 },
    { axis: 'Comfort', value: d.week_avg.pain != null ? 10 - d.week_avg.pain : 0 }, { axis: 'Hydration', value: Math.min(10, (d.week_avg.water || 0) * 10 / 8) }]
  const trk = d.tracker.map((r: any) => ({ ...r, day: shortDate(r.entry_date) }))
  return <div className="stack" style={{ gap: 20 }}>
    <div className="hero fade-in"><div className="row between wrap" style={{ position: 'relative', zIndex: 1, gap: 24 }}>
      <div><div className="eyebrow" style={{ color: 'rgba(255,255,255,.75)' }}>{new Date().toLocaleDateString(curLocale(), { weekday: 'long', day: 'numeric', month: 'long' })}</div>
        <h1>{t('welcome')}, {user?.name.split(' ')[0]}</h1><p>Viewing <b>{profile?.name}</b>. {d.flag_count ? `${d.flag_count} item${d.flag_count > 1 ? 's' : ''} worth discussing with your clinician.` : 'Nothing is flagged right now. Keep logging to stay ahead.'}</p>
        <div className="row wrap" style={{ marginTop: 18 }}><Btn variant="primary" onClick={() => nav('/tracker')}><Activity size={16} />Log today</Btn><Btn onClick={() => nav('/echo')}><MessageCircleHeart size={16} />Ask Echo</Btn><Btn onClick={() => nav('/insights')}><Sparkles size={16} />View insights</Btn></div></div>
      <div className="row" style={{ background: 'rgba(255,255,255,.14)', borderRadius: 20, padding: '14px 20px', gap: 18 }}><ScoreRing value={d.score.score} size={118} /><div><div style={{ fontWeight: 700, fontSize: 15 }}>{t('health_score')}</div><div className="small" style={{ opacity: .85 }}>Self-reported indicator</div><div className="row small" style={{ marginTop: 8 }}><Flame size={15} />{d.streak}-day streak</div></div></div>
    </div></div>

    {empty && <Alert tone="info" icon={<Wand2 size={18} />} title="This profile is empty">Add your first story or check-in, or load a realistic 45-day demo history to explore every chart, flag and insight. <Btn size="sm" variant="primary" onClick={seed} style={{ marginLeft: 10 }}>Load demo data</Btn></Alert>}

    <Marquee items={TIPS} />

    <div className="grid g4">
      <Stat label="Story entries" value={d.counts.story} icon={<ScrollText size={15} />} foot={`${d.counts.evidence} evidence chunks indexed`} />
      <Stat label="Medicine adherence" value={d.adherence.percent ?? '—'} unit={d.adherence.percent != null ? '%' : undefined} icon={<Pill size={15} />} tone={d.adherence.percent != null && d.adherence.percent < 60 ? 'bad' : 'ok'} foot={`${d.adherence.taken}/${d.adherence.expected} doses this week`} />
      <Stat label="Reports on file" value={d.counts.reports} icon={<FlaskConical size={15} />} tone={d.lab_alerts.length ? 'warn' : undefined} foot={`${d.lab_alerts.length} value(s) out of range`} />
      <Stat label="AI insights" value={d.counts.insights} icon={<Sparkles size={15} />} foot={`${d.counts.appointments} upcoming appointment(s)`} />
    </div>

    <div className="grid g-main">
      <Card><CardHead title="14-day wellbeing trend" sub="Sleep, energy and stress from your daily check-ins" right={<Btn size="sm" onClick={() => nav('/analytics')}>Open analytics</Btn>} />
        {trk.length ? <TrendChart data={trk} x="day" area height={270} series={[{ key: 'sleep_hours', name: 'Sleep (h)' }, { key: 'energy_level', name: 'Energy /10' }, { key: 'stress_level', name: 'Stress /10' }]} /> : <Empty title="No check-ins yet" sub="Log your first day to see trends." />}</Card>
      <Card><CardHead title="This week's balance" sub="Higher is better on every axis" /><Radar2 data={radar} height={280} /></Card>
    </div>

    <div className="grid g3">
      <Card><CardHead title="Risk flags" sub="Cross-source discussion points" icon={<AlertTriangle size={17} />} />
        {d.flags.length ? d.flags.slice(0, 4).map((f: any, i: number) => <div className="list-item" key={i}><Badge tone={toneOf(f.level)}>{f.level}</Badge><div><b className="small">{f.title}</b><div className="small muted">{f.detail}</div></div></div>) : <Empty title="Nothing flagged" sub="Great: no patterns need attention." />}</Card>
      <Card><CardHead title="Symptom themes" sub="From your evidence, by specialty" />{themeData.length ? <><Donut data={themeData} height={180} center={<div><b style={{ fontSize: 22 }}>{d.themes.reduce((a: number, x: any) => a + x.count, 0)}</b><div className="tiny faint">mentions</div></div>} /><Legend2 data={themeData} /></> : <Empty title="No themes yet" sub="Themes appear as you write your story." />}</Card>
      <Card><CardHead title="Latest vitals" icon={<HeartPulse size={17} />} right={<Btn size="sm" onClick={() => nav('/vitals')}>Details</Btn>} />
        {lv ? <div className="stack" style={{ gap: 10 }}>
          {[['Blood pressure', lv.systolic ? `${lv.systolic}/${lv.diastolic} mmHg` : null, lv.bp_cat], ['BMI', lv.bmi ? `${lv.bmi}` : null, lv.bmi_cat], ['Fasting sugar', lv.fasting_sugar ? `${lv.fasting_sugar} mg/dL` : null, lv.fasting_cat], ['Post-meal sugar', lv.postmeal_sugar ? `${lv.postmeal_sugar} mg/dL` : null, lv.postmeal_cat]].filter(r => r[1]).map(([n, v, c]: any) =>
            <div className="row between" key={n}><div><div className="small muted">{n}</div><b className="mono">{v}</b></div>{c && <Badge tone={toneOf(c[1])}>{c[0]}</Badge>}</div>)}<div className="tiny faint">Recorded {fmtDate(lv.entry_date)}</div>{d.vitals_trend.length > 1 && <TrendChart data={d.vitals_trend.map((v: any) => ({ ...v, day: shortDate(v.date) }))} x="day" height={120} series={[{ key: 'systolic', name: 'Systolic' }, { key: 'diastolic', name: 'Diastolic' }]} />}</div> : <Empty title="No vitals yet" />}</Card>
    </div>

    <div className="grid g-main">
      <Card><CardHead title="Out-of-range lab values" sub="Latest reading per test" icon={<FlaskConical size={17} />} right={<Btn size="sm" onClick={() => nav('/labs')}>Lab trends</Btn>} />
        {d.lab_alerts.length ? <div className="table-wrap"><table className="table"><thead><tr><th>Test</th><th>Latest</th><th>Reference</th><th>Trend</th><th>Status</th></tr></thead><tbody>{d.lab_alerts.map((a: any, i: number) => <tr key={i}><td><b>{a.label}</b></td><td className="mono">{a.value} {a.unit}</td><td className="mono muted">{refText(a.low, a.high)}</td><td>{a.trend || '—'}</td><td><Badge tone="bad">{a.direction}</Badge></td></tr>)}</tbody></table></div> : <Empty title="All reported values are in range" />}{d.lab_history.length > 0 && <div style={{ marginTop: 16 }}><div className="small muted" style={{ marginBottom: 4 }}>Values per report</div><BarsChart data={d.lab_history.map((r: any) => ({ ...r, day: shortDate(r.date) }))} x="day" stacked height={140} series={[{ key: 'in_range', name: 'In range', color: 'var(--ok)' }, { key: 'out_of_range', name: 'Out of range', color: 'var(--bad)' }]} /></div>}</Card>
      <div className="stack">
        <Card><CardHead title="Upcoming" icon={<CalendarClock size={17} />} />{d.upcoming.length ? d.upcoming.map((a: any) => <div className="list-item" key={a.id}><span className="icon-chip">{new Date(a.appt_date + 'T00:00').getDate()}</span><div><b className="small">{a.doctor_name}</b><div className="small muted">{fmtDate(a.appt_date)} · {a.appt_time} · {a.hospital}</div></div></div>) : <p className="muted small">No upcoming appointments.</p>}</Card>
        <Card><CardHead title="Goals" />{d.goals.length ? <div className="stack" style={{ gap: 12 }}>{d.goals.slice(0, 4).map((g: any) => { const p = Math.min(100, (g.current / g.target) * 100); return <div key={g.id}><div className="row between small"><span>{g.title}</span><b className="mono">{g.current}/{g.target}</b></div><Progress value={p} tone={p >= 100 ? 'ok' : p < 40 ? 'warn' : undefined} /></div> })}</div> : <p className="muted small">Set goals in Wellness &amp; Goals.</p>}</Card>
      </div>
    </div>

    <Slideshow height={170} slides={[
      { icon: <HeartPulse size={20} />, title: 'Know your numbers', body: 'Blood pressure, sugar and BMI trends are most useful when recorded on a steady schedule. Add vitals weekly.' },
      { icon: <Moon size={20} />, title: 'Sleep is a vital sign', body: 'A week of short sleep is something EchoCare will flag as a discussion point, alongside stress and energy.' },
      { icon: <Brain size={20} />, title: 'Let evidence speak', body: 'Insights are generated only when multiple sources agree, and you can always see exactly why.' }]} />
  </div>
}
