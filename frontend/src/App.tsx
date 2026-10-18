import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import { useApp } from './lib/store'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'

const P = (f: () => Promise<any>) => lazy(f)
const Story = P(() => import('./pages/Story')), Survey = P(() => import('./pages/Survey')), Tracker = P(() => import('./pages/Tracker')), Vitals = P(() => import('./pages/Vitals'))
const Reports = P(() => import('./pages/Reports')), Labs = P(() => import('./pages/Labs')), Medicines = P(() => import('./pages/Medicines')), Timeline = P(() => import('./pages/Timeline'))
const Insights = P(() => import('./pages/Insights')), Echo = P(() => import('./pages/Echo')), Guard = P(() => import('./pages/Guard')), Doctors = P(() => import('./pages/Doctors'))
const Appointments = P(() => import('./pages/Appointments')), Family = P(() => import('./pages/Family')), Emergency = P(() => import('./pages/Emergency')), Consult = P(() => import('./pages/Consult'))
const Wellness = P(() => import('./pages/Wellness')), Learn = P(() => import('./pages/Learn')), Analytics = P(() => import('./pages/Analytics')), SettingsPage = P(() => import('./pages/Settings'))
const Admin = P(() => import('./pages/Admin')), PublicEmergency = P(() => import('./pages/PublicEmergency'))
const Verification = P(() => import('./pages/Verification')), Vault = P(() => import('./pages/Vault')), Alerts = P(() => import('./pages/Alerts')), Sharing = P(() => import('./pages/Sharing'))
const Privacy = P(() => import('./pages/Privacy')), VerifiedReport = P(() => import('./pages/VerifiedReport')), VerifiedPrint = P(() => import('./pages/VerifiedPrint'))
const PublicVerify = P(() => import('./pages/PublicVerify')), PublicShare = P(() => import('./pages/PublicShare'))

const Fallback = () => <div style={{ display: 'grid', placeItems: 'center', height: 240 }}><Spinner /></div>

export default function App() {
  const { user, ready } = useApp()
  if (!ready) return <Fallback />
  return <Suspense fallback={<Fallback />}><Routes>
    <Route path="/e/:token" element={<PublicEmergency />} />
    <Route path="/verify/:id" element={<PublicVerify />} /><Route path="/s/:token" element={<PublicShare />} />
    {!user ? <><Route path="/login" element={<Login />} /><Route path="*" element={<Navigate to="/login" replace />} /></> :
      <><Route path="/login" element={<Navigate to="/" replace />} />
        <Route path="/verified-report/:id/print" element={<VerifiedPrint />} />
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} /><Route path="analytics" element={<Analytics />} /><Route path="timeline" element={<Timeline />} />
          <Route path="story" element={<Story />} /><Route path="survey" element={<Survey />} /><Route path="tracker" element={<Tracker />} /><Route path="vitals" element={<Vitals />} />
          <Route path="reports" element={<Reports />} /><Route path="labs" element={<Labs />} /><Route path="medicines" element={<Medicines />} />
          <Route path="insights" element={<Insights />} /><Route path="echo" element={<Echo />} /><Route path="guard" element={<Guard />} />
          <Route path="doctors" element={<Doctors />} /><Route path="appointments" element={<Appointments />} /><Route path="consult" element={<Consult />} /><Route path="emergency" element={<Emergency />} /><Route path="family" element={<Family />} />
          <Route path="wellness" element={<Wellness />} /><Route path="learn" element={<Learn />} /><Route path="settings" element={<SettingsPage />} /><Route path="admin" element={<Admin />} />
          <Route path="verification" element={<Verification />} /><Route path="vault" element={<Vault />} /><Route path="verified-report" element={<VerifiedReport />} />
          <Route path="alerts" element={<Alerts />} /><Route path="sharing" element={<Sharing />} /><Route path="privacy" element={<Privacy />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route></>}
  </Routes></Suspense>
}
