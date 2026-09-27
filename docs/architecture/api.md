# API Reference

## Base URL

```
http://localhost:8000/api
```

All endpoints under `/api` unless noted.

---

## Health & Status

### GET /health
**Liveness probe**

```json
{
  "status": "ok",
  "service": "guardarr",
  "version": "0.1.2",
  "environment": "production"
}
```

### GET /ready
**Readiness probe (filesystem + DB)**

```json
// 200 OK
{
  "status": "ready",
  "service": "guardarr",
  "data_dir": "/config",
  "storage_path": "/data"
}

// 503 Not Ready
{
  "status": "not_ready",
  "reason": "Storage path does not exist: /data"
}
```

### GET /status
**Full status with thresholds**

```json
{
  "total_bytes": 10995116277760,
  "available_bytes": 800000000000,
  "configured_admission_floor_bytes": 750000000000,
  "warning_threshold_bytes": 1000000000000,
  "emergency_threshold_bytes": 500000000000,
  "critical_threshold_bytes": 250000000000,
  "current_threshold_state": "WARNING",
  "inode_total": 10000000,
  "inode_available": 8000000,
  "inode_usage_percent": 20.0,
  "filesystem_identity": "/data",
  "device_identity": "0x12345678",
  "ready": true
}
```

---

## Core Reservations

### POST /estimate
**Pre-admission dry run**

```json
// Request
{
  "max_bytes": 300000000000,
  "expected_bytes": 280000000000,
  "import_mode": "hardlink",
  "target_device": "/data"
}

// Response
{
  "available_bytes": 800000000000,
  "outstanding_unfulfilled_bytes": 0,
  "requested_bytes": 300000000000,
  "projected_available_bytes": 500000000000,
  "admission_floor_bytes": 750000000000,
  "admissible": false,
  "reason": "Projected available bytes (500000000000) would fall below admission floor (750000000000)"
}
```

### POST /admit
**Create reservation**

```json
// Request
{
  "adapter_name": "seerr",
  "idempotency_key": "req_abc123",
  "content_id": "12345",
  "max_bytes": 300000000000,
  "expected_bytes": 280000000000,
  "observed_materialized_bytes": 0,
  "target_device": "/data",
  "import_mode": "hardlink",
  "priority": 0,
  "owner": "user1",
  "torrent_tag": null,
  "ttl_seconds": 86400
}

// Response (201)
{
  "id": "uuid",
  "idempotency_key": "req_abc123",
  "adapter_name": "seerr",
  "content_id": "12345",
  "torrent_metadata_hash": null,
  "target_device": "/data",
  "max_bytes": 300000000000,
  "expected_bytes": 280000000000,
  "observed_materialized_bytes": 0,
  "remaining_unfulfilled_bytes": 300000000000,
  "import_mode": "hardlink",
  "priority": 0,
  "owner": "user1",
  "torrent_tag": null,
  "state": "RESERVED",
  "arr_item_id": null,
  "associated_path": null,
  "created_at": "2026-09-27T00:00:00",
  "updated_at": "2026-09-27T00:00:00",
  "expires_at": "2026-09-28T00:00:00"
}
```

### POST /reservations/{id}/release
**Release reservation**

```json
// Request
{
  "reason": "User cancelled"
}

// Response
{... reservation with state=RELEASED ...}
```

### GET /reservations
**List reservations**

Query params: `state`, `adapter_name`

```json
// Response
[... array of reservation objects ...]
```

### GET /reservations/{id}
**Get reservation**

```json
// Response: same as admit response
```

### POST /reconcile
**Run core reconciliation**

```json
// Response
{
  "status": "success",
  "expired_count": 2,
  "details": "Expired 2 reservations, fixed 0 inconsistencies"
}
```

---

## qBittorrent

### GET /qbittorrent/status
```json
{
  "status": "connected",
  "version": "v5.1.4",
  "reason": null
}
```

### POST /qbittorrent/reservations/{id}/associate
```json
// Request
{
  "torrent_hash": "abc123def456..."
}

// Response
{
  "status": "success",
  "reservation_id": "uuid",
  "torrent_metadata_hash": "abc123def456...",
  "torrent_tag": "guardarr:uuid",
  "state": "ACTIVE",
  "observed_materialized_bytes": 0,
  "remaining_unfulfilled_bytes": 300000000000
}
```

### POST /qbittorrent/reservations/{id}/add
**Controlled add torrent**

```json
// Request
{
  "url_or_magnet": "magnet:?xt=urn:btih:abc123...",
  "savepath": "/data/media/movies/Movie (2024)",
  "category": "movies",
  "idempotency_key": "unique_key"
}

// Response (201)
{
  "reservation_id": "uuid",
  "torrent_hash": "abc123def456...",
  "torrent_tag": "guardarr:uuid",
  "state": "ACTIVE",
  "qbittorrent_status": "added",
  "association_status": "associated",
  "recovery_info": null
}
```

### POST /qbittorrent/reconcile
```json
// Response
{
  "status": "success",
  "reconciled_reservations_count": 5,
  "recovered_reservations_count": 1,
  "unreserved_torrents_count": 2,
  "unreserved_torrents": [...],
  "details": "Reconciled 5 reservations...",
  "timestamp": "2026-09-27T00:00:00"
}
```

### GET /qbittorrent/unreserved
```json
// Response
[... array of UnreservedTorrentResponse ...]
```

---

## Seerr / Jellyseerr

All endpoints under `/api/seerr`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health/{provider}` | GET | Connectivity check |
| `/estimate` | POST | Pre-admission estimate |
| `/admit` | POST | Create reservation |
| `/{id}/imported` | POST | Confirm import |
| `/{id}/release` | POST | Release capacity |
| `/{id}` | GET | Get reservation |

---

## Sonarr / Radarr

All endpoints under `/api/arr`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health/{provider}` | GET | Connectivity check |
| `/estimate` | POST | Pre-admission estimate |
| `/admit` | POST | Create reservation |
| `/{id}/imported` | POST | Confirm import |
| `/{id}/release` | POST | Release capacity |
| `/{id}` | GET | Get reservation |

---

## Error Responses

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created (reservation) |
| 400 | Bad request (validation) |
| 404 | Not found (reservation) |
| 409 | Conflict (idempotency, storage full) |
| 503 | Unavailable (filesystem, qBittorrent, DB) |
| 500 | Internal error |

---

## Next: [Database](database.md)
