import os
import tempfile
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def isolate_test_environment():
    """Isolate test environment from production settings.
    
    This fixture sets up temporary directories and test-appropriate
    configuration values before each test, ensuring tests don't
    interfere with production data or thresholds.
    """
    # Reset the Settings singleton so get_settings() re-reads from env
    from app.core import config as _config
    _config._settings = None

    # Create temporary directories for test isolation
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Set test environment variables
        os.environ['GUARDARR_DATA_DIR'] = str(tmp_path / 'data')
        os.environ['GUARDARR_STORAGE_PATH'] = str(tmp_path / 'storage')
        os.environ['DATABASE_URL'] = f"sqlite:///{tmp_path / 'guardarr_test.db'}"
        
        # Test-appropriate thresholds (much smaller than production)
        os.environ['ADMISSION_FLOOR_BYTES'] = '10000000'  # 10MB for tests
        os.environ['EMERGENCY_THRESHOLD_BYTES'] = '5000000'   # 5MB
        os.environ['CRITICAL_THRESHOLD_BYTES'] = '1000000'    # 1MB
        os.environ['WARNING_THRESHOLD_BYTES'] = '20000000'   # 20MB
        
        # Ensure the directories exist
        (tmp_path / 'data').mkdir(parents=True, exist_ok=True)
        (tmp_path / 'storage').mkdir(parents=True, exist_ok=True)
        
        yield
        
        # Clean up environment variables after test
        env_vars_to_clean = [
            'GUARDARR_DATA_DIR',
            'GUARDARR_STORAGE_PATH', 
            'DATABASE_URL',
            'ADMISSION_FLOOR_BYTES',
            'EMERGENCY_THRESHOLD_BYTES',
            'CRITICAL_THRESHOLD_BYTES',
            'WARNING_THRESHOLD_BYTES'
        ]
        
        for var in env_vars_to_clean:
            os.environ.pop(var, None)