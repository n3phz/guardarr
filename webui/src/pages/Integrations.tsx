import { useEffect, useState } from 'react'
import { api, ApiError } from '../services/api'
import type { IntegrationHealthResponse } from '../types'
import { StatusBadge } from '../components/StatusBadge'
import { getIntegrationStatusColor, cn } from '../utils/formatters'

const typeLabels: Record<string, string> = {
  arr: 'Arr',
  seerr: 'Seerr/Jellyseerr',
  qbittorrent: 'qBittorrent',
}

const typeIcons: Record<string, () => React.ReactNode> = {
  arr: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <path d="M8 21h8M12 17v4" />
    </svg>
  ),
  seerr: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 6v6l4 2" />
    </svg>
  ),
  qbittorrent: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2z" />
      <path d="M8 12l3 3 6-6" />
    </svg>
  ),
}

export function Integrations() {
  const [integrations, setIntegrations] = useState<IntegrationHealthResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  useEffect(() => {
    loadIntegrations()
    const interval = setInterval(loadIntegrations, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadIntegrations = async () => {
    try {
      setLoading(true)
      const data = await api.integrationsHealth()
      setIntegrations(data)
      setLastUpdated(new Date())
      setError(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load integrations')
    } finally {
      setLoading(false)
    }
  }

  if (loading && integrations.length === 0) {
    return (
      <div className="page page-integrations">
        <div className="page-header">
          <h1>Integrations</h1>
        </div>
        <div className="integrations-grid">
          {[...Array(5)].map((_, i) => (
            <IntegrationCardSkeleton key={i} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="page page-integrations">
      <div className="page-header">
        <h1>Integrations</h1>
        <div className="page-header-actions">
          <button onClick={loadIntegrations} className="btn btn-secondary" disabled={loading}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
              <polyline points="23 4 23 10 17 10" />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <span>⚠</span>
          <span>{error}</span>
          <button onClick={loadIntegrations} className="btn btn-ghost btn-sm">Retry</button>
        </div>
      )}

      {lastUpdated && (
        <div className="last-updated">
          Last updated: {lastUpdated.toLocaleTimeString()}
        </div>
      )}

      <div className="integrations-grid">
        {integrations.map((integration) => (
          <IntegrationCard
            key={integration.provider}
            integration={integration}
          />
        ))}
      </div>
    </div>
  )
}

function IntegrationCard({ integration }: { integration: IntegrationHealthResponse }) {
  const statusColor = getIntegrationStatusColor(integration.status)
  const Icon = typeIcons[integration.type] || typeIcons.arr

  const getStatusText = (status: string) => {
    switch (status.toLowerCase()) {
      case 'connected': return 'Connected'
      case 'degraded': return 'Degraded'
      case 'disconnected': return 'Offline'
      default: return status
    }
  }

  return (
    <article
      className={cn('integration-card', integration.status === 'connected' && 'healthy')}
      style={{ '--status-color': statusColor } as React.CSSProperties}
    >
      <div className="integration-header">
        <div className="integration-icon" aria-hidden="true">
          {Icon()}
        </div>
        <div className="integration-info">
          <h3 className="integration-name">{integration.provider}</h3>
          <span className="integration-type">{typeLabels[integration.type] || integration.type}</span>
        </div>
        <StatusBadge variant="integration" color={statusColor}>
          {getStatusText(integration.status)}
        </StatusBadge>
      </div>

      <div className="integration-details">
        {integration.version && (
          <div className="detail-row">
            <span className="detail-label">Version</span>
            <span className="detail-value mono">{integration.version}</span>
          </div>
        )}
        {integration.reason && (
          <div className="detail-row">
            <span className="detail-label">Status</span>
            <span className="detail-value">{integration.reason}</span>
          </div>
        )}
        {integration.latency_ms !== null && integration.latency_ms !== undefined && (
          <div className="detail-row">
            <span className="detail-label">Latency</span>
            <span className="detail-value mono">{integration.latency_ms}ms</span>
          </div>
        )}
      </div>

      <div className="integration-actions">
        <button className="btn btn-ghost btn-sm">Configure</button>
        <button className="btn btn-ghost btn-sm">Test</button>
      </div>
    </article>
  )
}

function IntegrationCardSkeleton() {
  return (
    <article className="integration-card skeleton-card">
      <div className="integration-header">
        <div className="skeleton skeleton-icon" />
        <div>
          <div className="skeleton skeleton-text" />
          <div className="skeleton skeleton-text short" />
        </div>
        <div className="skeleton skeleton-badge" />
      </div>
      <div className="integration-details">
        <div className="skeleton skeleton-text short" />
        <div className="skeleton skeleton-text short" />
      </div>
    </article>
  )
}