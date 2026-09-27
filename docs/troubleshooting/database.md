# Database Issues

## Schema

```sql
-- reservations
CREATE TABLE reservations (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL,
    adapter_name TEXT NOT NULL,
    content_id TEXT,
    torrent_metadata_hash TEXT,
    target_device TEXT NOT NULL DEFAULT '/data',
    max_bytes INTEGER NOT NULL,
    expected_bytes INTEGER NOT NULL,
    observed_materialized_bytes INTEGER NOT NULL DEFAULT 0,
    remaining_unfulfilled_bytes INTEGER NOT NULL,
    import_mode TEXT NOT NULL DEFAULT 'unknown',
    priority INTEGER NOT NULL DEFAULT 0,
    owner TEXT,
    torrent_tag TEXT,
    state TEXT NOT NULL DEFAULT 'RESERVED',
    arr_item_id TEXT,
    associated_path TEXT,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),
    expires_at DATETIME,
    UNIQUE(adapter_name, idempotency_key)
);

-- audit_log
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reservation_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    details TEXT,
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);

-- reconcile_state
CREATE TABLE reconcile_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component TEXT NOT NULL UNIQUE,
    last_run_at DATETIME NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL,
    details TEXT
);
```

---

## Common Issues

### Missing tables on fresh install
**Fixed in 0.1.2:** Lifespan handler auto-creates tables
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield
```

### SQLite locking
- Only one Guardarr container per database
- Use WAL mode (default in SQLAlchemy)
- No concurrent writers

### Corrupted database
**Symptoms:** `sqlite3.DatabaseError`, `disk I/O error`
**Solution:**
1. Stop container
2. Backup `/config/guardarr.db`
3. Delete database file
4. Restart container (auto-recreates)

---

## Manual Queries

### List all reservations
```sql
SELECT id, adapter_name, state, max_bytes, remaining_unfulfilled_bytes, created_at
FROM reservations
ORDER BY created_at DESC;
```

### Find expired reservations
```sql
SELECT * FROM reservations
WHERE expires_at IS NOT NULL AND expires_at < datetime('now')
AND state IN ('PENDING', 'RESERVED', 'ACTIVE');
```

### Fix negative remaining bytes
```sql
UPDATE reservations
SET remaining_unfulfilled_bytes = 0, updated_at = datetime('now')
WHERE remaining_unfulfilled_bytes < 0;
```

### List audit log for reservation
```sql
SELECT * FROM audit_log WHERE reservation_id = 'uuid-here' ORDER BY created_at;
```

---

## Next: [Storage Issues](storage.md)
