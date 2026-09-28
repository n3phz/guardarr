import { useEffect, useState } from 'react'
import { api, ApiError } from '../services/api'
import type { StatusResponse, EstimateRequest, EstimateResponse } from '../types'
import { StorageGauge } from '../components/StorageGauge'
import { AdmissionCard } from '../components/AdmissionCard'
import { StatusBadge } from '../components/StatusBadge'
import { formatBytes, getThresholdStateColor, cn } from '../utils/formatters'

export function Dashboard() {
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [estimate, setEstimate] = useState<EstimateResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [estimateLoading, setEstimateLoading] = useState(false)

  useEffect(() => {
    loadStatus()
    const interval = setInterval(loadStatus, 15000)
    return () => clearInterval(interval)
  }, [])

  const loadStatus = async () => {
    try {
      const data = await api.status()
      setStatus(data)
      setError(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load status')
    } finally {
      setLoading(false)
    }
  }

  const handleEstimate = async (req: EstimateRequest) => {
    setEstimateLoading(true)
    try {
      const result = await api.estimate(req)
      setEstimate(result)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Estimate failed')
      setEstimate(null)
    } finally {
      setEstimateLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="page page-dashboard">
        <div className="page-header">
          <h1>Dashboard</h1>
        </div>
        <div className="dashboard-grid">
          <StorageGaugeSkeleton />
          <AdmissionCardSkeleton />
        </div>
      </div>
    )
  }

  if (error && !status) {
    return (
      <ErrorState message={error} onRetry={loadStatus} />
    )
  }

  const thresholdState = status?.current_threshold_state ?? 'UNKNOWN'
  const stateColor = getThresholdStateColor(thresholdState)

  return (
    <div className="page page-dashboard">
      <div className="page-header">
        <h1>Dashboard</h1>
        <div className="page-header-actions">
          <StatusBadge variant="threshold" color={stateColor}>
            {thresholdState}
          </StatusBadge>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <span>⚠</span>
          <span>{error}</span>
          <button onClick={loadStatus} className="btn btn-ghost btn-sm">Retry</button>
        </div>
      )}

      <div className="dashboard-grid">
        <section className="dashboard-card storage-section" aria-labelledby="storage-heading">
          <h2 id="storage-heading" className="section-title">Storage</h2>
          {status && (
            <StorageGauge
              totalBytes={status.total_bytes}
              availableBytes={status.available_bytes}
              warningThreshold={status.warning_threshold_bytes}
              admissionFloor={status.configured_admission_floor_bytes}
              emergencyThreshold={status.emergency_threshold_bytes}
              criticalThreshold={status.critical_threshold_bytes}
              currentState={status.current_threshold_state}
              inodeTotal={status.inode_total}
              inodeAvailable={status.inode_available}
              inodeUsagePercent={status.inode_usage_percent}
            />
          )}
        </section>

        <section className="dashboard-card admission-section" aria-labelledby="admission-heading">
          <h2 id="admission-heading" className="section-title">Admission Check</h2>
          <AdmissionCard
            estimate={estimate}
            loading={estimateLoading}
            onEstimate={handleEstimate}
          />
        </section>
      </div>

      <section className="dashboard-card quick-stats" aria-labelledby="quick-stats-heading">
        <h2 id="quick-stats-heading" className="section-title">Quick Stats</h2>
        <div className="stats-grid">
          {status && (
            <>
              <StatCard
                label="Available"
                value={formatBytes(status.available_bytes)}
                color="var(--cyan)"
              />
              <StatCard
                label="Admission Floor"
                value={formatBytes(status.configured_admission_floor_bytes)}
                color="var(--red)"
              />
              <StatCard
                label="Warning Threshold"
                value={formatBytes(status.warning_threshold_bytes)}
                color="var(--gold)"
              />
              <StatCard
                label="Used"
                value={formatBytes(status.total_bytes - status.available_bytes)}
                color="var(--blue)"
              />
              <StatCard
                label="Inodes Used"
                value={`${status.inode_usage_percent ?? 0}%`}
                color={status.inode_usage_percent && status.inode_usage_percent > 80 ? 'var(--red)' : 'var(--green)'}
              />
              <StatCard
                label="Filesystem"
                value={status.filesystem_identity}
                color="var(--text-muted)"
                mono
              />
            </>
          )}
        </div>
      </section>
    </div>
  )
}

function StatCard({ label, value, color, mono = false }: { label: string; value: string; color: string; mono?: boolean }) {
  return (
    <div className="stat-card" style={{ '--stat-color': color } as React.CSSProperties}>
      <div className="stat-label">{label}</div>
      <div className={cn('stat-value', mono && 'mono')}>{value}</div>
    </div>
  )
}

function StorageGaugeSkeleton() {
  return (
    <section className="dashboard-card storage-section">
      <div className="skeleton skeleton-title" />
      <div className="skeleton skeleton-gauge" />
      <div className="skeleton skeleton-text" />
    </section>
  )
}

function AdmissionCardSkeleton() {
  return (
    <section className="dashboard-card admission-section">
      <div className="skeleton skeleton-title" />
      <div className="skeleton skeleton-card" />
    </section>
  )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="page page-dashboard">
      <div className="error-state">
        <div className="error-icon">⚠</div>
        <h2>Unable to load dashboard</h2>
        <p>{message}</p>
        <button onClick={onRetry} className="btn btn-primary">Retry</button>
      </div>
    </div>
  )
}