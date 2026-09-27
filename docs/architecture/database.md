# Database

## Engine

```python
# app/db/base.py
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
```

- **SQLite** with WAL mode (default in SQLAlchemy 2.0)
- File-based at `/config/guardarr.db`
- Single writer, multiple readers

---

## Schema

### reservations
```sql
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
```

**Indexes:**
- `ix_reservations_adapter_idempotency` — `(adapter_name, idempotency_key)` UNIQUE
- `ix_reservations_state_target` — `(state, target_device)`

---

### audit_log
```sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reservation_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    details TEXT,
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

**Index:** `reservation_id`

---

### reconcile_state
```sql
CREATE TABLE reconcile_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component TEXT NOT NULL UNIQUE,
    last_run_at DATETIME NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL,
    details TEXT
);
```

---

## Models

### ReservationModel
```python
class ReservationModel(Base):
    id = Column(String(36), primary_key=True)
    idempotency_key = Column(String(255), nullable=False)
    adapter_name = Column(String(100), nullable=False)
    content_id = Column(String(255), nullable=True)
    torrent_metadata_hash = Column(String(64), nullable=True, index=True)
    target_device = Column(String(255), nullable=False, default="/data")
    max_bytes = Column(BigInteger, nullable=False)
    expected_bytes = Column(BigInteger, nullable=False)
    observed_materialized_bytes = Column(BigInteger, nullable=False, default=0)
    remaining_unfulfilled_bytes = Column(BigInteger, nullable=False)
    import_mode = Column(SQLEnum(ImportMode), nullable=False, default=ImportMode.UNKNOWN)
    priority = Column(Integer, nullable=False, default=0)
    owner = Column(String(100), nullable=True)
    torrent_tag = Column(String(100), nullable=True, index=True)
    state = Column(SQLEnum(ReservationState), nullable=False, default=ReservationState.RESERVED)
    arr_item_id = Column(String(255), nullable=True, index=True)
    associated_path = Column(String(1024), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
```

### States
```python
class ReservationState(str, enum.Enum):
    PENDING = "PENDING"
    RESERVED = "RESERVED"
    ACTIVE = "ACTIVE"
    OWNED = "OWNED"
    RELEASED = "RELEASED"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
```

### Import Modes
```python
class ImportMode(str, enum.Enum):
    HARDLINK = "hardlink"
    COPY = "copy"
    UNKNOWN = "unknown"
```

---

## Session Management

```python
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Used as FastAPI dependency: `db: Session = Depends(get_db)`

---

## Lifespan Initialization

```python
# app/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield
```

Called once at startup — creates tables if missing (0.1.2 fix).

---

## Transaction Patterns

### Admission (BEGIN IMMEDIATE)
```python
db.execute(text("BEGIN IMMEDIATE"))
# Check idempotency
# Calculate outstanding
# Check projected available
# Create reservation
db.commit()
```

### Reconciliation (BEGIN IMMEDIATE)
```python
db.execute(text("BEGIN IMMEDIATE"))
# Expire old reservations
# Fix negative bytes
# Update reconcile state
db.commit()
```

---

## Next: [Services](services.md)
