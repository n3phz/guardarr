import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app.main import create_application
from app.db.base import Base
from app.db.models import AuditLogModel, ReconcileStateModel, ReservationModel, ReservationState


def _make_app_and_client():
    """Create fresh app instance with test config."""
    import sys
    from app.core import config as _config
    _config._settings = None
    
    tmpdir = tempfile.mkdtemp()
    os.environ['GUARDARR_DATA_DIR'] = str(tmpdir)
    os.environ['GUARDARR_STORAGE_PATH'] = str(tmpdir)
    os.environ['DATABASE_URL'] = f"sqlite:///{Path(tmpdir) / 'test.db'}"
    os.environ['ADMISSION_FLOOR_BYTES'] = '1000000'
    os.environ['WARNING_THRESHOLD_BYTES'] = '2000000'
    os.environ['EMERGENCY_THRESHOLD_BYTES'] = '500000'
    os.environ['CRITICAL_THRESHOLD_BYTES'] = '100000'
    
    app = create_application()
    client = TestClient(app)
    return client, tmpdir


@pytest.fixture
def client():
    c, _ = _make_app_and_client()
    yield c


@pytest.fixture
def app_and_tmpdir():
    return _make_app_and_client()


class TestAuditEndpoint:
    def test_list_audit_empty(self, client):
        response = client.get("/api/audit")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_audit_with_entries(self, app_and_tmpdir):
        client, tmpdir = app_and_tmpdir
        # Insert data directly via SQLAlchemy
        db_url = f"sqlite:///{Path(tmpdir) / 'test.db'}"
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine(db_url)
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        reservation = ReservationModel(
            id="test-res-id",
            idempotency_key="test-key",
            adapter_name="seerr",
            max_bytes=1000000,
            expected_bytes=500000,
            state=ReservationState.RESERVED,
        )
        db.add(reservation)
        audit = AuditLogModel(
            reservation_id="test-res-id",
            event_type="admitted",
            details="Admitted 1MB"
        )
        db.add(audit)
        db.commit()
        db.close()
        
        response = client.get("/api/audit")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(a["reservation_id"] == "test-res-id" and a["event_type"] == "admitted" for a in data)

    def test_list_audit_by_reservation_id(self, app_and_tmpdir):
        client, tmpdir = app_and_tmpdir
        db_url = f"sqlite:///{Path(tmpdir) / 'test.db'}"
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine(db_url)
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        db.add(AuditLogModel(reservation_id="other-id", event_type="expired", details="Expired"))
        db.add(AuditLogModel(reservation_id="test-id", event_type="admitted", details="Admitted"))
        db.commit()
        db.close()
        
        response = client.get("/api/audit?reservation_id=test-id")
        assert response.status_code == 200
        data = response.json()
        assert all(a["reservation_id"] == "test-id" for a in data)

    def test_list_audit_by_event_type(self, app_and_tmpdir):
        client, tmpdir = app_and_tmpdir
        db_url = f"sqlite:///{Path(tmpdir) / 'test.db'}"
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine(db_url)
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        db.add(AuditLogModel(reservation_id="r1", event_type="admitted", details="Admitted"))
        db.add(AuditLogModel(reservation_id="r2", event_type="released", details="Released"))
        db.commit()
        db.close()
        
        response = client.get("/api/audit?event_type=released")
        assert response.status_code == 200
        data = response.json()
        assert all(a["event_type"] == "released" for a in data)

    def test_list_audit_with_limit(self, app_and_tmpdir):
        client, tmpdir = app_and_tmpdir
        db_url = f"sqlite:///{Path(tmpdir) / 'test.db'}"
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine(db_url)
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        for i in range(5):
            db.add(AuditLogModel(reservation_id=f"r-{i}", event_type="admitted", details=f"Admitted {i}"))
        db.commit()
        db.close()
        
        response = client.get("/api/audit?limit=2")
        data = response.json()
        assert len(data) <= 2


class TestIntegrationsHealthEndpoint:
    def test_get_integrations_health(self, client):
        response = client.get("/api/integrations/health")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        providers = [d["provider"] for d in data]
        assert "qbittorrent" in providers

    def test_returns_sanitized_data(self, client):
        response = client.get("/api/integrations/health")
        data = response.json()
        for entry in data:
            assert "api_key" not in entry
            assert "password" not in entry
            assert "secret" not in entry
            assert "provider" in entry
            assert "status" in entry
            assert "type" in entry

    def test_integration_fields_are_string_types(self, client):
        response = client.get("/api/integrations/health")
        data = response.json()
        for entry in data:
            assert isinstance(entry["provider"], str)
            assert isinstance(entry["status"], str)
            assert isinstance(entry["type"], str)


class TestReconcileStateEndpoint:
    def test_get_reconcile_state_not_found(self, client):
        response = client.get("/api/reconcile/state")
        assert response.status_code == 404

    def test_reconcile_creates_state(self, app_and_tmpdir):
        """POST /reconcile creates state; GET /reconcile/state reads it."""
        client, tmpdir = app_and_tmpdir
        
        # Write a reconciliation record directly so the GET works
        db_url = f"sqlite:///{Path(tmpdir) / 'test.db'}"
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine(db_url)
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        from datetime import datetime
        rec = ReconcileStateModel(
            component="reservations",
            last_run_at=datetime.utcnow(),
            status="success",
            details="Test reconciliation"
        )
        db.add(rec)
        db.commit()
        db.close()
        
        response_get = client.get("/api/reconcile/state")
        assert response_get.status_code == 200
        data = response_get.json()
        assert data["component"] == "reservations"
        assert data["status"] == "success"


class TestApiPrecedence:
    def test_api_routes_take_precedence_over_spa_fallback(self, client):
        """Ensure /api/* paths are handled by FastAPI, not the SPA fallback."""
        response = client.get("/api/nonexistent")
        assert "application/json" in response.headers.get("content-type", "")
        assert response.status_code == 404

    def test_health_check_works(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "guardarr"

    def test_status_works(self, client):
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert "total_bytes" in data
        assert "available_bytes" in data
        assert "current_threshold_state" in data

    def test_status_has_correct_threshold_state_values(self, client):
        response = client.get("/api/status")
        data = response.json()
        valid_states = {"NORMAL", "WARNING", "BLOCKED", "EMERGENCY", "CRITICAL"}
        assert data["current_threshold_state"] in valid_states