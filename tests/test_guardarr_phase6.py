import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import application
from app.db.base import Base, get_db
from app.db.models import ReservationModel, ReservationState, ImportMode
from app.integrations.arr.base import SonarrClient, RadarrClient
from app.integrations.seerr.base import SeerrClient, JellyseerrClient

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

application.dependency_overrides[get_db] = override_get_db
client = TestClient(application)


@pytest.fixture(autouse=True)
def clear_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


# ── Helpers ──────────────────────────────────────────────────────────────

def _admit_seerr(request_id="req-1", media_id="media-1", target_device="/tmp"):
    return client.post("/api/seerr/admit", json={
        "provider": "seerr",
        "request_id": request_id,
        "media_id": media_id,
        "max_bytes": 1_000_000_000,
        "expected_bytes": 1_000_000_000,
        "target_device": target_device,
        "import_mode": "copy",
        "priority": 0,
    })


def _admit_reservation(db, provider="seerr", request_id="req-1", media_id="media-1",
                       target_device="/tmp", import_mode=ImportMode.COPY):
    """Create a reservation directly in RESERVED state (for lifecycle tests)."""
    from app.services.seerr_orchestration import SeerrOrchestrationService
    from app.schemas.seerr import SeerrAdmitRequest
    req = SeerrAdmitRequest(
        provider=provider, request_id=request_id, media_id=media_id,
        max_bytes=1_000_000_000, expected_bytes=1_000_000_000,
        target_device=target_device, import_mode="copy", priority=0,
    )
    return SeerrOrchestrationService.admit(db, req)


def _activate_reservation(db, reservation_id, torrent_hash=None):
    """Transition RESERVED → ACTIVE (simulates controlled add success)."""
    reservation = db.query(ReservationModel).filter(ReservationModel.id == reservation_id).first()
    assert reservation.state == ReservationState.RESERVED
    reservation.state = ReservationState.ACTIVE
    reservation.torrent_metadata_hash = torrent_hash or "aabbccddeeff00112233445566778899aabbccdd"
    reservation.updated_at = db.query(ReservationModel).first().updated_at
    db.commit()
    db.refresh(reservation)
    return reservation


# ── Seerr / Jellyseerr Health ────────────────────────────────────────────

@patch("app.integrations.seerr.base.requests.Session.request")
def test_seerr_health_connected(mock_request):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"version": "2.0.0.0"}
    mock_request.return_value = mock_resp

    res = client.get("/api/seerr/health/seerr")
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "seerr"
    assert data["status"] == "connected"
    assert data["version"] == "2.0.0.0"


@patch("app.integrations.seerr.base.requests.Session.request")
def test_jellyseerr_health_connected(mock_request):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"version": "3.0.0.0"}
    mock_request.return_value = mock_resp

    res = client.get("/api/seerr/health/jellyseerr")
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "jellyseerr"
    assert data["status"] == "connected"
    assert data["version"] == "3.0.0.0"


def test_seerr_health_invalid_provider():
    res = client.get("/api/seerr/health/badprovider")
    assert res.status_code == 400


@patch("app.integrations.seerr.base.requests.Session.request")
def test_seerr_health_disconnected(mock_request):
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_request.return_value = mock_resp

    res = client.get("/api/seerr/health/seerr")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "disconnected"


# ── Estimate ─────────────────────────────────────────────────────────────

def test_seerr_estimate_success():
    res = client.post("/api/seerr/estimate", json={
        "provider": "seerr",
        "request_id": "req-est-1",
        "estimated_size_bytes": 5_000_000_000,
        "target_device": "/tmp",
    })
    assert res.status_code == 200
    data = res.json()
    assert "projected_available_bytes" in data
    assert "admissible" in data


def test_seerr_estimate_invalid_provider():
    res = client.post("/api/seerr/estimate", json={
        "provider": "invalid",
        "request_id": "req-est-2",
        "estimated_size_bytes": 5_000_000_000,
        "target_device": "/tmp",
    })
    assert res.status_code == 400


# ── Admit ────────────────────────────────────────────────────────────────

def test_seerr_admit_success():
    res = _admit_seerr()
    assert res.status_code == 201
    data = res.json()
    assert data["state"] == "RESERVED"
    assert "reservation_id" in data


def test_seerr_admit_idempotent():
    res1 = _admit_seerr(request_id="req-idem", media_id="media-idem")
    assert res1.status_code == 201
    r_id = res1.json()["reservation_id"]

    res2 = _admit_seerr(request_id="req-idem", media_id="media-idem")
    assert res2.status_code == 201
    assert res2.json()["reservation_id"] == r_id
    assert res2.json()["state"] == "RESERVED"


def test_seerr_admit_invalid_provider():
    res = client.post("/api/seerr/admit", json={
        "provider": "invalid",
        "request_id": "req-bad",
        "max_bytes": 1_000_000_000,
        "expected_bytes": 1_000_000_000,
    })
    assert res.status_code == 400


