# Common Issues

## Database

### `no such table: reservations`
**Cause:** Database not initialized on fresh install
**Fixed in 0.1.2:** FastAPI lifespan now calls `Base.metadata.create_all(bind=engine)` on startup
**Verify:** `docker exec guardarr python3 -c "import sqlite3; db=sqlite3.connect('/config/guardarr.db'); print([r[0] for r in db.execute('SELECT name FROM sqlite_master WHERE type=\"table\"')])"`

### Database locked
**Cause:** Multiple processes accessing SQLite
**Solution:** Ensure single container instance; check for stale processes

---

## Storage Admission

### All requests denied (409 Conflict)
**Cause:** Available space below admission floor
**Check:** `curl /api/status` → verify `current_threshold_state` and `available_bytes`
**Solutions:**
- Free up space
- Increase thresholds
- Wait for downloads to complete/import

### Requests admitted but storage fills anyway
**Cause:** Outstanding reservations not tracked correctly
**Check:** `curl /api/status` → compare `available_bytes` vs `outstanding_unfulfilled_bytes`
**Solutions:**
- Run reconciliation: `POST /api/reconcile`
- Check for external writes to `/data`

### Threshold ordering error at startup
**Error:** `ValueError: warning threshold must be greater than admission floor`
**Fix:** Ensure `WARNING > ADMISSION_FLOOR > EMERGENCY > CRITICAL` in env vars

---

## qBittorrent

### `503 Service Unavailable` on qBittorrent endpoints
**Cause:** qBittorrent unreachable or auth failed
**Check:**
```bash
# Test from host
curl http://qbittorrent:8080/api/v2/app/version

# Test from container
docker exec guardarr python3 -c "
import urllib.request
resp = urllib.request.urlopen('http://qbittorrent:8080/api/v2/app/version')
print(resp.read().decode())
"
```

### `403` on auth/login
**Cause:** Wrong username/password
**Fix:** Verify `QBITTORRENT_USERNAME` and `QBITTORRENT_PASSWORD` in env

### Torrent hash already claimed
**Error:** `400 Torrent hash already claimed by another active reservation`
**Cause:** Duplicate association attempt
**Solution:** Run reconciliation to clean up, or manually release conflicting reservation

### Save path validation failed
**Error:** `400 Savepath must reside within authorized container storage boundaries`
**Fix:** Use paths starting with `/data/` or `/config/`

---

## Seerr/Jellyseerr

### `400 Invalid provider`
**Cause:** Provider field not "seerr" or "jellyseerr"
**Fix:** Use exactly `seerr` or `jellyseerr`

### `503 Unavailable` on connectivity
**Cause:** Seerr API unreachable
**Check:** `SEERR_URL`, `SEERR_API_KEY`, network connectivity

### `409 Conflict` on admit
**Cause:** Idempotency key already used, or storage below floor
**Fix:** Use unique `request_id`, or wait for space

---

## Sonarr/Radarr

### `400 Invalid provider`
**Cause:** Provider field not "sonarr" or "radarr"
**Fix:** Use exactly `sonarr` or `radarr`

### API key errors
**Cause:** Wrong/missing API key
**Fix:** Verify `SONARR_API_KEY` / `RADARR_API_KEY` from respective configs

### Import confirmation fails
**Error:** `404 Reservation not found` or `400 Invalid arr_item_id`
**Fix:** Ensure reservation ID matches, arr_item_id valid

---

## Reconciliation

### Reservations not expiring
**Cause:** Reconciliation not running
**Fix:** Run `POST /api/reconcile` manually or set up cron

### Unreserved torrents accumulating
**Cause:** Reservations deleted/expired but torrents remain
**Fix:** Run `POST /api/qbittorrent/reconcile`, review unreserved list

### Negative remaining bytes
**Symptom:** `remaining_unfulfilled_bytes < 0` in DB
**Fix:** Reconciliation auto-fixes; or manually: `UPDATE reservations SET remaining_unfulfilled_bytes = 0 WHERE remaining_unfulfilled_bytes < 0`

---

## Next: [Database Issues](database.md)
