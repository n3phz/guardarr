import time
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import application
from app.db.base import Base, get_db
from app.db.models import ReservationModel, ReservationState, ImportMode
from app.services.admission import AdmissionService, calculate_remaining_unfulfilled
from app.services.reconciliation import ReconciliationService

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


def test_calculate_remaining_unfulfilled():
    assert calculate_remaining_unfulfilled(1000, 200, ImportMode.COPY) == 800
    assert calculate_remaining_unfulfilled(1000, 1000, ImportMode.HARDLINK) == 0
    assert calculate_remaining_unfulfilled(1000, 1200, ImportMode.UNKNOWN) == 0


def test_successful_admission():
    response = client.post("/api/admit", json={
        "adapter_name": "sonarr",
        "idempotency_key": "key-1",
        "max_bytes": 10_000_000_000,
        "expected_bytes": 8_000_000_000,
        "import_mode": "copy",
        "target_device": "/"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["adapter_name"] == "sonarr"
    assert data["state"] == "RESERVED"
    assert data["remaining_unfulfilled_bytes"] == 10_000_000_000


def test_admission_below_floor():
    # admission floor in default settings is 750GB, root filesystem might have less or more depending on container,
    # but we can test with a massive reservation exceeding disk space or floor.
    response = client.post("/api/admit", json={
        "adapter_name": "sonarr",
        "idempotency_key": "key-floor",
        "max_bytes": 999_999_999_999_999_000,
        "expected_bytes": 999_999_999_999_999_000,
        "target_device": "/"
    })
    assert response.status_code == 409


def test_idempotent_admission():
    payload = {
        "adapter_name": "radarr",
        "idempotency_key": "idem-123",
        "max_bytes": 5_000_000_000,
        "expected_bytes": 4_000_000_000,
        "target_device": "/"
    }
    res1 = client.post("/api/admit", json=payload)
    assert res1.status_code == 201
    id1 = res1.json()["id"]

    res2 = client.post("/api/admit", json=payload)
    assert res2.status_code == 201
    id2 = res2.json()["id"]

    assert id1 == id2


def test_zero_or_negative_bytes():
    response = client.post("/api/admit", json={
        "adapter_name": "sonarr",
        "idempotency_key": "key-zero",
        "max_bytes": 0,
        "expected_bytes": 100,
        "target_device": "/"
    })
    assert response.status_code == 422


def test_release_reservation():
    res = client.post("/api/admit", json={
        "adapter_name": "sonarr",
        "idempotency_key": "key-rel",
        "max_bytes": 1_000_000_000,
        "expected_bytes": 1_000_000_000,
        "target_device": "/"
    })
    assert res.status_code == 201
    r_id = res.json()["id"]

    rel_res = client.post(f"/api/reservations/{r_id}/release", json={"reason": "Manual cleanup"})
    assert rel_res.status_code == 200
    assert rel_res.json()["state"] == "RELEASED"
    assert rel_res.json()["remaining_unfulfilled_bytes"] == 0


def test_reconciliation_expiration():
    db = TestingSessionLocal()
    # Insert expired reservation
    expired_res = ReservationModel(
        id="expired-1",
        idempotency_key="exp-key",
        adapter_name="test",
        target_device="/",
        max_bytes=1000,
        expected_bytes=1000,
        remaining_unfulfilled_bytes=1000,
        state=ReservationState.RESERVED,
        expires_at=datetime.utcnow() - timedelta(hours=1)
    )
    db.add(expired_res)
    db.commit()
    db.close()

    res = client.post("/api/reconcile")
    assert res.status_code == 200
    data = res.json()
    assert data["expired_count"] == 1

    # Check state via GET
    get_res = client.get("/api/reservations/expired-1")
    assert get_res.status_code == 200
    assert get_res.json()["state"] == "EXPIRED"
    assert get_res.json()["remaining_unfulfilled_bytes"] == 0


def test_estimate_endpoint():
    res = client.post("/api/estimate", json={
        "max_bytes": 2_000_000_000,
        "expected_bytes": 1_000_000_000,
        "import_mode": "copy",
        "target_device": "/"
    })
    assert res.status_code == 200
    data = res.json()
    assert "available_bytes" in data
    assert "projected_available_bytes" in data
    assert "admissible" in data
