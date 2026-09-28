import type { HealthResponse, ReadyResponse, StatusResponse, ThresholdState, EstimateRequest, ImportMode, EstimateResponse, AdmitRequest, ReservationResponse, ReservationState, ReleaseRequest, ReconcileResponse, ReconcileStateResponse, QBittorrentStatusResponse, IntegrationHealthResponse, AuditEntryResponse, UnreservedTorrentResponse, TorrentReconcileResponse } from '../types'

const API_BASE = '/api'

class ApiError extends Error {
  constructor(public status: number, message: string, public data?: unknown) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })

  if (!response.ok) {
    let message = `API error: ${response.status} ${response.statusText}`
    let data: unknown
    try {
      data = await response.json()
      if (typeof data === 'object' && data !== null && 'detail' in data) {
        message = String(data.detail)
      }
    } catch {
      // ignore parse errors
    }
    throw new ApiError(response.status, message, data)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

export const api = {
  // Health & Status
  health: () => request<HealthResponse>('/health'),
  ready: () => request<ReadyResponse>('/ready'),
  status: () => request<StatusResponse>('/status'),

  // Reservations
  estimate: (req: EstimateRequest) =>
    request<EstimateResponse>('/estimate', { method: 'POST', body: JSON.stringify(req) }),
  admit: (req: AdmitRequest) =>
    request<ReservationResponse>('/admit', { method: 'POST', body: JSON.stringify(req) }),
  listReservations: (params?: { state?: string; adapter_name?: string }) => {
    const search = new URLSearchParams()
    if (params?.state) search.append('state', params.state)
    if (params?.adapter_name) search.append('adapter_name', params.adapter_name)
    return request<ReservationResponse[]>(`/reservations${search.toString() ? `?${search}` : ''}`)
  },
  getReservation: (id: string) => request<ReservationResponse>(`/reservations/${id}`),
  releaseReservation: (id: string, reason?: string) =>
    request<ReservationResponse>(`/reservations/${id}/release`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  // Reconciliation
  getReconcileState: () => request<ReconcileStateResponse>('/reconcile/state'),
  reconcile: () => request<ReconcileResponse>('/reconcile', { method: 'POST' }),

  // qBittorrent
  qbStatus: () => request<QBittorrentStatusResponse>('/qbittorrent/status'),
  qbAssociate: (reservationId: string, torrentHash: string) =>
    request<unknown>(`/qbittorrent/reservations/${reservationId}/associate`, {
      method: 'POST',
      body: JSON.stringify({ torrent_hash: torrentHash }),
    }),
  qbControlledAdd: (reservationId: string, req: { url_or_magnet: string; savepath?: string; category?: string; idempotency_key: string }) =>
    request<unknown>(`/qbittorrent/reservations/${reservationId}/add`, {
      method: 'POST',
      body: JSON.stringify(req),
    }),
  qbReconcile: () => request<TorrentReconcileResponse>('/qbittorrent/reconcile', { method: 'POST' }),
  qbUnreserved: () => request<UnreservedTorrentResponse[]>('/qbittorrent/unreserved'),

  // Integrations
  integrationsHealth: () => request<IntegrationHealthResponse[]>('/integrations/health'),

  // Audit
  listAudit: (params?: { reservation_id?: string; event_type?: string; limit?: number; offset?: number }) => {
    const search = new URLSearchParams()
    if (params?.reservation_id) search.append('reservation_id', params.reservation_id)
    if (params?.event_type) search.append('event_type', params.event_type)
    if (params?.limit) search.append('limit', params.limit.toString())
    if (params?.offset) search.append('offset', params.offset.toString())
    return request<AuditEntryResponse[]>(`/audit${search.toString() ? `?${search}` : ''}`)
  },
}

export { ApiError }
export type { HealthResponse, ReadyResponse, StatusResponse, ThresholdState, EstimateRequest, ImportMode, EstimateResponse, AdmitRequest, ReservationResponse, ReservationState, ReleaseRequest, ReconcileResponse, ReconcileStateResponse, QBittorrentStatusResponse, IntegrationHealthResponse, AuditEntryResponse, UnreservedTorrentResponse, TorrentReconcileResponse }