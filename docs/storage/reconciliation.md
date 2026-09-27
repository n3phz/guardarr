# Reconciliation

## Overview

Reconciliation compares three sources of truth:
1. **Reservation Ledger** — What Guardarr expects
2. **Filesystem** — What actually exists on disk  
3. **qBittorrent** — What's actively downloading

## API Endpoint

```bash
POST /api/reconcile                    # Core reservations
POST /api/qbittorrent/reconcile        # Torrent-level
```

---

## Core Reconciliation (`/api/reconcile`)

```python
# From app/services/reconciliation.py
def reconcile(db: Session) -> dict:
    db.execute(text("BEGIN IMMEDIATE"))
    now = datetime.utcnow()
    
    # 1. Detect expired reservations
    expired_res = db.query(ReservationModel).filter(
        ReservationModel.state.in_([PENDING, RESERVED, ACTIVE]),
        ReservationModel.expires_at.isnot(None),
        ReservationModel.expires_at < now
    ).all()
    
    for r in expired_res:
        r.state = EXPIRED
        r.remaining_unfulfilled_bytes = 0
        # Create audit log
    
    # 2. Fix negative remaining bytes
    inconsistent = db.query(ReservationModel).filter(
        ReservationModel.remaining_unfulfilled_bytes < 0
    ).all()
    
    for r in inconsistent:
        r.remaining_unfulfilled_bytes = 0
    
    # 3. Update reconcile state log
    # ...
```

**Actions:**
- Expired reservations → `EXPIRED`, capacity returned
- Negative remaining bytes → zeroed
- Reconcile state log updated

---

## qBittorrent Reconciliation (`/api/qbittorrent/reconcile`)

```python
# From app/services/qbittorrent_reconciliation.py
def reconcile_torrents(db: Session) -> dict:
    client = QBittorrentClient()
    torrents = client.get_torrents()
    
    # 1. Match torrents to reservations by tag
    # 2. Update observed_materialized_bytes from progress
    # 3. Detect unreserved torrents (guardarr tag but no active reservation)
    # 4. Recover reservations with matching torrent hash but no tag
```

**Returns:**
```json
{
  "status": "success",
  "reconciled_reservations_count": 5,
  "recovered_reservations_count": 1,
  "unreserved_torrents_count": 2,
  "unreserved_torrents": [...],
  "details": "Reconciled 5 reservations, recovered 1, found 2 unreserved torrents"
}
```

---

## Unreserved Torrents

Torrents with `guardarr:*` tag but no matching active reservation:

```bash
GET /api/qbittorrent/unreserved
```

Indicates:
- Reservation expired/deleted but torrent remains
- Manual torrent addition with guardarr tag
- Reconciliation gap

---

## Reconciliation Schedule

Guardarr does **not** run reconciliation automatically. It must be triggered:

| Method | How |
|--------|-----|
| Manual | `POST /api/reconcile` or `POST /api/qbittorrent/reconcile` |
| Cron | External scheduler (e.g., `cron` in container) |
| Saltbox | `guardarr-reconcile` timer (if configured) |

---

## When to Run Reconciliation

| Scenario | Why |
|----------|-----|
| Periodic (hourly) | Catch expired TTLs |
| After qBittorrent restart | Sync state |
| After *Arr import | Verify owned state |
| Storage issues | Diagnose discrepancies |
| Unreserved torrents alert | Clean up |

---

## Next: [Docker Deployment](../deployment/docker.md)
