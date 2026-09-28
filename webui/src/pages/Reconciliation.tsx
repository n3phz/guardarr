import { useEffect, useState } from 'react'
import { api, ApiError } from '../services/api'
import type { ReconcileStateResponse, ReconcileResponse } from '../types'
import { StatusBadge } from '../components/StatusBadge'
import { formatRelativeTime } from '../utils/formatters'

export function Reconciliation() {
  const [reconcileState, setReconcileState] = useState<ReconcileStateResponse | null>(null)
  const [reconcileResult, setReconcileResult] = useState<ReconcileResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [reconciling, setReconciling] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadReconcileState()
  }, [])

  const loadReconcileState = async () => {
    try {
      setLoading(true)
      const data = await api.getReconcileState()
      setReconcileState(data)
      setError(null)
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        // No reconciliation state yet - that's fine
        setReconcileState(null)
        setError(null)
      } else {
        setError(err instanceof ApiError ? err.message : 'Failed to load reconciliation state')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleReconcile = async () => {
    setReconciling(true)
    setError(null)
    try {
      const result = await api.reconcile()
      setReconcileResult(result)
      await loadReconcileState()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Reconciliation failed')
    } finally {
      setReconciling(false)
    }
  }

  if (loading) {
    return (
      <div className="page page-reconciliation">
        <div className="page-header">
          <h1>Reconciliation</h1>
        </div>
        <ReconciliationSkeleton />
      </div>
    )
  }

  return (
    <div className="page page-reconciliation">
      <div className="page-header">
        <h1>Reconciliation</h1>
        <div className="page-header-actions">
          <button
            onClick={handleReconcile}
            disabled={reconciling}
            className="btn btn-primary"
          >
            {reconciling ? (
              <>
                <span className="spinner-sm" aria-hidden="true" />
                Reconciling...
              </>
            ) : (
              'Run Reconciliation'
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <span>⚠</span>
          <span>{error}</span>
          <button onClick={loadReconcileState} className="btn btn-ghost btn-sm">Retry</button>
        </div>
      )}

      <section className="dashboard-card" aria-labelledby="last-run-heading">
        <h2 id="last-run-heading" className="section-title">Last Reconciliation</h2>
        {reconcileState ? (
          <div className="reconcile-state">
            <div className="reconcile-meta">
              <div className="meta-item">
                <span className="meta-label">Component</span>
                <span className="meta-value mono">{reconcileState.component}</span>
              </div>
              <div className="meta-item">
                <span className="meta-label">Last Run</span>
                <span className="meta-value">
                  {reconcileState.last_run_at
                    ? formatRelativeTime(reconcileState.last_run_at)
                    : 'Never'}
                </span>
              </div>
              <div className="meta-item">
                <span className="meta-label">Status</span>
                <span className="meta-value">
                  <StatusBadge
                    variant="default"
                    color={
                      reconcileState.status === 'success'
                        ? 'var(--green)'
                        : reconcileState.status === 'failed'
                        ? 'var(--red)'
                        : 'var(--gold)'
                    }
                  >
                    {reconcileState.status ?? 'Unknown'}
                  </StatusBadge>
                </span>
              </div>
            </div>
            {reconcileState.details && (
              <div className="reconcile-details">
                <span className="details-label">Details</span>
                <pre className="details-text mono">{reconcileState.details}</pre>
              </div>
            )}
          </div>
        ) : (
          <div className="empty-state">
            <div className="empty-icon">🔄</div>
            <p>No reconciliation has been run yet</p>
            <button onClick={handleReconcile} className="btn btn-primary" disabled={reconciling}>
              Run First Reconciliation
            </button>
          </div>
        )}
      </section>

      {reconcileResult && (
        <section className="dashboard-card" aria-labelledby="result-heading">
          <h2 id="result-heading" className="section-title">Latest Result</h2>
          <div className="reconcile-result">
            <div className="result-summary">
              <div className="result-item">
                <span className="result-label">Expired Reservations</span>
                <span className="result-value mono">{reconcileResult.expired_count}</span>
              </div>
              <div className="result-item">
                <span className="result-label">Status</span>
                <span className="result-value">
                  <StatusBadge
                    variant="default"
                    color={reconcileResult.status === 'success' ? 'var(--green)' : 'var(--red)'}
                  >
                    {reconcileResult.status}
                  </StatusBadge>
                </span>
              </div>
              <div className="result-item">
                <span className="result-label">Completed</span>
                <span className="result-value mono">{formatRelativeTime(reconcileResult.timestamp)}</span>
              </div>
            </div>
            {reconcileResult.details && (
              <div className="result-details">
                <span className="details-label">Details</span>
                <pre className="details-text mono">{reconcileResult.details}</pre>
              </div>
            )}
          </div>
        </section>
      )}

      <section className="dashboard-card" aria-labelledby="about-heading">
        <h2 id="about-heading" className="section-title">About Reconciliation</h2>
        <div className="about-content">
          <p>
            Reconciliation compares the reservation ledger with the actual filesystem state and qBittorrent
            download state. It detects and corrects inconsistencies such as:
          </p>
          <ul>
            <li>Expired reservations (past their TTL)</li>
            <li>Negative remaining unfulfilled bytes</li>
            <li>Orphaned torrents without reservations</li>
            <li>Reservations that should be marked OWNED after import</li>
          </ul>
          <p>
            Run reconciliation periodically or after unexpected shutdowns to ensure the admission
            engine has an accurate view of storage commitments.
          </p>
        </div>
      </section>
    </div>
  )
}

function ReconciliationSkeleton() {
  return (
    <section className="dashboard-card skeleton-card">
      <div className="skeleton skeleton-title" />
      <div className="skeleton skeleton-text" />
      <div className="skeleton skeleton-text" />
    </section>
  )
}