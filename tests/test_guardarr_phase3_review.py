import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import application
from app.db.base import Base, get_db
from app.db.models import ReservationModel, ReservationState, ImportMode
from app.services.qbittorrent import QBittorrentClient
from app.services.qbittorrent_reconciliation import QBittorrentReconciliationService

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


@patch("app.services.qbittorrent.QBittorrentClient.get_torrent_by_hash")
@patch("app.services.qbittorrent.QBittorrentClient.add_torrent_tags")
def test_association_safety_checks(mock_add_tags, mock_get_torrent):
    db = TestingSessionLocal()
    r1 = ReservationModel(
        id="res-1",
        idempotency_key="k1",
        adapter_name="sonarr",
        target_device="/",
        max_bytes=1000,
        expected_bytes=1000,
        remaining_unfulfilled_bytes=1000,
        state=ReservationState.RESERVED
    )
    r2 = ReservationModel(
        id="res-2",
        idempotency_key="k2",
        adapter_name="radarr",
        target_device="/",
        max_bytes=1000,
        expected_bytes=1000,
        remaining_unfulfilled_bytes=1000,
        state=ReservationState.RESERVED
    )
    db.add_all([r1, r2])
    db.commit()
    db.close()

    mock_get_torrent.return_value = {
        "hash": "aabbccddeeff0011",
        "name": "Torrent 1",
        "completed": 100,
        "size": 1000
    }
    mock_add_tags.return_value = True

    # 1. Successful association for res-1
    res = client.post("/api/qbittorrent/reservations/res-1/associate", json={
        "torrent_hash": "AABBCCDDEEFF0011" # uppercase to test case normalization
    })
    assert res.status_code == 200
    assert res.json()["torrent_metadata_hash"] == "aabbccddeeff0011"

    # 2. Attempting to associate res-1 with a DIFFERENT torrent should fail (already associated)
    mock_get_torrent.return_value = {
        "hash": "1122334455667788",
        "name": "Torrent 2",
        "completed": 0,
        "size": 1000
    }
    res_diff = client.post("/api/qbittorrent/reservations/res-1/associate", json={
        "torrent_hash": "1122334455667788"
    })
    assert res_diff.status_code == 400

    # 3. Attempting to associate res-2 with the ALREADY CLAIMED torrent hash should fail (conflict/claimed)
    mock_get_torrent.return_value = {
        "hash": "aabbccddeeff0011",
        "name": "Torrent 1",
        "completed": 100,
        "size": 1000
    }
    res_claim = client.post("/api/qbittorrent/reservations/res-2/associate", json={
        "torrent_hash": "aabbccddeeff0011"
    })
    assert res_claim.status_code == 400


@patch("app.services.qbittorrent.QBittorrentClient.get_torrents")
@patch("app.services.qbittorrent.QBittorrentClient.test_connectivity")
def test_missing_torrent_preserves_reservation(mock_test_conn, mock_get_torrents):
    mock_test_conn.return_value = {"status": "connected", "version": "v4.6.0"}
    
    db = TestingSessionLocal()
    r = ReservationModel(
        id="res-missing",
        idempotency_key="km",
        adapter_name="sonarr",
        target_device="/",
        max_bytes=1000,
        expected_bytes=1000,
        remaining_unfulfilled_bytes=1000,
        torrent_metadata_hash="missinghash123",
        state=ReservationState.ACTIVE
    )
    db.add(r)
    db.commit()
    db.close()

    # qBittorrent returns NO torrents (missing torrent)
    mock_get_torrents.return_value = []

    res = client.post("/api/qbittorrent/reconcile")
    assert res.status_code == 200

    # Verify reservation did NOT become RELEASED or EXPIRED; remains ACTIVE
    db_verify = TestingSessionLocal()
    fetched = db_verify.query(ReservationModel).filter(ReservationModel.id == "res-missing").first()
    assert fetched.state == ReservationState.ACTIVE
    db_verify.close()


@patch("app.services.qbittorrent.QBittorrentClient.get_torrents")
@patch("app.services.qbittorrent.QBittorrentClient.test_connectivity")
def test_reconciliation_idempotency(mock_test_conn, mock_get_torrents):
    mock_test_conn.return_value = {"status": "connected", "version": "v4.6.0"}
    mock_get_torrents.return_value = []

    # Run reconciliation twice consecutively
    res1 = client.post("/api/qbittorrent/reconcile")
    assert res1.status_code == 200

    res2 = client.post("/api/qbittorrent/reconcile")
    assert res2.status_code == 200
    assert res2.json()["status"] == "success"
