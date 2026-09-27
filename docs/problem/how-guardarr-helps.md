# How Guardarr Helps

## The Guardarr Thesis

> **Guardarr prevents concurrent automated media downloads from exceeding a defined storage budget.**

The core idea is deliberately narrow:

**check → reserve → admit → observe → reconcile → release**

The reservation ledger is the centre of the system. Integrations exist to make that ledger reliable across the *Arr ecosystem.

---

## Visual Comparison

### Without Guardarr
```text
Request A ──► qBittorrent ──► Download ──► Import
Request B ──► qBittorrent ──► Download ──► Import
Request C ──► qBittorrent ──► Download ──► Import
                     │
                     ▼
            Storage full ❌
```

### With Guardarr
```text
Request A ──► Guardarr ──► RESERVED ──► qBittorrent ──► Download ──► Import ──► OWNED
Request B ──► Guardarr ──► RESERVED ──► qBittorrent ──► Download ──► Import ──► OWNED
Request C ──► Guardarr ──► BLOCKED ❌
                     │
                     ▼
            Storage safe ✅
```

---

## Core Capabilities

### 1. Storage Admission
Determines whether a request fits within the available storage budget *before* the download starts.

```python
# Simplified admission logic
available = filesystem.available_bytes
reserved = sum(active_reservations.remaining_unfulfilled_bytes)
requested = calculate_remaining(request.max_bytes, 0, request.import_mode)
projected = available - reserved - requested

admissible = projected >= admission_floor
```

### 2. Persistent Reservations
Accepted requests create a persistent reservation record:

| Field | Purpose |
|-------|---------|
| `id` | Unique reservation identifier |
| `idempotency_key` | Prevents duplicate admissions |
| `adapter_name` | Source (seerr, sonarr, radarr) |
| `content_id` | Media identifier |
| `max_bytes` | Maximum space this reservation may consume |
| `expected_bytes` | Expected final size after import |
| `remaining_unfulfilled_bytes` | Space still needed |
| `state` | PENDING → RESERVED → ACTIVE → OWNED → RELEASED |
| `expires_at` | TTL for automatic expiry |

### 3. Concurrency Control
Multiple outstanding requests are tracked together:

```python
outstanding = sum(r.remaining_unfulfilled_bytes 
                  for r in reservations 
                  if r.state in [PENDING, RESERVED, ACTIVE])
projected_available = available - outstanding - new_request
```

### 4. Lifecycle Tracking
Reservations follow a deterministic state machine:

```
PENDING → RESERVED → ACTIVE → OWNED → RELEASED
                ↓
            EXPIRED (TTL)
                ↓
            STALE (orphaned)
```

### 5. Reconciliation
Periodic comparison of three sources of truth:

| Source | What It Tells Us |
|--------|------------------|
| **Reservation Ledger** | What we *think* is happening |
| **Filesystem** | What *actually* exists on disk |
| **qBittorrent** | What *downloads* are in progress |

Reconciliation fixes:
- Expired reservations → EXPIRED, capacity returned
- Negative remaining bytes → zeroed
- Orphaned torrents → flagged as unreserved

### 6. Fail-Closed Admission
When safety cannot be verified:
- Filesystem unreadable → **DENY**
- qBittorrent unreachable → **DENY**
- Database unavailable → **DENY**
- Threshold ordering invalid → **STARTUP FAIL**

---

## What This Means in Practice

| Scenario | Without Guardarr | With Guardarr |
|----------|------------------|---------------|
| 3 × 300GB requests, 800GB free | All 3 start, disk fills | 2 admitted, 1 blocked |
| Stalled 50GB download | Space lost forever | Reservation expires, space returned |
| External process writes 100GB | Not detected | Reconciliation adjusts available |
| Hardlinked import | Double-counted | Import mode tracks correctly |

---

## Next: [Workflow Overview](../how-it-works/workflow.md)
