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
from app.services.controlled_admission import ControlledAdmissionService
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


@patch("app.services.controlled_admission.QBittorrentClient.test_connectivity")
@patch("app.services.controlled_admission.QBittorrentClient.get_torrents")
@patch("app.services.controlled_admission.QBittorrentClient.add_torrent")
@patch("app.services.controlled_admission.QBittorrentClient.add_torrent_tags")
@patch("app.services.controlled_admission.QBittorrentClient.resume_torrents")
def test_successful_controlled_add(mock_resume, mock_add_tags, mock_add_torrent, mock_get_torrents, mock_test_conn):
    mock_test_conn.return_value = {"status": "connected", "version": "v4.6.0"}
    mock_add_torrent.return_value = True
    mock_add_tags.return_value = True
    mock_resume.return_value = True

    # First call to get_torrents returns empty (to add torrent), second call returns torrent with hash
    mock_get_torrents.side_effect = [
        [], # check existing by tag
        [{"hash": "11223344556677889900aabbccddeeff", "name": "Test", "completed": 0, "size": 1000}]
    ]

    db = TestingSessionLocal()
    r = ReservationModel(
        id="res-controlled-1",
        idempotency_key="key-c1",
        adapter_name="sonarr",
        target_device="/",
        max_bytes=2_000_000_000,
        expected_bytes=1_000_000_000,
        remaining_unfulfilled_bytes=2_000_000_000,
        state=ReservationState.RESERVED
    )
    db.add(r)
    db.commit()
    db.close()

    response = client.post("/api/qbittorrent/reservations/res-controlled-1/add", json={
        "url_or_magnet": "magnet:?xt=urn:btih:11223344556677889900aabbccddeeff&dn=Test",
        "idempotency_key": "idem-key-1"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == "ACTIVE"
    assert data["torrent_hash"] == "11223344556677889900aabbccddeeff"
    assert data["association_status"] == "associated"


@patch("app.services.controlled_admission.QBittorrentClient.test_connectivity")
def test_controlled_add_expired_reservation(mock_test_conn):
    mock_test_conn.return_value = {"status": "connected", "version": "v4.6.0"}
    from datetime import datetime, timedelta

    db = TestingSessionLocal()
    r = ReservationModel(
        id="res-expired",
        idempotency_key="key-exp",
        adapter_name="sonarr",
        target_device="/",
        max_bytes=1000,
        expected_bytes=1000,
        remaining_unfulfilled_bytes=1000,
        state=ReservationState.RESERVED,
        expires_at=datetime.utcnow() - timedelta(hours=1)
    )
    db.add(r)
    db.commit()
    db.close()

    response = client.post("/api/qbittorrent/reservations/res-expired/add", json={
        "url_or_magnet": "magnet:?xt=urn:btih:11223344556677889900aabbccddeeff",
        "idempotency_key": "idem-key-exp"
    })
    assert response.status_code == 400


def test_controlled_add_invalid_url_or_path():
    db = TestingSessionLocal()
    r = ReservationModel(
        id="res-val",
        idempotency_key="key-val",
        adapter_name="sonarr",
        target_device="/",
        max_bytes=1000,
        expected_bytes=1000,
        remaining_unfulfilled_bytes=1000,
        state=ReservationState.RESERVED
    )
    db.add(r)
    db.commit()
    db.close()

    # Invalid URL scheme
    res1 = client.post("/api/qbittorrent/reservations/res-val/add", json={
        "url_or_magnet": "ftp://malicious.com/file.torrent",
        "idempotency_key": "idem-val-1"
    })
    assert res1.status_code == 422

    # Path traversal in savepath
    res2 = client.post("/api/qbittorrent/reservations/res-val/add", json={
        "url_or_magnet": "magnet:?xt=urn:btih:11223344556677889900aabbccddeeff",
        "savepath": "/data/../etc/passwd",
        "idempotency_key": "idem-val-2"
    })
    assert res2.status_code == 422


@patch("app.services.controlled_admission.QBittorrentClient.test_connectivity")
@patch("app.services.controlled_admission.QBittorrentClient.get_torrents")
@patch("app.services.controlled_admission.QBittorrentClient.add_torrent")
def test_controlled_add_hash_pending(mock_add_torrent, mock_get_torrents, mock_test_conn):
    mock_test_conn.return_value = {"status": "connected", "version": "v4.6.0"}
    mock_add_torrent.return_value = True
    # get_torrents returns empty list even after add (hash acquisition pending)
    mock_get_torrents.return_value = []

    db = TestingSessionLocal()
    r = ReservationModel(
        id="res-pending",
        idempotency_key="key-pend",
        adapter_name="sonarr",
        target_device="/",
        max_bytes=1000,
        expected_bytes=1000,
        remaining_unfulfilled_bytes=1000,
        state=ReservationState.RESERVED
    )
    db.add(r)
    db.commit()
    db.close()

    response = client.post("/api/qbittorrent/reservations/res-pending/add", json={
        "url_or_magnet": "magnet:?xt=urn:btih:11223344556677889900aabbccddeeff",
        "idempotency_key": "idem-pend"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["association_status"] == "association_pending"
    assert data["torrent_hash"] is None


@patch("app.services.qbittorrent_reconciliation.QBittorrentClient.test_connectivity")
@patch("app.services.qbittorrent_reconciliation.QBittorrentClient.get_torrents")
def test_reconciliation_association_recovery(mock_get_torrents, mock_test_conn):
    mock_test_conn.return_value = {"status": "connected", "version": "v4.6.0"}
    
    db = TestingSessionLocal()
    r = ReservationModel(
        id="res-recov",
        idempotency_key="key-recov",
        adapter_name="sonarr",
        target_device="/",
        max_bytes=1000,
        expected_bytes=1000,
        remaining_unfulfilled_bytes=1000,
        torrent_tag="guardarr:res-recov",
        state=ReservationState.RESERVED
    )
    db.add(r)
    db.commit()
    db.close()

    # qBittorrent returns torrent matching the tag but hash wasn't associated yet
    mock_get_torrents.return_value = [
        {
            "hash": "aabbccddeeff00112233445566778899",
            "name": "Recovered Torrent",
            "completed": 100,
            "size": 1000,
            "tags": "guardarr:res-recov"
        }
    ]

    res = client.post("/api/qbittorrent/reconcile")
    assert res.status_code == 200
    data = res.json()
    assert data["recovered_reservations_count"] == 1

    # Verify reservation is now ACTIVE and associated
    db_verify = TestingSessionLocal()
    fetched = db_verify.query(ReservationModel).filter(ReservationModel.id == "res-recov").first()
    assert fetched.state == ReservationState.ACTIVE
    assert fetched.torrent_metadata_hash == "aabbccddeeff00112233445566778899"
    db_verify.close()
