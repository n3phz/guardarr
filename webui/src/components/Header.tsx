import { useState } from 'react'
import { Link } from 'react-router-dom'
import { formatBytes, getThresholdStateColor } from '../utils/formatters'
import { StatusResponse } from '../types'
import { cn } from '../utils/formatters'

interface HeaderProps {
  status: StatusResponse | null
}

export function Header({ status }: HeaderProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const thresholdState = status?.current_threshold_state ?? 'UNKNOWN'
  const stateColor = getThresholdStateColor(thresholdState)
  const available = status?.available_bytes ?? 0
  const total = status?.total_bytes ?? 0

  return (
    <header className="header" role="banner">
      <div className="header-left">
        <button
          className="mobile-menu-btn"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-expanded={mobileMenuOpen}
          aria-controls="sidebar"
          aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            {mobileMenuOpen ? (
              <path d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path d="M3 12h18M3 6h18M3 18h18" />
            )}
          </svg>
        </button>

        <Link to="/" className="header-logo" aria-label="Guardarr Home">
          <svg className="logo-shield" viewBox="0 0 112 143" fill="none">
            <path d="M56 0L112 40v103c0 83-48 143-112 176C48 286 0 226 0 143V40Z" stroke="var(--cyan)" strokeWidth="8" />
            <path d="M56 24L100 55v85c0 65-35 114-88 145-53-31-88-80-88-145V55Z" fill="none" stroke="var(--blue)" strokeWidth="4" opacity="0.9" />
            <path d="M44 82 44 190 83 136Z" fill="var(--text-primary)" />
          </svg>
          <span className="logo-text">Guardarr</span>
        </Link>
      </div>

      <div className="header-center">
        <div
          className={cn('header-status', 'threshold-indicator')}
          style={{ '--threshold-color': stateColor } as React.CSSProperties}
        >
          <span className="status-dot" aria-hidden="true" />
          <span className="status-label">Storage</span>
          <span className="status-value">{thresholdState}</span>
          <span className="status-detail">
            {formatBytes(available)} / {formatBytes(total)}
          </span>
        </div>
      </div>

      <div className="header-right">
        <nav className="header-nav" aria-label="Secondary navigation">
          <Link to="/settings" className={cn('header-nav-item', location.pathname === '/settings' && 'active')}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
            <span>Settings</span>
          </Link>
        </nav>
      </div>

      {mobileMenuOpen && (
        <div className="mobile-overlay" onClick={() => setMobileMenuOpen(false)} aria-hidden="true" />
      )}
    </header>
  )
}