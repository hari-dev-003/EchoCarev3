import { useState } from 'react'
import { Plus, Trash2, UserCheck } from 'lucide-react'
import { api } from '../lib/api'
import { useApp } from '../lib/store'
import { Avatar, Badge, Btn, Card, CardHead, Confirm, Field, Modal, PageHead } from '../components/ui'

const REL = ['mother', 'father', 'spouse', 'child', 'sibling', 'grandparent', 'other']
export default function Family() {
  const { profiles, profile, switchProfile, refreshProfiles, toast } = useApp(); const [open, setOpen] = useState(false); const [f, setF] = useState({ name: '', relation: 'mother', dob: '', gender: '' }); const [del, setDel] = useState<any>(null)
  const add = async () => { try { const p = await api.post('/api/profiles', f); await refreshProfiles(); switchProfile(p.id); setOpen(false); setF({ name: '', relation: 'mother', dob: '', gender: '' }); toast('Profile created. Records are fully separate.', 'ok') } catch (e: any) { toast(e.message, 'bad') } }
  return <div className="stack" style={{ gap: 20 }}>
    <PageHead eyebrow="Care" title="Family profiles" sub="Manage health records for people you care for. Each profile has fully separate stories, vitals, reports, insights and an emergency card." right={<Btn variant="primary" onClick={() => setOpen(true)}><Plus size={16} />Add family member</Btn>} />
    <div className="grid g3">{profiles.filter(p => !p.shared).map(p => <Card key={p.id} hover style={p.id === profile?.id ? { borderColor: 'var(--primary)', boxShadow: '0 0 0 3px var(--primary-50)' } : undefined}><div className="row"><Avatar name={p.name} lg /><div className="grow"><h3>{p.name}</h3><div className="small muted" style={{ textTransform: 'capitalize' }}>{p.relation}</div></div>{p.id === profile?.id && <Badge tone="ok">active</Badge>}</div>
      <div className="row" style={{ marginTop: 16 }}><Btn size="sm" disabled={p.id === profile?.id} onClick={() => switchProfile(p.id)}><UserCheck size={14} />Switch to</Btn>{p.relation !== 'self' && <Btn size="sm" variant="danger" onClick={() => setDel(p)}><Trash2 size={14} />Delete</Btn>}</div></Card>)}</div>
    <Card className="flat"><p className="small muted">Tip: use the profile switcher in the top bar at any time. Deleting a profile permanently removes all of its data, including its ChromaDB evidence vectors.</p></Card>
    <Modal open={open} onClose={() => setOpen(false)} title="Add family member"><div className="stack"><Field label="Name"><input className="input" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} /></Field><div className="form-grid"><Field label="Relation"><select className="select" value={f.relation} onChange={e => setF({ ...f, relation: e.target.value })}>{REL.map(r => <option key={r}>{r}</option>)}</select></Field><Field label="Date of birth"><input className="input" type="date" value={f.dob} onChange={e => setF({ ...f, dob: e.target.value })} /></Field></div><div className="row end"><Btn onClick={() => setOpen(false)}>Cancel</Btn><Btn variant="primary" disabled={!f.name.trim()} onClick={add}>Create</Btn></div></div></Modal>
    <Confirm open={!!del} title={`Delete ${del?.name}?`} text="All records for this profile will be permanently deleted." onNo={() => setDel(null)} onYes={async () => { await api.del(`/api/profiles/${del.id}`); setDel(null); await refreshProfiles(); }} />
  </div>
}
