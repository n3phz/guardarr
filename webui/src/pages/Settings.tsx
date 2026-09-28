import { useEffect, useState } from 'react'
import { api, ApiError } from '../services/api'
import { StatusResponse } from '../types'
import { StatusBadge } from '../components/StatusBadge'
import { formatBytes, cn } from '../utils/formatters'

export function Settings() {
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadStatus()
  }, [])

  const loadStatus = async () => {
    try {
      setLoading(true)
      const data = await api.status()
      setStatus(data)
      setError(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load settings')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="page page-settings">
        <div className="page-header">
          <h1>Settings</h1>
        </div>
        <SettingsSkeleton />
      </div>
    )
  }

  return (
    <div className="page page-settings">
      <div className="page-header">
        <h1>Settings</h1>
        <span className="badge-readonly">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <rect x="2" y="9" width="20" height="6" rx="1" />
            <path d="M12 15v4M12 19v2" />
          </svg>
          Read-only (MVP)
        </span>
      </div>

      {error && (
        <div className="error-banner">
          <span>⚠</span>
          <span>{error}</span>
          <button onClick={loadStatus} className="btn btn-ghost btn-sm">Retry</button>
        </div>
      )}

      <section className="dashboard-card" aria-labelledby="storage-heading">
        <h2 id="storage-heading" className="section-title">Storage Configuration</h2>
        <div className="settings-grid">
          {status && (
            <>
              <SettingItem
                label="Storage Path"
                value={status.filesystem_identity}
                description="Monitored filesystem mount point"
                mono
              />
              <SettingItem
                label="Total Capacity"
                value={formatBytes(status.total_bytes)}
                description="Total filesystem size"
              />
              <SettingItem
                label="Available"
                value={formatBytes(status.available_bytes)}
                description="Space available to unprivileged users"
                color="var(--cyan)"
              />
              <SettingItem
                label="Device Identity"
                value={status.device_identity}
                description="Filesystem device identifier"
                mono
              />
            </>
          )}
        </div>
      </section>

      <section className="dashboard-card" aria-labelledby="thresholds-heading">
        <h2 id="thresholds-heading" className="section-title">Thresholds</h2>
        <div className="settings-grid">
          {status && (
            <>
              <ThresholdSetting
                label="Warning Threshold"
                value={formatBytes(status.warning_threshold_bytes)}
                description="Free space below this triggers WARNING state"
                state="WARNING"
              />
              <ThresholdSetting
                label="Admission Floor"
                value={formatBytes(status.configured_admission_floor_bytes)}
                description="New reservations denied below this"
                state="BLOCKED"
              />
              <ThresholdSetting
                label="Emergency Threshold"
                value={formatBytes(status.emergency_threshold_bytes)}
                description="Free space below this triggers EMERGENCY"
                state="EMERGENCY"
              />
              <ThresholdSetting
                label="Critical Threshold"
                value={formatBytes(status.critical_threshold_bytes)}
                description="Free space below this triggers CRITICAL"
                state="CRITICAL"
              />
            </>
          )}
        </div>
      </section>

      <section className="dashboard-card" aria-labelledby="system-heading">
        <h2 id="system-heading" className="section-title">System</h2>
        <div className="settings-grid">
          {status && (
            <>
              <SettingItem
                label="Current State"
                value={
                  <StatusBadge variant="threshold" color={
                    status.current_threshold_state === 'NORMAL' ? 'var(--green)' :
                    status.current_threshold_state === 'WARNING' ? 'var(--gold)' :
                    status.current_threshold_state === 'BLOCKED' ? 'var(--red)' :
                    status.current_threshold_state === 'EMERGENCY' ? 'var(--state-emergency)' :
                    'var(--red)'
                  }>
                    {status.current_threshold_state}
                  </StatusBadge>
                }
                description="Current storage threshold state"
              />
              <SettingItem
                label="Inodes Total"
                value={status.inode_total.toLocaleString()}
                description="Total inodes on filesystem"
              />
              <SettingItem
                label="Inodes Available"
                value={status.inode_available.toLocaleString()}
                description="Available inodes"
              />
              <SettingItem
                label="Inode Usage"
                value={`${status.inode_usage_percent ?? 0}%`}
                description="Percentage of inodes in use"
                color={status.inode_usage_percent && status.inode_usage_percent > 80 ? 'var(--red)' : 'var(--green)'}
              />
              <SettingItem
                label="Readiness"
                value={
                  <StatusBadge variant="default" color={status.ready ? 'var(--green)' : 'var(--red)'}>
                    {status.ready ? 'Ready' : 'Not Ready'}
                  </StatusBadge>
                }
                description="Filesystem readiness for admission"
              />
            </>
          )}
        </div>
      </section>

      <section className="dashboard-card" aria-labelledby="api-heading">
        <h2 id="api-heading" className="section-title">API Information</h2>
        <div className="settings-grid">
          <SettingItem
            label="API Version"
            value="0.1.4"
            description="Guardarr API version"
            mono
          />
          <SettingItem
            label="Base Path"
            value="/api"
            description="All API endpoints are under this path"
            mono
          />
          <SettingItem
            label="Documentation"
            value="MkDocs site"
            description="Full documentation at /docs (separate from this UI)"
          />
        </div>
      </section>

      <section className="dashboard-card" aria-labelledby="notes-heading">
        <h2 id="notes-heading" className="section-title">Notes</h2>
        <div className="settings-notes">
          <p>
            <strong>This is the MVP read-only settings view.</strong> Configuration changes
            must be made via environment variables and container restart.
          </p>
          <ul>
            <li>Thresholds are configured via environment variables: <code>WARNING_THRESHOLD_BYTES</code>, <code>ADMISSION_FLOOR_BYTES</code>, <code>EMERGENCY_THRESHOLD_BYTES</code>, <code>CRITICAL_THRESHOLD_BYTES</code></li>
            <li>Storage path: <code>GUARDARR_STORAGE_PATH</code></li>
            <li>Data directory: <code>GUARDARR_DATA_DIR</code></li>
            <li>Database: <code>DATABASE_URL</code></li>
          </ul>
          <p>
            A future version will add in-UI configuration management with validation.
          </p>
        </div>
      </section>
    </div>
  )
}

