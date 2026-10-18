import { useEffect, useState } from 'react'
import { Save } from 'lucide-react'
import { api } from '../lib/api'
import { useApp } from '../lib/store'
import { useFetch } from '../lib/hooks'
import { Btn, Card, CardHead, Field, Loading, PageHead, Progress } from '../components/ui'
import { EmergencyAlert, EmergencyInfo } from '../components/Emergency'

const SCHEMA: Record<string, { title: string; fields: { k: string; label: string; type?: 'select' | 'area'; opts?: string[] }[] }> = {
  about_you: { title: 'About you', fields: [{ k: 'age', label: 'Age' }, { k: 'gender', label: 'Gender', type: 'select', opts: ['', 'Female', 'Male', 'Other', 'Prefer not to say'] }, { k: 'occupation', label: 'Occupation' }, { k: 'activity_level', label: 'Activity level', type: 'select', opts: ['', 'Low', 'Moderate', 'High'] }] },
  main_concern: { title: 'Main concern', fields: [{ k: 'primary_concern', label: 'What is your main health concern?', type: 'area' }, { k: 'since_when', label: 'Since when?' }, { k: 'what_helps', label: 'What helps or makes it worse?', type: 'area' }] },
  care_context: { title: 'Care context', fields: [{ k: 'conditions', label: 'Known conditions' }, { k: 'allergies', label: 'Allergies' }, { k: 'family_history', label: 'Family history' }, { k: 'current_care', label: 'Currently seeing a doctor for this?', type: 'select', opts: ['', 'Yes', 'No', 'Planning to'] }] },
}
export default function Survey() {
  const { toast } = useApp(); const { data, loading } = useFetch<any>('/api/survey'); const [form, setForm] = useState<any>({}); const [em, setEm] = useState<EmergencyInfo | null>(null)
  useEffect(() => { if (data) setForm({ about_you: data.about_you || {}, main_concern: data.main_concern || {}, care_context: data.care_context || {} }); else setForm({ about_you: {}, main_concern: {}, care_context: {} }) }, [data])
  const total = Object.values(SCHEMA).reduce((a, g) => a + g.fields.length, 0); const filled = Object.keys(SCHEMA).reduce((a, g) => a + SCHEMA[g].fields.filter(f => form[g]?.[f.k]).length, 0)
  const save = async () => { setEm(null); try { const r = await api.put('/api/survey', form); if (r.is_emergency) setEm(r); else toast('Survey saved', 'ok') } catch (e: any) { toast(e.message, 'bad') } }
  if (loading) return <Loading rows={5} />
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Record" title="Health Survey" sub="A structured snapshot that feeds your evidence base and the consultation report." right={<div style={{ width: 200 }}><div className="row between tiny faint"><span>Completeness</span><b>{Math.round(100 * filled / total)}%</b></div><Progress value={100 * filled / total} /></div>} />
    {em && <EmergencyAlert info={em} />}
    <div className="grid g3">{Object.entries(SCHEMA).map(([g, s]) => <Card key={g}><CardHead title={s.title} /><div className="stack">{s.fields.map(f => <Field key={f.k} label={f.label}>
      {f.type === 'select' ? <select className="select" value={form[g]?.[f.k] || ''} onChange={e => setForm({ ...form, [g]: { ...form[g], [f.k]: e.target.value } })}>{f.opts!.map(o => <option key={o} value={o}>{o || 'Select…'}</option>)}</select>
        : f.type === 'area' ? <textarea className="textarea" style={{ minHeight: 84 }} value={form[g]?.[f.k] || ''} onChange={e => setForm({ ...form, [g]: { ...form[g], [f.k]: e.target.value } })} />
          : <input className="input" value={form[g]?.[f.k] || ''} onChange={e => setForm({ ...form, [g]: { ...form[g], [f.k]: e.target.value } })} />}</Field>)}</div></Card>)}</div>
    <div className="row end"><Btn variant="primary" onClick={save}><Save size={16} />Save survey</Btn></div>
  </div>
}
