import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../services/api'
import type { ReservationResponse } from '../types'
import { DataTable, createReservationColumns } from '../components/DataTable'

const STATE_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All States' },
  { value: 'PENDING', label: 'Pending' },
  { value: 'RESERVED', label: 'Reserved' },
  { value: 'ACTIVE', label: 'Active' },
  { value: 'OWNED', label: 'Owned' },
  { value: 'RELEASED', label: 'Released' },
  { value: 'EXPIRED', label: 'Expired' },
  { value: 'STALE', label: 'Stale' },
]

const ADAPTER_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All Sources' },
  { value: 'seerr', label: 'Seerr' },
  { value: 'jellyseerr', label: 'Jellyseerr' },
  { value: 'sonarr', label: 'Sonarr' },
  { value: 'radarr', label: 'Radarr' },
  { value: 'qbittorrent', label: 'qBittorrent' },
]

export function Reservations() {
  const [reservations, setReservations] = useState<ReservationResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [stateFilter, setStateFilter] = useState('')
  const [adapterFilter, setAdapterFilter] = useState('')
  // const [releasingId, setReleasingId] = useState<string | null>(null)

  useEffect(() => {
    loadReservations()
    const interval = setInterval(loadReservations, 10000)
    return () => clearInterval(interval)
  }, [stateFilter, adapterFilter])

  const loadReservations = async () => {
    try {
      setLoading(true)
      const data = await api.listReservations({
        state: stateFilter || undefined,
        adapter_name: adapterFilter || undefined,
      })
      setReservations(data)
      setError(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load reservations')
    } finally {
      setLoading(false)
    }
  }

  const handleRelease = async (id: string) => {
    if (!confirm('Release this reservation? This will return the reserved capacity.')) return

    // setReleasingId(id)
    try {
      await api.releaseReservation(id)
      setReservations((prev) => prev.filter((r) => r.id !== id))
    } catch (err) {
      alert(err instanceof ApiError ? err.message : 'Failed to release reservation')
    } finally {
      // setReleasingId(null)
    }
  }

  const handleView = (row: ReservationResponse) => {
    // Navigate to detail page - will be implemented in Phase 2
    console.log('View reservation:', row.id)
  }

  const columns = createReservationColumns(handleRelease, handleView)

  return (
    <div className="page page-reservations">
      <div className="page-header">
        <h1>Reservations</h1>
        <div className="page-header-actions">
          <Link to="/reservations/new" className="btn btn-primary">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M12 5v14M5 12h14" />
            </svg>
            Create Reservation
          </Link>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <span>⚠</span>
          <span>{error}</span>
          <button onClick={loadReservations} className="btn btn-ghost btn-sm">Retry</button>
        </div>
      )}

      <div className="filters-bar">
        <div className="filters-group">
          <label className="filter-select" htmlFor="state-filter">
            <select
              id="state-filter"
              value={stateFilter}
              onChange={(e) => setStateFilter(e.target.value)}
              aria-label="Filter by state"
            >
              {STATE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </label>
          <label className="filter-select" htmlFor="adapter-filter">
            <select
              id="adapter-filter"
              value={adapterFilter}
              onChange={(e) => setAdapterFilter(e.target.value)}
              aria-label="Filter by source"
            >
              {ADAPTER_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="filters-count">
          {reservations.length} reservation{reservations.length !== 1 ? 's' : ''}
        </div>
      </div>

      <div className="table-wrapper">
        <DataTable
          columns={columns}
          data={reservations}
          keyExtractor={(r) => r.id}
          loading={loading}
          emptyMessage="No reservations found"
          onRowClick={handleView}
        />
      </div>
    </div>
  )
}