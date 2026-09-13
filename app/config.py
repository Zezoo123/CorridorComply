"""
Application configuration
"""
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

# Base directories
BASE_DIR = Path(__file__).parent.parent

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Audit logging
AUDIT_LOG_DIR = BASE_DIR / "logs/audit"
AUDIT_LOG_RETENTION_DAYS = 30  # Number of days to keep audit logs
AUDIT_LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB per log file
AUDIT_LOG_BACKUP_COUNT = 5  # Number of backup files to keep

# CORS (comma-separated list of allowed origins; empty disables browser access)
CORS_ORIGINS: List[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

# Tenant used when the API runs open (no keys configured) and by the web UI
DEFAULT_TENANT = os.getenv("UI_TENANT", "default")
# Web UI login (HTTP Basic). Set both to require a login on /screen, /review, /alerts.
UI_USERNAME = os.getenv("UI_USERNAME", "")
UI_PASSWORD = os.getenv("UI_PASSWORD", "")

# Sanctions data location (contains raw/, normalized/, combined/)
SANCTIONS_DATA_DIR = Path(os.getenv("SANCTIONS_DATA_DIR", str(BASE_DIR / "app" / "data" / "sanctions")))

# Application Settings
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Sanctions Update Settings
SANCTIONS_UPDATE_INTERVAL_DAYS = int(os.getenv("SANCTIONS_UPDATE_INTERVAL_DAYS", "7"))  # Update weekly by default
# Off by default: run scripts/update_sanctions.py from a scheduler instead (see docs). The running
# API notices a new combined file on its own.
SANCTIONS_AUTO_UPDATE_ENABLED = os.getenv("SANCTIONS_AUTO_UPDATE_ENABLED", "false").lower() == "true"
# How often the API checks the data directory for a newer combined file (seconds)
SANCTIONS_RELOAD_CHECK_SECONDS = int(os.getenv("SANCTIONS_RELOAD_CHECK_SECONDS", "60"))

class AppConfig:
    """Application configuration with type hints"""
    
    @staticmethod
    def get_audit_log_config() -> Dict[str, Any]:
        """Get audit log configuration"""
        return {
            "level": LOG_LEVEL,
            "format": LOG_FORMAT,
            "dir": str(AUDIT_LOG_DIR),
            "retention_days": AUDIT_LOG_RETENTION_DAYS,
            "max_size": AUDIT_LOG_MAX_SIZE,
            "backup_count": AUDIT_LOG_BACKUP_COUNT
        }