function SettingItem({
  label,
  value,
  description,
  mono = false,
  color,
}: {
  label: string
  value: React.ReactNode
  description?: string
  mono?: boolean
  color?: string
}) {
  return (
    <div className="setting-item" style={{ '--setting-color': color } as React.CSSProperties}>
      <div className="setting-label-container">
        <span className="setting-label">{label}</span>
        {description && <span className="setting-description">{description}</span>}
      </div>
      <div className={cn('setting-value', mono && 'mono')}>{value}</div>
    </div>
  )
}

function ThresholdSetting({
  label,
  value,
  description,
  state,
}: {
  label: string
  value: string
  description?: string
  state: 'WARNING' | 'BLOCKED' | 'EMERGENCY' | 'CRITICAL'
}) {
  const colors = {
    WARNING: 'var(--gold)',
    BLOCKED: 'var(--red)',
    EMERGENCY: 'var(--state-emergency)',
    CRITICAL: 'var(--state-critical)',
  }

  return (
    <div className="setting-item threshold-setting">
      <div className="setting-label-container">
        <span className="setting-label">{label}</span>
        {description && <span className="setting-description">{description}</span>}
      </div>
      <div className="setting-value threshold-value" style={{ '--threshold-color': colors[state] } as React.CSSProperties}>
        <StatusBadge variant="threshold" color={colors[state]} className="inline">
          {state}
        </StatusBadge>
        <span className="mono threshold-amount">{value}</span>
      </div>
    </div>
  )
}

function SettingsSkeleton() {
  return (
    <div className="settings-skeleton">
      {[...Array(4)].map((_, i) => (
        <section key={i} className="dashboard-card skeleton-card">
          <div className="skeleton skeleton-title" />
          <div className="skeleton skeleton-text" />
          <div className="skeleton skeleton-text" />
        </section>
      ))}
    </div>
  )
}