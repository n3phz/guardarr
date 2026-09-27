# Safety Model

## Core Principles

Guardarr treats storage safety as a **deterministic control problem**.

| Principle | Implementation |
|-----------|----------------|
| Storage safety is deterministic | No AI/ML in admission path |
| AI/agents never the safety authority | Admission logic is pure code |
| Reservations are persistent and auditable | SQLite with audit log |
| Concurrent requests accounted for | Outstanding unfulfilled tracked |
| Hardlinks/cross-seeds handled conservatively | Import mode awareness |
| Existing downloads never deleted | No destructive operations |
| New admissions fail closed | 503/409 when safety unverifiable |
| Cleanup/retention outside scope | Separate tools (Reclaimerr) |
| AI cannot override admission | No override endpoint exists |

---

## Fail-Closed Behavior

| Condition | Response |
|-----------|----------|
| Filesystem unreadable | `503 Service Unavailable` |
| qBittorrent unreachable | `503 Service Unavailable` (on reconcile/associate) |
| Database unavailable | `500 Internal Server Error` |
| Threshold ordering invalid | Startup crash (`validate_threshold_order`) |
| Idempotency conflict | `409 Conflict` |
| Projected available < admission floor | `409 Conflict` |

---

## Threshold Ordering (Enforced at Startup)

```python
# From app/core/config.py
if warning <= admission_floor:
    raise ValueError("warning threshold must be greater than admission floor")
if admission_floor <= emergency:
    raise ValueError("admission floor must be greater than emergency threshold")
if emergency <= critical:
    raise ValueError("emergency threshold must be greater than critical threshold")
```

**Required:** `warning > admission_floor > emergency > critical`

---

## Conservative Accounting

Guardarr prefers conservative accounting over optimistic assumptions:

> When storage ownership cannot be safely determined, Guardarr assumes the more conservative interpretation.

### Examples

| Situation | Conservative Approach |
|-----------|----------------------|
| Hardlink vs copy unknown | Assume `copy` (space consumed) |
| Cross-seed detected | Count space for each reservation |
| Partial download | Count full `max_bytes` until import |
| External files in download dir | Counted by filesystem stats |
| Inode exhaustion | Tracked separately via `f_favail` |

---

## Transaction Isolation

Critical operations use `BEGIN IMMEDIATE`:

```python
# From app/services/admission.py
db.execute(text("BEGIN IMMEDIATE"))

# Check idempotency
# Calculate outstanding
# Check projected available
# Create reservation
# Commit
```

This serializes concurrent admission attempts, preventing race conditions.

---

## No Destructive Operations

| Operation | Guardarr Behavior |
|-----------|-------------------|
| Delete files | ❌ Never |
| Pause/stop torrents | ❌ Never (qBittorrent controls) |
| Remove torrents | ❌ Never |
| Modify *Arr libraries | ❌ Never |
| Override admission | ❌ No endpoint |

---

## What Happens When Safety Can't Be Verified

```
Request → Estimate → Filesystem Check → ❌ FAIL
                                    ↓
                              Return 503
                                    ↓
                              Client retries later
```

The system **never** admits a request when it cannot verify safety.

---

## Audit Trail

Every state change creates an audit log entry:

```sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    reservation_id TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- admitted, expired, released, imported, etc.
    details TEXT,
    created_at DATETIME DEFAULT now()
);
```

This provides full traceability for debugging and compliance.

---

## Next: [Integrations Overview](../integrations/overview.md)
