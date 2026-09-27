# Admission Logic

## Core Algorithm

```python
# From app/services/admission.py

def estimate(db: Session, req: EstimateRequest) -> EstimateResponse:
    settings = get_settings()
    stats = get_filesystem_stats(req.target_device)
    
    available_bytes = stats["available_bytes"]
    outstanding_unfulfilled = calculate_outstanding_unfulfilled(db, req.target_device)
    
    requested = calculate_remaining_unfulfilled(req.max_bytes, 0, req.import_mode)
    projected_available = available_bytes - outstanding_unfulfilled - requested
    
    admissible = projected_available >= settings.admission_floor_bytes
```

---

## Inputs

| Input | Source |
|-------|--------|
| `available_bytes` | `statvfs(req.target_device)` |
| `outstanding_unfulfilled` | Sum of `remaining_unfulfilled_bytes` for active reservations |
| `requested` | `calculate_remaining_unfulfilled(max_bytes, 0, import_mode)` |
| `admission_floor` | `ADMISSION_FLOOR_BYTES` from config |

---

## Outstanding Unfulfilled Calculation

```python
def calculate_outstanding_unfulfilled(db: Session, target_device: str) -> int:
    active_states = [PENDING, RESERVED, ACTIVE]
    reservations = db.query(ReservationModel).filter(
        ReservationModel.target_device == target_device,
        ReservationModel.state.in_(active_states)
    ).all()
    return sum(r.remaining_unfulfilled_bytes for r in reservations)
```

**Active states:** `PENDING`, `RESERVED`, `ACTIVE`
**Excluded states:** `OWNED`, `RELEASED`, `EXPIRED`, `STALE`

---

## Remaining Unfulfilled Calculation

```python
def calculate_remaining_unfulfilled(max_bytes: int, observed_materialized_bytes: int, import_mode: ImportMode) -> int:
    if import_mode in [ImportMode.HARDLINK, ImportMode.COPY]:
        return max(0, max_bytes - observed_materialized_bytes)
    else:
        # Unknown / conservative
        return max(0, max_bytes - observed_materialized_bytes)
```

| Import Mode | Behavior |
|-------------|----------|
| `hardlink` | Full `max_bytes` reserved until release |
| `copy` | Capacity reduces as materialized |
| `unknown` | Conservative (full capacity) |

---

## Decision

```
projected_available = available - outstanding - requested

if projected_available >= admission_floor:
    → ADMISSIBLE (200/201)
else:
    → DENIED (409 Conflict)
```

---

## Concurrency Control

Admission uses `BEGIN IMMEDIATE` transaction:

```python
db.execute(text("BEGIN IMMEDIATE"))

# 1. Check idempotency key
# 2. Calculate outstanding unfulfilled
# 3. Get filesystem stats
# 4. Check projected available
# 5. Create reservation
# 6. Commit
```

This serializes concurrent admission attempts on the same database, preventing race conditions where two requests both see the same available space.

---

## Estimate vs Admit

| Endpoint | Purpose | Side Effects |
|----------|---------|--------------|
| `POST /api/estimate` | Dry-run check | None |
| `POST /api/admit` | Create reservation | Creates DB record |

**Always call estimate first** to avoid unnecessary conflicts.

---

## Next: [Reconciliation](reconciliation.md)
