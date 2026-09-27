# Integration Verification

## Quick Verification Checklist

After deployment, verify each integration:

```bash
# 1. Core health
curl -s http://localhost:8000/api/health | jq .

# 2. Readiness (filesystem + DB)
curl -s http://localhost:8000/api/ready | jq .

# 3. Full status
curl -s http://localhost:8000/api/status | jq .

# 4. qBittorrent connectivity
curl -s http://localhost:8000/api/qbittorrent/status | jq .

# 5. Seerr connectivity
curl -s http://localhost:8000/api/seerr/health/seerr | jq .

# 6. Jellyseerr connectivity
curl -s http://localhost:8000/api/seerr/health/jellyseerr | jq .

# 7. Sonarr connectivity
curl -s http://localhost:8000/api/arr/health/sonarr | jq .

# 8. Radarr connectivity
curl -s http://localhost:8000/api/arr/health/radarr | jq .
```

---

## Expected Responses

### qBittorrent Status
```json
{
  "status": "connected",
  "version": "v5.1.4",
  "reason": null
}
```

### Seerr/Jellyseerr Health
```json
{
  "provider": "seerr",
  "status": "connected",
  "version": "3.4.1",
  "reason": null
}
```

### Sonarr/Radarr Health
```json
{
  "provider": "sonarr",
  "status": "connected",
  "version": "4.0.0",
  "reason": null
}
```

---

## End-to-End Test

### Test Seerr Flow

```bash
# 1. Estimate
curl -s -X POST http://localhost:8000/api/seerr/estimate \
  -H "Content-Type: application/json" \
  -d '{"provider":"seerr","request_id":"test123","estimated_size_bytes":10000000000}' | jq .

# 2. Admit
curl -s -X POST http://localhost:8000/api/seerr/admit \
  -H "Content-Type: application/json" \
  -d '{"provider":"seerr","request_id":"test123","max_bytes":10000000000,"expected_bytes":9000000000}' | jq .

# 3. Check reservation
curl -s http://localhost:8000/api/reservations | jq .
```

### Test Arr Flow

```bash
# 1. Estimate
curl -s -X POST http://localhost:8000/api/arr/estimate \
  -H "Content-Type: application/json" \
  -d '{"provider":"sonarr","content_id":"test123","estimated_size_bytes":5000000000}' | jq .

# 2. Admit
curl -s -X POST http://localhost:8000/api/arr/admit \
  -H "Content-Type: application/json" \
  -d '{"provider":"sonarr","content_id":"test123","arr_item_id":"ep456","max_bytes":5000000000,"expected_bytes":4500000000}' | jq .
```

### Test qBittorrent Controlled Add

```bash
# Get reservation ID from admit response, then:
curl -s -X POST http://localhost:8000/api/qbittorrent/reservations/{reservation_id}/add \
  -H "Content-Type: application/json" \
  -d '{"url_or_magnet":"magnet:?xt=urn:btih:...","savepath":"/data/media/movies/Test","idempotency_key":"test123"}' | jq .
```

---

## Reconciliation Test

```bash
# Core reservations
curl -s -X POST http://localhost:8000/api/reconcile | jq .

# qBittorrent torrents
curl -s -X POST http://localhost:8000/api/qbittorrent/reconcile | jq .

# Unreserved torrents
curl -s http://localhost:8000/api/qbittorrent/unreserved | jq .
```

---

## Database Verification

```bash
# Check tables exist
docker exec guardarr python3 -c "
import sqlite3
db = sqlite3.connect('/config/guardarr.db')
cur = db.cursor()
print('Tables:', [r[0] for r in cur.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")])
"
```

Expected: `['reservations', 'audit_log', 'reconcile_state']`

---

## Next: [Troubleshooting Common Issues](../troubleshooting/common.md)
