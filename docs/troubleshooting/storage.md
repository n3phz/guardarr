# Storage Issues

## Filesystem Not Accessible

**Error:** `503 Service Unavailable` on `/api/ready` or `/api/status`

**Causes:**
- `/data` mount missing
- Permission denied
- Path doesn't exist

**Debug:**
```bash
# From host
ls -la /mnt/unionfs
stat /mnt/unionfs

# From container
docker exec guardarr ls -la /data
docker exec guardarr stat /data
```

---

## Available Space Not Updating

**Symptom:** `/api/status` shows stale `available_bytes`

**Causes:**
- Filesystem stats cached (not in Guardarr — `statvfs` is real-time)
- External process consuming space
- Mergerfs/unionfs not reflecting changes

**Debug:**
```bash
# Compare
curl -s http://localhost:8000/api/status | jq .available_bytes
df -h /mnt/unionfs
```

---

## Inode Exhaustion

**Symptom:** `inode_available` near 0, `inode_usage_percent` > 95%

**Causes:**
- Millions of small files
- Incomplete downloads with many pieces
- Temporary files not cleaned

**Solutions:**
- Run reconciliation to expire old reservations
- Check for stale downloads in qBittorrent
- Consider separate volume for metadata

---

## Threshold State Unexpected

**Symptom:** `current_threshold_state` doesn't match expectations

**Check:**
```bash
curl -s http://localhost:8000/api/status | jq '.current_threshold_state, .available_bytes, .configured_admission_floor_bytes, .warning_threshold_bytes'
```

**Remember:** State is determined by `available_bytes` only:
- NORMAL: > warning
- WARNING: ≤ warning
- BLOCKED: ≤ admission_floor
- EMERGENCY: ≤ emergency
- CRITICAL: ≤ critical

---

## External Writes

**Problem:** Space consumed by non-Guardarr processes

**Detection:** Run reconciliation — unreserved torrents or unexpected filesystem usage

**Mitigation:**
- Isolate `/data` for Guardarr-managed media only
- Monitor with external tools (Prometheus/node_exporter)
- Set conservative admission floor with headroom

---

## Next: [qBittorrent Issues](qbittorrent.md)
