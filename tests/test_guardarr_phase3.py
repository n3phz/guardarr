import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import application
from app.db.base import Base, get_db
from app.db.models import ReservationModel, ReservationState, ImportMode
from app.services.qbittorrent import QBittorrentClient
from app.services.qbittorrent_reconciliation import QBittorrentReconciliationService

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


@patch("app.services.qbittorrent.requests.Session.post")
def test_qbittorrent_client_authentication(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "Ok."
    mock_post.return_value = mock_response

    qb = QBittorrentClient()
    success = qb.login()
    assert success is True


@patch("app.services.qbittorrent.requests.Session.post")
def test_qbittorrent_client_auth_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = "Unauthorized."
    mock_post.return_value = mock_response

    qb = QBittorrentClient()
    success = qb.login()
    assert success is False


@patch("app.services.qbittorrent.QBittorrentClient.test_connectivity")
def test_qbittorrent_status_endpoint(mock_test_conn):
    mock_test_conn.return_value = {"status": "connected", "version": "v4.6.0"}
    res = client.get("/api/qbittorrent/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "connected"
    assert data["version"] == "v4.6.0"


@patch("app.services.qbittorrent.QBittorrentClient.get_torrent_by_hash")
@patch("app.services.qbittorrent.QBittorrentClient.add_torrent_tags")
def test_torrent_association(mock_add_tags, mock_get_torrent):
    db = TestingSessionLocal()
    res_model = ReservationModel(
        id="test-res-id-123",
        idempotency_key="key-assoc",
        adapter_name="sonarr",
        target_device="/",
        max_bytes=1000,
        expected_bytes=1000,
        remaining_unfulfilled_bytes=1000,
        state=ReservationState.RESERVED
    )
    db.add(res_model)
    db.commit()
    db.close()

    mock_get_torrent.return_value = {
        "hash": "abcdef1234567890",
        "name": "Test Torrent",
        "completed": 200,
        "size": 1000
    }
    mock_add_tags.return_value = True

    response = client.post("/api/qbittorrent/reservations/test-res-id-123/associate", json={
        "torrent_hash": "abcdef1234567890"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["state"] == "ACTIVE"
    assert data["observed_materialized_bytes"] == 200
    assert data["remaining_unfulfilled_bytes"] == 800


@patch("app.services.qbittorrent.QBittorrentClient.get_torrents")
@patch("app.services.qbittorrent.QBittorrentClient.test_connectivity")
def test_reconciliation_and_unreserved_detection(mock_test_conn, mock_get_torrents):
    mock_test_conn.return_value = {"status": "connected", "version": "v4.6.0"}
    
    db = TestingSessionLocal()
    # 1. Associated active reservation
    r = ReservationModel(
        id="res-1",
        idempotency_key="k1",
        adapter_name="sonarr",
        target_device="/",
        max_bytes=1000,
        expected_bytes=1000,
        remaining_unfulfilled_bytes=1000,
        torrent_metadata_hash="hash1",
        torrent_tag="guardarr:res-1",
        state=ReservationState.ACTIVE
    )
    db.add(r)
    db.commit()
    db.close()

    # qBittorrent returns associated torrent (500 bytes completed) and an unreserved torrent with guardarr tag
    mock_get_torrents.return_value = [
        {
            "hash": "hash1",
            "name": "Associated Torrent",
            "completed": 500,
            "size": 1000,
            "tags": "guardarr:res-1",
            "progress": 0.5,
            "state": "downloading",
            "save_path": "/data"
        },
        {
            "hash": "hash_rogue",
            "name": "Unreserved Torrent",
            "completed": 100,
            "size": 200,
            "tags": "guardarr:rogue-tag",
            "progress": 0.5,
            "state": "downloading",
            "save_path": "/data"
        }
    ]

    res = client.post("/api/qbittorrent/reconcile")
    assert res.status_code == 200
    data = res.json()
    assert data["reconciled_reservations_count"] == 1
    assert data["unreserved_torrents_count"] == 1
    assert data["unreserved_torrents"][0]["hash"] == "hash_rogue"


@patch("app.services.qbittorrent.QBittorrentClient.test_connectivity")
@patch("app.services.qbittorrent.QBittorrentClient.get_torrents")
def test_qbittorrent_unavailable_during_reconciliation(mock_get_torrents, mock_test_conn):
    mock_test_conn.return_value = {"status": "disconnected", "reason": "timeout"}
    mock_get_torrents.return_value = []

    res = client.post("/api/qbittorrent/reconcile")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "warning_qbittorrent_unavailable"
    assert data["reconciled_reservations_count"] == 0
