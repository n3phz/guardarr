import os
import pytest
from fastapi.testclient import TestClient
from app.main import application
from app.core.config import get_settings
from app.core.filesystem import get_filesystem_stats, get_filesystem_status, check_filesystem_health
from app.core.thresholds import classify_storage, ThresholdState
from app.services.filesystem import FilesystemMonitor

client = TestClient(application)


def test_python_version():
    import sys
    assert sys.version_info >= (3, 13)


def test_settings_defaults():
    settings = get_settings()
    assert settings.guardarr_data_dir == Path("/config") if 'Path' in globals() else str(settings.guardarr_data_dir) == "/config"
    assert settings.guardarr_storage_path.name == "data" or str(settings.guardarr_storage_path) == "/data"
    assert settings.warning_threshold_bytes == 1_000_000_000_000
    assert settings.admission_floor_bytes == 750_000_000_000
    assert settings.emergency_threshold_bytes == 500_000_000_000
    assert settings.critical_threshold_bytes == 250_000_000_000
    assert settings.database_url == "sqlite:////config/guardarr.db" or "guardarr.db" in settings.database_url


def test_threshold_classification():
    settings = get_settings()
    t = settings.thresholds
    
    # NORMAL
    res = classify_storage(2_000_000_000_000, t)
    assert res.state == ThresholdState.NORMAL
    assert not res.admission_blocked

    # WARNING
    res = classify_storage(900_000_000_000, t)
    assert res.state == ThresholdState.WARNING
    assert not res.admission_blocked

    # BLOCKED
    res = classify_storage(600_000_000_000, t)
    assert res.state == ThresholdState.BLOCKED
    assert res.admission_blocked

    # EMERGENCY
    res = classify_storage(400_000_000_000, t)
    assert res.state == ThresholdState.EMERGENCY
    assert res.admission_blocked

    # CRITICAL
    res = classify_storage(100_000_000_000, t)
    assert res.state == ThresholdState.CRITICAL
    assert res.admission_blocked


def test_filesystem_monitor():
    monitor = FilesystemMonitor()
    # Test size conversion helper
    assert monitor.to_bytes("1GB") == 1024**3
    assert monitor.to_bytes("500MB") == 500 * 1024**2
    assert monitor.to_bytes(1024) == 1024


def test_api_endpoints():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "guardarr"

    response = client.get("/api/ready")
    # ready might be 200 or 503 depending on whether /data exists in test container, but should return json
    assert response.status_code in (200, 503)

    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "total_bytes" in data
    assert "available_bytes" in data
    assert "current_threshold_state" in data
    assert "inode_total" in data
    assert "device_identity" in data
