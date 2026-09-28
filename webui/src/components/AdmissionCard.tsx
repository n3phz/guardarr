import { formatBytes } from '../utils/formatters'
import type { EstimateResponse, EstimateRequest } from '../types'
import { useState } from 'react'

interface AdmissionCardProps {
  estimate: EstimateResponse | null
  loading: boolean
  onEstimate: (req: EstimateRequest) => void
}

export function AdmissionCard({ estimate, loading, onEstimate }: AdmissionCardProps) {
  const [maxBytes, setMaxBytes] = useState('300')
  const [expectedBytes, setExpectedBytes] = useState('280')
  const [unit, setUnit] = useState<'GB' | 'TB'>('GB')

  const handleEstimate = (e: React.FormEvent) => {
    e.preventDefault()
    const multiplier = unit === 'GB' ? 1_000_000_000 : 1_000_000_000_000
    onEstimate({
      max_bytes: parseInt(maxBytes) * multiplier,
      expected_bytes: parseInt(expectedBytes) * multiplier,
      import_mode: 'unknown',
      target_device: '/data',
    })
  }

  if (loading && !estimate) {
    return (
      <div className="admission-card">
        <div className="card-header">
          <h3>Admission Check</h3>
        </div>
        <div className="card-body loading">
          <div className="skeleton skeleton-text" />
          <div className="skeleton skeleton-text short" />
        </div>
      </div>
    )
  }

  if (!estimate) {
    return (
      <div className="admission-card">
        <div className="card-header">
          <h3>Admission Check</h3>
        </div>
        <form onSubmit={handleEstimate} className="estimate-form">
          <div className="form-row">
            <label>
              <span className="form-label">Requested (Max)</span>
              <div className="input-with-unit">
                <input
                  type="number"
                  value={maxBytes}
                  onChange={(e) => setMaxBytes(e.target.value)}
                  min="1"
                  placeholder="300"
                  inputMode="numeric"
                />
                <select value={unit} onChange={(e) => setUnit(e.target.value as 'GB' | 'TB')}>
                  <option value="GB">GB</option>
                  <option value="TB">TB</option>
                </select>
              </div>
            </label>
            <label>
              <span className="form-label">Expected Size</span>
              <div className="input-with-unit">
                <input
                  type="number"
                  value={expectedBytes}
                  onChange={(e) => setExpectedBytes(e.target.value)}
                  min="1"
                  placeholder="280"
                  inputMode="numeric"
                />
                <select value={unit} onChange={(e) => setUnit(e.target.value as 'GB' | 'TB')}>
                  <option value="GB">GB</option>
                  <option value="TB">TB</option>
                </select>
              </div>
            </label>
          </div>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            Check Admission
          </button>
        </form>
      </div>
    )
  }

  const { available_bytes, outstanding_unfulfilled_bytes, requested_bytes, projected_available_bytes, admission_floor_bytes, admissible, reason } = estimate

  return (
    <div className="admission-card" style={{ '--result-color': admissible ? 'var(--green)' : 'var(--red)' } as React.CSSProperties}>
      <div className="card-header">
        <h3>Admission Result</h3>
      </div>

      <div className="admission-result">
        <div className="result-status">
          <div
            className="result-indicator"
            style={{ background: admissible ? 'var(--green)' : 'var(--red)' }}
          />
          <span className={admissible ? 'result-allowed' : 'result-denied'}>
            {admissible ? 'ADMISSIBLE' : 'DENIED'}
          </span>
        </div>

        <div className="result-metrics">
          <div className="metric">
            <span className="metric-label">Available</span>
            <span className="metric-value">{formatBytes(available_bytes)}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Outstanding</span>
            <span className="metric-value">{formatBytes(outstanding_unfulfilled_bytes)}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Requested</span>
            <span className="metric-value">{formatBytes(requested_bytes)}</span>
          </div>
          <div className="metric highlight">
            <span className="metric-label">Projected Available</span>
            <span className="metric-value projected">{formatBytes(projected_available_bytes)}</span>
          </div>
          <div className="metric floor">
            <span className="metric-label">Admission Floor</span>
            <span className="metric-value">{formatBytes(admission_floor_bytes)}</span>
          </div>
        </div>

        {!admissible && reason && (
          <div className="result-reason">
            <span className="reason-icon">⚠</span>
            <span>{reason}</span>
          </div>
        )}

        <div className="admission-actions">
          <button
            className="btn btn-secondary"
            onClick={() => {}}
            disabled={!admissible}
          >
            Create Reservation
          </button>
          <button className="btn btn-ghost" onClick={() => {}}>
            Adjust Request
          </button>
        </div>
      </div>
    </div>
  )
}