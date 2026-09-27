# Integration Issues

## Seerr/Jellyseerr

### `400 Invalid provider`
**Fix:** Use exactly `seerr` or `jellyseerr`

### `503 Unavailable` on health check
**Check:** `SEERR_URL`, network, API key

### Import confirmation fails
**Error:** `404 Reservation not found`
**Fix:** Ensure `reservation_id` from admit response matches

---

## Sonarr/Radarr

### `400 Invalid provider`
**Fix:** Use exactly `sonarr` or `radarr`

### API key rejected
**Fix:** Verify API key from Settings → General → Security

### Import confirmation: `400 Invalid arr_item_id`
**Fix:** Use valid episode/movie ID from Sonarr/Radarr

---

## Cross-Integration

### Reservation not found across adapters
**Cause:** Each adapter has its own idempotency namespace
**Fix:** Include `adapter_name` in queries, don't mix IDs

### TTL conflicts
**Cause:** Different adapters using same reservation IDs
**Fix:** Each adapter manages its own reservations

---

## Next: [Architecture Overview](../architecture/overview.md)
