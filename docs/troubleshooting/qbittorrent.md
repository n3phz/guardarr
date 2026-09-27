# qBittorrent Issues

## Connection Refused

**Error:** `503 Service Unavailable` on `/api/qbittorrent/status`

**Causes:**
- qBittorrent not running
- Wrong URL/port
- Network isolation

**Debug:**
```bash
# From host
curl http://qbittorrent:8080/api/v2/app/version

# From container
docker exec guardarr python3 -c "
import urllib.request
try:
    resp = urllib.request.urlopen('http://qbittorrent:8080/api/v2/app/version')
    print(resp.read().decode())
except Exception as e:
    print(f'Error: {e}')
"
```

---

## Authentication Failed

**Error:** `403` or `503` on controlled add/associate

**Causes:**
- Wrong username/password
- qBittorrent WebUI authentication changed
- CSRF protection (unlikely with API)

**Fix:**
```bash
# Verify credentials
docker exec guardarr python3 -c "
import urllib.request, urllib.parse
data = urllib.parse.urlencode({'username': 'YOUR_USER', 'password': 'YOUR_PASS'}).encode()
req = urllib.request.Request('http://qbittorrent:8080/api/v2/auth/login', data=data, method='POST')
resp = urllib.request.urlopen(req)
print(f'Status: {resp.status}, Body: {resp.read().decode()}')
"
```

---

## Torrent Already Claimed

**Error:** `400 Torrent hash already claimed by another active reservation`

**Cause:** Hash collision or stale reservation

**Fix:**
```bash
# Run reconciliation
curl -X POST http://localhost:8000/api/qbittorrent/reconcile

# Or manually release
curl -X POST http://localhost:8000/api/reservations/{id}/release -d '{"reason":"cleanup"}'
```

---

## Save Path Outside Boundaries

**Error:** `400 Savepath must reside within authorized container storage boundaries`

**Fix:** Use `/data/...` or `/config/...` paths only

---

## Unreserved Torrents

**Symptom:** `GET /api/qbittorrent/unreserved` returns many torrents

**Causes:**
- Reservations expired but torrents still downloading
- Manual torrent additions with guardarr tag
- Reconciliation not running

**Fix:**
1. Run `POST /api/qbittorrent/reconcile`
2. Review unreserved list
3. Manually clean up or re-associate

---

## Tag Not Applied

**Symptom:** Torrents added but no `guardarr:*` tag

**Cause:** Tag application failed in controlled add

**Debug:**
```bash
# Check qBittorrent tags
curl -s "http://qbittorrent:8080/api/v2/torrents/info" | jq '.[] | {hash, tags}'
```

---

## Next: [Integration Issues](integrations.md)
