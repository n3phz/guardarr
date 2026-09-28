import { useEffect, useState } from 'react'
import { Router as AppRouter } from './Router'
import { Header } from './components/Header'
import { Sidebar } from './components/Sidebar'
import { api } from './services/api'
import type { StatusResponse } from './types'

function App() {
  const [status, setStatus] = useState<StatusResponse | null>(null)

  useEffect(() => {
    loadStatus()
    const interval = setInterval(loadStatus, 15000)
    return () => clearInterval(interval)
  }, [])

  const loadStatus = async () => {
    try {
      const data = await api.status()
      setStatus(data)
    } catch {
      // Silently fail - header will show unknown state
    }
  }

  return (
    <div className="app">
      <Sidebar />
      <div className="app-main" style={{ '--sidebar-width': '280px' } as React.CSSProperties}>
        <Header status={status} />
        <main className="app-content" role="main">
          <AppRouter />
        </main>
      </div>
    </div>
  )
}

export default App