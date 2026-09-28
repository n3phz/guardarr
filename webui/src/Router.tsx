import { Routes, Route } from 'react-router-dom'
import { Dashboard } from './pages/Dashboard'
import { Reservations } from './pages/Reservations'
import { Integrations } from './pages/Integrations'
import { Reconciliation } from './pages/Reconciliation'
import { Settings } from './pages/Settings'

export function Router() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/reservations" element={<Reservations />} />
      <Route path="/integrations" element={<Integrations />} />
      <Route path="/reconciliation" element={<Reconciliation />} />
      <Route path="/settings" element={<Settings />} />
    </Routes>
  )
}