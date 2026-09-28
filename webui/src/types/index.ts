export interface HealthResponse {
  status: string
  service: string
  version: string
  environment: string
}

export interface ReadyResponse {
  status: string
  service: string
  data_dir: string
  storage_path: string
}

export interface StatusResponse {
  total_bytes: number
  available_bytes: number
  configured_admission_floor_bytes: number
  warning_threshold_bytes: number
  emergency_threshold_bytes: number
  critical_threshold_bytes: number
  current_threshold_state: ThresholdState
  inode_total: number
  inode_available: number
  inode_usage_percent: number | null
  filesystem_identity: string
  device_identity: string
  ready: boolean
}

export type ThresholdState = 'NORMAL' | 'WARNING' | 'BLOCKED' | 'EMERGENCY' | 'CRITICAL'

export interface EstimateRequest {
  max_bytes: number
  expected_bytes: number
  import_mode: ImportMode
  target_device: string
}

export type ImportMode = 'hardlink' | 'copy' | 'unknown'

export interface EstimateResponse {
  available_bytes: number
  outstanding_unfulfilled_bytes: number
  requested_bytes: number
  projected_available_bytes: number
  admission_floor_bytes: number
  admissible: boolean
  reason: string | null
}

export interface AdmitRequest {
  adapter_name: string
  idempotency_key: string
  content_id: string | null
  torrent_metadata_hash: string | null
  max_bytes: number
  expected_bytes: number
  observed_materialized_bytes: number
  target_device: string
  import_mode: ImportMode
  priority: number
  owner: string | null
  torrent_tag: string | null
  ttl_seconds: number | null
}

export interface ReservationResponse {
  id: string
  idempotency_key: string
  adapter_name: string
  content_id: string | null
  torrent_metadata_hash: string | null
  target_device: string
  max_bytes: number
  expected_bytes: number
  observed_materialized_bytes: number
  remaining_unfulfilled_bytes: number
  import_mode: ImportMode
  priority: number
  owner: string | null
  torrent_tag: string | null
  state: ReservationState
  created_at: string
  updated_at: string
  expires_at: string | null
}

export type ReservationState =
  | 'PENDING'
  | 'RESERVED'
  | 'ACTIVE'
  | 'OWNED'
  | 'RELEASED'
  | 'STALE'
  | 'EXPIRED'

export interface ReleaseRequest {
  reason?: string
}

export interface ReconcileResponse {
  status: string
  expired_count: number
  details: string | null
  timestamp: string
}

export interface ReconcileStateResponse {
  component: string
  last_run_at: string | null
  status: string | null
  details: string | null
}

export interface QBittorrentStatusResponse {
  status: string
  version: string | null
  reason: string | null
}

export interface IntegrationHealthResponse {
  provider: string
  type: 'arr' | 'seerr' | 'qbittorrent'
  status: string
  version: string | null
  reason: string | null
  latency_ms: number | null
}

export interface AuditEntryResponse {
  id: number
  reservation_id: string
  event_type: string
  details: string | null
  created_at: string
}

export interface UnreservedTorrentResponse {
  hash: string
  name: string
  size: number
  progress: number
  state: string
  tags: string[]
  save_path: string
}

export interface TorrentReconcileResponse {
  status: string
  reconciled_reservations_count: number
  recovered_reservations_count: number
  unreserved_torrents_count: number
  unreserved_torrents: UnreservedTorrentResponse[]
  details: string | null
  timestamp: string
}