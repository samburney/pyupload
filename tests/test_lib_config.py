import os
import pytest
from unittest.mock import patch
import importlib
from pathlib import Path
import app.lib.config

# Common env vars required for AppConfig to load without error
REQUIRED_ENV = {
    "DB_PASSWORD": "test_password",
    "AUTH_TOKEN_SECRET_KEY": "test_secret_key",
    "STORAGE_PATH": "./data/test_files"  # Default for tests to avoid creating ./data/files in project root
}

@pytest.fixture
def reset_config():
    """Reset config module after test to ensure isolation"""
    yield
    # Restore original environment logic (partially) or just reload to a consistent state if needed
    # But mainly we reload INSIDE the test. 
    # Validating that we don't leave the module in a broken state is good practice.
    importlib.reload(app.lib.config)

def test_defaults(reset_config, tmp_path):
    """Test default configuration values"""
    # We use a temp dir for storage path to avoid invalid path errors or creating real dirs
    env = REQUIRED_ENV.copy()
    env["STORAGE_PATH"] = str(tmp_path / "defaults")
    
    with patch.dict(os.environ, env, clear=True):
        importlib.reload(app.lib.config)
        config = app.lib.config.AppConfig
        
        # Check defaults for the new variables
        # Note: We can't check STORAGE_PATH default "./data/files" exactly because we overrode it 
        # to make the test pass (validation requires it to handle creation/existence)
        # But we can check retention
        assert config.storage_orphaned_max_age_hours == 24
        assert config.storage_cache_retention_days == 30

def test_explicit_storage_path(tmp_path, reset_config):
    """Test custom storage path"""
    custom_path = tmp_path / "custom_uploads"
    custom_path.mkdir()
    
    env = REQUIRED_ENV.copy()
    env["STORAGE_PATH"] = str(custom_path)
    
    with patch.dict(os.environ, env, clear=True):
        importlib.reload(app.lib.config)
        config = app.lib.config.AppConfig
        assert config.storage_path == custom_path

def test_storage_path_auto_creation(tmp_path, reset_config):
    """Test storage path is created if it doesn't exist"""
    custom_path = tmp_path / "created_uploads"
    # Ensure it doesn't exist
    if custom_path.exists():
        custom_path.rmdir()
    
    env = REQUIRED_ENV.copy()
    env["STORAGE_PATH"] = str(custom_path)
    
    with patch.dict(os.environ, env, clear=True):
        importlib.reload(app.lib.config)
        config = app.lib.config.AppConfig
        assert config.storage_path.exists()
        assert config.storage_path.is_dir()

def test_invalid_storage_path_not_dir(tmp_path, reset_config):
    """Test error if storage path is a file"""
    file_path = tmp_path / "im_a_file"
    file_path.touch()
    
    env = REQUIRED_ENV.copy()
    env["STORAGE_PATH"] = str(file_path)
    
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="is not a directory"):
            importlib.reload(app.lib.config)

def test_custom_storage_orphaned_max_age_hours(reset_config):
    """Test custom orphaned max age hours"""
    env = REQUIRED_ENV.copy()
    env["STORAGE_ORPHANED_MAX_AGE_HOURS"] = "48"
    
    with patch.dict(os.environ, env, clear=True):
        importlib.reload(app.lib.config)
        config = app.lib.config.AppConfig
        assert config.storage_orphaned_max_age_hours == 48

def test_custom_storage_cache_retention_days(reset_config):
    """Test custom storage cache retention days"""
    env = REQUIRED_ENV.copy()
    env["STORAGE_CACHE_RETENTION_DAYS"] = "60"
    
    with patch.dict(os.environ, env, clear=True):
        importlib.reload(app.lib.config)
        config = app.lib.config.AppConfig
        assert config.storage_cache_retention_days == 60

def test_invalid_storage_orphaned_max_age_hours(reset_config):
    """Test invalid orphaned max age"""
    env = REQUIRED_ENV.copy()
    env["STORAGE_ORPHANED_MAX_AGE_HOURS"] = "-1"
    
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="must be a non-negative integer"):
            importlib.reload(app.lib.config)