def test_seerr_admit_conflict_below_floor():
    res = client.post("/api/seerr/admit", json={
        "provider": "seerr",
        "request_id": "req-massive",
        "max_bytes": 999_999_999_999_999_000,
        "expected_bytes": 999_999_999_999_999_000,
    })
    assert res.status_code == 409


# ── Lifecycle: RESERVED → ACTIVE → OWNED → RELEASED ──────────────────────

def test_seerr_full_lifecycle(db=TestingSessionLocal()):
    """Explicit RESERVED → ACTIVE → OWNED → RELEASED."""
    db_session = TestingSessionLocal()
    try:
        admit = _admit_reservation(db_session, provider="seerr", request_id="lifecycle-1")
        r_id = admit.reservation_id
        assert admit.state == ReservationState.RESERVED

        # Transition RESERVED → ACTIVE via controlled add simulation
        _activate_reservation(db_session, r_id, torrent_hash="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")
        reservation = db_session.query(ReservationModel).filter(ReservationModel.id == r_id).first()
        assert reservation.state == ReservationState.ACTIVE

        # ACTIVE → OWNED via imported callback
        imported_res = client.post(f"/api/seerr/{r_id}/imported", json={
            "provider": "seerr",
            "request_id": "lifecycle-1",
            "media_id": "media-1",
            "torrent_hash": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            "imported_path": "/data/tv/Show.S01E01.mkv",
        })
        assert imported_res.status_code == 200
        assert imported_res.json()["state"] == "OWNED"
        assert imported_res.json()["ownership_verified"] is True
        assert imported_res.json()["released"] is False

        db_session.expire_all()
        reservation = db_session.query(ReservationModel).filter(ReservationModel.id == r_id).first()
        assert reservation.state == ReservationState.OWNED

        # OWNED → RELEASED
        release_res = client.post(f"/api/seerr/{r_id}/release", json={"reason": "done"})
        assert release_res.status_code == 200
        assert release_res.json()["state"] == "RELEASED"
    finally:
        db_session.close()


def test_seerr_imported_reserved_rejected():
    """RESERVED → OWNED must be rejected (no ACTIVE)."""
    db_session = TestingSessionLocal()
    try:
        admit = _admit_reservation(db_session, provider="seerr", request_id="reserved-block")
        r_id = admit.reservation_id

        imported_res = client.post(f"/api/seerr/{r_id}/imported", json={
            "provider": "seerr",
            "request_id": "reserved-block",
            "media_id": "media-1",
        })
        assert imported_res.status_code == 400
    finally:
        db_session.close()


# ── Imported: ownership verification ─────────────────────────────────────

def test_seerr_imported_provider_mismatch():
    db_session = TestingSessionLocal()
    try:
        admit = _admit_reservation(db_session, provider="seerr", request_id="prov-mismatch")
        r_id = admit.reservation_id
        _activate_reservation(db_session, r_id)

        res = client.post(f"/api/seerr/{r_id}/imported", json={
            "provider": "jellyseerr",
            "request_id": "prov-mismatch",
            "media_id": "media-1",
        })
        assert res.status_code == 400
    finally:
        db_session.close()


def test_seerr_imported_request_id_mismatch():
    db_session = TestingSessionLocal()
    try:
        admit = _admit_reservation(db_session, provider="seerr", request_id="req-mismatch", media_id="media-1")
        r_id = admit.reservation_id
        _activate_reservation(db_session, r_id)

        res = client.post(f"/api/seerr/{r_id}/imported", json={
            "provider": "seerr",
            "request_id": "wrong-request-id",
            "media_id": "media-1",
        })
        assert res.status_code == 400
    finally:
        db_session.close()


def test_seerr_imported_media_id_mismatch():
    db_session = TestingSessionLocal()
    try:
        admit = _admit_reservation(db_session, provider="seerr", request_id="media-mismatch", media_id="media-1")
        r_id = admit.reservation_id
        _activate_reservation(db_session, r_id)

        res = client.post(f"/api/seerr/{r_id}/imported", json={
            "provider": "seerr",
            "request_id": "media-mismatch",
            "media_id": "wrong-media",
        })
        assert res.status_code == 400
    finally:
        db_session.close()


def test_seerr_imported_torrent_hash_mismatch():
    db_session = TestingSessionLocal()
    try:
        admit = _admit_reservation(db_session, provider="seerr", request_id="hash-mismatch", media_id="media-1")
        r_id = admit.reservation_id
        _activate_reservation(db_session, r_id, torrent_hash="correcthashcorrecthashcorrecthashcorrecthashcorrect")

        res = client.post(f"/api/seerr/{r_id}/imported", json={
            "provider": "seerr",
            "request_id": "hash-mismatch",
            "media_id": "media-1",
            "torrent_hash": "wronghashwronghashwronghashwronghashwronghashwron",
        })
        assert res.status_code == 400
    finally:
        db_session.close()


