import { Siren } from 'lucide-react'
import { Alert } from './ui'
export type EmergencyInfo = { message: string; resources: { label: string; value: string }[] }
export const EmergencyAlert = ({ info }: { info: EmergencyInfo }) =>
  <Alert tone="bad" icon={<Siren size={22} color="var(--bad)" />} title="This may be an emergency">
    <p>{info.message}</p><ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>{info.resources.map(r => <li key={r.label}><b>{r.label}:</b> {r.value}</li>)}</ul></Alert>
