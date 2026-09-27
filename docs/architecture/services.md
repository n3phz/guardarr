# Services

## AdmissionService

**File:** `app/services/admission.py`

### Responsibilities
- Calculate outstanding unfulfilled capacity
- Estimate admission feasibility
- Create reservations with transaction isolation

### Key Methods

```python
@staticmethod
def calculate_outstanding_unfulfilled(db: Session, target_device: str) -> int:
    """Sum remaining_unfulfilled_bytes for active reservations on device."""

@staticmethod
def estimate(db: Session, req: EstimateRequest) -> EstimateResponse:
    """Dry-run admission check."""

@staticmethod
def admit(db: Session, req: AdmitRequest) -> Tuple[ReservationModel, bool, str]:
    """Create reservation with BEGIN IMMEDIATE transaction."""
```

---

## ReconciliationService

**File:** `app/services/reconciliation.py`

### Responsibilities
- Expire old reservations (TTL)
- Fix data inconsistencies
- Update reconciliation state log

### Key Methods

```python
@staticmethod
def reconcile(db: Session) -> dict:
    """Run core reconciliation with BEGIN IMMEDIATE."""
```

### Actions
1. Find reservations with `expires_at < now` in active states → `EXPIRED`
2. Fix `remaining_unfulfilled_bytes < 0` → zero
3. Update `reconcile_state` table

---

## QBittorrentClient

**File:** `app/services/qbittorrent.py`

### Responsibilities
- qBittorrent WebUI authentication
- Torrent management (add, tag, status)
- API communication

### Key Methods

```python
def login(self) -> bool
def _request(self, method, endpoint, **kwargs) -> Optional[requests.Response]
def test_connectivity(self) -> dict
def add_torrent(self, url_or_magnet, savepath, category) -> dict
def set_torrent_tag(self, hash, tag) -> dict
def get_torrents(self) -> list
```

---

## QBittorrentReconciliationService

**File:** `app/services/qbittorrent_reconciliation.py`

### Responsibilities
- Associate torrents with reservations
- Update observed bytes from qBittorrent progress
- Detect unreserved torrents

### Key Methods

```python
@staticmethod
def associate_torrent(db: Session, reservation_id: str, torrent_hash: str) -> ReservationModel

@staticmethod
def reconcile_torrents(db: Session) -> dict:
    """Full torrent reconciliation."""
```

---

## ControlledAdmissionService

**File:** `app/services/controlled_admission.py`

### Responsibilities
- Extract magnet hash from URL/magnet
- Add torrent to qBittorrent with tag
- Update reservation state

### Key Methods

```python
@staticmethod
def controlled_add(db: Session, reservation_id: str, req: ControlledAddRequest) -> dict
```

---

## ArrOrchestrationService

**File:** `app/services/arr_orchestration.py`

### Responsibilities
- Sonarr/Radarr estimate/admit/import/release
- Connectivity checks

### Key Methods

```python
@staticmethod
def estimate(db: Session, req: ArrEstimateRequest) -> ArrEstimateResponse
@staticmethod
def admit(db: Session, req: ArrAdmitRequest) -> ArrAdmitResponse
@staticmethod
def confirm_imported(db: Session, reservation_id: str, req: ArrImportedRequest) -> ArrImportedResponse
@staticmethod
def release_owned(db: Session, reservation_id: str, reason: str) -> ReservationModel
```

---

## SeerrOrchestrationService

**File:** `app/services/seerr_orchestration.py`

### Responsibilities
- Seerr/Jellyseerr estimate/admit/import/release
- Connectivity checks

### Key Methods

```python
@staticmethod
def estimate(db: Session, req: SeerrEstimateRequest) -> SeerrEstimateResponse
@staticmethod
def admit(db: Session, req: SeerrAdmitRequest) -> SeerrAdmitResponse
@staticmethod
def confirm_imported(db: Session, reservation_id: str, req: SeerrImportedRequest) -> SeerrImportedResponse
@staticmethod
def release_owned(db: Session, reservation_id: str, reason: str) -> ReservationModel
```

---

## Integration Clients

**Files:** `app/integrations/arr/base.py`, `app/integrations/seerr/base.py`

### Base Classes
- `BaseArrClient` — Sonarr/Radarr API wrapper
- `BaseSeerrClient` — Seerr/Jellyseerr API wrapper

### Features
- Shared session with `X-Api-Key` header
- TLS verification configurable
- Security: API keys never logged
- Abstract `test_connectivity()` method

---

## Next: [Roadmap](../roadmap.md)
