import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet'
import { LocateFixed, MapPin, Navigation, Phone, Star, CalendarPlus } from 'lucide-react'
import { api } from '../lib/api'
import { useApp } from '../lib/store'
import { useFetch } from '../lib/hooks'
import { Alert, Badge, Btn, Card, CardHead, DataTable, Field, Modal, PageHead, Stat } from '../components/ui'
import { BarsChart } from '../components/charts'
import { useNavigate } from 'react-router-dom'

function Fly({ center, zoom }: { center: [number, number]; zoom: number }) { const map = useMap(); useEffect(() => { map.flyTo(center, zoom, { duration: 0.8 }) }, [center[0], center[1], zoom]); return null }

const SHORT: Record<string, string> = { 'General Medicine': 'General', Neurology: 'Neuro', Cardiology: 'Cardio', Gastroenterology: 'Gastro', Dermatology: 'Derma', Orthopedics: 'Ortho', ENT: 'ENT', Pulmonology: 'Pulmo', 'Psychiatry / Mental Health': 'Psych', Gynecology: 'Gynae' }
export default function Doctors() {
  const { toast } = useApp(); const nav = useNavigate(); const meta = useFetch<any>('/api/doctors/meta'); const stats = useFetch<any>('/api/doctors/stats')
  const [district, setDistrict] = useState('All'); const [specialty, setSpecialty] = useState('All'); const [minRating, setMinRating] = useState(0); const [me, setMe] = useState<[number, number] | null>(null); const [q, setQ] = useState('')
  const [sel, setSel] = useState<any>(null); const [book, setBook] = useState<any>(null); const [when, setWhen] = useState({ appt_date: '', appt_time: '10:00' })
  const params = new URLSearchParams({ ...(district !== 'All' && { district }), ...(specialty !== 'All' && { specialty }), ...(minRating && { min_rating: String(minRating) }), ...(q && { q }), ...(me && { lat: String(me[0]), lon: String(me[1]) }) } as any)
  const list = useFetch<any>(`/api/doctors?${params}`)
  const items: any[] = list.data?.items || []
  const center: [number, number] = useMemo(() => { if (me) return me; if (district !== 'All' && meta.data?.districts?.[district]) return meta.data.districts[district]; return [11.1, 78.4] }, [district, me, meta.data])
  const zoom = me ? 11 : district !== 'All' ? 11 : 7
  const locate = () => navigator.geolocation ? navigator.geolocation.getCurrentPosition(p => { setMe([p.coords.latitude, p.coords.longitude]); toast('Ranking by distance from you', 'ok') }, () => toast('Location permission denied', 'bad')) : toast('Geolocation unavailable', 'bad')
  const bookIt = async () => { await api.post('/api/appointments', { doctor_name: book.name, specialty: book.specialty, hospital: book.hospital, ...when }); toast('Appointment added', 'ok'); setBook(null); nav('/appointments') }
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Care" title="Find doctors, district by district" sub="Filter by district and specialty, rank by rating, experience and distance, then navigate or book." right={<Btn onClick={locate}><LocateFixed size={16} />Use my location</Btn>} />
    {meta.data?.source === 'demo' && <Alert tone="warn" icon={<MapPin size={18} />} title="Demo directory">{meta.data.disclaimer} Admins can import a real CSV/Excel directory.</Alert>}
    <Card><div className="grid g4"><Field label="District"><select className="select" value={district} onChange={e => setDistrict(e.target.value)}><option>All</option>{Object.keys(meta.data?.districts || {}).map(d => <option key={d}>{d}</option>)}</select></Field>
      <Field label="Specialty"><select className="select" value={specialty} onChange={e => setSpecialty(e.target.value)}><option>All</option>{(meta.data?.specialties || []).map((s: string) => <option key={s}>{s}</option>)}</select></Field>
      <Field label={`Minimum rating: ${minRating || 'any'}`}><input className="range" type="range" min={0} max={5} step={0.5} value={minRating} onChange={e => setMinRating(Number(e.target.value))} /></Field>
      <Field label="Search name / hospital"><input className="input" value={q} onChange={e => setQ(e.target.value)} /></Field></div></Card>
    <div className="grid g-main">
      <Card style={{ padding: 12 }}><div className="map-box"><MapContainer center={center} zoom={zoom} style={{ height: '100%', width: '100%' }} scrollWheelZoom>
        <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" /><Fly center={center} zoom={zoom} />
        {items.slice(0, 300).map(d => <CircleMarker key={d.id} center={[d.lat, d.lon]} radius={sel?.id === d.id ? 11 : 7} pathOptions={{ color: '#fff', weight: 2, fillColor: d.rating >= 4.5 ? '#0f9d6b' : d.rating >= 4 ? '#2563eb' : '#f59e0b', fillOpacity: .95 }} eventHandlers={{ click: () => setSel(d) }}>
          <Popup><b>{d.name}</b><br />{d.specialty}<br />{d.hospital}<br />★ {d.rating} · {d.years_experience} yrs · ₹{d.consultation_fee_inr}<br /><a href={d.navigate_url} target="_blank" rel="noreferrer">Navigate →</a></Popup></CircleMarker>)}
        {me && <CircleMarker center={me} radius={9} pathOptions={{ color: '#fff', weight: 3, fillColor: '#e5484d', fillOpacity: 1 }}><Popup>You are here</Popup></CircleMarker>}</MapContainer></div>
        <div className="row small faint" style={{ padding: '10px 6px 0', gap: 16 }}><span style={{ color: '#0f9d6b' }}>● 4.5+</span><span style={{ color: '#2563eb' }}>● 4.0+</span><span style={{ color: '#f59e0b' }}>● below 4</span><span className="grow" />{items.length} doctors</div></Card>
      <div className="stack"><Stat label="Matching doctors" value={items.length} icon={<MapPin size={15} />} foot={me ? 'ranked with distance' : 'ranked by rating + experience'} />
        <Card><CardHead title="Top matches" />{items.slice(0, 4).map(d => <div className="list-item" key={d.id} style={{ cursor: 'pointer' }} onClick={() => setSel(d)}><span className="icon-chip">{d.rating.toFixed(1)}</span><div className="grow"><b className="small">{d.name}</b><div className="tiny muted">{d.specialty} · {d.hospital}{d.distance_km != null && ` · ${d.distance_km} km`}</div></div></div>)}</Card></div></div>
    {sel && <Card><div className="row between wrap"><div className="row"><span className="icon-chip lg"><Star size={18} /></span><div><h2>{sel.name}</h2><div className="muted small">{sel.specialty} · {sel.hospital}, {sel.district}</div></div></div><div className="row wrap"><Badge tone="ok">★ {sel.rating}</Badge><Badge>{sel.years_experience} yrs</Badge><Badge>₹{sel.consultation_fee_inr}</Badge><a className="btn" href={sel.navigate_url} target="_blank" rel="noreferrer"><Navigation size={15} />Navigate</a>{sel.phone && <a className="btn" href={`tel:${sel.phone}`}><Phone size={15} />{sel.phone}</a>}<Btn variant="primary" onClick={() => setBook(sel)}><CalendarPlus size={15} />Book</Btn></div></div></Card>}
    <div className="grid g2"><Card><CardHead title="Doctors by specialty" sub="Directory coverage" /><BarsChart data={(stats.data?.by_specialty || []).map((s: any) => ({ s: SHORT[s.specialty] || s.specialty, n: s.count }))} x="s" height={260} series={[{ key: 'n', name: 'Doctors' }]} /></Card>
      <Card><CardHead title="Avg consultation fee (₹)" sub="By specialty" /><BarsChart data={(stats.data?.by_specialty || []).map((s: any) => ({ s: SHORT[s.specialty] || s.specialty, fee: s.avg_fee }))} x="s" height={260} series={[{ key: 'fee', name: 'Avg fee ₹', color: 'var(--c2)' }]} /></Card></div>
    <Card><CardHead title="Directory" sub="Sortable results" /><DataTable rows={items} pageSize={8} cols={[{ key: 'name', label: 'Doctor', sort: d => d.name, render: d => <b>{d.name}</b> }, { key: 'specialty', label: 'Specialty', sort: d => d.specialty }, { key: 'hospital', label: 'Hospital' }, { key: 'district', label: 'District', sort: d => d.district }, { key: 'rating', label: 'Rating', sort: d => d.rating, render: d => `★ ${d.rating}` }, { key: 'years_experience', label: 'Exp.', sort: d => d.years_experience, render: d => `${d.years_experience} y` }, { key: 'fee', label: 'Fee', sort: d => d.consultation_fee_inr, render: d => `₹${d.consultation_fee_inr}` }, { key: 'distance_km', label: 'Distance', sort: d => d.distance_km ?? 9999, render: d => d.distance_km != null ? `${d.distance_km} km` : '—' }, { key: 'go', label: '', render: d => <a href={d.navigate_url} target="_blank" rel="noreferrer">Navigate</a> }]} /></Card>
    <Modal open={!!book} onClose={() => setBook(null)} title={`Book with ${book?.name || ''}`}><div className="stack"><div className="form-grid"><Field label="Date"><input className="input" type="date" value={when.appt_date} onChange={e => setWhen({ ...when, appt_date: e.target.value })} /></Field><Field label="Time"><input className="input" type="time" value={when.appt_time} onChange={e => setWhen({ ...when, appt_time: e.target.value })} /></Field></div><div className="row end"><Btn onClick={() => setBook(null)}>Cancel</Btn><Btn variant="primary" disabled={!when.appt_date} onClick={bookIt}>Add to appointments</Btn></div></div></Modal>
  </div>
}
