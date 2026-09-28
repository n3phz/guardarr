import { cn, formatBytes, formatRelativeTime, getStateColor, ReservationState } from '../utils/formatters'
import { ReservationResponse } from '../types'
import { StatusBadge } from './StatusBadge'

interface Column<T> {
  key: string
  header: string
  render?: (row: T) => React.ReactNode
  className?: string
  width?: string
}

interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  keyExtractor: (row: T) => string
  loading?: boolean
  emptyMessage?: string
  onRowClick?: (row: T) => void
  className?: string
}

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  loading = false,
  emptyMessage = 'No data',
  onRowClick,
  className,
}: DataTableProps<T>) {
  if (loading) {
    return (
      <div className={cn('data-table-container', className)}>
        <table className="data-table" role="grid">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key} style={{ width: col.width }} className={col.className}>
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...Array(5)].map((_, i) => (
              <tr key={i} className="skeleton-row">
                {columns.map((col) => (
                  <td key={col.key} className={col.className}>
                    <div className="skeleton skeleton-cell" />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className={cn('data-table-container', className)}>
        <div className="empty-state">
          <div className="empty-icon">📋</div>
          <p>{emptyMessage}</p>
        </div>
      </div>
    )
  }

  return (
    <div className={cn('data-table-container', className)}>
      <table className="data-table" role="grid">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} style={{ width: col.width }} className={col.className}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr
              key={keyExtractor(row)}
              onClick={() => onRowClick?.(row)}
              className={cn('data-row', onRowClick && 'clickable')}
            >
              {columns.map((col) => (
                <td key={col.key} className={col.className}>
                  {col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function createReservationColumns(
  onRelease?: (id: string) => void,
  onView?: (row: ReservationResponse) => void
): Column<ReservationResponse>[] {
  return [
    {
      key: 'adapter_name',
      header: 'Source',
      width: '140px',
      render: (row) => (
        <span className="source-badge">{row.adapter_name}</span>
      ),
    },
    {
      key: 'content_id',
      header: 'Media / Request',
      width: '200px',
      render: (row) => (
        <div className="content-cell">
          <span className="content-id">{row.content_id ?? '—'}</span>
          {row.torrent_metadata_hash && (
            <span className="torrent-hash" title={row.torrent_metadata_hash}>
              {row.torrent_metadata_hash.slice(0, 12)}…
            </span>
          )}
        </div>
      ),
    },
    {
      key: 'max_bytes',
      header: 'Requested',
      width: '120px',
      render: (row) => <span className="mono">{formatBytes(row.max_bytes)}</span>,
    },
    {
      key: 'remaining_unfulfilled_bytes',
      header: 'Reserved',
      width: '120px',
      render: (row) => <span className="mono">{formatBytes(row.remaining_unfulfilled_bytes)}</span>,
    },
    {
      key: 'state',
      header: 'State',
      width: '110px',
      render: (row) => (
        <StatusBadge
          variant="state"
          color={getStateColor(row.state as ReservationState)}
        >
          {row.state}
        </StatusBadge>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      width: '160px',
      render: (row) => <span className="mono">{formatRelativeTime(row.created_at)}</span>,
    },
    {
      key: 'age',
      header: 'Age',
      width: '100px',
      render: (row) => {
        const created = new Date(row.created_at).getTime()
        const now = Date.now()
        const diffHours = Math.floor((now - created) / 3_600_000)
        const diffDays = Math.floor(diffHours / 24)
        if (diffDays > 0) return `${diffDays}d ${diffHours % 24}h`
        return `${diffHours}h`
      },
    },
    {
      key: 'actions',
      header: '',
      width: '80px',
      render: (row) => (
        <div className="actions-cell">
          {onView && (
            <button
              className="btn-icon"
              onClick={(e) => { e.stopPropagation(); onView(row) }}
              title="View details"
              aria-label="View details"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </button>
          )}
          {onRelease && row.state !== 'RELEASED' && row.state !== 'EXPIRED' && row.state !== 'STALE' && (
            <button
              className="btn-icon danger"
              onClick={(e) => { e.stopPropagation(); onRelease(row.id) }}
              title="Release reservation"
              aria-label="Release reservation"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
            </button>
          )}
        </div>
      ),
    },
  ]
}