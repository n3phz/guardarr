// No external imports needed

export function getStateColor(state: ReservationState): string {
  switch (state) {
    case 'PENDING': return 'var(--gold)'
    case 'RESERVED': return 'var(--blue)'
    case 'ACTIVE': return 'var(--cyan)'
    case 'OWNED': return 'var(--green)'
    case 'RELEASED': return 'var(--text-muted)'
    case 'EXPIRED': return 'var(--red)'
    case 'STALE': return 'var(--gold)'
    default: return 'var(--text-muted)'
  }
}

export function getStateLabel(state: ReservationState): string {
  return state
}

export function getThresholdStateColor(state: string): string {
  switch (state) {
    case 'NORMAL': return 'var(--state-normal)'
    case 'WARNING': return 'var(--state-warning)'
    case 'BLOCKED': return 'var(--state-blocked)'
    case 'EMERGENCY': return 'var(--state-emergency)'
    case 'CRITICAL': return 'var(--state-critical)'
    default: return 'var(--text-muted)'
  }
}

export function getIntegrationStatusColor(status: string): string {
  switch (status?.toLowerCase()) {
    case 'connected': return 'var(--status-connected)'
    case 'degraded': return 'var(--status-degraded)'
    case 'disconnected': return 'var(--status-offline)'
    default: return 'var(--text-muted)'
  }
}

export function formatBytes(bytes: number, decimals = 2): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`
}

export function formatBytesShort(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  const val = bytes / Math.pow(k, i)
  if (val >= 100) return `${Math.round(val)} ${sizes[i]}`
  if (val >= 10) return `${val.toFixed(1)} ${sizes[i]}`
  return `${val.toFixed(2)} ${sizes[i]}`
}

export function formatPercent(used: number, total: number): string {
  if (total === 0) return '0%'
  return `${((used / total) * 100).toFixed(1)}%`
}

export function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSecs < 60) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return formatDate(dateString)
}

export function cn(...classes: (string | boolean | undefined | null)[]): string {
  return classes.filter(Boolean).join(' ')
}

export type ReservationState = 
  | 'PENDING'
  | 'RESERVED'
  | 'ACTIVE'
  | 'OWNED'
  | 'RELEASED'
  | 'STALE'
  | 'EXPIRED'