import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../services/api'
import type { ReservationResponse, AuditEntryResponse } from '../types'
import { StatusBadge } from '../components/StatusBadge'
import { getStateColor, formatBytes, formatRelativeTime, cn } from '../utils/formatters'

export function ReservationDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [reservation, setReservation] = useState<ReservationResponse | null>(null)
  const [auditLogs, setAuditLogs] = useState<AuditEntryResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [releasing, setReleasing] = useState(false)
  const [releaseReason, setReleaseReason] = useState('')
  const [releaseResult, setReleaseResult] = useState<string | null>(null)

  useEffect(() => {
    loadReservation()
  }, [id])

  const loadReservation = async () => {
    if (!id) return
    try {
      setLoading(true)
      const [res, audits] = await Promise.all([
        api.getReservation(id),
        api.listAudit({ reservation_id: id, limit: 50 }),
      ])
      setReservation(res)
      setAuditLogs(audits)
      setError(null)
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError('Reservation not found')
      } else {
        setError(err instanceof ApiError ? err.message : 'Failed to load reservation')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleRelease = async () => {
    if (!reservation || releasing) return
    setReleasing(true)
    setReleaseResult(null)
    try {
      await api.releaseReservation(reservation.id, releaseReason || undefined)
      setReleaseResult(`Released${releaseReason ? ` (${releaseReason})` : ''}`)
      loadReservation()
      setTimeout(() => navigate('/reservations'), 1500)
    } catch (err) {
      setReleaseResult(err instanceof ApiError ? err.message : 'Release failed')
    } finally {
      setReleasing(false)
    }
  }

  if (loading) {
    return (
      <div className="page page-reservation-detail">
        <div className="page-header">
          <h1>Reservation Details</h1>
          <Link to="/reservations" className="btn btn-ghost btn-sm">
            ← Back to Reservations
          </Link>
        </div>
        <div className="dashboard-card">
          <div className="skeleton skeleton-title" />
          <div className="skeleton skeleton-text" />
          <div className="skeleton skeleton-text short" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page page-reservation-detail">
        <div className="page-header">
          <h1>Reservation Details</h1>
          <Link to="/reservations" className="btn btn-ghost btn-sm">
            ← Back to Reservations
          </Link>
        </div>
        <div className="error-state">
          <div className="error-icon">⚠</div>
          <h2>{error}</h2>
          <button onClick={() => navigate('/reservations')} className="btn btn-primary">
            Return to Reservations
          </button>
        </div>
      </div>
    )
  }

  if (!reservation) return null

  return (
    <div className="page page-reservation-detail">
      <div className="page-header">
        <h1>Reservation Details</h1>
        <div className="page-header-actions">
          <Link to="/reservations" className="btn btn-ghost btn-sm">
            ← Back to Reservations
          </Link>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <span>⚠</span>
          <span>{error}</span>
          <button onClick={loadReservation} className="btn btn-ghost btn-sm">Retry</button>
        </div>
      )}

      <section className="dashboard-card" aria-labelledby="details-heading">
        <h2 id="details-heading" className="section-title">Reservation Info</h2>
        <div className="settings-grid">
          <DetailRow label="ID" value={reservation.id.slice(0, 8)} mono />
          <DetailRow label="State" value={
            <StatusBadge variant="state" color={getStateColor(reservation.state)}>
              {reservation.state}
            </StatusBadge>
          } />
          <DetailRow label="Source" value={<span className="source-badge">{reservation.adapter_name}</span>} />
          <DetailRow label="Content ID" value={reservation.content_id || '—'} mono />
          <DetailRow label="Adapter Item ID" value={reservation.arr_item_id || '—'} mono />
          <DetailRow label="Associated Path" value={reservation.associated_path || '—'} mono />
          <DetailRow label="Torrent Hash" value={reservation.torrent_metadata_hash?.slice(0, 12) || '—'} mono />
          <DetailRow label="Requester" value={reservation.owner || '—'} />
          <DetailRow label="Target Device" value={reservation.target_device} mono />
          <DetailRow label="Max Bytes" value={formatBytes(reservation.max_bytes)} mono />
          <DetailRow label="Expected Bytes" value={formatBytes(reservation.expected_bytes)} mono />
          <DetailRow label="Observed Bytes" value={formatBytes(reservation.observed_materialized_bytes)} mono />
          <DetailRow label="Remaining" value={formatBytes(reservation.remaining_unfulfilled_bytes)} mono />
          <DetailRow label="Import Mode" value={reservation.import_mode} />
          <DetailRow label="Priority" value={reservation.priority.toString()} />
          <DetailRow label="Created" value={formatRelativeTime(reservation.created_at)} />
          <DetailRow label="Updated" value={formatRelativeTime(reservation.updated_at)} />
          {reservation.expires_at && (
            <DetailRow label="Expires" value={formatRelativeTime(reservation.expires_at)} />
          )}
        </div>
      </section>

      <section className="dashboard-card" aria-labelledby="audit-heading">
        <h2 id="audit-heading" className="section-title">Audit History</h2>
        {auditLogs.length > 0 ? (
          <div className="audit-timeline">
            {auditLogs.map((entry, idx) => (
              <div key={entry.id} className={cn('audit-entry', idx === 0 ? 'audit-entry--newest' : '')}>
                <div className="audit-entry-time">
                  {formatRelativeTime(entry.created_at)}
                </div>
                <div className="audit-entry-content">
                  <span className="audit-entry-type">{entry.event_type}</span>
                  {entry.details && (
                    <span className="audit-entry-details">{entry.details}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <div className="empty-icon">📋</div>
            <p>No audit events recorded yet</p>
          </div>
        )}
      </section>

      {(reservation.state === 'RESERVED' || reservation.state === 'ACTIVE') && (
        <section className="dashboard-card" aria-labelledby="actions-heading">
          <h2 id="actions-heading" className="section-title">Actions</h2>
          <div className="form-row" style={{ alignItems: 'flex-end' }}>
            <div className="form-group">
              <label className="form-label" htmlFor="release-reason">
                Release Reason (optional)
              </label>
              <input
                id="release-reason"
                type="text"
                placeholder="e.g., Import complete, Aborting"
                value={releaseReason}
                onChange={(e) => setReleaseReason(e.target.value)}
                className="form-input"
                disabled={releasing}
              />
            </div>
            <button
              onClick={handleRelease}
              disabled={releasing}
              className="btn btn-danger"
            >
              {releasing ? (
                <>
                  <span className="spinner-sm" aria-hidden="true" />
                  Releasing...
                </>
              ) : 'Release Reservation'}
            </button>
          </div>
          {releaseResult && (
            <div className={cn('result-status', releaseResult.startsWith('Released') ? 'result-allowed' : 'result-denied')}>
              <span className={releaseResult.startsWith('Released') ? 'result-allowed' : 'result-denied'}>
                {releaseResult}
              </span>
            </div>
          )}
        </section>
      )}
    </div>
  )
}

function DetailRow({
  label,
  value,
  mono = false,
}: {
  label: string
  value: React.ReactNode
  mono?: boolean
}) {
  return (
    <div className="detail-row">
      <span className="detail-label">{label}</span>
      <span className={cn('detail-value', mono && 'mono')}>{value}</span>
    </div>
  )
}
