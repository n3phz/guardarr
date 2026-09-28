import { NavLink, useLocation } from 'react-router-dom'
import { cn } from '../utils/formatters'

const navItems = [
  { path: '/', label: 'Dashboard', icon: DashboardIcon },
  { path: '/reservations', label: 'Reservations', icon: DatabaseIcon },
  { path: '/integrations', label: 'Integrations', icon: PlugIcon },
  { path: '/reconciliation', label: 'Reconciliation', icon: RefreshIcon },
  { path: '/settings', label: 'Settings', icon: SettingsIcon },
] as const

function DashboardIcon({ className }: { className?: string }) {
  return (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  )
}

function DatabaseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M3 5v14c0 1.7 3.5 3 9 3s9-1.3 9-3V5" />
      <path d="M3 12c0 1.7 3.5 3 9 3s9-1.3 9-3" />
    </svg>
  )
}

function PlugIcon({ className }: { className?: string }) {
  return (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M6.3 20.3a2.4 2.4 0 0 0 3.4 0L12 18l-2.3-2.3a2.4 2.4 0 0 1 0-3.4l2.3-2.3" />
      <path d="M17.7 3.7a2.4 2.4 0 0 1 0 3.4l2.3 2.3a2.4 2.4 0 0 0 3.4 0L22 9l-2.3 2.3a2.4 2.4 0 0 1 0 3.4l2.3 2.3" />
      <path d="M12 2v20" />
    </svg>
  )
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
      <polyline points="23 4 23 10 17 10" />
    </svg>
  )
}

function SettingsIcon({ className }: { className?: string }) {
  return (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  )
}

export function Sidebar() {
  const location = useLocation()

  return (
    <aside className="sidebar" role="navigation" aria-label="Main navigation">
      <div className="sidebar-header">
        <NavLink to="/" className="sidebar-logo" aria-label="Guardarr Home">
          <svg className="logo-shield" viewBox="0 0 112 143" fill="none">
            <path d="M56 0L112 40v103c0 83-48 143-112 176C48 286 0 226 0 143V40Z" stroke="var(--cyan)" strokeWidth="8" />
            <path d="M56 24L100 55v85c0 65-35 114-88 145-53-31-88-80-88-145V55Z" fill="none" stroke="var(--blue)" strokeWidth="4" opacity="0.9" />
            <path d="M44 82 44 190 83 136Z" fill="var(--text-primary)" />
          </svg>
          <span className="logo-text">Guardarr</span>
        </NavLink>
      </div>

      <nav className="sidebar-nav" aria-label="Sidebar navigation">
        <ul role="list">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path
            return (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  className={cn('nav-link', isActive && 'active')}
                  aria-current={isActive ? 'page' : undefined}
                >
                  <span className="nav-icon" aria-hidden="true">
                    <item.icon className="nav-icon-svg" />
                  </span>
                  <span className="nav-label">{item.label}</span>
                </NavLink>
              </li>
            )
          })}
        </ul>
      </nav>

      <div className="sidebar-footer">
        <div className="version-info">
          <span className="version-label">v0.1.2</span>
          <span className="version-status">alpha</span>
        </div>
      </div>
    </aside>
  )
}