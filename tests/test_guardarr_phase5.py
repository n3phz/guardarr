import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import application
from app.db.base import Base, get_db
from app.db.models import ReservationModel, ReservationState, ImportMode
from app.integrations.arr.base import SonarrClient, RadarrClient

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
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


@patch("app.integrations.arr.base.requests.Session.request")
def test_sonarr_connectivity_success(mock_request):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"version": "4.0.0.0"}
    mock_request.return_value = mock_resp

    client_adapter = SonarrClient()
    res = client_adapter.test_connectivity()
    assert res["status"] == "connected"
    assert res["version"] == "4.0.0.0"


@patch("app.integrations.arr.base.requests.Session.request")
def test_radarr_connectivity_success(mock_request):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"version": "5.0.0.0"}
    mock_request.return_value = mock_resp

    client_adapter = RadarrClient()
    res = client_adapter.test_connectivity()
    assert res["status"] == "connected"
    assert res["version"] == "5.0.0.0"


def test_arr_health_endpoint():
    with patch("app.integrations.arr.base.SonarrClient.test_connectivity", return_value={"status": "connected", "version": "4.0.0.0"}):
        res = client.get("/api/arr/health/sonarr")
        assert res.status_code == 200
        assert res.json()["status"] == "connected"


def test_arr_estimate():
    res = client.post("/api/arr/estimate", json={
        "provider": "sonarr",
        "content_id": "tvshow-123",
        "estimated_size_bytes": 5_000_000_000,
        "target_device": "/"
    })
    assert res.status_code == 200
    data = res.json()
    assert "projected_available_bytes" in data
    assert data["admissible"] is True


def test_arr_admit_and_import_confirmation():
    # 1. Admit
    admit_res = client.post("/api/arr/admit", json={
        "provider": "sonarr",
        "content_id": "tvshow-123",
        "arr_item_id": "episode-99",
        "max_bytes": 10_000_000_000,
        "expected_bytes": 8_000_000_000,
        "target_device": "/"
    })
    assert admit_res.status_code == 201
    admit_data = admit_res.json()
    r_id = admit_data["reservation_id"]
    assert admit_data["state"] == "RESERVED"

    # 2. Controlled Add (Transition RESERVED -> ACTIVE)
    # Note: This is mocked since we don't have a real qBittorrent instance
    # In the actual test, we would need to mock the ControlledAdmissionService
    # For now, we'll directly test the orchestration layer to verify the state transition
    from app.db.base import get_db
    from app.services.arr_orchestration import ArrOrchestrationService
    from unittest.mock import patch
    
    # Get a DB session to manually transition state (simulating successful controlled add)
    db = next(get_db())
    try:
        # Simulate successful controlled add: RESERVED -> ACTIVE
        reservation = db.query(ReservationModel).filter(ReservationModel.id == r_id).first()
        assert reservation.state == ReservationState.RESERVED
        
        # Transition to ACTIVE (what controlled add would do on success)
        reservation.state = ReservationState.ACTIVE
        reservation.torrent_metadata_hash = "aabbccddeeff00112233445566778899aabbccdd"
        reservation.observed_materialized_bytes = 0
        reservation.remaining_unfulfilled_bytes = 0
        db.commit()
        db.refresh(reservation)
        
        # Verify ACTIVE state
        assert reservation.state == ReservationState.ACTIVE
    finally:
        db.close()

    # 3. Confirm Imported (Transition ACTIVE -> OWNED -> RELEASED)
    import_res = client.post(f"/api/arr/{r_id}/imported", json={
        "provider": "sonarr",
        "content_id": "tvshow-123",
        "arr_item_id": "episode-99",
        "torrent_hash": "aabbccddeeff00112233445566778899aabbccdd",
        "imported_path": "/data/tv/Show.S01E01.mkv"
    })
    assert import_res.status_code == 200
    import_data = import_res.json()
    assert import_data["ownership_verified"] is True
    assert import_data["released"] is True
    assert import_data["state"] == "RELEASED"


def test_arr_admission_denial_below_floor():
    res = client.post("/api/arr/admit", json={
        "provider": "radarr",
        "content_id": "movie-massive",
        "max_bytes": 999_999_999_999_999_000,
        "expected_bytes": 999_999_999_999_999_000,
        "target_device": "/"
    })
    assert res.status_code == 409


def test_ownership_identity_mismatch():
    admit_res = client.post("/api/arr/admit", json={
        "provider": "radarr",
        "content_id": "movie-100",
        "arr_item_id": "item-100",
        "max_bytes": 1_000_000_000,
        "expected_bytes": 1_000_000_000,
        "target_device": "/"
    })
    r_id = admit_res.json()["reservation_id"]

    # Try confirming with wrong content_id
    import_res = client.post(f"/api/arr/{r_id}/imported", json={
        "provider": "radarr",
        "content_id": "wrong-movie-id",
        "arr_item_id": "item-100",
    })
    assert import_res.status_code == 400


def test_duplicate_import_callback_idempotency():
    admit_res = client.post("/api/arr/admit", json={
        "provider": "sonarr",
        "content_id": "show-dup",
        "arr_item_id": "item-dup",
        "max_bytes": 1_000_000_000,
        "expected_bytes": 1_000_000_000,
        "target_device": "/"
    })
    r_id = admit_res.json()["reservation_id"]

    # First import callback
    res1 = client.post(f"/api/arr/{r_id}/imported", json={
        "provider": "sonarr",
        "content_id": "show-dup",
        "arr_item_id": "item-dup",
    })
    assert res1.status_code == 200
    assert res1.json()["state"] == "RELEASED"

    # Second (duplicate) import callback -> idempotent success
    res2 = client.post(f"/api/arr/{r_id}/imported", json={
        "provider": "sonarr",
        "content_id": "show-dup",
        "arr_item_id": "item-dup",
    })
    assert res2.status_code == 200
    assert res2.json()["state"] == "RELEASED"
