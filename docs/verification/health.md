# Health Checks

## Endpoints

| Endpoint | Purpose | Auth | Expected |
|----------|---------|------|----------|
| `GET /api/health` | Basic liveness | None | 200 OK |
| `GET /api/ready` | Readiness (filesystem + DB) | None | 200 OK / 503 |
| `GET /api/status` | Full status with thresholds | None | 200 OK |

---

## /api/health

Basic liveness probe. Returns immediately if process is running.

```bash
curl http://localhost:8000/api/health
```

**Response (200):**
```json
{
  "status": "ok",
  "service": "guardarr",
  "version": "0.1.2",
  "environment": "production"
}
```

---

## /api/ready

Readiness probe. Checks:
1. Filesystem path exists and readable
2. Database accessible

```bash
curl http://localhost:8000/api/ready
```

**Response (200):**
```json
{
  "status": "ready",
  "service": "guardarr",
  "data_dir": "/config",
  "storage_path": "/data"
}
```

**Response (503):**
```json
{
  "status": "not_ready",
  "reason": "Storage path does not exist: /data"
}
```

---

## /api/status

Full status with storage thresholds and inode info.

```bash
curl http://localhost:8000/api/status
```

**Response (200):**
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

## Docker Healthcheck

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 5s
```

---

## Saltbox Healthcheck

```yaml
guardarr_role_docker_healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
  interval: 30s
  timeout: 5s
  start_period: 10s
  retries: 3
```

---

## Monitoring Integration

### Prometheus (example)
```yaml
- job_name: 'guardarr'
  static_configs:
    - targets: ['guardarr:8000']
  metrics_path: /api/status
```

### Grafana Dashboard Queries
- Storage available: `guardarr_status_available_bytes`
- Threshold state: `guardarr_status_current_threshold_state` (0=NORMAL, 1=WARNING, 2=BLOCKED, 3=EMERGENCY, 4=CRITICAL)
- Inode usage: `guardarr_status_inode_usage_percent`

---

## Next: [Integration Tests](integrations.md)
