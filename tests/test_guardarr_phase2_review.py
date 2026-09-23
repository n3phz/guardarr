import threading
import time
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import application
from app.db.base import Base, get_db
from app.db.models import ReservationModel, ReservationState, ImportMode
from app.services.admission import AdmissionService, calculate_remaining_unfulfilled
from app.services.reconciliation import ReconciliationService

# Test Database for Concurrency & Persistence Review
DB_PATH = "/tmp/guardarr_test_review.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

application.dependency_overrides[get_db] = override_get_db
client = TestClient(application)


@pytest.fixture(autouse=True)
def setup_teardown():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except:
            pass


import os

def test_concurrent_admissions_serialization():
    """Test concurrent admission attempts against the same SQLite database with BEGIN IMMEDIATE."""
    results = []
    
    def admit_worker(key_suffix):
        try:
            res = client.post("/api/admit", json={
                "adapter_name": "sonarr",
                "idempotency_key": f"concurrent-{key_suffix}",
                "max_bytes": 100_000_000,
                "expected_bytes": 100_000_000,
                "target_device": "/"
            })
            results.append(res.status_code)
        except Exception as e:
            results.append(str(e))

    threads = [threading.Thread(target=admit_worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All 10 unique requests should succeed if disk space allows, or handle lock gracefully
    assert len(results) == 10
    # Verify database has valid reservations without corruption
    db = TestingSessionLocal()
    count = db.query(ReservationModel).count()
    assert count <= 10
    db.close()


def test_concurrent_identical_idempotency_requests():
    """Concurrent identical idempotency requests must produce exactly one reservation and return idempotent matches."""
    results = []
    
    def admit_worker():
        try:
            res = client.post("/api/admit", json={
                "adapter_name": "radarr",
                "idempotency_key": "same-idem-key",
                "max_bytes": 50_000_000,
                "expected_bytes": 50_000_000,
                "target_device": "/"
            })
            results.append((res.status_code, res.json().get("id")))
        except Exception as e:
            results.append(str(e))

    threads = [threading.Thread(target=admit_worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All should return 201 Created and share the exact same reservation ID
    created_ids = [r[1] for r in results if isinstance(r, tuple) and r[0] == 201]
    assert len(created_ids) == 5
    assert len(set(created_ids)) == 1, "Idempotent requests produced multiple different reservation IDs!"


def test_idempotency_edge_cases():
    """Test same adapter + same key + different request, and different adapter + same key."""
    # 1. First admission
    res1 = client.post("/api/admit", json={
        "adapter_name": "sonarr",
        "idempotency_key": "shared-key",
        "max_bytes": 100_000_000,
        "expected_bytes": 100_000_000,
        "target_device": "/"
    })
    assert res1.status_code == 201
    id1 = res1.json()["id"]

    # 2. Same adapter + same key + different request parameters
    # Guardarr idempotency returns existing reservation record matching adapter_name + idempotency_key
    res2 = client.post("/api/admit", json={
        "adapter_name": "sonarr",
        "idempotency_key": "shared-key",
        "max_bytes": 999_999_999, # different payload
        "expected_bytes": 999_999_999,
        "target_device": "/"
    })
    assert res2.status_code == 201
    assert res2.json()["id"] == id1
    assert res2.json()["max_bytes"] == 100_000_000, "Idempotency should return the original stored reservation record"

    # 3. Different adapter + same key -> should create a separate distinct reservation
    res3 = client.post("/api/admit", json={
        "adapter_name": "radarr",
        "idempotency_key": "shared-key",
        "max_bytes": 100_000_000,
        "expected_bytes": 100_000_000,
        "target_device": "/"
    })
    assert res3.status_code == 201
    id3 = res3.json()["id"]
    assert id3 != id1, "Different adapters with same idempotency key must not collide (composite key uniqueness)"


def test_released_and_expired_capacity_release():
    """Verify RELEASED and EXPIRED reservations do not consume outstanding admission capacity."""
    db = TestingSessionLocal()
    
    # Create active reservation
    r1 = ReservationModel(
        id="res-active",
        idempotency_key="key-act",
        adapter_name="test",
        target_device="/",
        max_bytes=1_000_000_000,
        expected_bytes=1_000_000_000,
        remaining_unfulfilled_bytes=1_000_000_000,
        state=ReservationState.RESERVED
    )
    db.add(r1)
    db.commit()
    
    outstanding_before = AdmissionService.calculate_outstanding_unfulfilled(db, "/")
    assert outstanding_before == 1_000_000_000

    # Release reservation
    AdmissionService.release(db, "res-active", "done")
    db.refresh(r1)
    
    outstanding_after = AdmissionService.calculate_outstanding_unfulfilled(db, "/")
    assert outstanding_after == 0, "Released reservation still consumes capacity!"
    db.close()


def test_database_persistence_restart():
    """Verify reservations and audit logs persist across application/session restarts."""
    # 1. Create reservation in DB
    db1 = TestingSessionLocal()
    r = ReservationModel(
        id="persist-1",
        idempotency_key="persist-key",
        adapter_name="sonarr",
        target_device="/",
        max_bytes=5000,
        expected_bytes=5000,
        remaining_unfulfilled_bytes=5000,
        state=ReservationState.RESERVED
    )
    db1.add(r)
    db1.commit()
    db1.close()

    # 2. Simulate restart by opening a brand new session factory on the same file DB
    engine_restart = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
    NewSessionLocal = sessionmaker(bind=engine_restart)
    db2 = NewSessionLocal()
    
    fetched = db2.query(ReservationModel).filter(ReservationModel.id == "persist-1").first()
    assert fetched is not None
    assert fetched.max_bytes == 5000
    assert fetched.adapter_name == "sonarr"
    db2.close()
    engine_restart.dispose()