def test_seerr_imported_missing_reservation():
    res = client.post("/api/seerr/nonexistent-id/imported", json={
        "provider": "seerr",
        "request_id": "missing",
        "media_id": "media-1",
    })
    assert res.status_code == 404


# ── Imported: idempotency ────────────────────────────────────────────────


def test_seerr_imported_duplicate_owned_idempotent():
    """Repeated import callback on OWNED reservation must stay OWNED and succeed."""
    db_session = TestingSessionLocal()
    try:
        admit = _admit_reservation(db_session, provider="seerr", request_id="idem-owned")
        r_id = admit.reservation_id
        _activate_reservation(db_session, r_id)

        res1 = client.post(f"/api/seerr/{r_id}/imported", json={
            "provider": "seerr",
            "request_id": "idem-owned",
            "media_id": "media-1",
        })
        assert res1.status_code == 200
        assert res1.json()["state"] == "OWNED"

        res2 = client.post(f"/api/seerr/{r_id}/imported", json={
            "provider": "seerr",
            "request_id": "idem-owned",
            "media_id": "media-1",
        })
        assert res2.status_code == 200
        assert res2.json()["state"] == "OWNED"
    finally:
        db_session.close()


def test_seerr_imported_callback_released():
    """Import callback on RELEASED reservation must be idempotent success."""
    db_session = TestingSessionLocal()
    try:
        admit = _admit_reservation(db_session, provider="seerr", request_id="released-cb")
        r_id = admit.reservation_id
        _activate_reservation(db_session, r_id)

        imported = client.post(f"/api/seerr/{r_id}/imported", json={
            "provider": "seerr",
            "request_id": "released-cb",
            "media_id": "media-1",
        })
        assert imported.status_code == 200
        assert imported.json()["state"] == "OWNED"

        client.post(f"/api/seerr/{r_id}/release", json={"reason": "done"})

        res = client.post(f"/api/seerr/{r_id}/imported", json={
            "provider": "seerr",
            "request_id": "released-cb",
            "media_id": "media-1",
        })
        assert res.status_code == 200
        assert res.json()["state"] == "RELEASED"
        assert res.json()["released"] is True
    finally:
        db_session.close()


# ── Release ──────────────────────────────────────────────────────────────

def test_seerr_release_owned():
    db_session = TestingSessionLocal()
    try:
        admit = _admit_reservation(db_session, provider="seerr", request_id="release-test")
        r_id = admit.reservation_id
        _activate_reservation(db_session, r_id)

        imported = client.post(f"/api/seerr/{r_id}/imported", json={
            "provider": "seerr",
            "request_id": "release-test",
            "media_id": "media-1",
        })
        assert imported.status_code == 200
        assert imported.json()["state"] == "OWNED"

        release = client.post(f"/api/seerr/{r_id}/release", json={"reason": "finished"})
        assert release.status_code == 200
        assert release.json()["state"] == "RELEASED"
    finally:
        db_session.close()


def test_seerr_release_repeated_idempotent():
    db_session = TestingSessionLocal()
    try:
        admit = _admit_reservation(db_session, provider="seerr", request_id="idem-release")
        r_id = admit.reservation_id
        _activate_reservation(db_session, r_id)

        client.post(f"/api/seerr/{r_id}/imported", json={
            "provider": "seerr",
            "request_id": "idem-release",
            "media_id": "media-1",
        })

        rel1 = client.post(f"/api/seerr/{r_id}/release", json={"reason": "done"})
        assert rel1.status_code == 200
        assert rel1.json()["state"] == "RELEASED"

        rel2 = client.post(f"/api/seerr/{r_id}/release", json={"reason": "done again"})
        assert rel2.status_code == 200
        assert rel2.json()["state"] == "RELEASED"
    finally:
        db_session.close()


def test_seerr_release_invalid_reservation():
    res = client.post("/api/seerr/nonexistent/release", json={"reason": "nope"})
    assert res.status_code == 404


def test_seerr_release_invalid_state():
    """Releasing a RESERVED reservation must be rejected."""
    db_session = TestingSessionLocal()
    try:
        admit = _admit_reservation(db_session, provider="seerr", request_id="bad-state-release")
        r_id = admit.reservation_id

        res = client.post(f"/api/seerr/{r_id}/release", json={"reason": "too early"})
        assert res.status_code == 400
    finally:
        db_session.close()


def test_seerr_release_optional_body():
    """Release with no request body must succeed (reason is optional)."""
    db_session = TestingSessionLocal()
    try:
        admit = _admit_reservation(db_session, provider="seerr", request_id="opt-body")
        r_id = admit.reservation_id
        _activate_reservation(db_session, r_id)

        client.post(f"/api/seerr/{r_id}/imported", json={
            "provider": "seerr",
            "request_id": "opt-body",
            "media_id": "media-1",
        })

        res = client.post(f"/api/seerr/{r_id}/release")
        assert res.status_code == 200
        assert res.json()["state"] == "RELEASED"
    finally:
        db_session.close()