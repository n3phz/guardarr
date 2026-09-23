import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import application
from app.db.base import Base, get_db
from app.db.models import ReservationModel, ReservationState, ImportMode
from app.services.controlled_admission import ControlledAdmissionService, extract_magnet_hash
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


def test_magnet_hash_extraction():
    magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=Ubuntu"
    assert extract_magnet_hash(magnet) == "1234567890abcdef1234567890abcdef12345678"
    assert extract_magnet_hash("http://example.com/file.torrent") is None


@patch("app.services.controlled_admission.QBittorrentClient.test_connectivity")
@patch("app.services.controlled_admission.QBittorrentClient.get_torrents")
@patch("app.services.controlled_admission.QBittorrentClient.add_torrent")
@patch("app.services.controlled_admission.QBittorrentClient.add_torrent_tags")
@patch("app.services.controlled_admission.QBittorrentClient.resume_torrents")
def test_idempotent_retry_same_magnet(mock_resume, mock_add_tags, mock_add_torrent, mock_get_torrents, mock_test_conn):
    mock_test_conn.return_value = {"status": "connected", "version": "v4.6.0"}
    mock_add_torrent.return_value = True
    mock_add_tags.return_value = True
    mock_resume.return_value = True

    h = "11223344556677889900aabbccddeeff11223344"
    magnet = f"magnet:?xt=urn:btih:{h}&dn=Test"

    # First call: no existing torrent, adds new
    # Second call: existing torrent with same tag found
    mock_get_torrents.side_effect = [
        [],
        [{"hash": h, "name": "Test", "completed": 0, "size": 1000}],
        [{"hash": h, "name": "Test", "completed": 0, "size": 1000}],
        [{"hash": h, "name": "Test", "completed": 0, "size": 1000}],
    ]

    db = TestingSessionLocal()
    r = ReservationModel(
        id="res-retry",
        idempotency_key="key-retry",
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

    # Retry 1
    res1 = client.post("/api/qbittorrent/reservations/res-retry/add", json={
        "url_or_magnet": magnet,
        "idempotency_key": "idem-key"
    })
    assert res1.status_code == 201

    # Retry 2 (same magnet, same reservation) -> reuses safely
    res2 = client.post("/api/qbittorrent/reservations/res-retry/add", json={
        "url_or_magnet": magnet,
        "idempotency_key": "idem-key"
    })
    assert res2.status_code == 201
    assert res2.json()["torrent_hash"] == h


@patch("app.services.controlled_admission.QBittorrentClient.test_connectivity")
@patch("app.services.controlled_admission.QBittorrentClient.get_torrents")
def test_idempotent_retry_different_magnet_conflict(mock_get_torrents, mock_test_conn):
    mock_test_conn.return_value = {"status": "connected", "version": "v4.6.0"}
    
    h1 = "11223344556677889900aabbccddeeff11223344"
    h2 = "99887766554433221100ffeeddccbbaa99887766"
    magnet2 = f"magnet:?xt=urn:btih:{h2}&dn=Different"

    # Existing torrent has hash h1
    mock_get_torrents.return_value = [{"hash": h1, "name": "Test", "completed": 0, "size": 1000}]

    db = TestingSessionLocal()
    r = ReservationModel(
        id="res-conflict",
        idempotency_key="key-conf",
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

    # Requesting different magnet for same reservation tag should fail
    res = client.post("/api/qbittorrent/reservations/res-conflict/add", json={
        "url_or_magnet": magnet2,
        "idempotency_key": "idem-key"
    })
    assert res.status_code == 400


@patch("app.services.controlled_admission.QBittorrentClient.test_connectivity")
@patch("app.services.controlled_admission.QBittorrentClient.get_torrents")
@patch("app.services.controlled_admission.QBittorrentClient.add_torrent")
@patch("app.services.controlled_admission.QBittorrentClient.add_torrent_tags")
@patch("app.services.controlled_admission.QBittorrentClient.resume_torrents")
def test_resume_failure_retains_active_state(mock_resume, mock_add_tags, mock_add_torrent, mock_get_torrents, mock_test_conn):
    mock_test_conn.return_value = {"status": "connected", "version": "v4.6.0"}
    mock_add_torrent.return_value = True
    mock_add_tags.return_value = True
    mock_resume.return_value = False # Resume call fails!

    h = "11223344556677889900aabbccddeeff11223344"
    magnet = f"magnet:?xt=urn:btih:{h}&dn=Test"

    mock_get_torrents.return_value = [
        [],
        [{"hash": h, "name": "Test", "completed": 0, "size": 1000}]
    ]

    db = TestingSessionLocal()
    r = ReservationModel(
        id="res-resume-fail",
        idempotency_key="key-rf",
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

    response = client.post("/api/qbittorrent/reservations/res-resume-fail/add", json={
        "url_or_magnet": magnet,
        "idempotency_key": "idem-rf"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == "ACTIVE" # Must remain ACTIVE, not rolled back
    assert data["qbittorrent_status"] == "success_associated_resume_failed"

    # Verify DB state is ACTIVE and hash is persisted
    db_verify = TestingSessionLocal()
    fetched = db_verify.query(ReservationModel).filter(ReservationModel.id == "res-resume-fail").first()
    assert fetched.state == ReservationState.ACTIVE
    assert fetched.torrent_metadata_hash == h
    db_verify.close()


@patch("app.services.controlled_admission.QBittorrentClient.test_connectivity")
@patch("app.services.controlled_admission.QBittorrentClient.get_torrents")
@patch("app.services.controlled_admission.QBittorrentClient.add_torrent")
@patch("app.services.controlled_admission.QBittorrentClient.add_torrent_tags")
def test_tag_failure_keeps_torrent_paused_and_inactive(mock_add_tags, mock_add_torrent, mock_get_torrents, mock_test_conn):
    mock_test_conn.return_value = {"status": "connected", "version": "v4.6.0"}
    mock_add_torrent.return_value = True
    mock_add_tags.return_value = False # Tagging fails!

    h = "11223344556677889900aabbccddeeff11223344"
    magnet = f"magnet:?xt=urn:btih:{h}&dn=Test"

    mock_get_torrents.return_value = [
        [],
        [{"hash": h, "name": "Test", "completed": 0, "size": 1000}]
    ]

    db = TestingSessionLocal()
    r = ReservationModel(
        id="res-tag-fail",
        idempotency_key="key-tf",
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

    response = client.post("/api/qbittorrent/reservations/res-tag-fail/add", json={
        "url_or_magnet": magnet,
        "idempotency_key": "idem-tf"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == "RESERVED" # Must NOT be ACTIVE
    assert data["association_status"] == "tag_application_failed_pending"

    # Verify DB state is still RESERVED
    db_verify = TestingSessionLocal()
    fetched = db_verify.query(ReservationModel).filter(ReservationModel.id == "res-tag-fail").first()
    assert fetched.state == ReservationState.RESERVED
    assert fetched.torrent_metadata_hash is None
    db_verify.close()


def test_path_validation_storage_containment():
    db = TestingSessionLocal()
    r = ReservationModel(
        id="res-path",
        idempotency_key="key-path",
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

    # Attempting to save to /etc (outside container storage boundaries)
    res = client.post("/api/qbittorrent/reservations/res-path/add", json={
        "url_or_magnet": "magnet:?xt=urn:btih:11223344556677889900aabbccddeeff&dn=Test",
        "savepath": "/etc/malicious",
        "idempotency_key": "idem-path"
    })
    assert res.status_code == 422
